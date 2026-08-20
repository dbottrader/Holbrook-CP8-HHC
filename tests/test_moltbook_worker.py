import os
import unittest
from unittest.mock import patch

from moltbook.client import ClientError
from moltbook.worker import _items, _verify_readback, run_once


class FakeProvider:
    def __init__(self, text="OBSERVED: useful external contribution"):
        self.text = text
        self.prompts = []

    def generate(self, prompt):
        self.prompts.append(prompt)
        return self.text


class FakeClient:
    def __init__(self, *, mismatch=False, reject_claim=False):
        self.mismatch = mismatch
        self.reject_claim = reject_claim
        self.completed = []
        self.failed = []
        self.replies = []
        self.heartbeats = []

    def heartbeat(self, **kwargs):
        self.heartbeats.append(kwargs)
        return {"ok": True}

    def list_work(self, *, limit=20):
        return {
            "items": [
                {
                    "work_id": "work-1",
                    "status": "open",
                    "room_slug": "cp8-ops",
                    "title": "Review external evidence",
                    "description": "Check one thing.",
                    "metadata": {"parent_post_id": "root-1"},
                }
            ]
        }

    def claim_work(self, work_id, *, lease_minutes=15):
        if self.reject_claim:
            raise ClientError("Worker role mismatch", status=409)
        return {"item": self.list_work()["items"][0] | {"status": "claimed"}}

    def get_post(self, post_id):
        if post_id == "root-1":
            return {
                "post": {"post_id": "root-1", "content_hash": "a" * 64},
                "receipts": [{"receipt_id": "root-receipt"}],
                "has_bound_receipt": True,
            }
        return {
            "post": {
                "post_id": "result-1",
                "content_hash": ("c" if self.mismatch else "b") * 64,
            },
            "receipts": [{"receipt_id": "result-receipt"}],
            "has_bound_receipt": True,
        }

    def reply(self, post_id, content, *, evidence_refs=None, nonce=None):
        self.replies.append((post_id, content, evidence_refs))
        return {"post": {"post_id": "result-1", "content_hash": "b" * 64}}

    def create_post(self, *args, **kwargs):
        raise AssertionError("parented fixture should use reply")

    def complete_work(self, work_id, *, result_post_id, result_hash):
        self.completed.append((work_id, result_post_id, result_hash))
        return {"item": {"status": "completed"}}

    def fail_work(self, work_id, *, reason):
        self.failed.append((work_id, reason))
        return {"item": {"status": "failed"}}


class HeadlessWorkerTests(unittest.TestCase):
    def test_items_accepts_current_and_compatibility_keys(self):
        self.assertEqual(_items({"items": [{"work_id": "1"}]}), [{"work_id": "1"}])
        self.assertEqual(
            _items({"work_items": [{"work_id": "2"}]}), [{"work_id": "2"}]
        )

    def test_receipt_readback_is_required(self):
        with self.assertRaisesRegex(RuntimeError, "bound receipt"):
            _verify_readback(
                {
                    "post": {"post_id": "p", "content_hash": "f" * 64},
                    "receipts": [],
                    "has_bound_receipt": False,
                },
                "p",
                "f" * 64,
            )

    @patch.dict(os.environ, {"CP8_WORKER_HANDLE": "grok-headless"}, clear=False)
    def test_worker_completes_only_after_exact_readback_and_receipt(self):
        client = FakeClient()
        provider = FakeProvider()

        result = run_once(client, provider)

        self.assertEqual(result[0]["status"], "COMPLETED")
        self.assertEqual(client.completed, [("work-1", "result-1", "b" * 64)])
        self.assertEqual(client.failed, [])
        self.assertEqual(client.replies[0][0], "root-1")
        self.assertIn("sha256:" + "a" * 64, client.replies[0][2])
        self.assertIn("work:work-1", client.replies[0][2])
        self.assertIn("do not claim to have used tools", provider.prompts[0].lower())
        self.assertIn("do not include a fake receipt", provider.prompts[0].lower())

    def test_hash_mismatch_fails_work_and_never_completes(self):
        client = FakeClient(mismatch=True)

        result = run_once(client, FakeProvider())

        self.assertEqual(result[0]["status"], "FAILED")
        self.assertEqual(client.completed, [])
        self.assertEqual(len(client.failed), 1)
        self.assertIn("content_hash mismatch", client.failed[0][1])

    def test_server_rejected_claim_is_not_bypassed(self):
        client = FakeClient(reject_claim=True)

        result = run_once(client, FakeProvider())

        self.assertEqual(result, [])
        self.assertEqual(client.completed, [])
        self.assertEqual(client.failed, [])


if __name__ == "__main__":
    unittest.main()

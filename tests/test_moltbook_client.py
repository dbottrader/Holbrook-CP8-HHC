import json
import unittest

from moltbook import ClientError, MoltbookClient


class FakeResponse:
    def __init__(self, payload, status=200):
        self.status = status
        self._raw = (
            payload
            if isinstance(payload, bytes)
            else json.dumps(payload).encode("utf-8")
        )

    def read(self):
        return self._raw

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        return False


class RecordingOpener:
    def __init__(self, *responses):
        self.responses = list(responses)
        self.requests = []

    def __call__(self, request, timeout):
        self.requests.append((request, timeout))
        return self.responses.pop(0)


class MoltbookClientTests(unittest.TestCase):
    def test_public_feed_encodes_path_and_query(self):
        opener = RecordingOpener(FakeResponse({"posts": []}))
        client = MoltbookClient(
            "https://moltbook.example/api", opener=opener, token=""
        )

        result = client.feed("cp8 ops", limit=7)

        self.assertEqual(result, {"posts": []})
        request, timeout = opener.requests[0]
        self.assertEqual(request.method, "GET")
        self.assertEqual(
            request.full_url,
            "https://moltbook.example/api/rooms/cp8%20ops/posts?limit=7",
        )
        self.assertEqual(timeout, 20.0)
        self.assertNotIn("Authorization", request.headers)

    def test_search_omits_absent_room(self):
        opener = RecordingOpener(FakeResponse({"posts": []}))
        client = MoltbookClient("https://moltbook.example", opener=opener, token="")

        client.search("parent hash", limit=3)

        request, _ = opener.requests[0]
        self.assertIn("q=parent+hash", request.full_url)
        self.assertIn("limit=3", request.full_url)
        self.assertNotIn("room=", request.full_url)

    def test_connect_can_remember_returned_token(self):
        token = "hc_" + ("a" * 64)
        opener = RecordingOpener(
            FakeResponse({"ok": True, "credential": {"token": token}}, status=201)
        )
        client = MoltbookClient("https://moltbook.example", opener=opener, token="")

        client.connect("open-agent", display_name="Open Agent", ttl_minutes=60)

        self.assertEqual(client.token, token)
        request, _ = opener.requests[0]
        self.assertEqual(request.method, "POST")
        self.assertEqual(
            json.loads(request.data),
            {
                "handle": "open-agent",
                "display_name": "Open Agent",
                "ttl_minutes": 60,
            },
        )

    def test_reply_uses_dedicated_route_and_bearer_token(self):
        token = "hc_" + ("b" * 64)
        opener = RecordingOpener(FakeResponse({"ok": True, "post": {}}))
        client = MoltbookClient(
            "https://moltbook.example", opener=opener, token=token
        )

        client.reply(
            "parent-id",
            "canonical reply",
            evidence_refs=["sha256:" + ("c" * 64)],
        )

        request, _ = opener.requests[0]
        self.assertEqual(
            request.full_url,
            "https://moltbook.example/posts/parent-id/replies",
        )
        self.assertEqual(request.headers["Authorization"], f"Bearer {token}")
        self.assertEqual(
            json.loads(request.data),
            {
                "content": "canonical reply",
                "evidence_refs": ["sha256:" + ("c" * 64)],
            },
        )

    def test_claim_work_uses_atomic_route_lease_and_bearer(self):
        token = "hc_" + ("d" * 64)
        claim_item = {
            "status": "claimed",
            "claimed_by": "guest_external",
            "lease_expires_at": "2026-08-20T21:00:00Z",
        }
        opener = RecordingOpener(FakeResponse({"ok": True, "item": claim_item}))
        client = MoltbookClient("https://moltbook.example", opener=opener, token=token)

        result = client.claim_work("work-id", lease_minutes=30)

        self.assertEqual(result["item"], claim_item)
        self.assertEqual(result["item"]["claimed_by"], "guest_external")
        self.assertEqual(
            result["item"]["lease_expires_at"], "2026-08-20T21:00:00Z"
        )
        request, _ = opener.requests[0]
        self.assertEqual(request.method, "POST")
        self.assertEqual(request.full_url, "https://moltbook.example/work/items/work-id/claim")
        self.assertEqual(request.headers["Authorization"], f"Bearer {token}")
        self.assertEqual(json.loads(request.data), {"lease_minutes": 30})

    def test_get_post_preserves_nested_post_receipt_contract(self):
        payload = {
            "post": {"post_id": "result-post", "content_hash": "f" * 64},
            "receipts": [{"receipt_id": "receipt-1", "cp8_receipt_id": "cp8-1"}],
            "has_bound_receipt": True,
        }
        opener = RecordingOpener(FakeResponse(payload))
        client = MoltbookClient("https://moltbook.example", opener=opener, token="")

        result = client.get_post("result-post")

        self.assertEqual(result, payload)
        self.assertEqual(result["post"]["post_id"], "result-post")
        self.assertEqual(result["post"]["content_hash"], "f" * 64)
        self.assertTrue(result["has_bound_receipt"])
        request, _ = opener.requests[0]
        self.assertEqual(request.method, "GET")
        self.assertEqual(request.full_url, "https://moltbook.example/posts/result-post")
        self.assertNotIn("Authorization", request.headers)

    def test_complete_work_sends_exact_result_binding(self):
        token = "hc_" + ("e" * 64)
        result_hash = "1" * 64
        opener = RecordingOpener(FakeResponse({"ok": True, "item": {"status": "completed"}}))
        client = MoltbookClient("https://moltbook.example", opener=opener, token=token)

        client.complete_work(
            "work-id", result_post_id="result-post", result_hash=result_hash
        )

        request, _ = opener.requests[0]
        self.assertEqual(request.method, "POST")
        self.assertEqual(
            request.full_url, "https://moltbook.example/work/items/work-id/complete"
        )
        self.assertEqual(request.headers["Authorization"], f"Bearer {token}")
        self.assertEqual(
            json.loads(request.data),
            {"result_post_id": "result-post", "result_hash": result_hash},
        )

    def test_fail_work_preserves_factual_reason(self):
        token = "hc_" + ("f" * 64)
        reason = "receipt hash mismatch; completion not attempted"
        opener = RecordingOpener(FakeResponse({"ok": True, "item": {"status": "failed"}}))
        client = MoltbookClient("https://moltbook.example", opener=opener, token=token)

        client.fail_work("work-id", reason=reason)

        request, _ = opener.requests[0]
        self.assertEqual(request.method, "POST")
        self.assertEqual(request.full_url, "https://moltbook.example/work/items/work-id/fail")
        self.assertEqual(request.headers["Authorization"], f"Bearer {token}")
        self.assertEqual(json.loads(request.data), {"reason": reason})

    def test_protected_call_fails_before_network_without_token(self):
        opener = RecordingOpener()
        client = MoltbookClient("https://moltbook.example", opener=opener, token="")

        with self.assertRaisesRegex(ClientError, "requires a capability token"):
            client.heartbeat(capabilities=["read"])

        self.assertEqual(opener.requests, [])

    def test_non_object_json_is_rejected(self):
        opener = RecordingOpener(FakeResponse(b"[]"))
        client = MoltbookClient("https://moltbook.example", opener=opener, token="")

        with self.assertRaisesRegex(ClientError, "non-object JSON"):
            client.health()


if __name__ == "__main__":
    unittest.main()

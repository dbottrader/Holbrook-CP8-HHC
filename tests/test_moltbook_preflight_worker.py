import unittest

from moltbook.preflight_worker import (
    CapabilityFilteringClient,
    missing_requirements,
    requirements_for,
)


class FakeClient:
    def __init__(self):
        self.heartbeats = []

    @property
    def token(self):
        return "token"

    def heartbeat(self, **kwargs):
        self.heartbeats.append(kwargs)
        return {"ok": True}

    def list_work(self, *, limit=20):
        return {
            "items": [
                {
                    "work_id": "compatible",
                    "status": "open",
                    "title": "HTTP review",
                    "metadata": {
                        "requires": {
                            "capabilities": ["research"],
                            "execution": ["http"],
                        }
                    },
                },
                {
                    "work_id": "blocked",
                    "status": "open",
                    "title": "Git write",
                    "metadata": {
                        "requires": {
                            "capabilities": ["coding"],
                            "execution": ["git_write"],
                        }
                    },
                },
            ]
        }


class CapabilityPreflightTests(unittest.TestCase):
    def setUp(self):
        self.profile = {
            "schema": "CP8-EXECUTION-PROFILE-v1",
            "platform": "github-actions",
            "capabilities": ["research", "coding"],
            "execution": ["http", "moltbook_read", "moltbook_write"],
            "limitations": ["stateless_model_call"],
        }

    def test_requirement_parser_supports_structured_and_legacy_fields(self):
        item = {
            "metadata": {
                "required_capabilities": ["review"],
                "requires": {
                    "capabilities": ["testing"],
                    "execution": ["http"],
                },
            }
        }
        self.assertEqual(
            requirements_for(item),
            {
                "capabilities": ["review", "testing"],
                "execution": ["http"],
            },
        )

    def test_missing_execution_capability_is_explicit(self):
        item = {
            "metadata": {
                "requires": {
                    "capabilities": ["coding"],
                    "execution": ["git_write"],
                }
            }
        }
        self.assertEqual(
            missing_requirements(item, self.profile),
            {"execution": ["git_write"]},
        )

    def test_incompatible_work_is_removed_before_claim_stage(self):
        base = FakeClient()
        client = CapabilityFilteringClient(base, self.profile)

        queue = client.list_work(limit=20)

        self.assertEqual([item["work_id"] for item in queue["items"]], ["compatible"])
        self.assertEqual(client.skipped[0]["work_id"], "blocked")
        self.assertEqual(
            client.skipped[0]["missing"],
            {"execution": ["git_write"]},
        )

    def test_heartbeat_advertises_execution_capabilities(self):
        base = FakeClient()
        client = CapabilityFilteringClient(base, self.profile)

        client.heartbeat(capabilities=["research"], current_work_id=None)

        declared = base.heartbeats[0]["capabilities"]
        self.assertIn("research", declared)
        self.assertIn("exec:http", declared)
        self.assertIn("exec:moltbook_write", declared)
        self.assertIn("platform:github-actions", declared)


if __name__ == "__main__":
    unittest.main()

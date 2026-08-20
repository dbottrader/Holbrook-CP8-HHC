import hashlib
import json
import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CONTRACTS = ROOT / "docs" / "moltbook" / "contracts"


def load(path):
    return json.loads(path.read_text(encoding="utf-8"))


class MoltbookContractTests(unittest.TestCase):
    def test_source_snapshot_hashes_and_newline_normalization(self):
        snapshot = load(
            ROOT / "supabase" / "functions" / "MOLTBOOK_SOURCE_SNAPSHOT.json"
        )
        self.assertFalse(snapshot["deployment_performed_by_this_snapshot"])
        self.assertEqual(len(snapshot["functions"]), 3)

        for function in snapshot["functions"]:
            raw = (ROOT / function["source_path"]).read_bytes()
            self.assertTrue(raw.endswith(b"\n"))
            self.assertEqual(
                hashlib.sha256(raw).hexdigest(),
                function["local_file_sha256"],
            )
            self.assertEqual(
                hashlib.sha256(raw[:-1]).hexdigest(),
                function["retrieved_source_sha256"],
            )

    def test_connector_manifest_preserves_only_real_open_gates(self):
        manifest = load(CONTRACTS / "connector-manifest.v1.json")
        self.assertEqual(
            manifest["status"],
            {
                "evidence_level": "E2",
                "verdict": "PASS_WITH_OPEN_GATES",
                "promotion": "HOLD",
            },
        )
        self.assertEqual(
            manifest["evidence"]["independent_two_hop_replay"], "OPEN"
        )
        self.assertEqual(
            manifest["endpoints"]["a2a"]["status"], "candidate_not_deployed"
        )
        self.assertEqual(
            manifest["endpoints"]["agent_manifest"]["version"], "0.3.7"
        )
        active = manifest["active_round"]
        self.assertEqual(active["external_builder_receipt"], "CLOSED")
        self.assertEqual(active["external_builder_post_id"], "979aa9dd-6c0d-4540-8fc0-e8b2142024f8")
        self.assertRegex(active["external_builder_content_hash"], r"^[0-9a-f]{64}$")
        self.assertEqual(active["external_builder_receipt_id"], "2de4101e-181a-4487-9b5f-ba67816945a2")
        self.assertEqual(active["external_builder_cp8_receipt_id"], "2fbfad9b-d057-4c6d-9c8f-5ed163404608")

    def test_connector_version_domains_are_independent(self):
        manifest = load(CONTRACTS / "connector-manifest.v1.json")
        versions = manifest["version_domains"]
        self.assertEqual(versions["agent_manifest"], "0.3.7")
        self.assertEqual(versions["rest_contract"], "0.3.2")
        self.assertEqual(versions["moltbook_api_edge"], 5)
        self.assertFalse(versions["numeric_equality_required"])
        self.assertEqual(manifest["endpoints"]["rest"]["edge_version"], 5)

    def test_openapi_covers_every_source_route(self):
        openapi = load(CONTRACTS / "openapi.v0.3.2.json")
        self.assertEqual(openapi["openapi"], "3.1.0")
        self.assertEqual(openapi["info"]["version"], "0.3.2")
        expected = {
            "/": {"get"},
            "/health": {"get"},
            "/connect": {"post"},
            "/rooms": {"get"},
            "/rooms/{slug}/posts": {"get"},
            "/posts": {"post"},
            "/posts/{post_id}": {"get"},
            "/posts/{post_id}/replies": {"post"},
            "/posts/{post_id}/challenges": {"post"},
            "/thread/{post_id}": {"get"},
            "/search": {"get"},
            "/artifacts": {"get"},
            "/status/{post_id}": {"get"},
            "/work/heartbeat": {"post"},
            "/work/items": {"get", "post"},
            "/work/items/{work_id}/claim": {"post"},
            "/work/items/{work_id}/complete": {"post"},
            "/work/items/{work_id}/fail": {"post"},
            "/work/mine": {"get"},
        }
        actual = {
            path: {method for method in item if method in {"get", "post"}}
            for path, item in openapi["paths"].items()
        }
        self.assertEqual(actual, expected)

    def test_receipt_example_preserves_dual_binding(self):
        event = load(CONTRACTS / "receipt-event.example.json")
        data = event["data"]
        sha256 = re.compile(r"^[0-9a-f]{64}$")

        self.assertEqual(event["specversion"], "1.0")
        self.assertEqual(event["timebasis"], "post_created_at")
        self.assertEqual(event["id"], data["receipt_id"])
        self.assertEqual(event["subject"], data["post_id"])
        self.assertEqual(data["content_hash"], data["cp8_payload_hash"])
        self.assertEqual(data["receipt_hash"], data["cp8_receipt_hash"])
        self.assertEqual(data["promotion"], "HOLD")
        for field in (
            "content_hash",
            "parent_hash",
            "receipt_hash",
            "cp8_payload_hash",
            "cp8_receipt_hash",
        ):
            self.assertRegex(data[field], sha256)

    def test_a2a_card_is_non_routable_candidate(self):
        card = load(CONTRACTS / "a2a-agent-card.candidate.json")
        self.assertIn("candidate", card["version"])
        self.assertTrue(
            all(
                interface["url"].startswith("https://example.invalid/")
                for interface in card["supportedInterfaces"]
            )
        )

    def test_migration_inventory_is_catalog_only_and_ordered(self):
        catalog = load(
            ROOT
            / "supabase"
            / "migrations"
            / "MOLTBOOK_RUNTIME_MIGRATIONS_20260820.json"
        )
        versions = [item["version"] for item in catalog["migrations"]]
        self.assertEqual(catalog["snapshot_kind"], "catalog_only")
        self.assertEqual(
            catalog["reproduction_status"], "BLOCKED_ON_FULL_SQL_SNAPSHOT"
        )
        self.assertEqual(catalog["promotion"], "HOLD")
        self.assertEqual(len(versions), 26)
        self.assertEqual(versions, sorted(versions))
        for item in catalog["migrations"][-3:]:
            self.assertIn("exact_sql_path", item)
            self.assertTrue((ROOT / item["exact_sql_path"]).exists())

    def test_status_document_does_not_overclaim_e3(self):
        status = (
            ROOT / "docs" / "MOLTBOOK_INTEROP_STATUS_20260819.md"
        ).read_text(encoding="utf-8")
        self.assertIn("E2 / PASS_WITH_OPEN_GATES / HOLD", status)
        self.assertIn("The evidence level remains `E2`, not `E3`.", status)
        self.assertIn(
            "No documentation-only change can close that runtime gate.", status
        )


if __name__ == "__main__":
    unittest.main()

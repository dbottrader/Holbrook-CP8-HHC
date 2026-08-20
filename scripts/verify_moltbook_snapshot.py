#!/usr/bin/env python3
"""Verify the public Moltbook source and contract snapshot without network."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]


def load(relative_path: str) -> Any:
    return json.loads((ROOT / relative_path).read_text(encoding="utf-8"))


def require(condition: bool, message: str, checks: list[str]) -> None:
    if not condition:
        raise AssertionError(message)
    checks.append(message)


def verify() -> tuple[list[str], list[str]]:
    checks: list[str] = []
    open_gates: list[str] = []
    snapshot = load("supabase/functions/MOLTBOOK_SOURCE_SNAPSHOT.json")
    require(snapshot["deployment_performed_by_this_snapshot"] is False, "snapshot records no deployment", checks)
    require(len(snapshot["functions"]) == 3, "three Edge Function sources are inventoried", checks)
    for function in snapshot["functions"]:
        raw = (ROOT / function["source_path"]).read_bytes()
        require(raw.endswith(b"\n"), f"{function['slug']} has a normalized final newline", checks)
        require(hashlib.sha256(raw).hexdigest() == function["local_file_sha256"], f"{function['slug']} local source hash matches", checks)
        require(hashlib.sha256(raw[:-1]).hexdigest() == function["retrieved_source_sha256"], f"{function['slug']} retrieved source hash matches before normalization", checks)

    connector = load("docs/moltbook/contracts/connector-manifest.v1.json")
    require(connector["status"] == {"evidence_level": "E2", "verdict": "PASS_WITH_OPEN_GATES", "promotion": "HOLD"}, "connector evidence remains E2 / PASS_WITH_OPEN_GATES / HOLD", checks)
    versions = connector["version_domains"]
    require(versions["agent_manifest"] == "0.3.8" and versions["rest_contract"] == "0.3.2" and versions["moltbook_api_edge"] == 5 and versions["numeric_equality_required"] is False, "manifest, REST contract, and Edge deployment version domains are declared independently", checks)
    require(connector["endpoints"]["agent_manifest"]["version"] == "0.3.8", "connector manifest tracks AppDeploy agent manifest 0.3.8", checks)
    engagement = connector["discovery_artifacts"]["universal_engagement_payload"]
    require((ROOT / engagement).exists(), "universal dynamic engagement payload is mirrored", checks)

    replay_gate = connector["evidence"]["independent_two_hop_replay"]
    require(replay_gate in {"OPEN", "CLOSED"}, "independent two-hop replay gate has a recognized state", checks)
    if replay_gate == "OPEN":
        open_gates.append("independent_two_hop_replay")
    external_gate = connector["active_round"]["external_builder_receipt"]
    require(external_gate in {"OPEN", "CLOSED"}, "EVOLUTION-003 external-builder receipt gate has a recognized state", checks)
    if external_gate == "OPEN":
        open_gates.append("evolution_003_external_builder_receipt")
    if external_gate == "CLOSED":
        require(bool(connector["active_round"].get("external_builder_post_id")) and len(connector["active_round"].get("external_builder_content_hash", "")) == 64 and bool(connector["active_round"].get("external_builder_receipt_id")) and bool(connector["active_round"].get("external_builder_cp8_receipt_id")), "closed EVOLUTION-003 external-builder gate carries post/hash/surface/core receipt identifiers", checks)

    openapi = load("docs/moltbook/contracts/openapi.v0.3.2.json")
    required_paths = {"/", "/connect", "/rooms", "/rooms/{slug}/posts", "/posts", "/posts/{post_id}", "/posts/{post_id}/replies", "/posts/{post_id}/challenges", "/status/{post_id}", "/work/heartbeat", "/work/items", "/work/items/{work_id}/claim", "/work/items/{work_id}/complete", "/work/items/{work_id}/fail", "/work/mine"}
    require(required_paths <= set(openapi["paths"]), "OpenAPI includes social, post deep-link, and worker routes", checks)

    receipt = load("docs/moltbook/contracts/receipt-event.example.json")
    data = receipt["data"]
    require(receipt["id"] == data["receipt_id"] and receipt["subject"] == data["post_id"], "receipt envelope identifiers bind to the surface receipt and post", checks)
    require(receipt["timebasis"] == "post_created_at", "receipt event declares the observed timestamp basis", checks)
    require(data["content_hash"] == data["cp8_payload_hash"] and data["receipt_hash"] == data["cp8_receipt_hash"], "surface and core receipt hashes are bound", checks)
    require(data["promotion"] == "HOLD", "receipt promotion remains HOLD", checks)

    migrations = load("supabase/migrations/MOLTBOOK_RUNTIME_MIGRATIONS_20260820.json")
    versions_list = [item["version"] for item in migrations["migrations"]]
    require(migrations["snapshot_kind"] == "catalog_only" and migrations["reproduction_status"] == "BLOCKED_ON_FULL_SQL_SNAPSHOT", "migration inventory remains catalog evidence until all historical SQL is mirrored", checks)
    require(len(versions_list) == 26 and versions_list == sorted(versions_list), "26 observed Moltbook migrations are ordered", checks)
    exact_tail = migrations["migrations"][-3:]
    require(all(item.get("exact_sql_path") for item in exact_tail) and all((ROOT / item["exact_sql_path"]).exists() for item in exact_tail), "latest three runtime migrations have exact SQL mirrors", checks)

    a2a = load("docs/moltbook/contracts/a2a-agent-card.candidate.json")
    require("candidate" in a2a["version"] and all(interface["url"].startswith("https://example.invalid/") for interface in a2a["supportedInterfaces"]), "A2A card is a non-routable candidate", checks)
    return checks, open_gates


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--strict-gates", action="store_true", help="Return exit code 2 when evidence gates remain open.")
    args = parser.parse_args(argv)
    try:
        checks, open_gates = verify()
    except (AssertionError, KeyError, OSError, ValueError) as error:
        print(json.dumps({"ok": False, "integrity_ok": False, "gate_ok": False, "kind": "INTEGRITY_FAILURE", "error": str(error)}, indent=2))
        return 1
    gate_ok = not open_gates
    payload = {"ok": gate_ok or not args.strict_gates, "integrity_ok": True, "gate_ok": gate_ok, "verdict": "PASS" if gate_ok else "PASS_WITH_OPEN_GATES", "open_gates": open_gates, "checks": checks}
    print(json.dumps(payload, indent=2))
    if args.strict_gates and not gate_ok:
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
"""Verify the public Moltbook source and contract snapshot without network."""

from __future__ import annotations

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


def verify() -> list[str]:
    checks: list[str] = []
    snapshot = load("supabase/functions/MOLTBOOK_SOURCE_SNAPSHOT.json")
    require(
        snapshot["deployment_performed_by_this_snapshot"] is False,
        "snapshot records no deployment",
        checks,
    )
    require(
        len(snapshot["functions"]) == 3,
        "three Edge Function sources are inventoried",
        checks,
    )
    for function in snapshot["functions"]:
        raw = (ROOT / function["source_path"]).read_bytes()
        require(
            raw.endswith(b"\n"),
            f"{function['slug']} has a normalized final newline",
            checks,
        )
        require(
            hashlib.sha256(raw).hexdigest() == function["local_file_sha256"],
            f"{function['slug']} local source hash matches",
            checks,
        )
        require(
            hashlib.sha256(raw[:-1]).hexdigest()
            == function["retrieved_source_sha256"],
            f"{function['slug']} retrieved source hash matches before normalization",
            checks,
        )

    connector = load("docs/moltbook/contracts/connector-manifest.v1.json")
    require(
        connector["status"]
        == {
            "evidence_level": "E2",
            "verdict": "PASS_WITH_OPEN_GATES",
            "promotion": "HOLD",
        },
        "connector evidence remains E2 / PASS_WITH_OPEN_GATES / HOLD",
        checks,
    )
    require(
        connector["evidence"]["independent_two_hop_replay"] == "OPEN",
        "independent two-hop replay gate remains open",
        checks,
    )
    require(
        connector["endpoints"]["agent_manifest"]["version"] == "0.3.3"
        and connector["active_round"]["external_builder_receipt"] == "OPEN",
        "EVOLUTION-003 external-builder receipt gate remains open",
        checks,
    )

    openapi = load("docs/moltbook/contracts/openapi.v0.3.2.json")
    required_paths = {
        "/",
        "/connect",
        "/rooms",
        "/rooms/{slug}/posts",
        "/posts",
        "/posts/{post_id}/replies",
        "/posts/{post_id}/challenges",
        "/status/{post_id}",
        "/work/heartbeat",
        "/work/items",
        "/work/items/{work_id}/claim",
        "/work/items/{work_id}/complete",
        "/work/items/{work_id}/fail",
        "/work/mine",
    }
    require(
        required_paths <= set(openapi["paths"]),
        "OpenAPI includes social and worker routes",
        checks,
    )

    receipt = load("docs/moltbook/contracts/receipt-event.example.json")
    data = receipt["data"]
    require(
        receipt["id"] == data["receipt_id"]
        and receipt["subject"] == data["post_id"],
        "receipt envelope identifiers bind to the surface receipt and post",
        checks,
    )
    require(
        receipt["timebasis"] == "post_created_at",
        "receipt event declares the observed timestamp basis",
        checks,
    )
    require(
        data["content_hash"] == data["cp8_payload_hash"]
        and data["receipt_hash"] == data["cp8_receipt_hash"],
        "surface and core receipt hashes are bound",
        checks,
    )
    require(data["promotion"] == "HOLD", "receipt promotion remains HOLD", checks)

    migrations = load(
        "supabase/migrations/MOLTBOOK_RUNTIME_MIGRATIONS_20260820.json"
    )
    versions = [item["version"] for item in migrations["migrations"]]
    require(
        migrations["snapshot_kind"] == "catalog_only"
        and migrations["reproduction_status"] == "BLOCKED_ON_FULL_SQL_SNAPSHOT",
        "migration inventory is explicitly non-reproducible catalog evidence",
        checks,
    )
    require(
        len(versions) == 23 and versions == sorted(versions),
        "23 observed migrations are ordered",
        checks,
    )

    a2a = load("docs/moltbook/contracts/a2a-agent-card.candidate.json")
    require(
        "candidate" in a2a["version"]
        and all(
            interface["url"].startswith("https://example.invalid/")
            for interface in a2a["supportedInterfaces"]
        ),
        "A2A card is a non-routable candidate",
        checks,
    )
    return checks


def main() -> int:
    try:
        checks = verify()
    except (AssertionError, KeyError, OSError, ValueError) as error:
        print(json.dumps({"ok": False, "error": str(error)}, indent=2))
        return 1
    print(json.dumps({"ok": True, "checks": checks}, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())

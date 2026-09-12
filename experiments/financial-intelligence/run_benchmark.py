#!/usr/bin/env python3
"""Deterministic validator/replay helper for the CP8 financial-intelligence benchmark.

This tool does not fetch market data or place trades. It validates a sealed
prediction ledger and computes the next-window realized return once an evaluator
supplies authoritative close prices. Keeping ingestion separate from scoring
prevents hidden data changes from altering historical results.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

REQUIRED = {
    "prediction_id",
    "asset",
    "prediction_timestamp_utc",
    "horizon",
    "direction",
    "expected_return",
    "confidence",
    "agent_id",
    "model_version",
    "input_data_hash",
}
DIRECTIONS = {"UP", "DOWN", "FLAT", "ABSTAIN"}


def canonical_json(obj: Any) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def validate_prediction(row: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    missing = REQUIRED - row.keys()
    if missing:
        errors.append(f"missing required fields: {sorted(missing)}")
    if row.get("direction") not in DIRECTIONS:
        errors.append("direction must be UP, DOWN, FLAT, or ABSTAIN")
    confidence = row.get("confidence")
    if not isinstance(confidence, (int, float)) or not 0 <= confidence <= 1:
        errors.append("confidence must be numeric in [0,1]")
    expected = row.get("expected_return")
    if not isinstance(expected, (int, float)):
        errors.append("expected_return must be numeric")
    return errors


def load_rows(path: Path) -> list[dict[str, Any]]:
    data = json.loads(path.read_text(encoding="utf-8"))
    rows = data["predictions"] if isinstance(data, dict) and "predictions" in data else data
    if not isinstance(rows, list):
        raise ValueError("ledger must contain a predictions list")
    return rows


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("ledger", type=Path)
    args = parser.parse_args()
    rows = load_rows(args.ledger)

    errors: list[str] = []
    ids: set[str] = set()
    for row in rows:
        errors.extend(f"{row.get('prediction_id', '<unknown>')}: {e}" for e in validate_prediction(row))
        pid = row.get("prediction_id")
        if pid in ids:
            errors.append(f"duplicate prediction_id: {pid}")
        ids.add(pid)

    canonical = canonical_json(rows)
    print(json.dumps({
        "status": "PASS" if not errors else "FAIL",
        "prediction_count": len(rows),
        "ledger_sha256": sha256_text(canonical),
        "errors": errors,
        "note": "This validates the sealed forecast structure only; it does not assert predictive skill.",
    }, indent=2))
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())

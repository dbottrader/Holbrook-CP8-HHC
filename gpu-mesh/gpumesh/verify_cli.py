"""Replay a ledger file offline: ``gpumesh-verify-ledger ledger.json``."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from gpumesh.ledger import verify_export


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Replay a GPU Mesh ledger export")
    parser.add_argument("path", help="JSON file from GET /api/ledger")
    args = parser.parse_args(argv)
    raw = json.loads(Path(args.path).read_text(encoding="utf-8"))
    entries = raw["entries"] if isinstance(raw, dict) else raw
    result = verify_export(entries)
    json.dump(result, sys.stdout, indent=2)
    sys.stdout.write("\n")
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

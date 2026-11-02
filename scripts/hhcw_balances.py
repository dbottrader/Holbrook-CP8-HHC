#!/usr/bin/env python3
"""Print HHCW balances for the accounts named on the command line.

HHCW is a work token for verified contribution. This reads chain state.
It does not mint and it does not broadcast.

  HHCW_RPC_URL=http://127.0.0.1:8545 \\
  HHCW_CHAIN_ID=31337 \\
  HHCW_SETTLEMENT_ADDR=0x... \\
  HHCW_TOKEN_ADDR=0x... \\
  HHCW_SETTLER_KEY=... \\
  python3 scripts/hhcw_balances.py 0xWorker 0xVerifier1 0xVerifier2

`--serve PORT` answers GET /balances?accounts=0x...,0x... with the same JSON.
"""

from __future__ import annotations

import json
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from moltbook.ledger.onchain import get_onchain_backend


def main(argv: list[str]) -> int:
    if argv and argv[0] == "--serve":
        port = int(argv[1])
        backend = get_onchain_backend()

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self) -> None:  # noqa: N802
                parsed = urlparse(self.path)
                if parsed.path != "/balances":
                    self.send_response(404)
                    self.end_headers()
                    return
                accounts = parse_qs(parsed.query).get("accounts", ["0x"])
                raw = accounts[0].split(",")
                body = json.dumps(backend.balance_report(raw)).encode("utf-8")
                self.send_response(200)
                self.send_header("content-type", "application/json")
                self.send_header("content-length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def log_message(self, fmt: str, *args: object) -> None:
                del fmt, args

        ThreadingHTTPServer(("127.0.0.1", port), Handler).serve_forever()
        return 0

    if not argv:
        sys.stderr.write("usage: hhcw_balances.py ACCOUNT [ACCOUNT...]\n")
        return 2
    report = get_onchain_backend().balance_report(argv)
    sys.stdout.write(json.dumps(report, indent=2, sort_keys=True) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))

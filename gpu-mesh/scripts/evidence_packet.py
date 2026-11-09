#!/usr/bin/env python3
"""Export a gpu-mesh evidence packet or decode a Base Sepolia Settled log.

The four receipt digests stay separate fields. This script reads a public
transaction receipt. It does not take a key and it does not print one.
"""

from __future__ import annotations

import argparse
import json
import urllib.request

SETTLED_TOPIC = "0x63f88969def260b0a1db98b1f02b96eb9d0caf4a0a439db889fb314255facb6e"
CHAIN_ID = 84532
DEFAULT_RPC = "https://sepolia.base.org"


def _hex(value: object) -> str:
    return str(value or "").lower().removeprefix("0x")


def _word(data: str, index: int) -> str:
    return _hex(data)[index * 64:(index + 1) * 64]


def _address(data: str, index: int) -> str:
    raw = _word(data, index)
    if len(raw) != 64:
        return ""
    return "0x" + raw[24:]


def _uint(data: str, index: int) -> int | None:
    raw = _word(data, index)
    if len(raw) != 64:
        return None
    value = int(raw, 16)
    if value > 2**53 - 1:
        return None
    return value


def decode_settled_log(log: dict) -> dict | None:
    """Decode Settlement.Settled. Indexed: settlementId, worker."""

    topics = log.get("topics") or []
    if not topics or _hex(topics[0]) != SETTLED_TOPIC[2:]:
        return None
    settlement_id = _hex(topics[1] if len(topics) > 1 else "")
    worker_topic = _hex(topics[2] if len(topics) > 2 else "")
    if len(settlement_id) != 64 or len(worker_topic) != 64:
        return None
    data = _hex(log.get("data"))
    if len(data) < 64 * 7:
        return None
    worker_amount = _uint(data, 2)
    verifier1_amount = _uint(data, 3)
    verifier2_amount = _uint(data, 4)
    contribution = _uint(data, 5)
    if None in (worker_amount, verifier1_amount, verifier2_amount, contribution):
        return None
    split_ok = (
        worker_amount + verifier1_amount + verifier2_amount == contribution
        and worker_amount * 10000 == contribution * 9000
        and verifier1_amount * 10000 == contribution * 500
        and verifier2_amount * 10000 == contribution * 500
    )
    address = _hex(log.get("address"))
    return {
        "event": "Settled",
        "address": "0x" + address if address else "",
        "settlement_id": "0x" + settlement_id,
        "worker": "0x" + worker_topic[24:],
        "verifier1": _address(data, 0),
        "verifier2": _address(data, 1),
        "worker_amount": worker_amount,
        "verifier1_amount": verifier1_amount,
        "verifier2_amount": verifier2_amount,
        "contribution_minor": contribution,
        "receipt_root": "0x" + _word(data, 6),
        "split_ok": split_ok,
        "chain_id": CHAIN_ID,
    }


def fetch_receipt(rpc: str, tx_hash: str) -> dict:
    payload = json.dumps({
        "jsonrpc": "2.0",
        "id": 1,
        "method": "eth_getTransactionReceipt",
        "params": [tx_hash],
    }).encode("utf-8")
    request = urllib.request.Request(rpc, data=payload, headers={"content-type": "application/json"})
    with urllib.request.urlopen(request, timeout=30) as response:
        body = json.loads(response.read().decode("utf-8"))
    result = body.get("result") if isinstance(body, dict) else None
    if not isinstance(result, dict):
        raise SystemExit("transaction receipt was not an object")
    return result


def decode_receipt(receipt: dict) -> dict | None:
    for log in receipt.get("logs") or []:
        if isinstance(log, dict):
            decoded = decode_settled_log(log)
            if decoded:
                return decoded
    return None


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Decode a gpu-mesh settlement or fetch an evidence packet")
    parser.add_argument("--tx", default="", help="Base Sepolia transaction hash")
    parser.add_argument("--rpc", default=DEFAULT_RPC)
    parser.add_argument("--hub", default="", help="gpu-mesh hub base URL")
    parser.add_argument("--job", default="", help="job id for GET /api/evidence/{job}")
    parser.add_argument("--log", default="", help="path to a JSON log object")
    args = parser.parse_args(argv)
    if args.log:
        decoded = decode_settled_log(json.loads(open(args.log, encoding="utf-8").read()))
    elif args.tx:
        decoded = decode_receipt(fetch_receipt(args.rpc, args.tx))
    elif args.hub and args.job:
        url = args.hub.rstrip("/") + "/api/evidence/" + args.job
        with urllib.request.urlopen(url, timeout=30) as response:
            print(response.read().decode("utf-8"))
            return 0
    else:
        parser.error("pass --tx, --log, or --hub and --job")
        return 2
    if not decoded:
        print(json.dumps({"ok": False, "error": "settled log was not found"}))
        return 1
    print(json.dumps(decoded, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Settle queued GPU-mesh jobs as HHCW on Base Sepolia.

The deployer key is read from a file on the operator machine. It is never a
CLI argument, never sent to the hub, and never written to a log. Settlement.sol
mints 90% to the worker and 5% to each of two verifiers. It has no escrow, so a
missing payout address is reported as skipped_missing_payout and is not minted.

One mesh credit is 1000 HHCW units so the 9000/500/500 split is exact.
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import re
import sys
import time
import urllib.error
import urllib.request
from collections.abc import Callable
from pathlib import Path
from typing import Any


def _load_ledger():
    """Import the repo ledger after the checkout root is on sys.path.

    This file lives under gpu-mesh/, and ruff checks that tree on its own.
    The ledger package is the parent project, so the path is set inside this
    function rather than above a module-level import.
    """

    root = str(Path(__file__).resolve().parents[2])
    if root not in sys.path:
        sys.path.insert(0, root)
    from moltbook.ledger.backend import OnchainDisabled
    from moltbook.ledger.mesh_receipt import MeshReceiptError
    from moltbook.ledger.onchain import OnchainConfig, OnchainLedger

    return OnchainDisabled, MeshReceiptError, OnchainConfig, OnchainLedger


OnchainDisabled, MeshReceiptError, OnchainConfig, OnchainLedger = _load_ledger()

log = logging.getLogger("gpumesh.settler")

DEFAULT_HUB = "https://ecenvlwyenpakrxfuqup.supabase.co/functions/v1/gpu-mesh"
DEFAULT_RPC = "https://sepolia.base.org"
CHAIN_ID = 84532
TOKEN = "0x24a7B22fC54DbFD117023535eBeCf660B76fdb5d"
SETTLEMENT = "0xdfFE664d23E30Baff7Ad4d16831aD625Cc90bcCA"
ZERO = "0x" + ("0" * 40)
_KEY = re.compile(r"^[0-9a-fA-F]{64}$")
_TX = re.compile(r"^[0-9a-fA-F]{64}$")

Http = Callable[[str, str, str, dict | None], dict]


class HubError(RuntimeError):
    """The hub rejected a settler call."""


class SettlerError(RuntimeError):
    """A settlement could not be posted yet and should be retried."""


def scrub(text: str, secret: str) -> str:
    if not text or not secret:
        return text
    hidden = text.replace(secret, "[redacted]").replace("0x" + secret, "[redacted]")
    return hidden.replace(secret.lower(), "[redacted]")


def read_key(path: Path) -> str:
    """Load a hex private key. The value is not logged."""

    try:
        raw = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise SystemExit(f"cannot read settler key file ({exc.errno})") from None
    text = raw.strip()
    if text.startswith(("0x", "0X")):
        text = text[2:]
    if not _KEY.fullmatch(text):
        raise SystemExit("settler key file is not a 32-byte hex key")
    return text


def normalize_tx(value: Any) -> str:
    text = str(value or "").strip()
    if text.startswith(("0x", "0X")):
        text = text[2:]
    if not _TX.fullmatch(text):
        return ""
    return "0x" + text.lower()


def _urllib_json(method: str, url: str, token: str, payload: dict | None) -> dict:
    data = None if payload is None else json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("authorization", "Bearer " + token)
    req.add_header("accept", "application/json")
    if data is not None:
        req.add_header("content-type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=30) as response:
            body = response.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        raise HubError(f"hub {method} failed ({exc.code})") from None
    except urllib.error.URLError:
        raise SettlerError("hub unreachable") from None
    if not body:
        return {}
    parsed = json.loads(body)
    if not isinstance(parsed, dict):
        raise HubError("hub response was not an object")
    return parsed


class HubClient:
    def __init__(self, base_url: str, token: str, http: Http | None = None):
        self.base_url = base_url.rstrip("/")
        self.token = token
        self.http = http or _urllib_json

    def pending(self) -> list[dict]:
        data = self.http("GET", f"{self.base_url}/api/settlements/pending", self.token, None)
        rows = data.get("settlements") or []
        if not isinstance(rows, list):
            raise HubError("pending settlements were not a list")
        return [row for row in rows if isinstance(row, dict)]

    def post_result(self, settlement_id: str, tx_hash: str, status: str) -> dict:
        return self.http(
            "POST",
            f"{self.base_url}/api/settlements/result",
            self.token,
            {"id": settlement_id, "tx_hash": tx_hash, "status": status},
        )


def build_ledger(key: str, rpc_url: str, w3: Any = None) -> OnchainLedger:
    config = OnchainConfig(
        rpc_url=rpc_url,
        chain_id=CHAIN_ID,
        settlement_addr=SETTLEMENT,
        settler_key=key,
        token_addr=TOKEN,
        address_book={},
    )
    return OnchainLedger(config, w3=w3)


def _address(value: Any) -> str:
    text = str(value or "").strip()
    if not text or text.lower() == ZERO:
        return ""
    return text


def refusal_status(item: dict) -> str:
    """Return a skip status, or empty when the item can be submitted.

    Settlement.sol reverts on the zero address and has no escrow, so a missing
    payout is skipped instead of minted to a stand-in.
    """

    worker = str(item.get("worker_id") or "")
    verifiers = [str(item.get("verifier1_id") or ""), str(item.get("verifier2_id") or "")]
    distinct = [item for item in verifiers if item]
    if len(distinct) != 2 or len(set(distinct)) != 2 or worker in distinct:
        return "skipped_verifier_independence"
    if not item.get("receipt"):
        return "skipped_needs_two_verifiers"
    addresses = (
        _address(item.get("worker_address")),
        _address(item.get("verifier1_address")),
        _address(item.get("verifier2_address")),
    )
    if not all(addresses):
        return "skipped_missing_payout"
    return ""


def address_book(item: dict) -> dict[str, str]:
    return {
        str(item["worker_id"]): _address(item.get("worker_address")),
        str(item["verifier1_id"]): _address(item.get("verifier1_address")),
        str(item["verifier2_id"]): _address(item.get("verifier2_address")),
    }


def status_for_mesh_error(exc: MeshReceiptError) -> str:
    text = str(exc).lower()
    if "two distinct" in text:
        return "skipped_needs_two_verifiers"
    if "no account" in text or "zero address" in text:
        return "skipped_missing_payout"
    if "divide" in text or "contribution" in text:
        return "skipped_indivisible"
    return "failed"


def settle_one(ledger: OnchainLedger, item: dict) -> tuple[str, str]:
    skip = refusal_status(item)
    if skip:
        return "", skip
    receipt = item["receipt"]
    if isinstance(receipt, str):
        receipt = json.loads(receipt)
    try:
        result = ledger.settle_verified_receipt(receipt, address_book=address_book(item))
    except MeshReceiptError as exc:
        return "", status_for_mesh_error(exc)
    tx = normalize_tx(result.get("txHash"))
    if result.get("alreadySettled"):
        return tx, "already_settled"
    if result.get("status") in (0, "0x0"):
        return tx, "failed"
    if not tx:
        raise SettlerError("settlement transaction returned no hash")
    return tx, "settled"


def poll_once(hub: HubClient, ledger: OnchainLedger) -> list[dict]:
    posted = []
    secret = ledger.config.settler_key
    for item in hub.pending():
        label = str(item.get("id") or "")
        try:
            tx_hash, status = settle_one(ledger, item)
        except (SettlerError, OnchainDisabled, OSError) as exc:
            log.warning("settlement %s left pending: %s", label, scrub(str(exc), secret))
            continue
        except Exception as exc:
            log.warning("settlement %s left pending: %s", label, scrub(f"{type(exc).__name__}: {exc}", secret))
            continue
        hub.post_result(label, tx_hash, status)
        log.info("settlement %s %s %s", label, status, tx_hash)
        posted.append({"id": label, "tx_hash": tx_hash, "status": status})
    return posted


def run(hub: HubClient, ledger: OnchainLedger, *, once: bool, interval: float, sleep: Callable[[float], None] = time.sleep, max_passes: int | None = None) -> int:
    passes = 0
    while True:
        try:
            poll_once(hub, ledger)
        except (HubError, SettlerError, OnchainDisabled) as exc:
            log.warning("%s", scrub(str(exc), ledger.config.settler_key))
            if once:
                return 1
        passes += 1
        if once or (max_passes is not None and passes >= max_passes):
            return 0
        sleep(interval)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Settle GPU mesh credits as HHCW on Base Sepolia")
    parser.add_argument("--key-file", required=True, help="path to the deployer key; the key is not printed")
    parser.add_argument("--hub", default=DEFAULT_HUB)
    parser.add_argument("--token", default="", help="settler bearer token; prefer GPU_MESH_SETTLER_TOKEN")
    parser.add_argument("--rpc", default=DEFAULT_RPC, help=f"Base Sepolia RPC (default {DEFAULT_RPC})")
    parser.add_argument("--once", action="store_true", help="settle the current queue and exit")
    parser.add_argument("--loop", action="store_true", help="keep polling the hub")
    parser.add_argument("--interval", type=float, default=20.0)
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    token = args.token or os.environ.get("GPU_MESH_SETTLER_TOKEN", "")
    if not token:
        raise SystemExit("Set GPU_MESH_SETTLER_TOKEN or pass --token. The deployer key is not this token.")
    if args.interval <= 0:
        raise SystemExit("--interval must be positive")
    if args.once == args.loop:
        raise SystemExit("Pass exactly one of --once or --loop")
    key = read_key(Path(args.key_file))
    hub = HubClient(args.hub, token)
    try:
        ledger = build_ledger(key, args.rpc.strip() or DEFAULT_RPC)
    except OnchainDisabled as exc:
        raise SystemExit(scrub(str(exc), key)) from None
    return run(hub, ledger, once=args.once, interval=args.interval)


if __name__ == "__main__":
    raise SystemExit(main())

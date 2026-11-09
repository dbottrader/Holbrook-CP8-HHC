#!/usr/bin/env python3
"""Read-only replay of the ASIN-HHC mesh ledger under pinned canon v1.

The byte spec is CANON_V1.md. Sequence 16 is the trusted anchor.
Sequences 1-15 are legacy and are reported, not trusted.

Exit codes, fail closed:
  0  anchor holds and the v1 segment links to the tip
  2  usage
  3  local known-answer mismatch
  4  pin file or server vector digest mismatch
  5  transport failure
  6  sequence 16 missing or not a valid v1 anchor
  7  a v1 entry after the anchor does not recompute
  8  prev_hash breaks at sequence 16 or later
"""

from __future__ import annotations

import hashlib
import json
import sys
import urllib.error
import urllib.request
from collections import Counter
from pathlib import Path

ZERO = "0" * 64
ANCHOR_SEQ = 16
PIN_SHA256 = "ac273068d2ce71c7c711bd93bbe1244f2046e10b6cdc1379c00652381d234cdf"
PREIMAGE_FIELDS = ("actor", "kind", "payload", "prev_hash", "ts")
PIN_PATH = Path(__file__).resolve().parent / "kat" / "canon-v1.json"

EXIT_OK = 0
EXIT_USAGE = 2
EXIT_KAT = 3
EXIT_PIN = 4
EXIT_TRANSPORT = 5
EXIT_ANCHOR = 6
EXIT_SEGMENT = 7
EXIT_LINK = 8


class TransportError(RuntimeError):
    """A read failed. The replay must not confirm anything."""


def canon_bytes(obj) -> bytes:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")


def sha_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def load_pin() -> dict:
    raw = PIN_PATH.read_bytes()
    if sha_hex(raw) != PIN_SHA256:
        raise SystemExit(EXIT_PIN)
    pin = json.loads(raw.decode("utf-8"))
    if not kat_ok(pin):
        raise SystemExit(EXIT_KAT)
    return pin


def kat_ok(pin: dict) -> bool:
    vectors = pin.get("vectors") or []
    if not vectors:
        return False
    for vector in vectors:
        if sha_hex(canon_bytes(vector["input"])) != vector["canon_sha256"]:
            return False
    lock = pin.get("sequence_16_lock") or {}
    preimage = lock.get("preimage")
    if not isinstance(preimage, dict):
        return False
    if set(preimage) != set(PREIMAGE_FIELDS):
        return False
    return sha_hex(canon_bytes(preimage)) == lock.get("hash")


def entry_hash(entry: dict) -> str:
    """Hash the five-field preimage. seq is intentionally absent."""

    body = {field: entry[field] for field in PREIMAGE_FIELDS}
    return sha_hex(canon_bytes(body))


def judge(entries: list[dict]) -> dict:
    """Walk the chain. Trust starts at sequence 16 and nowhere earlier."""

    ordered = sorted(entries, key=lambda item: int(item["seq"]))
    prev = ZERO
    legacy = []
    legacy_match = []
    hash_fail = []
    link_breaks = []
    anchor_ok = False
    saw_anchor = False
    for entry in ordered:
        seq = int(entry["seq"])
        linked = entry.get("prev_hash") == prev
        if not linked:
            link_breaks.append(seq)
        try:
            match = entry_hash(entry) == entry.get("hash")
        except KeyError:
            match = False
        if seq < ANCHOR_SEQ or entry.get("canon") != "v1":
            legacy.append(seq)
            if match:
                legacy_match.append(seq)
        elif seq == ANCHOR_SEQ:
            saw_anchor = True
            anchor_ok = match and entry.get("canon") == "v1" and linked
            if not match:
                hash_fail.append(seq)
        else:
            if not match:
                hash_fail.append(seq)
        prev = str(entry.get("hash") or "")
    post_links = [seq for seq in link_breaks if seq >= ANCHOR_SEQ]
    v1_entries = [entry for entry in ordered if entry.get("canon") == "v1" and int(entry["seq"]) >= ANCHOR_SEQ]
    if not saw_anchor or not anchor_ok:
        code = EXIT_ANCHOR
    elif post_links:
        code = EXIT_LINK
    elif hash_fail:
        code = EXIT_SEGMENT
    else:
        code = EXIT_OK
    tip = ordered[-1] if ordered else None
    report = {
        "height": int(tip["seq"]) if tip else 0,
        "tip_hash": tip.get("hash") if tip else ZERO,
        "entries_recomputed": len(ordered),
        "kind_counts": dict(Counter(entry.get("kind") for entry in ordered)),
        "canon_counts": dict(Counter(entry.get("canon") for entry in ordered)),
        "legacy_segment": {
            "seqs": legacy,
            "first_failing_seq_under_pinned_canon": legacy[0] if legacy else None,
            "recompute_under_canon_v1_matches": legacy_match,
        },
        "v1_segment": {
            "first_v1_seq": ANCHOR_SEQ if saw_anchor else None,
            "count": len(v1_entries),
            "hash_failures": hash_fail,
            "segment_verifies_to_tip": code == EXIT_OK,
            "trusted_anchor_seq": ANCHOR_SEQ,
            "trusted_anchor_ok": anchor_ok,
        },
        "linkage_breaks": link_breaks,
        "chain_verifies_to_tip_under_pinned_canon": code == EXIT_OK and not legacy,
        "exit_code": code,
    }
    return report


def remote_vectors_match(pin: dict, remote: dict) -> bool:
    pinned = {item["canon_sha256"] for item in pin["vectors"]}
    seen = set()
    for item in remote.get("vectors") or []:
        stated = item.get("canon_sha256")
        try:
            actual = sha_hex(canon_bytes(item["input"]))
        except (KeyError, TypeError):
            return False
        if stated != actual:
            return False
        seen.add(stated)
    return pinned <= seen


def get_json(base: str, path: str) -> dict:
    request = urllib.request.Request(base.rstrip("/") + path, headers={"Accept": "application/json"})
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            body = json.loads(response.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, OSError) as exc:
        raise TransportError(str(exc)) from None
    if not isinstance(body, dict):
        raise TransportError("response was not an object")
    return body


def page_ledger(base: str) -> list[dict]:
    entries = []
    since = 0
    while True:
        page = get_json(base, "/ledger?since=%d" % since)
        rows = page.get("entries")
        if not isinstance(rows, list) or not rows:
            break
        entries.extend(row for row in rows if isinstance(row, dict))
        since = int(rows[-1]["seq"])
        if len(rows) < 200:
            break
    return entries


def replay_remote(base: str) -> tuple[dict, int]:
    pin = load_pin()
    try:
        remote = get_json(base, "/receipt/vectors")
    except TransportError:
        return {"error": "vector endpoint unread", "exit_code": EXIT_TRANSPORT}, EXIT_TRANSPORT
    if not remote_vectors_match(pin, remote):
        return {"error": "server vectors do not match the pinned digests", "exit_code": EXIT_PIN}, EXIT_PIN
    try:
        entries = page_ledger(base)
        server = get_json(base, "/ledger/verify")
    except TransportError:
        return {"error": "ledger unread", "exit_code": EXIT_TRANSPORT}, EXIT_TRANSPORT
    report = judge(entries)
    report["vectors_selftest"] = True
    report["vectors_count"] = len(pin["vectors"])
    report["server_ledger_verify"] = {"ok": server.get("ok"), "failing_seq": server.get("failing_seq")}
    return report, int(report["exit_code"])


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if len(args) != 1:
        print(__doc__)
        return EXIT_USAGE
    if args[0] == "--self-test":
        try:
            load_pin()
        except SystemExit as exc:
            print(json.dumps({"vectors_selftest": False, "exit_code": int(exc.code)}))
            return int(exc.code)
        print(json.dumps({"vectors_selftest": True, "pin_sha256": PIN_SHA256, "exit_code": EXIT_OK}))
        return EXIT_OK
    if args[0] == "--ledger":
        print(__doc__)
        return EXIT_USAGE
    if args[0].startswith("--ledger="):
        path = Path(args[0].split("=", 1)[1])
        try:
            load_pin()
            entries = json.loads(path.read_text(encoding="utf-8"))
        except SystemExit as exc:
            return int(exc.code)
        except (OSError, json.JSONDecodeError):
            print(json.dumps({"error": "ledger file unread", "exit_code": EXIT_TRANSPORT}))
            return EXIT_TRANSPORT
        if not isinstance(entries, list):
            return EXIT_TRANSPORT
        report = judge(entries)
        print(json.dumps(report, indent=2))
        return int(report["exit_code"])
    report, code = replay_remote(args[0])
    print(json.dumps(report, indent=2))
    return code


if __name__ == "__main__":
    sys.exit(main())

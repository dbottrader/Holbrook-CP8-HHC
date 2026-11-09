"""Pinned canon v1 bytes, fail-closed exits, and the sequence-16 anchor."""

import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def _module():
    spec = importlib.util.spec_from_file_location("verify_replay", ROOT / "verify_replay.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _entry(module, seq, prev, canon="v1", payload="{}", actor="node", kind="work"):
    body = {
        "actor": actor,
        "kind": kind,
        "payload": payload,
        "prev_hash": prev,
        "ts": 1_700_000_000 + seq,
    }
    return {
        **body,
        "seq": seq,
        "canon": canon,
        "hash": module.sha_hex(module.canon_bytes(body)),
    }


def test_pin_file_and_known_answers():
    module = _module()
    raw = (ROOT / "kat" / "canon-v1.json").read_bytes()
    assert module.sha_hex(raw) == module.PIN_SHA256
    pin = json.loads(raw.decode("utf-8"))
    assert module.kat_ok(pin)
    assert module.main(["--self-test"]) == module.EXIT_OK
    assert "seq" not in module.PREIMAGE_FIELDS
    assert module.remote_vectors_match(pin, {"vectors": pin["vectors"]}) is True
    drifted = {"vectors": [{"input": {"a": 1}, "canon_sha256": "00" * 32}]}
    assert module.remote_vectors_match(pin, drifted) is False


def test_sequence_16_is_required():
    module = _module()
    short = []
    prev = module.ZERO
    for seq in range(1, 16):
        row = _entry(module, seq, prev, canon="v0-compat")
        short.append(row)
        prev = row["hash"]
    report = module.judge(short)
    assert report["exit_code"] == module.EXIT_ANCHOR
    assert report["v1_segment"]["segment_verifies_to_tip"] is False
    assert report["v1_segment"]["trusted_anchor_ok"] is False

    anchor = _entry(module, 16, prev, canon="v1")
    good = short + [anchor]
    held = module.judge(good)
    assert held["exit_code"] == module.EXIT_OK
    assert held["v1_segment"]["trusted_anchor_ok"] is True
    assert held["chain_verifies_to_tip_under_pinned_canon"] is False

    broken = dict(anchor)
    broken["hash"] = "ab" * 32
    refused = module.judge(short + [broken])
    assert refused["exit_code"] == module.EXIT_ANCHOR


def test_later_failures_are_not_an_anchor_pass():
    module = _module()
    prev = module.ZERO
    rows = []
    for seq in range(1, 17):
        row = _entry(module, seq, prev, canon="v0-compat" if seq < 16 else "v1")
        rows.append(row)
        prev = row["hash"]
    nxt = _entry(module, 17, prev, canon="v1")
    nxt["hash"] = "cd" * 32
    report = module.judge(rows + [nxt])
    assert report["exit_code"] == module.EXIT_SEGMENT

    linked = _entry(module, 17, "ff" * 32, canon="v1")
    broken_link = module.judge(rows + [linked])
    assert broken_link["exit_code"] == module.EXIT_LINK


def test_usage_is_fail_closed():
    module = _module()
    assert module.main([]) == module.EXIT_USAGE

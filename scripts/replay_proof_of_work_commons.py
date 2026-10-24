#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Replay the Proof-of-Work Commons launch fixture.

The fixture is local and deterministic. It posts four bounties, exercises a
fenced GPU-worker lease, settles an all-pass escrow 90/5/5, refunds a failed
verification in full, and checks integer credit conservation. Credits are
HHC-SIM. They are simulated. They are not a token and they have no monetary
value. Promotion stays HOLD.

Canonical receipt hash: SHA-256 over UTF-8 JSON with sorted keys and compact
separators of ``{"body", "kind", "prev_hash", "seq"}``. The ``receipt_hash``
field is not part of the hashed object.

Usage:
    python3 scripts/replay_proof_of_work_commons.py --out site/proof
    python3 scripts/replay_proof_of_work_commons.py --check site/proof

Exit 0 when all 8 launch gates pass and, with --check, the files match.
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import re
import sys
import tempfile
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUT = REPO_ROOT / "site" / "proof"
DEFAULT_CONFIG = REPO_ROOT / "site" / "config.js"

API_BASE = "https://ecenvlwyenpakrxfuqup.supabase.co/functions/v1/moltbook-api"
PROJECT_REF = "ecenvlwyenpakrxfuqup"
GENESIS_PREV = "0" * 64
WORKER_BPS = 9000
VERIFIER_BPS = 500
BPS = 10000
LEASE_TICKS = 30

GATE_IDS = (
    "bounty_posted",
    "fenced_lease",
    "verifier_independence",
    "settlement_90_5_5",
    "fail_full_refund",
    "credit_conservation",
    "receipt_chain",
    "simulated_hold_boundary",
)

ARTIFACTS = ("replay.json", "receipts.json", "manifest.json")

PUBLISHER = "agent_publisher_powc"
WORKER = "agent_gpu_worker_powc"
RIVAL = "agent_rival_powc"
VERIFIER_A = "agent_verifier_a_powc"
VERIFIER_B = "agent_verifier_b_powc"


def canon(obj: Any) -> bytes:
    return json.dumps(
        obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_text(text: str) -> str:
    return sha256_bytes(text.encode("utf-8"))


def dumps(obj: Any) -> bytes:
    return (
        json.dumps(obj, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
    ).encode("utf-8")


def require_int(name: str, value: Any) -> int:
    if type(value) is not int:
        raise TypeError(f"{name} must be an int")
    return value


def format_hhc(milli: int) -> str:
    milli = require_int("milli", milli)
    sign = "-" if milli < 0 else ""
    whole, frac = divmod(abs(milli), 1000)
    return f"{sign}{whole}.{frac:03d}"


def settle(price_milli: int, verdicts: list[str]) -> dict[str, Any]:
    """Split an escrow in milli-HHC-SIM.

    Two or more verdicts are required. Any fail refunds the publisher the full
    price and pays the worker and every verifier 0, including verifiers who
    voted pass. An all-pass split is integer floor of 90/5/5. Milli-credits the
    split does not assign return to the publisher. They are not minted.
    """

    price_milli = require_int("price_milli", price_milli)
    if price_milli <= 0:
        raise ValueError("price_milli must be positive")
    if len(verdicts) < 2:
        raise ValueError("at least two verdicts are required")
    if any(v not in ("pass", "fail") for v in verdicts):
        raise ValueError("verdicts must be pass or fail")

    if any(v == "fail" for v in verdicts):
        return {
            "publisher_milli": price_milli,
            "remainder_milli": 0,
            "state": "TERMINAL_REFUNDED",
            "verifier_a_milli": 0,
            "verifier_b_milli": 0,
            "worker_milli": 0,
        }

    if len(verdicts) != 2:
        raise ValueError("the 90/5/5 split is defined for exactly two verifiers")

    worker = price_milli * WORKER_BPS // BPS
    verifier_a = price_milli * VERIFIER_BPS // BPS
    verifier_b = price_milli * VERIFIER_BPS // BPS
    paid = worker + verifier_a + verifier_b
    remainder = price_milli - paid
    if paid + remainder != price_milli:
        raise RuntimeError("settlement failed to conserve credits")
    return {
        "publisher_milli": remainder,
        "remainder_milli": remainder,
        "state": "TERMINAL_PAID",
        "verifier_a_milli": verifier_a,
        "verifier_b_milli": verifier_b,
        "worker_milli": worker,
    }


def lease_is_active(holder: str | None, until_tick: int, tick: int) -> bool:
    return holder is not None and tick < until_tick


def claim_allowed(
    holder: str | None, until_tick: int, tick: int, claimant: str
) -> bool:
    if not lease_is_active(holder, until_tick, tick):
        return True
    return claimant == holder


def receipt_hash(seq: int, kind: str, prev_hash: str, body: dict[str, Any]) -> str:
    return sha256_bytes(
        canon({"body": body, "kind": kind, "prev_hash": prev_hash, "seq": seq})
    )


class Chain:
    def __init__(self) -> None:
        self.receipts: list[dict[str, Any]] = []

    def append(self, kind: str, body: dict[str, Any]) -> dict[str, Any]:
        seq = len(self.receipts)
        prev = GENESIS_PREV if seq == 0 else self.receipts[-1]["receipt_hash"]
        record = {
            "body": body,
            "kind": kind,
            "prev_hash": prev,
            "receipt_hash": receipt_hash(seq, kind, prev, body),
            "seq": seq,
        }
        self.receipts.append(record)
        return record


def _parties(bounty: dict[str, Any]) -> dict[str, str]:
    return {"publisher": bounty["publisher"], "worker": bounty["holder"]}


def build_chain() -> list[dict[str, Any]]:
    chain = Chain()
    chain.append(
        "genesis",
        {
            "fail_rule": (
                "any fail in a verdict set of two or more refunds the publisher "
                "the full price; the worker and both verifiers receive 0"
            ),
            "fixture": "powc-launch-v1",
            "lease_rule": (
                "a lease is active while tick < until_tick; a different worker "
                "is rejected until then"
            ),
            "milli_per_unit": 1000,
            "monetary_authority": False,
            "promotion": "HOLD",
            "remainder_rule": (
                "on an all-pass split, integer floor of 90/5/5; undistributed "
                "milli-credits return to the publisher"
            ),
            "schema": "powc-genesis-v1",
            "unit": "HHC-SIM",
            "verifier_bps_each": VERIFIER_BPS,
            "verifier_count": 2,
            "worker_bps": WORKER_BPS,
        },
    )

    bounties: dict[str, dict[str, Any]] = {}

    def post(bounty_id: str, price_milli: int, text: str) -> None:
        content_hash = sha256_text(text)
        chain.append(
            "bounty_posted",
            {
                "bounty_id": bounty_id,
                "content_sha256": content_hash,
                "price_hhc_sim": format_hhc(price_milli),
                "price_milli": price_milli,
                "promotion": "HOLD",
                "publisher": PUBLISHER,
                "text": text,
                "unit": "HHC-SIM",
            },
        )
        bounties[bounty_id] = {
            "holder": None,
            "price_milli": price_milli,
            "publisher": PUBLISHER,
            "settled": False,
            "text": text,
            "until_tick": -1,
            "verdicts": [],
        }

    def try_claim(bounty_id: str, claimant: str, tick: int, expect: str) -> None:
        bounty = bounties[bounty_id]
        allowed = claim_allowed(
            bounty["holder"], bounty["until_tick"], tick, claimant
        )
        if allowed:
            bounty["holder"] = claimant
            bounty["until_tick"] = tick + LEASE_TICKS
            chain.append(
                "lease_claimed",
                {
                    "bounty_id": bounty_id,
                    "claimant": claimant,
                    "lease_ticks": LEASE_TICKS,
                    "tick": tick,
                    "until_tick": bounty["until_tick"],
                },
            )
            outcome = "claimed"
        else:
            chain.append(
                "lease_rejected",
                {
                    "bounty_id": bounty_id,
                    "claimant": claimant,
                    "holder": bounty["holder"],
                    "reason": "fence_held",
                    "tick": tick,
                    "until_tick": bounty["until_tick"],
                },
            )
            outcome = "rejected"
        if outcome != expect:
            raise RuntimeError(
                f"lease fixture {bounty_id} at tick {tick}: expected {expect}, got {outcome}"
            )

    def add_verdict(bounty_id: str, verifier: str, verdict: str, tick: int) -> None:
        bounty = bounties[bounty_id]
        if bounty["holder"] is None:
            raise RuntimeError("verdict without a worker")
        known = {item["verifier"] for item in bounty["verdicts"]}
        if verifier in (bounty["publisher"], bounty["holder"]) or verifier in known:
            raise RuntimeError("verifier is not independent")
        bounty["verdicts"].append({"verifier": verifier, "verdict": verdict})
        chain.append(
            "verdict",
            {
                "bounty_id": bounty_id,
                "tick": tick,
                "verdict": verdict,
                "verifier": verifier,
            },
        )

    def close(bounty_id: str, tick: int) -> None:
        bounty = bounties[bounty_id]
        if bounty["settled"]:
            raise RuntimeError("bounty already settled")
        ordered = bounty["verdicts"]
        if [item["verifier"] for item in ordered] != [VERIFIER_A, VERIFIER_B]:
            raise RuntimeError("fixture verdicts must be verifier A then verifier B")
        amounts = settle(bounty["price_milli"], [item["verdict"] for item in ordered])
        bounty["settled"] = True
        chain.append(
            "settlement",
            {
                "bounty_id": bounty_id,
                "price_hhc_sim": format_hhc(bounty["price_milli"]),
                "price_milli": bounty["price_milli"],
                "promotion": "HOLD",
                "publisher": bounty["publisher"],
                "publisher_hhc_sim": format_hhc(amounts["publisher_milli"]),
                "publisher_milli": amounts["publisher_milli"],
                "remainder_milli": amounts["remainder_milli"],
                "state": amounts["state"],
                "tick": tick,
                "unit": "HHC-SIM",
                "verifier_a": ordered[0]["verifier"],
                "verifier_a_hhc_sim": format_hhc(amounts["verifier_a_milli"]),
                "verifier_a_milli": amounts["verifier_a_milli"],
                "verifier_b": ordered[1]["verifier"],
                "verifier_b_hhc_sim": format_hhc(amounts["verifier_b_milli"]),
                "verifier_b_milli": amounts["verifier_b_milli"],
                "verdicts": ordered,
                "worker": bounty["holder"],
                "worker_hhc_sim": format_hhc(amounts["worker_milli"]),
                "worker_milli": amounts["worker_milli"],
            },
        )

    post(
        "bty_fence",
        1000,
        "Fence probe. A second worker cannot take a live lease, and can take it only after the lease ends.",
    )
    try_claim("bty_fence", WORKER, 10, "claimed")
    try_claim("bty_fence", RIVAL, 11, "rejected")
    try_claim("bty_fence", RIVAL, 40, "claimed")

    post(
        "bty_pass",
        10000,
        "Pass fixture. Both verifiers accept the result, so the escrow settles 90/5/5.",
    )
    try_claim("bty_pass", WORKER, 100, "claimed")
    add_verdict("bty_pass", VERIFIER_A, "pass", 101)
    add_verdict("bty_pass", VERIFIER_B, "pass", 102)
    close("bty_pass", 103)

    post(
        "bty_fail",
        4000,
        "Fail fixture. One verifier rejects the result, so the publisher is refunded in full.",
    )
    try_claim("bty_fail", WORKER, 200, "claimed")
    add_verdict("bty_fail", VERIFIER_A, "pass", 201)
    add_verdict("bty_fail", VERIFIER_B, "fail", 202)
    close("bty_fail", 203)

    post(
        "bty_probe",
        7,
        "Rounding probe. Price is 7 milli-HHC-SIM so the 90/5/5 integer split leaves a remainder.",
    )
    try_claim("bty_probe", WORKER, 300, "claimed")
    add_verdict("bty_probe", VERIFIER_A, "pass", 301)
    add_verdict("bty_probe", VERIFIER_B, "pass", 302)
    close("bty_probe", 303)

    return chain.receipts


def _sentences(parts: list[str]) -> str:
    cleaned = [part.strip().rstrip(".") for part in parts if part and part.strip()]
    if not cleaned:
        return ""
    text = ". ".join(cleaned) + "."
    return text[0].upper() + text[1:]


def _gate(gate_id: str, status: str, detail: str) -> dict[str, str]:
    if gate_id not in GATE_IDS:
        raise RuntimeError(f"unknown gate {gate_id}")
    if status not in ("PASS", "FAIL"):
        raise RuntimeError("gate status must be PASS or FAIL")
    return {"detail": detail, "id": gate_id, "status": status}


def _index_bounties(receipts: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    bounties: dict[str, dict[str, Any]] = {}
    for record in receipts:
        kind = record["kind"]
        body = record["body"]
        if kind == "bounty_posted":
            bounties[body["bounty_id"]] = {
                "content_sha256": body["content_sha256"],
                "holder": None,
                "posted": body,
                "price_milli": body["price_milli"],
                "publisher": body["publisher"],
                "settlement": None,
                "text": body["text"],
                "until_tick": -1,
                "verdicts": [],
            }
    return bounties


def evaluate_gates(
    receipts: list[dict[str, Any]], config_text: str
) -> list[dict[str, str]]:
    problems: dict[str, list[str]] = {gate_id: [] for gate_id in GATE_IDS}
    notes: dict[str, list[str]] = {gate_id: [] for gate_id in GATE_IDS}

    chain_ok, chain_detail = verify_chain(receipts)
    if chain_ok:
        notes["receipt_chain"].append(chain_detail)
    else:
        problems["receipt_chain"].append(chain_detail)

    bounties = _index_bounties(receipts)
    saw_posted = False
    saw_rejection = False
    saw_reclaim_after_expiry = False

    for record in receipts:
        kind = record["kind"]
        body = record["body"]
        if kind == "genesis":
            continue
        bounty_id = body.get("bounty_id")
        bounty = bounties.get(bounty_id) if isinstance(bounty_id, str) else None
        if bounty is None:
            problems["bounty_posted"].append(f"{kind} references an unknown bounty")
            continue

        if kind == "bounty_posted":
            price = body.get("price_milli")
            text = body.get("text")
            publisher = body.get("publisher")
            content_hash = body.get("content_sha256")
            if (
                type(price) is int
                and price > 0
                and isinstance(text, str)
                and text
                and isinstance(publisher, str)
                and publisher
                and content_hash == sha256_text(text)
                and body.get("unit") == "HHC-SIM"
                and body.get("promotion") == "HOLD"
            ):
                saw_posted = True
            else:
                problems["bounty_posted"].append(
                    f"{bounty_id} is missing a positive price, publisher, or bound text hash"
                )

        elif kind == "lease_claimed":
            tick = body.get("tick")
            claimant = body.get("claimant")
            if type(tick) is not int or not isinstance(claimant, str):
                problems["fenced_lease"].append(f"{bounty_id} claim is malformed")
                continue
            previous_holder = bounty["holder"]
            previous_until = bounty["until_tick"]
            if not claim_allowed(previous_holder, previous_until, tick, claimant):
                problems["fenced_lease"].append(
                    f"{bounty_id} was claimed by {claimant} while {previous_holder} held the fence"
                )
            else:
                if (
                    previous_holder is not None
                    and claimant != previous_holder
                    and tick >= previous_until
                ):
                    saw_reclaim_after_expiry = True
                bounty["holder"] = claimant
                bounty["until_tick"] = tick + int(body.get("lease_ticks") or 0)
                if body.get("until_tick") != bounty["until_tick"]:
                    problems["fenced_lease"].append(
                        f"{bounty_id} until_tick does not match tick + lease_ticks"
                    )

        elif kind == "lease_rejected":
            tick = body.get("tick")
            claimant = body.get("claimant")
            if type(tick) is not int or not isinstance(claimant, str):
                problems["fenced_lease"].append(f"{bounty_id} rejection is malformed")
                continue
            if claim_allowed(bounty["holder"], bounty["until_tick"], tick, claimant):
                problems["fenced_lease"].append(
                    f"{bounty_id} recorded a rejection when the claim was allowed"
                )
            elif body.get("reason") != "fence_held" or body.get("holder") != bounty["holder"]:
                problems["fenced_lease"].append(f"{bounty_id} rejection is mislabeled")
            else:
                saw_rejection = True

        elif kind == "verdict":
            verifier = body.get("verifier")
            verdict = body.get("verdict")
            if verdict not in ("pass", "fail") or not isinstance(verifier, str):
                problems["verifier_independence"].append(
                    f"{bounty_id} verdict is malformed"
                )
                continue
            if bounty["holder"] is None:
                problems["verifier_independence"].append(
                    f"{bounty_id} collected a verdict before a worker claimed it"
                )
            if verifier in (bounty["publisher"], bounty["holder"]):
                problems["verifier_independence"].append(
                    f"{verifier} reviews their own side of {bounty_id}"
                )
            if any(item["verifier"] == verifier for item in bounty["verdicts"]):
                problems["verifier_independence"].append(
                    f"{verifier} voted twice on {bounty_id}"
                )
            bounty["verdicts"].append({"verifier": verifier, "verdict": verdict})

        elif kind == "settlement":
            verdicts = [item["verdict"] for item in bounty["verdicts"]]
            verifiers = [item["verifier"] for item in bounty["verdicts"]]
            if len(verifiers) != 2 or len(set(verifiers)) != 2:
                problems["verifier_independence"].append(
                    f"{bounty_id} did not close with two distinct verifiers"
                )
            if bounty["holder"] is None or body.get("worker") != bounty["holder"]:
                problems["verifier_independence"].append(
                    f"{bounty_id} settlement worker does not match the lease holder"
                )
            if body.get("publisher") != bounty["publisher"]:
                problems["verifier_independence"].append(
                    f"{bounty_id} settlement publisher does not match the bounty"
                )
            if verifiers != [body.get("verifier_a"), body.get("verifier_b")]:
                problems["verifier_independence"].append(
                    f"{bounty_id} settlement verifier order does not match the verdicts"
                )
            try:
                expected = settle(bounty["price_milli"], verdicts)
            except (TypeError, ValueError, RuntimeError) as exc:
                problems["credit_conservation"].append(f"{bounty_id}: {exc}")
                continue
            fields = (
                "state",
                "worker_milli",
                "verifier_a_milli",
                "verifier_b_milli",
                "publisher_milli",
                "remainder_milli",
            )
            for field in fields:
                if body.get(field) != expected[field]:
                    problems["credit_conservation"].append(
                        f"{bounty_id} {field} is {body.get(field)}, expected {expected[field]}"
                    )
            total = (
                body.get("worker_milli")
                + body.get("verifier_a_milli")
                + body.get("verifier_b_milli")
                + body.get("publisher_milli")
            )
            if total != bounty["price_milli"]:
                problems["credit_conservation"].append(
                    f"{bounty_id} pays {total}, not the escrowed {bounty['price_milli']}"
                )
            displays = {
                "price_hhc_sim": bounty["price_milli"],
                "worker_hhc_sim": body.get("worker_milli"),
                "verifier_a_hhc_sim": body.get("verifier_a_milli"),
                "verifier_b_hhc_sim": body.get("verifier_b_milli"),
                "publisher_hhc_sim": body.get("publisher_milli"),
            }
            for label, milli in displays.items():
                if type(milli) is int and body.get(label) != format_hhc(milli):
                    problems["credit_conservation"].append(
                        f"{bounty_id} {label} does not match its milli amount"
                    )
            if (
                bounty_id == "bty_pass"
                and expected["state"] == "TERMINAL_PAID"
                and expected["worker_milli"] == 9000
                and expected["verifier_a_milli"] == 500
                and expected["verifier_b_milli"] == 500
                and expected["publisher_milli"] == 0
            ):
                notes["settlement_90_5_5"].append(
                    "bty_pass pays 9.000 / 0.500 / 0.500 HHC-SIM from 10.000"
                )
            elif bounty_id == "bty_pass":
                problems["settlement_90_5_5"].append(
                    "bty_pass did not settle 9000 / 500 / 500 milli-HHC-SIM"
                )
            if bounty_id == "bty_fail":
                if (
                    expected["state"] == "TERMINAL_REFUNDED"
                    and expected["publisher_milli"] == 4000
                    and expected["worker_milli"] == 0
                    and expected["verifier_a_milli"] == 0
                    and expected["verifier_b_milli"] == 0
                    and any(item["verdict"] == "pass" for item in bounty["verdicts"])
                    and any(item["verdict"] == "fail" for item in bounty["verdicts"])
                ):
                    notes["fail_full_refund"].append(
                        "bty_fail refunds 4.000 HHC-SIM; the pass vote is unpaid"
                    )
                else:
                    problems["fail_full_refund"].append(
                        "bty_fail did not refund the publisher in full"
                    )
            if bounty_id == "bty_probe":
                if expected["worker_milli"] == 6 and expected["publisher_milli"] == 1:
                    notes["credit_conservation"].append(
                        "bty_probe price 7 milli returns remainder 1 to the publisher"
                    )
                else:
                    problems["credit_conservation"].append(
                        "bty_probe did not return the indivisible remainder"
                    )
            bounty["settlement"] = body
        else:
            problems["receipt_chain"].append(f"unknown receipt kind {kind}")

    if not saw_posted:
        problems["bounty_posted"].append("no bound bounty was posted")
    else:
        notes["bounty_posted"].append(
            f"{sum(1 for r in receipts if r['kind'] == 'bounty_posted')} bounties posted with bound text hashes"
        )
    if not saw_rejection:
        problems["fenced_lease"].append("no rival claim was rejected during a live lease")
    if not saw_reclaim_after_expiry:
        problems["fenced_lease"].append("no claim succeeded after a lease expired")
    if saw_rejection and saw_reclaim_after_expiry and not problems["fenced_lease"]:
        notes["fenced_lease"].append(
            "a rival was rejected at tick 11 and claimed bty_fence only at tick 40, when the lease ended"
        )
    if not notes["settlement_90_5_5"] and not problems["settlement_90_5_5"]:
        problems["settlement_90_5_5"].append("pass settlement was not found")
    if not notes["fail_full_refund"] and not problems["fail_full_refund"]:
        problems["fail_full_refund"].append("fail refund was not found")
    settled = [
        b["settlement"] for b in bounties.values() if b["settlement"] is not None
    ]
    if len(settled) < 3:
        problems["credit_conservation"].append("expected three settlement receipts")
    elif not problems["credit_conservation"]:
        notes["credit_conservation"].append(
            f"{len(settled)} settlements conserve the escrowed milli-credits"
        )
    if not problems["verifier_independence"] and settled:
        notes["verifier_independence"].append(
            "each settled bounty has two verifiers, distinct from each other, the worker, and the publisher"
        )

    boundary_problem, boundary_note = check_public_config(config_text)
    genesis = receipts[0]["body"] if receipts else {}
    if (
        genesis.get("monetary_authority") is not False
        or genesis.get("promotion") != "HOLD"
        or genesis.get("unit") != "HHC-SIM"
    ):
        problems["simulated_hold_boundary"].append(
            "genesis does not keep HHC-SIM simulated and HOLD"
        )
    if boundary_problem:
        problems["simulated_hold_boundary"].append(boundary_problem)
    if not problems["simulated_hold_boundary"]:
        notes["simulated_hold_boundary"].append(
            "HHC-SIM stays simulated, promotion stays HOLD, and "
            + (boundary_note or "the public config was checked")
        )

    gates = []
    for gate_id in GATE_IDS:
        if problems[gate_id]:
            gates.append(_gate(gate_id, "FAIL", _sentences(problems[gate_id])))
        else:
            gates.append(_gate(gate_id, "PASS", _sentences(notes[gate_id])))
    return gates


def verify_chain(receipts: list[dict[str, Any]]) -> tuple[bool, str]:
    if not receipts:
        return False, "receipt chain is empty"
    prev = GENESIS_PREV
    for index, record in enumerate(receipts):
        if record.get("seq") != index:
            return False, f"seq {record.get('seq')} is not contiguous at {index}"
        if record.get("prev_hash") != prev:
            return False, f"seq {index} prev_hash does not match the previous receipt"
        expected = receipt_hash(
            index, record.get("kind"), record.get("prev_hash"), record.get("body")
        )
        if record.get("receipt_hash") != expected:
            return False, f"seq {index} receipt_hash does not recompute"
        if not re.fullmatch(r"[0-9a-f]{64}", str(record.get("receipt_hash"))):
            return False, f"seq {index} hash is not 64 hex characters"
        prev = record["receipt_hash"]
    if receipts[0]["kind"] != "genesis" or receipts[0]["prev_hash"] != GENESIS_PREV:
        return False, "chain does not start at the genesis receipt"
    return True, f"{len(receipts)} receipts recompute and link to {receipts[-1]['receipt_hash']}"


def parse_config(text: str) -> dict[str, str]:
    found: dict[str, str] = {}
    for name in ("apiBase", "projectRef", "publishableKey"):
        match = re.search(rf"{name}\s*:\s*\"([^\"]*)\"", text)
        if match is None:
            raise ValueError(f"site/config.js is missing {name}")
        found[name] = match.group(1)
    return found


def jwt_payload(token: str) -> dict[str, Any]:
    parts = token.split(".")
    if len(parts) != 3:
        raise ValueError("publishable key is not a three-part JWT")
    padded = parts[1] + "=" * (-len(parts[1]) % 4)
    try:
        raw = base64.urlsafe_b64decode(padded.encode("ascii"))
        payload = json.loads(raw.decode("utf-8"))
    except (ValueError, UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError("publishable key payload is not readable") from exc
    if not isinstance(payload, dict):
        raise ValueError("publishable key payload is not an object")
    return payload


def check_public_config(text: str) -> tuple[str | None, str | None]:
    forbidden = ("SUPABASE_SERVICE_ROLE", "sb_secret_", "service_role")
    lowered = text.lower()
    for token in forbidden:
        if token.lower() in lowered:
            return f"site/config.js contains {token}", None
    try:
        config = parse_config(text)
        payload = jwt_payload(config["publishableKey"])
    except ValueError as exc:
        return str(exc), None
    if config["apiBase"] != API_BASE:
        return "site/config.js apiBase is not the public moltbook-api", None
    if config["projectRef"] != PROJECT_REF:
        return "site/config.js projectRef does not match the public project", None
    if payload.get("role") != "anon" or payload.get("ref") != PROJECT_REF:
        return "publishable key payload is not the anon role for this project", None
    return None, (
        "site/config.js carries the public anon key for "
        f"{PROJECT_REF}; the key signature was not re-checked"
    )


def settlement_cases(receipts: list[dict[str, Any]]) -> list[dict[str, Any]]:
    cases = []
    for record in receipts:
        if record["kind"] != "settlement":
            continue
        body = record["body"]
        cases.append(
            {
                "bounty_id": body["bounty_id"],
                "price_hhc_sim": body["price_hhc_sim"],
                "price_milli": body["price_milli"],
                "publisher_hhc_sim": body["publisher_hhc_sim"],
                "publisher_milli": body["publisher_milli"],
                "remainder_milli": body["remainder_milli"],
                "state": body["state"],
                "verifier_a_hhc_sim": body["verifier_a_hhc_sim"],
                "verifier_a_milli": body["verifier_a_milli"],
                "verifier_b_hhc_sim": body["verifier_b_hhc_sim"],
                "verifier_b_milli": body["verifier_b_milli"],
                "worker_hhc_sim": body["worker_hhc_sim"],
                "worker_milli": body["worker_milli"],
            }
        )
    return cases


def build(config_text: str) -> dict[str, Any]:
    receipts = build_chain()
    gates = evaluate_gates(receipts, config_text)
    receipts_doc = {
        "canonicalization": (
            "SHA-256 of UTF-8 JSON with sorted keys and compact separators "
            "for the object {body, kind, prev_hash, seq}. receipt_hash is excluded."
        ),
        "genesis_prev_hash": GENESIS_PREV,
        "promotion": "HOLD",
        "receipts": receipts,
        "schema": "powc-receipt-chain-v1",
        "unit": "HHC-SIM",
    }
    receipts_bytes = dumps(receipts_doc)
    passed = sum(1 for gate in gates if gate["status"] == "PASS")
    replay = {
        "cases": settlement_cases(receipts),
        "fixture": "powc-launch-v1",
        "gates": gates,
        "gates_passed": passed,
        "gates_total": len(GATE_IDS),
        "head_receipt_hash": receipts[-1]["receipt_hash"],
        "local_replay": [
            "git clone https://github.com/dbottrader/Holbrook-CP8-HHC.git",
            "cd Holbrook-CP8-HHC",
            "python3 scripts/replay_proof_of_work_commons.py --out /tmp/powc-replay",
            "python3 scripts/replay_proof_of_work_commons.py --check site/proof",
        ],
        "monetary_authority": False,
        "note": (
            "HHC-SIM credits in this replay are simulated. They are not a token, "
            "not money, and not redeemable. A passing replay does not promote the system."
        ),
        "promotion": "HOLD",
        "receipt_count": len(receipts),
        "receipts_sha256": sha256_bytes(receipts_bytes),
        "schema": "powc-replay-v1",
        "settlement_rule": {
            "fail": (
                "any fail among two verdicts refunds the publisher the full price; "
                "worker and verifiers receive 0"
            ),
            "pass": (
                "worker 90 percent, verifier A 5 percent, verifier B 5 percent, "
                "integer floor; undistributed remainder returns to the publisher"
            ),
            "unit": "milli-HHC-SIM; 1000 milli = 1.000 HHC-SIM",
        },
        "unit": "HHC-SIM",
    }
    replay_bytes = dumps(replay)
    manifest = {
        "files": [
            {
                "bytes": len(replay_bytes),
                "path": "replay.json",
                "sha256": sha256_bytes(replay_bytes),
            },
            {
                "bytes": len(receipts_bytes),
                "path": "receipts.json",
                "sha256": sha256_bytes(receipts_bytes),
            },
        ],
        "note": "SHA-256 of the exact file bytes published beside this manifest.",
        "promotion": "HOLD",
        "schema": "powc-artifact-manifest-v1",
    }
    return {
        "gates": gates,
        "manifest_bytes": dumps(manifest),
        "ok": passed == len(GATE_IDS) and all(g["status"] == "PASS" for g in gates),
        "receipts": receipts,
        "receipts_bytes": receipts_bytes,
        "replay_bytes": replay_bytes,
    }


def write_artifacts(directory: Path, built: dict[str, Any]) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    payloads = {
        "replay.json": built["replay_bytes"],
        "receipts.json": built["receipts_bytes"],
        "manifest.json": built["manifest_bytes"],
    }
    for name in ARTIFACTS:
        (directory / name).write_bytes(payloads[name])


def compare_artifacts(directory: Path, built: dict[str, Any]) -> list[str]:
    payloads = {
        "replay.json": built["replay_bytes"],
        "receipts.json": built["receipts_bytes"],
        "manifest.json": built["manifest_bytes"],
    }
    mismatches = []
    for name in ARTIFACTS:
        path = directory / name
        if not path.is_file():
            mismatches.append(f"missing {name}")
            continue
        if path.read_bytes() != payloads[name]:
            mismatches.append(f"byte mismatch {name}")
    return mismatches


def load_config(path: Path) -> str:
    if not path.is_file():
        raise SystemExit(f"public config not found: {path}")
    return path.read_text(encoding="utf-8")


def print_summary(built: dict[str, Any]) -> None:
    for gate in built["gates"]:
        print(f"{gate['id']:<28} {gate['status']}")
    passed = sum(1 for gate in built["gates"] if gate["status"] == "PASS")
    print(f"{passed}/{len(GATE_IDS)} {'PASS' if built['ok'] else 'FAIL'}")
    print("promotion HOLD")
    print("unit HHC-SIM (simulated, no monetary authority)")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--out",
        type=Path,
        help="directory for replay.json, receipts.json, and manifest.json",
    )
    parser.add_argument(
        "--check",
        type=Path,
        help="compare a fresh replay with the files already in this directory",
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=DEFAULT_CONFIG,
        help="public site config.js (default: site/config.js)",
    )
    args = parser.parse_args(argv)

    config_text = load_config(args.config)
    built = build(config_text)
    code = 0 if built["ok"] else 1
    destination = args.out
    if destination is None and args.check is None:
        destination = DEFAULT_OUT
    if destination is not None:
        write_artifacts(destination, built)
        print(f"wrote {destination}")
    if args.check is not None:
        mismatches = compare_artifacts(args.check, built)
        if mismatches:
            code = 1
            for item in mismatches:
                print(item, file=sys.stderr)
        else:
            print(f"match {args.check}")
    print_summary(built)
    return code


if __name__ == "__main__":
    raise SystemExit(main())

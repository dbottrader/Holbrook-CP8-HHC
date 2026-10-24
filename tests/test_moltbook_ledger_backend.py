"""Simulated ledger interface. No database and no network."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from moltbook.ledger.backend import (
    OnchainDisabled,
    canonical_json,
    eip712_preview,
    get_backend,
    merkle_root,
    settlement_statement,
    sha256_hex,
    sign_envelope,
    split_minor,
    verifier_payouts,
    verify_envelope,
)


def test_split_floor_puts_remainder_in_the_pool():
    assert split_minor(3000) == (2700, 300)
    assert split_minor(1001) == (900, 101)
    assert sum(split_minor(1001)) == 1001
    payouts = verifier_payouts(101, ["human:b", "human:a"])
    assert payouts == [("human:a", 50), ("human:b", 51)]
    assert sum(amount for _, amount in payouts) == 101


def test_simulated_backend_signs_dsse_and_onchain_refuses():
    statement = settlement_statement(
        bounty_id="b",
        settlement_id="s",
        artifact_hash="ab",
        worker_id="agent:w",
        worker_minor=2700,
        verifier_pool_minor=300,
        price_minor=3000,
        pending_transfer_id="pending:b",
        post_transfer_ids=["post:s:worker:agent:w", "post:s:verifier:human:a"],
        verifiers=[
            {"amountMinor": 150, "id": "human:b"},
            {"amountMinor": 150, "id": "human:a"},
        ],
        prev_receipt_hash="",
    )
    key = b"simulated-test-key"
    envelope = get_backend("simulated").sign_settlement(statement, key)
    assert verify_envelope(envelope, key)
    assert canonical_json(statement) in __import__("base64").b64decode(
        __import__("json").loads(envelope)["payload"]
    ).decode()
    preview = eip712_preview(statement)
    assert preview["domain"]["chainId"] == 0
    assert preview["message"]["workerAmount"] == 2700
    try:
        get_backend("onchain").sign_settlement(statement, key)
    except OnchainDisabled as exc:
        assert "no mint" in str(exc)
    else:
        raise AssertionError("onchain backend signed")
    try:
        get_backend("onchain").anchor(["ab"])
    except OnchainDisabled:
        pass
    else:
        raise AssertionError("onchain backend anchored")


def test_merkle_matches_repo_pairing_rule():
    leaves = [sha256_hex("one"), sha256_hex("two"), sha256_hex("three")]
    assert merkle_root(leaves) == merkle_root(leaves)
    assert merkle_root([]) == sha256_hex("")
    # Odd leaf is duplicated, same as scripts/build-merkle.py.
    duplicated = [leaves[0], leaves[1], leaves[2], leaves[2]]
    parent_one = sha256_hex(duplicated[0] + duplicated[1])
    parent_two = sha256_hex(duplicated[2] + duplicated[3])
    assert merkle_root(leaves) == sha256_hex(parent_one + parent_two)


def test_sign_envelope_is_deterministic():
    key = b"k"
    first = sign_envelope('{"a":1}', key)
    assert first == sign_envelope('{"a":1}', key)
    assert not verify_envelope(first, b"other")

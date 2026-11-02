"""Offline checks for the mesh receipt and the 9000/500/500 split. No RPC."""

from __future__ import annotations

import hashlib

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from moltbook.ledger.backend import SimulatedLedger, sign_ed25519_envelope, verify_ed25519_envelope
from moltbook.ledger.mesh_receipt import (
    GENESIS_PREV,
    MeshReceiptError,
    mesh_merkle_root,
    receipt_is_verified,
    sign_mesh_receipt,
    split_contribution,
    verify_mesh_receipt,
)
from moltbook.ledger.onchain import settlement_id_bytes32


def _verified_receipt():
    private = Ed25519PrivateKey.generate()
    worker = "0x70997970C51812dc3A010C7d01b50e0d17dc79C8"
    v1 = "0x3C44CdDdB6a900fa2b585dd299e03d12FA4293BC"
    v2 = "0x90F79bf6EB2c4f870365E785982E1f101E93b906"
    receipt = sign_mesh_receipt(
        actor="groq-test",
        kind="inference_receipt",
        payload={
            "schema": "gpumesh.execution.v1",
            "status": "verified",
            "verifier_decision": "agree",
            "work_id": "work_groq",
            "worker_id": worker,
            "verifier_ids": [v1, v2],
            "settlement_id": "settle-groq-1",
            "amount": 1000,
        },
        prev_hash=GENESIS_PREV,
        seq=1,
        ts=1700000000000,
        private_key=private,
    )
    return receipt


def test_settlement_id_bytes32_stable():
    assert settlement_id_bytes32("abc") == hashlib.sha256(b"abc").digest()


def test_split_is_exact_90_5_5():
    assert split_contribution(1000) == (900, 50, 50)
    assert split_contribution(2000) == (1800, 100, 100)
    with pytest.raises(MeshReceiptError):
        split_contribution(101)


def test_mesh_receipt_verifies_and_rejects_tamper():
    receipt = _verified_receipt()
    claim = verify_mesh_receipt(receipt)
    assert claim["worker_id"] == "0x70997970C51812dc3A010C7d01b50e0d17dc79C8"
    assert claim["verifier_ids"] == (
        "0x3C44CdDdB6a900fa2b585dd299e03d12FA4293BC,"
        "0x90F79bf6EB2c4f870365E785982E1f101E93b906"
    )
    forged = dict(receipt)
    forged["amount"] = 2000
    with pytest.raises(MeshReceiptError):
        verify_mesh_receipt(forged)
    assert receipt_is_verified(claim)


def test_execution_submitted_is_not_settled():
    private = Ed25519PrivateKey.generate()
    receipt = sign_mesh_receipt(
        actor="groq-test",
        kind="execution_submitted",
        payload={
            "schema": "gpumesh.execution.v1",
            "verifier_decision": "pending",
            "worker_id": "node-1",
            "amount": 0,
        },
        prev_hash=GENESIS_PREV,
        seq=1,
        ts=1700000000000,
        private_key=private,
    )
    claim = verify_mesh_receipt(receipt)
    assert receipt_is_verified(claim) is False


def test_merkle_root_of_one_receipt_is_the_hash():
    receipt = _verified_receipt()
    assert mesh_merkle_root([receipt["hash"]]) == receipt["hash"]
    left = "11" * 32
    right = "22" * 32
    root = mesh_merkle_root([left, right])
    assert len(root) == 64
    assert root != left


def test_ed25519_sign_and_verify_roundtrip():
    private = Ed25519PrivateKey.generate()
    raw = private.private_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PrivateFormat.Raw,
        encryption_algorithm=serialization.NoEncryption(),
    )
    public = private.public_key().public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    )
    env = sign_ed25519_envelope('{"hello":1}', private_key_raw=raw, key_id="k1")
    assert verify_ed25519_envelope(env, {"k1": public}) == "k1"
    ledger = SimulatedLedger()
    stmt = {"ed25519_key_id": "k1", "predicate": {"x": 1}, "_type": "t"}
    env2 = ledger.sign_settlement(stmt, raw)
    assert verify_ed25519_envelope(env2, {"k1": public}) == "k1"

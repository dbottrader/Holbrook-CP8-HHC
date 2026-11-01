"""Integer simulated-credit ledger: signed claims, simulated backend, Merkle anchor."""

import socket

import pytest
from sqlalchemy import UniqueConstraint

from gpumesh.db import Settlement, build_database, session_scope
from gpumesh.errors import MeshError
from gpumesh.ledger import append, verify_export, verify_session
from gpumesh.ledger_backend import OnchainLedger, get_backend
from gpumesh.merkle import anchor_chain, merkle_root
from gpumesh.work import ledger_export
from gpumesh_node.toploc_proof import build_prompt_proofs, library_ready, verify_prompt_proofs
from tests.conftest import make_settings


def test_amounts_are_integers_and_claims_are_signed(tmp_path):
    settings = make_settings(tmp_path)
    _engine, factory = build_database(settings)
    with session_scope(factory) as session:
        with pytest.raises(MeshError) as bad:
            append(session, actor="node_a", kind="note", payload={"amount": 1.5})
        assert bad.value.code == "amount_not_integer"
        append(session, actor="node_a", kind="note", payload={"credits": 4, "worker_id": "node_a", "settlement_id": "job_1:worker_award"})
        report = verify_session(session)
        assert report["ok"] is True
        exported = ledger_export(session)
    checked = verify_export(exported["entries"])
    assert checked["ok"] is True
    claim = exported["entries"][-1]
    assert claim["amount"] == 4
    assert claim["typed_data"]["domain"]["chainId"] == 0
    assert claim["typed_data"]["message"]["settlementId"] == "job_1:worker_award"
    assert len(claim["signature"]) == 128


def test_simulated_backend_is_default_and_onchain_refuses(tmp_path, monkeypatch):
    settings = make_settings(tmp_path)
    assert settings.ledger_backend == "simulated"
    assert get_backend("simulated").name == "simulated"
    _engine, factory = build_database(settings)

    def boom(*_args, **_kwargs):
        raise AssertionError("anchor tried to use the network")

    monkeypatch.setattr(socket, "socket", boom)
    with pytest.raises(MeshError) as refused:
        OnchainLedger().append(None, actor="x", kind="y", payload={"amount": 1})
    assert refused.value.code == "onchain_disabled"
    with pytest.raises(MeshError):
        OnchainLedger().anchor(None)
    with session_scope(factory) as session:
        first = anchor_chain(session, "simulated")
        second = anchor_chain(session, "simulated")
        assert first["published"] is False
        assert first["chain_called"] is False
        assert second["reused"] is True
        assert first["root"] == merkle_root(
            [row["hash"] for row in ledger_export(session)["entries"]]
        )


def test_toploc_rejects_a_proof_for_a_different_prompt():
    pytest.importorskip("toploc")
    assert library_ready()
    messages = [{"role": "user", "content": "Say hello in one sentence."}]
    proofs = build_prompt_proofs(messages, "mock-tiny")
    assert proofs
    good = verify_prompt_proofs(messages, "mock-tiny", proofs)
    assert good["ok"] is True
    bad = verify_prompt_proofs([{"role": "user", "content": "a different prompt"}], "mock-tiny", proofs)
    assert bad["ok"] is False


def test_settlement_key_is_unique_metadata():
    assert any(isinstance(item, UniqueConstraint) and item.name == "uq_settlement_idempotency" for item in Settlement.__table__.constraints)

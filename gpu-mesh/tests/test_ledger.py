import json

from sqlalchemy import select

from gpumesh.db import LedgerEntry, build_database, session_scope
from gpumesh.ledger import append, verify_export, verify_session
from gpumesh.work import ledger_export
from tests.conftest import make_settings


def test_chain_links_and_detects_tampering(tmp_path):
    settings = make_settings(tmp_path)
    _engine, factory = build_database(settings)
    with session_scope(factory) as session:
        append(session, actor="node_a", kind="note", payload={"credits": 1, "job_id": "job_1"})
        append(session, actor="node_a", kind="note", payload={"credits": 2, "job_id": "job_2"})
        report = verify_session(session)
        assert report["ok"] is True
        assert report["length"] == 3
        exported = ledger_export(session)

    assert verify_export(exported["entries"])["ok"] is True

    with session_scope(factory) as session:
        first = session.scalar(select(LedgerEntry).where(LedgerEntry.seq == 1))
        first.payload = first.payload + " "
        session.flush()
        broken = verify_session(session)
        assert broken["ok"] is False
        assert any("diverges" in error or "hash" in error for error in broken["errors"])


def test_verify_cli_round_trip(tmp_path, capsys):
    settings = make_settings(tmp_path)
    _engine, factory = build_database(settings)
    with session_scope(factory) as session:
        exported = ledger_export(session)
    path = tmp_path / "ledger.json"
    path.write_text(json.dumps(exported), encoding="utf-8")
    from gpumesh.verify_cli import main

    assert main([str(path)]) == 0
    assert "true" in capsys.readouterr().out

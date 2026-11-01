"""Console ledger math and the public page's read-only boundary."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
CONSOLE = ROOT / "site" / "console"
SITE = ROOT / "site"


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_node_ledger_math() -> None:
    node = shutil.which("node")
    if node is None:
        pytest.skip("node is not installed")
    subprocess.run(
        [node, "--test", "site/console/ledger.test.mjs"],
        cwd=ROOT,
        check=True,
    )


def test_console_is_read_only_and_names_the_public_views() -> None:
    html = read(CONSOLE / "index.html")
    script = read(CONSOLE / "console.js")
    ledger = read(CONSOLE / "ledger.js")
    combined = html + script + ledger
    assert "service_role" not in combined
    assert "eyJ" not in script
    assert "eyJ" not in ledger
    for name in (
        "cp8_moltbook_public_bounties",
        "cp8_moltbook_public_bounty_attempts",
        "cp8_moltbook_public_bounty_verdicts",
        "cp8_moltbook_public_bounty_events",
        "cp8_moltbook_public_transfers",
        "cp8_moltbook_settlement_receipt_ok",
        "cp8_moltbook_list_rooms",
    ):
        assert name in combined
    assert "No live bounties yet." in html
    assert "The GPU network is not live." in html
    assert "not for sale" in html.lower() or "Nothing here is for sale." in html
    assert "innerHTML" not in script
    assert 'jwtRole(cfg.publishableKey) !== "anon"' in script
    for page in (SITE / "index.html", SITE / "feed.html", SITE / "proof.html"):
        text = read(page)
        assert 'href="console/index.html"' in text


def test_proof_page_labels_the_replay_as_demo() -> None:
    html = read(SITE / "proof.html")
    script = read(SITE / "proof.js")
    assert "Demo data." in html
    assert "powc-launch-v1" in html
    assert "This demo artifact has no receipts." in script
    assert "This demo artifact has no settlement cases." in script
    assert "links to the previous demo receipt" in script


def test_receipt_migration_is_a_proposal_not_a_grant_of_secrets() -> None:
    sql = read(ROOT / "supabase" / "migrations" / "20261024230000_moltbook_public_receipt_chain.sql")
    assert "NOT APPLIED" in sql
    assert "cp8_moltbook_public_receipts" in sql
    assert "statement_json" in sql
    assert "envelope_json" in sql
    assert "prev_hash" in sql
    assert "entry_hash" in sql
    lowered = sql.lower()
    assert "insert into" not in lowered
    assert "service_role key" not in lowered

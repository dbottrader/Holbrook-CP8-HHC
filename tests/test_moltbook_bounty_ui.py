"""The human page gains bounty controls without dropping the PR #36 labels."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP = (ROOT / "moltbook/human/app.js").read_text()
HTML = (ROOT / "moltbook/human/index.html").read_text()
MIGRATION = (ROOT / "supabase/migrations/20261024160000_moltbook_bounty_escrow.sql").read_text().lower()
README = (ROOT / "README.md").read_text()


def test_page_funds_browses_and_promotes_without_removing_human_posting():
    for needle in (
        "cp8_moltbook_human_post",
        "cp8_moltbook_human_open_bounty",
        "cp8_moltbook_bounty_file_verdict",
        "cp8_moltbook_bounty_promote",
        "cp8_moltbook_public_bounties",
        "cp8_moltbook_my_sim_balance",
        "author_kind",
        "Unlabeled",
    ):
        assert needle in APP
    for control in ("bounty-form", "fund-bounty", "bounty-list", "promote-bounty"):
        assert control in HTML
    assert "Human" in APP
    assert "Agent" in APP
    assert "90" in HTML
    assert "minor" in HTML.lower()


def test_migration_does_not_replace_agent_functions_and_locks_the_chain():
    assert "create or replace function public.cp8_moltbook_agent_post" not in MIGRATION
    assert "create or replace function public.cp8_moltbook_worker_" not in MIGRATION
    assert "create or replace function public.cp8_moltbook_guest_connect" not in MIGRATION
    assert "simulated_only_no_monetary_authority" in MIGRATION
    assert "onchain_backend_locked" in MIGRATION
    assert "custom_access_token_hook" in MIGRATION
    assert "actor_type" in MIGRATION
    for state in ("draft", "open", "claimed", "submitted", "verifying", "verified", "settled", "cancelled", "expired", "disputed", "rejected"):
        assert state in MIGRATION


def test_readme_cites_template_sources_and_licenses():
    for name in ("TigerBeetle", "Apache-2.0", "Algora", "AGPL-3.0", "in-toto", "DSSE", "Supabase"):
        assert name in README

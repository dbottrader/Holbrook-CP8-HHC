"""The human page must call Supabase Auth and render server-side actor labels."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP = (ROOT / "moltbook/human/app.js").read_text()
RENDER = (ROOT / "moltbook/human/render.js").read_text()
HTML = (ROOT / "moltbook/human/index.html").read_text()
MIGRATION = (ROOT / "supabase/migrations/20261024143000_moltbook_human_actors.sql").read_text().lower()


def test_page_has_human_auth_and_posting_controls():
    assert "signInWithOtp" in APP
    assert "signInWithPassword" in APP
    assert "signUp" in APP
    assert 'oauth("github")' in APP or 'oauth("github")' in APP
    assert "signInWithOAuth" in APP
    assert "github" in APP
    assert "google" in APP
    assert "cp8_moltbook_ensure_human_profile" in APP
    assert "cp8_moltbook_human_post" in APP
    assert "cp8_moltbook_public_posts" in APP
    assert "cp8_moltbook_identity_directory" in APP
    assert "cp8_moltbook_rooms" in APP
    for control in ("magic-form", "password-form", "oauth-github", "oauth-google", "composer"):
        assert control in HTML


def test_labels_come_from_server_actor_kind():
    assert "author_kind" in APP
    assert "actor_kind" in APP
    assert "Unlabeled" in RENDER
    assert "textContent" in RENDER
    assert "innerHTML" not in APP
    assert "innerHTML" not in RENDER
    assert 'data.author_kind !== "human"' in APP
    assert 'data.promotion !== "HOLD"' in APP


def test_migration_does_not_replace_agent_or_worker_functions():
    assert "create or replace function public.cp8_moltbook_agent_post" not in MIGRATION
    assert "create or replace function public.cp8_moltbook_worker_" not in MIGRATION
    assert "create or replace function public.cp8_moltbook_guest_connect" not in MIGRATION
    assert "revoke all on function" in MIGRATION
    assert "service_role" in MIGRATION
    assert "author_kind" in MIGRATION
    assert "auth.users" in MIGRATION

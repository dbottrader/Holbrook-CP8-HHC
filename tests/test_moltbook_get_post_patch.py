"""The live GET /posts patch must apply to the known handler and leave 0.3.2 in place."""

import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PATCH = ROOT / "provenance/moltbook/deploy/2026-10-24-get-post-0.3.3/moltbook-api-get-post.patch"
README = ROOT / "provenance/moltbook/deploy/2026-10-24-get-post-0.3.3/README.md"
SNAPSHOT = ROOT / "provenance/moltbook/runtime-2026-08-20/moltbook-api/index.ts"
BRIEF = ROOT / "docs/ECOSYSTEM_BRIEF.md"


def test_patch_rewrites_only_the_get_post_handler(tmp_path):
    target = tmp_path / "index.ts"
    target.write_text(SNAPSHOT.read_text())
    subprocess.run(
        ["patch", "-p1", "-d", str(tmp_path), "-i", str(PATCH)],
        check=True,
        capture_output=True,
        text=True,
    )
    patched = target.read_text()
    original = SNAPSHOT.read_text()
    assert ".select('slug,name')" in original
    assert ".select('slug,name')" not in patched
    assert ".select('slug,title')" in patched
    assert "cp8_moltbook_human_profiles" in patched
    get_line = next(line for line in patched.splitlines() if "p[0]==='posts'&&p[1]&&p.length===2" in line)
    assert ".select('*')" not in get_line
    assert "evidence_refs" not in get_line
    assert "auth_user_id" not in get_line
    assert "signature" not in get_line
    assert ".insert(" not in get_line
    assert ".update(" not in get_line
    assert ".delete(" not in get_line
    assert "post_id,room_id,author_agent_id,author_human_id,author_kind" in get_line
    assert "actor_kind:post.author_kind==='human'?'human':'agent'" in patched
    assert "version:'0.3.2'" in patched
    assert "version:'0.3.3'" not in patched
    assert "agents/identities" not in patched


def test_deploy_readme_does_not_replace_the_live_function():
    text = README.read_text()
    assert "ecenvlwyenpakrxfuqup" in text
    assert "supabase functions download moltbook-api --project-ref ecenvlwyenpakrxfuqup" in text
    assert "supabase functions deploy moltbook-api --project-ref ecenvlwyenpakrxfuqup" in text
    assert "Do not deploy the 0.3.2 snapshot" in text
    assert "223b70c7-95ac-401d-99e7-419430c4f1e5" in text


def test_ecosystem_brief_is_checked_in():
    text = BRIEF.read_text()
    assert text.startswith("# ASIN-HHC Ecosystem — Shared Brief")
    assert "https://github.com/dbottrader/Holbrook-CP8-HHC/pull/36" in text
    assert "IN PROGRESS, stacked on PR #36" in text
    assert "column cp8_moltbook_rooms.name" in text or "cp8_moltbook_rooms.name" in text

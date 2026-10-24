"""Auth and RLS for human posts beside the existing agent RPCs.

The fixture is a local stand-in for the 2026-08-20 catalog. The migration under
test is the file Dennis applies to project ecenvlwyenpakrxfuqup. CI sets
MOLTBOOK_TEST_DSN to a disposable Postgres. Without that variable this module
is skipped so the package job can collect it; the moltbook-human-rls job always
sets the variable.
"""

import hashlib
import json
import os
import subprocess
import uuid
from pathlib import Path
from urllib.parse import urlparse, urlunparse

import pytest

DSN = os.environ.get("MOLTBOOK_TEST_DSN")
if not DSN:
    pytest.skip(
        "MOLTBOOK_TEST_DSN is required for Moltbook RLS tests",
        allow_module_level=True,
    )

import psycopg
from psycopg import sql
from psycopg.rows import dict_row

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "supabase/tests/fixtures/00_pre_human_baseline.sql"
MIGRATION = ROOT / "supabase/migrations/20261024143000_moltbook_human_actors.sql"
TOKEN = "hc_0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"
AGENT_ID = uuid.UUID("e393fc58-b1a5-4e50-a2aa-4d661f336e4c")
WORK_ID = uuid.UUID("798db35c-ba7b-455e-97a9-f70a95a846b4")
ROOM_ID = uuid.UUID("11111111-1111-4111-8111-111111111111")
AGENT_POST = "public.cp8_moltbook_agent_post(text,text,text,text,uuid,text[],text,text,text)"


def _database_url(name):
    parts = urlparse(DSN)
    return urlunparse(parts._replace(path=f"/{name}"))


@pytest.fixture(scope="module")
def database_url():
    admin = psycopg.connect(DSN, autocommit=True)
    admin.execute("DROP DATABASE IF EXISTS moltbook_human_rls WITH (FORCE)")
    admin.execute("CREATE DATABASE moltbook_human_rls")
    admin.close()
    url = _database_url("moltbook_human_rls")
    for path in (FIXTURE, MIGRATION):
        subprocess.run(
            ["psql", url, "-v", "ON_ERROR_STOP=1", "-f", str(path)],
            check=True,
            capture_output=True,
            text=True,
        )
    yield url
    admin = psycopg.connect(DSN, autocommit=True)
    admin.execute("DROP DATABASE IF EXISTS moltbook_human_rls WITH (FORCE)")
    admin.close()


@pytest.fixture
def conn(database_url):
    with psycopg.connect(database_url, row_factory=dict_row) as connection:
        yield connection
        connection.rollback()


def set_jwt(conn, uid, role):
    sub = "" if uid is None else str(uid)
    conn.execute("select set_config('request.jwt.claim.sub', %s, true)", (sub,))
    conn.execute("select set_config('request.jwt.claim.role', %s, true)", (role,))
    conn.execute(
        "select set_config('request.jwt.claims', %s, true)",
        (json.dumps({"sub": sub, "role": role}),),
    )


def become(conn, uid, role):
    if role not in {"anon", "authenticated", "service_role"}:
        raise AssertionError(role)
    set_jwt(conn, uid, role)
    conn.execute(sql.SQL("set local role {}").format(sql.Identifier(role)))


def clear_jwt(conn):
    set_jwt(conn, None, "")
    conn.execute("reset role")


def create_human(conn, email, metadata=None):
    uid = uuid.uuid4()
    clear_jwt(conn)
    conn.execute(
        "insert into auth.users (id, email, raw_user_meta_data) values (%s, %s, %s::jsonb)",
        (uid, email, json.dumps(metadata or {})),
    )
    return uid


def sha256(text):
    return hashlib.sha256(text.encode()).hexdigest()


def test_agent_functions_are_the_fixture_bodies(conn):
    row = conn.execute(
        "select pg_get_functiondef(%s::regprocedure) as src",
        (AGENT_POST,),
    ).fetchone()
    assert "fixture-agent-post-v1" in row["src"]
    claim = conn.execute(
        "select pg_get_functiondef('public.cp8_moltbook_worker_claim(text,uuid,integer)'::regprocedure) as src"
    ).fetchone()
    complete = conn.execute(
        "select pg_get_functiondef('public.cp8_moltbook_worker_complete(text,uuid,uuid,text)'::regprocedure) as src"
    ).fetchone()
    assert "fixture-worker-claim-v1" in claim["src"]
    assert "fixture-worker-complete-v1" in complete["src"]


def test_service_role_agent_post_claim_and_complete(conn):
    content = "agent says hello"
    become(conn, None, "service_role")
    posted = conn.execute(
        """
        select * from public.cp8_moltbook_agent_post(
          %s, 'cp8-ops', %s, 'post', null, null, null, 'OBSERVED', null
        )
        """,
        (TOKEN, content),
    ).fetchone()
    assert posted["promotion"] == "HOLD"
    assert posted["content_hash"] == sha256(content)
    claimed = conn.execute(
        "select * from public.cp8_moltbook_worker_claim(%s, %s, 15)",
        (TOKEN, WORK_ID),
    ).fetchone()
    assert claimed["status"] == "claimed"
    assert claimed["claimed_by"] == "ace"
    done = conn.execute(
        "select * from public.cp8_moltbook_worker_complete(%s, %s, %s, %s)",
        (TOKEN, WORK_ID, posted["post_id"], posted["content_hash"]),
    ).fetchone()
    assert done["status"] == "completed"
    assert done["result_hash"] == posted["content_hash"]
    clear_jwt(conn)
    stored = conn.execute(
        """
        select author_kind, author_agent_id, author_human_id, promotion
        from public.cp8_moltbook_posts where post_id = %s
        """,
        (posted["post_id"],),
    ).fetchone()
    assert stored == {
        "author_kind": "agent",
        "author_agent_id": AGENT_ID,
        "author_human_id": None,
        "promotion": "HOLD",
    }
    become(conn, None, "anon")
    labeled = conn.execute(
        """
        select author_kind, author_handle, has_bound_receipt, promotion
        from public.cp8_moltbook_public_posts where post_id = %s
        """,
        (posted["post_id"],),
    ).fetchone()
    assert labeled["author_kind"] == "agent"
    assert labeled["author_handle"] == "ace"
    assert labeled["has_bound_receipt"] is True
    assert labeled["promotion"] == "HOLD"


def test_authenticated_human_cannot_call_agent_rpcs(conn):
    uid = create_human(conn, "ada@example.com", {"display_name": "Ada"})
    become(conn, uid, "authenticated")
    for statement in (
        "select * from public.cp8_moltbook_agent_post(%s, 'cp8-ops', 'x', 'post', null, null, null, 'OBSERVED', null)",
        "select * from public.cp8_moltbook_worker_claim(%s, %s, 15)",
        "select * from public.cp8_moltbook_worker_complete(%s, %s, %s, %s)",
    ):
        conn.execute("savepoint denied")
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            if "complete" in statement:
                conn.execute(statement, (TOKEN, WORK_ID, uuid.uuid4(), "ab" * 32))
            elif "claim" in statement:
                conn.execute(statement, (TOKEN, WORK_ID))
            else:
                conn.execute(statement, (TOKEN,))
        conn.execute("rollback to savepoint denied")


def test_human_posts_and_replies_are_labeled_hold(conn):
    uid = create_human(conn, "ada@example.com", {"display_name": "Ada"})
    profile = conn.execute(
        "select human_id, handle, actor_kind, auth_user_id from public.cp8_moltbook_human_profiles where auth_user_id = %s",
        (uid,),
    ).fetchone()
    assert profile["actor_kind"] == "human"
    assert profile["handle"] == "ada"
    assert profile["auth_user_id"] == uid

    become(conn, uid, "authenticated")
    root_body = "hello from a human"
    root = conn.execute(
        "select public.cp8_moltbook_human_post('cp8-ops', %s, 'post', null) as post",
        (root_body,),
    ).fetchone()["post"]
    assert root["author_kind"] == "human"
    assert root["promotion"] == "HOLD"
    assert root["content_hash"] == sha256(root_body)
    reply_body = "a human reply"
    reply = conn.execute(
        "select public.cp8_moltbook_human_post('cp8-ops', %s, 'reply', %s) as post",
        (reply_body, root["post_id"]),
    ).fetchone()["post"]
    assert reply["author_kind"] == "human"
    assert reply["parent_post_id"] == str(root["post_id"]) or reply["parent_post_id"] == root["post_id"]

    conn.execute("savepoint rejected")
    with pytest.raises(psycopg.Error, match="content length rejected"):
        conn.execute("select public.cp8_moltbook_human_post('cp8-ops', '   ', 'post', null)")
    conn.execute("rollback to savepoint rejected")
    conn.execute("savepoint kind")
    with pytest.raises(psycopg.Error, match="kind rejected"):
        conn.execute(
            "select public.cp8_moltbook_human_post('cp8-ops', 'nope', 'challenge', null)"
        )
    conn.execute("rollback to savepoint kind")

    clear_jwt(conn)
    conn.execute(
        """
        insert into public.cp8_moltbook_rooms (slug, title, description, status)
        values ('other-room', 'Other', 'Other room', 'active')
        """
    )
    become(conn, uid, "authenticated")
    conn.execute("savepoint room")
    with pytest.raises(psycopg.Error, match="room mismatch"):
        conn.execute(
            "select public.cp8_moltbook_human_post('other-room', 'cross post', 'reply', %s)",
            (root["post_id"],),
        )
    conn.execute("rollback to savepoint room")

    clear_jwt(conn)
    stored = conn.execute(
        """
        select kind, promotion, author_kind, parent_hash, thread_root_post_id, content_hash,
               auth_mode, author_agent_id
        from public.cp8_moltbook_posts where post_id = %s
        """,
        (reply["post_id"],),
    ).fetchone()
    assert stored["kind"] == "reply"
    assert stored["promotion"] == "HOLD"
    assert stored["author_kind"] == "human"
    assert stored["author_agent_id"] is None
    assert stored["auth_mode"] == "SUPABASE_AUTH"
    assert stored["content_hash"] == sha256(reply_body)
    assert stored["parent_hash"] == root["content_hash"]
    assert str(stored["thread_root_post_id"]) == str(root["post_id"])
    receipt = conn.execute(
        """
        select actor_kind, actor_agent_id, cp8_receipt_id
        from public.cp8_moltbook_receipts where post_id = %s
        """,
        (reply["post_id"],),
    ).fetchone()
    assert receipt == {
        "actor_kind": "human",
        "actor_agent_id": None,
        "cp8_receipt_id": None,
    }
    become(conn, None, "anon")
    labeled = conn.execute(
        """
        select author_kind, author_handle, promotion, has_bound_receipt
        from public.cp8_moltbook_public_posts where post_id = %s
        """,
        (root["post_id"],),
    ).fetchone()
    assert labeled == {
        "author_kind": "human",
        "author_handle": "ada",
        "promotion": "HOLD",
        "has_bound_receipt": False,
    }


def test_human_direct_insert_is_self_only_and_hold(conn):
    ada = create_human(conn, "ada@example.com", {"display_name": "Ada"})
    bea = create_human(conn, "bea@example.com", {"display_name": "Bea"})
    ids = {
        row["auth_user_id"]: row["human_id"]
        for row in conn.execute(
            "select auth_user_id, human_id from public.cp8_moltbook_human_profiles"
        )
    }
    become(conn, ada, "authenticated")
    conn.execute("savepoint other")
    with pytest.raises(psycopg.Error, match="human post identity rejected|row-level security"):
        other = uuid.uuid4()
        conn.execute(
            """
            insert into public.cp8_moltbook_posts (
              post_id, room_id, author_human_id, author_kind, thread_root_post_id,
              kind, status, promotion, content, evidence_refs, nonce, request_hash,
              content_hash, auth_mode
            ) values (
              %s, %s, %s, 'human', %s,
              'post', 'OBSERVED', 'HOLD', 'forged', array['x'], 'n', 'pending', 'pending',
              'SUPABASE_AUTH'
            )
            """,
            (other, ROOM_ID, ids[bea], other),
        )
    conn.execute("rollback to savepoint other")
    conn.execute("savepoint agent")
    with pytest.raises(psycopg.Error, match="authenticated humans cannot author agent posts|row-level security"):
        conn.execute(
            """
            insert into public.cp8_moltbook_posts (
              post_id, room_id, author_agent_id, author_kind, thread_root_post_id,
              kind, status, promotion, content, evidence_refs, nonce, request_hash,
              content_hash, auth_mode
            ) values (
              gen_random_uuid(), %s, %s, 'agent', gen_random_uuid(),
              'post', 'OBSERVED', 'HOLD', 'nope', array['x'], 'n', 'h', 'h', 'CAPABILITY_TOKEN'
            )
            """,
            (ROOM_ID, AGENT_ID),
        )
    conn.execute("rollback to savepoint agent")
    own = uuid.uuid4()
    conn.execute(
        """
        insert into public.cp8_moltbook_posts (
          post_id, room_id, author_human_id, author_kind, thread_root_post_id,
          kind, status, promotion, content, evidence_refs, nonce, request_hash,
          content_hash, auth_mode
        ) values (
          %s, %s, %s, 'human', %s,
          'post', 'OBSERVED', 'HOLD', 'direct human post', array['surface:human-ui'],
          'n', 'pending', 'pending', 'SUPABASE_AUTH'
        )
        """,
        (own, ROOM_ID, ids[ada], own),
    )
    clear_jwt(conn)
    stored = conn.execute(
        "select author_kind, promotion, content_hash, author_human_id from public.cp8_moltbook_posts where post_id = %s",
        (own,),
    ).fetchone()
    assert stored["author_kind"] == "human"
    assert stored["promotion"] == "HOLD"
    assert stored["author_human_id"] == ids[ada]
    assert stored["content_hash"] == sha256("direct human post")
    with pytest.raises(psycopg.Error, match="human posts remain HOLD"):
        conn.execute(
            "update public.cp8_moltbook_posts set promotion = 'PROMOTED' where post_id = %s",
            (own,),
        )


def test_agent_rows_can_still_be_updated_by_the_owner_and_not_relabeled(conn):
    become(conn, None, "service_role")
    posted = conn.execute(
        """
        select * from public.cp8_moltbook_agent_post(
          %s, 'cp8-ops', 'agent body', 'post', null, null, null, 'OBSERVED', null
        )
        """,
        (TOKEN,),
    ).fetchone()
    clear_jwt(conn)
    conn.execute(
        "update public.cp8_moltbook_posts set promotion = 'REVIEW' where post_id = %s",
        (posted["post_id"],),
    )
    reviewed = conn.execute(
        "select promotion, author_kind from public.cp8_moltbook_posts where post_id = %s",
        (posted["post_id"],),
    ).fetchone()
    assert reviewed == {"promotion": "REVIEW", "author_kind": "agent"}
    with pytest.raises(psycopg.Error, match="author identity is immutable"):
        conn.execute(
            "update public.cp8_moltbook_posts set author_kind = 'human' where post_id = %s",
            (posted["post_id"],),
        )


def test_reserved_handles_and_profile_credentials(conn):
    taken = create_human(conn, "ace@example.com", {"display_name": "Not Ace", "handle": "ace"})
    row = conn.execute(
        "select handle, actor_kind from public.cp8_moltbook_human_profiles where auth_user_id = %s",
        (taken,),
    ).fetchone()
    assert row["actor_kind"] == "human"
    assert row["handle"] != "ace"
    assert row["handle"].startswith("ace-")
    owner = conn.execute(
        "select actor_kind, agent_id from public.cp8_moltbook_identity_handles where handle = 'ace'"
    ).fetchone()
    assert owner == {"actor_kind": "agent", "agent_id": AGENT_ID}


def test_ensure_profile_rejects_reserved_handle_and_agent_cannot_take_human_handle(conn):
    fresh = create_human(conn, "fresh@example.com")
    clear_jwt(conn)
    conn.execute(
        "delete from public.cp8_moltbook_human_profiles where auth_user_id = %s",
        (fresh,),
    )
    become(conn, fresh, "authenticated")
    conn.execute("savepoint reserved")
    with pytest.raises(psycopg.Error, match="handle reserved"):
        conn.execute("select public.cp8_moltbook_ensure_human_profile('Fresh', 'ace')")
    conn.execute("rollback to savepoint reserved")
    created = conn.execute(
        "select public.cp8_moltbook_ensure_human_profile('Fresh Person', null) as profile"
    ).fetchone()["profile"]
    assert created["actor_kind"] == "human"
    assert created["auth_user_id"] == str(fresh) or created["auth_user_id"] == fresh
    assert created["handle"] == "fresh"
    clear_jwt(conn)
    with pytest.raises(psycopg.errors.UniqueViolation):
        conn.execute(
            """
            insert into public.cp8_agents (agent_id, handle, display_name)
            values (gen_random_uuid(), 'fresh', 'Fresh Agent')
            """
        )


def test_service_role_jwt_cannot_mint_a_human_profile(conn):
    carol = create_human(conn, "carol@example.com")
    clear_jwt(conn)
    conn.execute(
        "delete from public.cp8_moltbook_human_profiles where auth_user_id = %s",
        (carol,),
    )
    set_jwt(conn, None, "service_role")
    with pytest.raises(psycopg.Error, match="cannot create a human profile"):
        conn.execute(
            """
            insert into public.cp8_moltbook_human_profiles (auth_user_id, handle, display_name)
            values (%s, 'carol', 'Carol')
            """,
            (carol,),
        )


def test_anon_can_read_labels_but_not_auth_ids_or_write(conn):
    create_human(conn, "ada@example.com", {"display_name": "Ada"})
    become(conn, None, "anon")
    directory = conn.execute(
        """
        select handle, actor_kind from public.cp8_moltbook_identity_directory
        where handle in ('ace', 'ada') order by handle
        """
    ).fetchall()
    assert directory == [
        {"handle": "ace", "actor_kind": "agent"},
        {"handle": "ada", "actor_kind": "human"},
    ]
    rooms = conn.execute("select slug from public.cp8_moltbook_list_rooms()").fetchall()
    assert any(row["slug"] == "cp8-ops" for row in rooms)
    conn.execute("savepoint secret")
    with pytest.raises(psycopg.errors.InsufficientPrivilege):
        conn.execute("select auth_user_id from public.cp8_moltbook_human_profiles")
    conn.execute("rollback to savepoint secret")
    conn.execute("savepoint meta")
    with pytest.raises(psycopg.errors.InsufficientPrivilege):
        conn.execute("select metadata from public.cp8_agents")
    conn.execute("rollback to savepoint meta")
    with pytest.raises(psycopg.errors.InsufficientPrivilege):
        conn.execute(
            """
            insert into public.cp8_moltbook_posts (
              post_id, room_id, author_kind, thread_root_post_id, kind, status, promotion,
              content, evidence_refs, nonce, request_hash, content_hash, auth_mode
            ) values (
              gen_random_uuid(), %s, 'human', gen_random_uuid(), 'post', 'OBSERVED', 'HOLD',
              'x', array['x'], 'n', 'h', 'h', 'SUPABASE_AUTH'
            )
            """,
            (ROOM_ID,),
        )


def test_rls_blocks_human_writes_to_agents_and_work_items(conn):
    ada = create_human(conn, "ada@example.com")
    clear_jwt(conn)
    conn.execute("grant insert on public.cp8_agents to authenticated")
    conn.execute("grant select, update on public.cp8_moltbook_work_items to authenticated")
    become(conn, ada, "authenticated")
    conn.execute("savepoint agent")
    with pytest.raises(psycopg.Error, match="row-level security"):
        conn.execute(
            """
            insert into public.cp8_agents (agent_id, handle, display_name)
            values (gen_random_uuid(), 'intruder', 'Intruder')
            """
        )
    conn.execute("rollback to savepoint agent")
    updated = conn.execute(
        """
        update public.cp8_moltbook_work_items
        set title = 'hijack'
        where work_id = %s
        returning work_id
        """,
        (WORK_ID,),
    ).fetchall()
    assert updated == []
    clear_jwt(conn)
    title = conn.execute(
        "select title from public.cp8_moltbook_work_items where work_id = %s",
        (WORK_ID,),
    ).fetchone()["title"]
    assert title == "Fixture task"


def test_policies_and_invoker_views_exist(conn):
    names = {
        row["polname"]
        for row in conn.execute(
            """
            select pol.polname
            from pg_policy pol
            join pg_class cls on cls.oid = pol.polrelid
            join pg_namespace nsp on nsp.oid = cls.relnamespace
            where nsp.nspname = 'public'
            """
        )
    }
    assert {
        "cp8_moltbook_posts_public_read",
        "cp8_moltbook_posts_human_insert",
        "cp8_moltbook_profiles_self_insert",
        "cp8_moltbook_agents_public_read",
    } <= names
    options = conn.execute(
        """
        select reloptions from pg_class
        where relname = 'cp8_moltbook_public_posts'
        """
    ).fetchone()["reloptions"]
    assert "security_invoker=true" in options

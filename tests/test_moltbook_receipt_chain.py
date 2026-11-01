"""Finish-line checks for the public receipt-chain projection.

Applies the pre-human fixture and the human, bounty, and advisor migrations
from the bounty escrow branch, then
supabase/migrations/20261024230000_moltbook_public_receipt_chain.sql.
Nothing here connects to project ecenvlwyenpakrxfuqup.

Skipped unless MOLTBOOK_TEST_DSN points at a disposable Postgres.
"""

import json
import os
import subprocess
import uuid
from pathlib import Path
from urllib.parse import urlparse, urlunparse

import pytest

DSN = os.environ.get("MOLTBOOK_TEST_DSN")
if not DSN:
    pytest.skip("MOLTBOOK_TEST_DSN is required for the receipt-chain test", allow_module_level=True)

import psycopg
from psycopg import sql
from psycopg.rows import dict_row

ROOT = Path(__file__).resolve().parents[1]
FILES = (
    ROOT / "supabase/tests/fixtures/00_pre_human_baseline.sql",
    ROOT / "supabase/migrations/20261024143000_moltbook_human_actors.sql",
    ROOT / "supabase/migrations/20261024160000_moltbook_bounty_escrow.sql",
    ROOT / "supabase/migrations/20261024180000_moltbook_advisor_hardening.sql",
    ROOT / "supabase/migrations/20261024230000_moltbook_public_receipt_chain.sql",
)
TRANSFER_COLUMNS = (
    "transfer_id",
    "bounty_id",
    "kind",
    "pending_transfer_id",
    "debit_account",
    "credit_account",
    "amount_minor",
    "code",
    "created_at",
    "prev_hash",
    "entry_hash",
)
RECEIPT_COLUMNS = (
    "receipt_hash",
    "prev_receipt_hash",
    "kind",
    "bounty_id",
    "settlement_id",
    "signature_scheme",
    "backend",
    "created_at",
)


def _database_url(name):
    parts = urlparse(DSN)
    if parts.netloc:
        return urlunparse(parts._replace(path=f"/{name}"))
    return f"{parts.scheme}:///{name}"


@pytest.fixture(scope="module")
def database_url():
    admin = psycopg.connect(DSN, autocommit=True)
    # Roles are cluster-wide. A Supabase project already has them. A bare
    # Postgres does not, and the fixture grants to them before its own
    # create-role block.
    admin.execute(
        """
        do $$
        begin
          if not exists (select 1 from pg_roles where rolname = 'anon') then
            create role anon nologin;
          end if;
          if not exists (select 1 from pg_roles where rolname = 'authenticated') then
            create role authenticated nologin;
          end if;
          if not exists (select 1 from pg_roles where rolname = 'service_role') then
            create role service_role nologin bypassrls;
          end if;
        end $$;
        """
    )
    admin.execute("DROP DATABASE IF EXISTS moltbook_receipt_chain WITH (FORCE)")
    admin.execute("CREATE DATABASE moltbook_receipt_chain")
    admin.close()
    url = _database_url("moltbook_receipt_chain")
    for path in FILES:
        applied = subprocess.run(
            ["psql", url, "-v", "ON_ERROR_STOP=1", "-q", "-f", str(path)],
            check=False,
            capture_output=True,
            text=True,
        )
        if applied.returncode != 0:
            raise RuntimeError(f"{path.name}\n{applied.stderr or applied.stdout}")
    yield url
    admin = psycopg.connect(DSN, autocommit=True)
    admin.execute("DROP DATABASE IF EXISTS moltbook_receipt_chain WITH (FORCE)")
    admin.close()


@pytest.fixture
def conn(database_url):
    with psycopg.connect(database_url, row_factory=dict_row) as connection:
        yield connection
        connection.rollback()


def columns(conn, schema, view):
    rows = conn.execute(
        """
        select a.attname
        from pg_attribute a
        join pg_class c on c.oid = a.attrelid
        join pg_namespace n on n.oid = c.relnamespace
        where n.nspname = %s and c.relname = %s
          and a.attnum > 0 and not a.attisdropped
        order by a.attnum
        """,
        (schema, view),
    ).fetchall()
    return tuple(row["attname"] for row in rows)


def reset(conn):
    conn.execute("reset role")
    for key in ("request.jwt.claim.sub", "request.jwt.claim.role", "request.jwt.claims"):
        conn.execute("select set_config(%s, '', true)", (key,))


def set_role(conn, role, claims):
    conn.execute("select set_config('request.jwt.claim.sub', %s, true)", (claims.get("sub", ""),))
    conn.execute("select set_config('request.jwt.claim.role', %s, true)", (role,))
    conn.execute("select set_config('request.jwt.claims', %s, true)", (json.dumps(claims),))
    conn.execute(sql.SQL("set local role {}").format(sql.Identifier(role)))


def as_human(conn, uid):
    reset(conn)
    event = {
        "user_id": str(uid),
        "claims": {
            "sub": str(uid),
            "role": "authenticated",
            "app_metadata": {"actor_type": "agent"},
        },
    }
    hooked = conn.execute(
        "select public.custom_access_token_hook(%s::jsonb) as event",
        (json.dumps(event),),
    ).fetchone()["event"]
    assert hooked["claims"]["app_metadata"]["actor_type"] == "human"
    set_role(conn, "authenticated", hooked["claims"])


def as_anon(conn):
    reset(conn)
    set_role(conn, "anon", {"role": "anon"})


def test_hash_columns_are_appended_and_bodies_stay_off_the_public_view(conn):
    assert columns(conn, "public", "cp8_moltbook_public_transfers") == TRANSFER_COLUMNS
    assert columns(conn, "cp8_moltbook_internal", "cp8_moltbook_public_transfers") == TRANSFER_COLUMNS
    assert columns(conn, "public", "cp8_moltbook_public_receipts") == RECEIPT_COLUMNS
    assert "statement_json" not in RECEIPT_COLUMNS
    assert "envelope_json" not in RECEIPT_COLUMNS
    grants = conn.execute(
        """
        select grantee
        from information_schema.role_table_grants
        where table_schema = 'public'
          and table_name = 'cp8_moltbook_receipt_chain'
          and grantee = 'anon'
        """
    ).fetchall()
    assert grants == []


def test_anon_reads_hash_links_and_not_the_statement_or_a_stipend(conn):
    uid = uuid.uuid4()
    reset(conn)
    conn.execute(
        "insert into auth.users (id, email, raw_user_meta_data) values (%s, %s, '{}'::jsonb)",
        (uid, "receipt-chain@example.com"),
    )
    as_human(conn, uid)
    opened = conn.execute(
        """
        select public.cp8_moltbook_human_open_bounty(
          'cp8-ops', 'Hash link', 'Describe the verifiable result.', 3000
        ) as j
        """
    ).fetchone()["j"]
    bounty_id = opened["bounty_id"]
    reset(conn)
    stored = conn.execute(
        """
        select public.cp8_moltbook_receipt_store(
          %s, 'promotion', %s, null, null
        ) as receipt_hash
        """,
        (json.dumps({"predicate": {"prevReceiptHash": ""}}), bounty_id),
    ).fetchone()["receipt_hash"]

    as_anon(conn)
    receipts = conn.execute(
        """
        select receipt_hash, prev_receipt_hash, kind, bounty_id::text as bounty_id
        from public.cp8_moltbook_public_receipts
        """
    ).fetchall()
    assert receipts == [{
        "receipt_hash": stored,
        "prev_receipt_hash": "",
        "kind": "promotion",
        "bounty_id": bounty_id,
    }]
    conn.execute("savepoint hidden")
    with pytest.raises(psycopg.errors.InsufficientPrivilege):
        conn.execute("select statement_json from public.cp8_moltbook_receipt_chain")
    conn.execute("rollback to savepoint hidden")
    conn.execute("savepoint hidden")
    with pytest.raises(psycopg.errors.UndefinedColumn):
        conn.execute("select statement_json from public.cp8_moltbook_public_receipts")
    conn.execute("rollback to savepoint hidden")

    transfers = conn.execute(
        """
        select kind, code, prev_hash, entry_hash
        from public.cp8_moltbook_public_transfers
        order by created_at
        """
    ).fetchall()
    assert len(transfers) == 1
    assert transfers[0]["kind"] == "pending"
    assert transfers[0]["code"] == "bounty_hold"
    assert len(transfers[0]["prev_hash"]) == 64
    assert len(transfers[0]["entry_hash"]) == 64
    hidden = conn.execute(
        """
        select count(*) as n
        from public.cp8_moltbook_public_transfers
        where code = 'stipend'
        """
    ).fetchone()["n"]
    assert hidden == 0
    reset(conn)
    stipend = conn.execute(
        "select entry_hash from public.cp8_moltbook_transfers where code = 'stipend'"
    ).fetchone()
    assert transfers[0]["prev_hash"] == stipend["entry_hash"]

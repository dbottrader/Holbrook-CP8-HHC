"""Build 2 launch gates for the simulated bounty escrow.

Applies the pre-human fixture, the human-actor migration, then the bounty
migration. Skips when MOLTBOOK_TEST_DSN is unset so the package job can collect
this file. The Moltbook CI job always sets the DSN.
"""

import hashlib
import json
import os
import subprocess
import sys
import threading
import uuid
from pathlib import Path
from urllib.parse import urlparse, urlunparse

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

DSN = os.environ.get("MOLTBOOK_TEST_DSN")
if not DSN:
    pytest.skip("MOLTBOOK_TEST_DSN is required for bounty gate tests", allow_module_level=True)

import psycopg
from psycopg import sql
from psycopg.rows import dict_row

from moltbook.ledger.backend import (
    canonical_json,
    merkle_root,
    settlement_statement,
    verifier_payouts,
    verify_envelope,
)

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "supabase/tests/fixtures/00_pre_human_baseline.sql"
HUMAN = ROOT / "supabase/migrations/20261024143000_moltbook_human_actors.sql"
BOUNTY = ROOT / "supabase/migrations/20261024160000_moltbook_bounty_escrow.sql"
HARDEN = ROOT / "supabase/migrations/20261024180000_moltbook_advisor_hardening.sql"
TOKEN = "hc_0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"
AGENT_ID = "e393fc58-b1a5-4e50-a2aa-4d661f336e4c"


def _database_url(name):
    parts = urlparse(DSN)
    if parts.netloc:
        return urlunparse(parts._replace(path=f"/{name}"))
    # postgresql:///postgres keeps the socket form. urlunparse drops a slash.
    return f"{parts.scheme}:///{name}"


@pytest.fixture(scope="module")
def database_url():
    admin = psycopg.connect(DSN, autocommit=True)
    admin.execute("DROP DATABASE IF EXISTS moltbook_bounty_gates WITH (FORCE)")
    admin.execute("CREATE DATABASE moltbook_bounty_gates")
    admin.close()
    url = _database_url("moltbook_bounty_gates")
    for path in (FIXTURE, HUMAN, BOUNTY, HARDEN):
        applied = subprocess.run(
            ["psql", url, "-v", "ON_ERROR_STOP=1", "-q", "-f", str(path)],
            check=False,
            capture_output=True,
            text=True,
        )
        if applied.returncode != 0:
            raise RuntimeError(applied.stderr or applied.stdout)
    yield url
    admin = psycopg.connect(DSN, autocommit=True)
    admin.execute("DROP DATABASE IF EXISTS moltbook_bounty_gates WITH (FORCE)")
    admin.close()


@pytest.fixture
def conn(database_url):
    with psycopg.connect(database_url, row_factory=dict_row) as connection:
        yield connection
        connection.rollback()


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
        "claims": {"sub": str(uid), "role": "authenticated", "app_metadata": {"actor_type": "agent"}},
    }
    hooked = conn.execute(
        "select public.custom_access_token_hook(%s::jsonb) as event",
        (json.dumps(event),),
    ).fetchone()["event"]
    assert hooked["claims"]["actor_type"] == "human"
    assert hooked["claims"]["app_metadata"]["actor_type"] == "human"
    set_role(conn, "authenticated", hooked["claims"])


def as_service(conn):
    reset(conn)
    set_role(conn, "service_role", {"role": "service_role"})


def create_human(conn, email):
    reset(conn)
    uid = uuid.uuid4()
    conn.execute(
        "insert into auth.users (id, email, raw_user_meta_data) values (%s, %s, '{}'::jsonb)",
        (uid, email),
    )
    return uid


def add_agent(conn, handle):
    reset(conn)
    agent_id = uuid.uuid4()
    token = "hc_" + hashlib.sha256(handle.encode()).hexdigest()
    conn.execute(
        """
        insert into public.cp8_agents (agent_id, handle, display_name, status, authentication_mode)
        values (%s, %s, %s, 'ACTIVE', 'CAPABILITY_TOKEN')
        """,
        (agent_id, handle, handle),
    )
    conn.execute(
        """
        insert into private.cp8_agent_tokens (agent_id, token_hash)
        values (%s, encode(extensions.digest(%s, 'sha256'), 'hex'))
        """,
        (agent_id, token),
    )
    return agent_id, token


def expect(conn, message, statement, params=None):
    conn.execute("savepoint gate")
    with pytest.raises(psycopg.Error) as caught:
        if params is None:
            conn.execute(statement)
        else:
            conn.execute(statement, params)
    conn.execute("rollback to savepoint gate")
    assert message in str(caught.value)


def fund(conn, uid, price=3000, title="Paid task"):
    as_human(conn, uid)
    return conn.execute(
        "select public.cp8_moltbook_human_open_bounty('cp8-ops', %s, 'Describe the verifiable result.', %s) as j",
        (title, price),
    ).fetchone()["j"]


def submit(conn, work_id, token=TOKEN, content="agent result"):
    as_service(conn)
    posted = conn.execute(
        """
        select * from public.cp8_moltbook_agent_post(
          %s, 'cp8-ops', %s, 'post', null, null, null, 'OBSERVED', null
        )
        """,
        (token, content),
    ).fetchone()
    conn.execute(
        "select * from public.cp8_moltbook_worker_claim(%s, %s, 15)",
        (token, work_id),
    )
    conn.execute(
        "select * from public.cp8_moltbook_worker_complete(%s, %s, %s, %s)",
        (token, work_id, posted["post_id"], posted["content_hash"]),
    )
    return posted


def balances_sum_to_zero(conn):
    reset(conn)
    total = conn.execute(
        """
        select coalesce(sum(amount_minor) filter (where credit_account is not null), 0)
             - coalesce(sum(amount_minor) filter (where debit_account is not null), 0) as net
        from (
          select amount_minor, credit_account, null::text as debit_account from public.cp8_moltbook_transfers
          union all
          select amount_minor, null::text, debit_account from public.cp8_moltbook_transfers
        ) legs
        """
    ).fetchone()
    # Each transfer is one debit and one credit of the same amount, so the
    # union above double-counts both sides and the difference is zero.
    assert total["net"] == 0


def test_gate_1_role_spoofing_rejected_both_ways(conn):
    poster = create_human(conn, "gate1-poster@example.com")
    as_human(conn, poster)
    conn.execute("savepoint gate")
    with pytest.raises(psycopg.errors.InsufficientPrivilege):
        conn.execute(
            "select * from public.cp8_moltbook_worker_claim(%s, %s, 15)",
            (TOKEN, uuid.uuid4()),
        )
    conn.execute("rollback to savepoint gate")

    reset(conn)
    conn.execute("grant execute on function public.cp8_moltbook_human_open_bounty(text, text, text, bigint) to service_role")
    conn.execute("grant execute on function public.cp8_moltbook_bounty_promote(uuid) to service_role")
    as_service(conn)
    expect(
        conn,
        "authentication_required",
        "select public.cp8_moltbook_human_open_bounty('cp8-ops','T','A description long enough.', 3000)",
    )
    expect(
        conn,
        "authentication_required",
        "select public.cp8_moltbook_bounty_promote(%s)",
        (uuid.uuid4(),),
    )
    reset(conn)
    expect(
        conn,
        "bounty_write_requires_function",
        """
        insert into public.cp8_moltbook_bounties (
          work_id, poster_human_id, room_slug, title, description,
          price_minor, worker_minor, pool_minor, status
        ) values (%s, %s, 'cp8-ops', 'x', 'y', 20, 18, 2, 'DRAFT')
        """,
        (uuid.uuid4(), uuid.uuid4()),
    )
    opened = fund(conn, poster, 3000, "Gate 1 bounty")
    reset(conn)
    conn.execute("grant select, update on public.cp8_moltbook_work_items to authenticated")
    conn.execute(
        """
        create policy cp8_moltbook_work_items_test_update
          on public.cp8_moltbook_work_items
          for all
          to authenticated
          using (true)
          with check (true)
        """
    )
    as_human(conn, poster)
    conn.execute("savepoint gate")
    with pytest.raises(psycopg.Error) as caught:
        conn.execute(
            """
            update public.cp8_moltbook_work_items
            set claimed_by_agent_id = %s, status = 'claimed'
            where work_id = %s
            """,
            (AGENT_ID, opened["work_id"]),
        )
    conn.execute("rollback to savepoint gate")
    assert "human_cannot_claim_as_agent" in str(caught.value)

    reset(conn)
    human_id = conn.execute(
        "select human_id from public.cp8_moltbook_human_profiles where auth_user_id = %s",
        (poster,),
    ).fetchone()["human_id"]
    set_role(
        conn,
        "authenticated",
        {"role": "authenticated", "sub": str(poster), "actor_type": "agent", "app_metadata": {"actor_type": "agent"}},
    )
    expect(
        conn,
        "actor_type must be human",
        """
        insert into public.cp8_moltbook_posts (
          post_id, room_id, author_agent_id, author_human_id, author_kind,
          thread_root_post_id, kind, status, promotion, content, evidence_refs,
          nonce, request_hash, content_hash, auth_mode
        )
        select gen_random_uuid(), room_id, null, %s, 'human', gen_random_uuid(),
               'post', 'OBSERVED', 'HOLD', 'spoof', array['surface:human-ui'],
               'n', 'h', 'h', 'SUPABASE_AUTH'
        from public.cp8_moltbook_rooms where slug = 'cp8-ops'
        """,
        (human_id,),
    )


def test_gate_2_cross_user_rls_isolation(conn):
    poster = create_human(conn, "gate2-poster@example.com")
    other = create_human(conn, "gate2-other@example.com")
    verifier = create_human(conn, "gate2-verifier@example.com")
    opened = fund(conn, poster, 3000, "Gate 2 bounty")
    posted = submit(conn, opened["work_id"], content="gate2 artifact")
    as_human(conn, verifier)
    conn.execute(
        "select public.cp8_moltbook_bounty_file_verdict(%s, true, 'secret note')",
        (opened["bounty_id"],),
    )

    as_human(conn, other)
    assert conn.execute(
        "select bounty_id from public.cp8_moltbook_bounties where bounty_id = %s",
        (opened["bounty_id"],),
    ).fetchone() is None
    assert conn.execute(
        "select transfer_id from public.cp8_moltbook_transfers where bounty_id = %s",
        (opened["bounty_id"],),
    ).fetchone() is None
    assert conn.execute(
        "select note from public.cp8_moltbook_bounty_verdicts where bounty_id = %s",
        (opened["bounty_id"],),
    ).fetchone() is None
    reset(conn)
    conn.execute("grant update, delete on public.cp8_moltbook_bounties to authenticated")
    as_human(conn, other)
    conn.execute("savepoint gate")
    updated = conn.execute(
        "update public.cp8_moltbook_bounties set title = 'stolen' where bounty_id = %s",
        (opened["bounty_id"],),
    )
    deleted = conn.execute(
        "delete from public.cp8_moltbook_bounties where bounty_id = %s",
        (opened["bounty_id"],),
    )
    conn.execute("rollback to savepoint gate")
    assert updated.rowcount == 0
    assert deleted.rowcount == 0

    reset(conn)
    conn.execute("set local role anon")
    public = conn.execute(
        "select bounty_id, status from public.cp8_moltbook_public_bounties where bounty_id = %s",
        (opened["bounty_id"],),
    ).fetchone()
    assert public["status"] == "VERIFYING"
    hidden = conn.execute(
        "select passed, verifier_handle from public.cp8_moltbook_public_bounty_verdicts where bounty_id = %s",
        (opened["bounty_id"],),
    ).fetchone()
    assert hidden["passed"] is True
    assert "note" not in hidden

    as_human(conn, poster)
    note = conn.execute(
        "select note from public.cp8_moltbook_bounty_verdicts where bounty_id = %s",
        (opened["bounty_id"],),
    ).fetchone()
    assert note["note"] == "secret note"
    own = conn.execute(
        "select transfer_id from public.cp8_moltbook_transfers where bounty_id = %s",
        (opened["bounty_id"],),
    ).fetchone()
    assert own is not None
    assert posted["promotion"] == "HOLD"


def test_gate_3_privileged_calls_without_a_session_do_not_write(conn):
    poster = create_human(conn, "gate3-poster@example.com")
    opened = fund(conn, poster, 3000, "Gate 3 bounty")
    before = conn.execute("select count(*) as n from public.cp8_moltbook_transfers").fetchone()["n"]
    reset(conn)
    expect(
        conn,
        "authentication_required",
        "select public.cp8_moltbook_human_open_bounty('cp8-ops','No session','Description here.', 3000)",
    )
    reset(conn)
    conn.execute("grant execute on function public.cp8_moltbook_ledger_onchain_emit(jsonb) to service_role")
    as_service(conn)
    expect(
        conn,
        "authentication_required",
        "select public.cp8_moltbook_bounty_file_verdict_as_agent('nope', %s, true, null)",
        (opened["bounty_id"],),
    )
    expect(conn, "onchain_backend_disabled_no_mint", "select public.cp8_moltbook_ledger_onchain_emit('{}'::jsonb)")
    reset(conn)
    expect(
        conn,
        "onchain_backend_locked",
        "update public.cp8_moltbook_ledger_backends set active = true where backend = 'onchain'",
    )
    as_human(conn, poster)
    conn.execute("savepoint gate")
    with pytest.raises(psycopg.errors.InsufficientPrivilege):
        conn.execute(
            "select public.cp8_moltbook_bounty_file_verdict_as_agent(%s, %s, true, null)",
            (TOKEN, opened["bounty_id"]),
        )
    conn.execute("rollback to savepoint gate")
    reset(conn)
    after = conn.execute("select count(*) as n from public.cp8_moltbook_transfers").fetchone()["n"]
    assert after == before


def test_gate_4_concurrent_claims_have_one_winner(conn, database_url):
    poster = create_human(conn, "gate4-poster@example.com")
    bob, bob_token = add_agent(conn, "bobgate4")
    opened = fund(conn, poster, 3000, "Gate 4 bounty")
    conn.commit()
    results = []
    errors = []
    barrier = threading.Barrier(2)

    def claim(token):
        with psycopg.connect(database_url, row_factory=dict_row) as other:
            other.execute("set lock_timeout = '8s'")
            other.execute("select set_config('request.jwt.claim.role', 'service_role', true)")
            other.execute(
                "select set_config('request.jwt.claims', %s, true)",
                (json.dumps({"role": "service_role"}),),
            )
            other.execute("set role service_role")
            barrier.wait(timeout=10)
            try:
                row = other.execute(
                    "select * from public.cp8_moltbook_worker_claim(%s, %s, 15)",
                    (token, opened["work_id"]),
                ).fetchone()
                other.commit()
                results.append(row["claimed_by"])
            except Exception as exc:
                other.rollback()
                errors.append(str(exc))

    threads = [
        threading.Thread(target=claim, args=(TOKEN,)),
        threading.Thread(target=claim, args=(bob_token,)),
    ]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=20)
    assert len(results) == 1, (results, errors)
    assert len(errors) == 1
    reset(conn)
    bounty = conn.execute(
        "select status, claim_generation, claimant_agent_id from public.cp8_moltbook_bounties where bounty_id = %s",
        (opened["bounty_id"],),
    ).fetchone()
    assert bounty["status"] == "CLAIMED"
    assert bounty["claim_generation"] == 1
    attempts = conn.execute(
        "select count(*) as n from public.cp8_moltbook_bounty_attempts where bounty_id = %s and status = 'claimed'",
        (opened["bounty_id"],),
    ).fetchone()
    assert attempts["n"] == 1
    assert results[0] in {"ace", "bobgate4"}
    assert bob is not None

    as_service(conn)
    winner = TOKEN if results[0] == "ace" else bob_token
    posted = conn.execute(
        """
        select * from public.cp8_moltbook_agent_post(
          %s, 'cp8-ops', 'late result', 'post', null, null, null, 'OBSERVED', null
        )
        """,
        (winner,),
    ).fetchone()
    conn.execute(
        "select public.cp8_moltbook_bounty_set_deadlines(%s, clock_timestamp() - interval '1 minute', null, null)",
        (opened["bounty_id"],),
    )
    expect(
        conn,
        "claim_lease_expired",
        "select * from public.cp8_moltbook_worker_complete(%s, %s, %s, %s)",
        (winner, opened["work_id"], posted["post_id"], posted["content_hash"]),
    )
    swept = conn.execute("select public.cp8_moltbook_bounty_sweep_expiry() as n").fetchone()["n"]
    assert swept >= 1
    reset(conn)
    reopened = conn.execute(
        "select status, claimant_agent_id from public.cp8_moltbook_bounties where bounty_id = %s",
        (opened["bounty_id"],),
    ).fetchone()
    assert reopened["status"] == "OPEN"
    assert reopened["claimant_agent_id"] is None


def test_gate_5_duplicate_verdict_and_claimant_cannot_verify(conn):
    poster = create_human(conn, "gate5-poster@example.com")
    verifier = create_human(conn, "gate5-verifier@example.com")
    opened = fund(conn, poster, 3000, "Gate 5 bounty")
    submit(conn, opened["work_id"], content="gate5 artifact")
    as_human(conn, poster)
    expect(
        conn,
        "poster_cannot_verify",
        "select public.cp8_moltbook_bounty_file_verdict(%s, true, 'self')",
        (opened["bounty_id"],),
    )
    as_service(conn)
    expect(
        conn,
        "claimant_cannot_verify",
        "select public.cp8_moltbook_bounty_file_verdict_as_agent(%s, %s, true, 'self')",
        (TOKEN, opened["bounty_id"]),
    )
    as_human(conn, verifier)
    first = conn.execute(
        "select public.cp8_moltbook_bounty_file_verdict(%s, true, 'one') as j",
        (opened["bounty_id"],),
    ).fetchone()["j"]
    assert first["status"] == "VERIFYING"
    expect(
        conn,
        "duplicate_verdict",
        "select public.cp8_moltbook_bounty_file_verdict(%s, false, 'again')",
        (opened["bounty_id"],),
    )
    reset(conn)
    assert conn.execute(
        "select count(*) as n from public.cp8_moltbook_bounty_verdicts where bounty_id = %s",
        (opened["bounty_id"],),
    ).fetchone()["n"] == 1
    assert conn.execute(
        "select count(*) as n from public.cp8_moltbook_bounty_settlements where bounty_id = %s",
        (opened["bounty_id"],),
    ).fetchone()["n"] == 0


def test_gate_6_replayed_settlement_reconciles(conn):
    poster = create_human(conn, "gate6-poster@example.com")
    first = create_human(conn, "gate6-a@example.com")
    second = create_human(conn, "gate6-b@example.com")
    opened = fund(conn, poster, 3000, "Gate 6 bounty")
    posted = submit(conn, opened["work_id"], content="gate6 artifact")
    as_human(conn, first)
    conn.execute("select public.cp8_moltbook_bounty_file_verdict(%s, true, 'a')", (opened["bounty_id"],))
    as_human(conn, second)
    settled = conn.execute(
        "select public.cp8_moltbook_bounty_file_verdict(%s, true, 'b') as j",
        (opened["bounty_id"],),
    ).fetchone()["j"]
    assert settled["replayed"] is False
    assert settled["promotion"] == "HOLD"
    reset(conn)
    replay = conn.execute(
        "select public.cp8_moltbook_bounty_settle(%s) as j",
        (opened["bounty_id"],),
    ).fetchone()["j"]
    assert replay["replayed"] is True
    assert replay["settlement_id"] == settled["settlement_id"]
    assert conn.execute(
        "select count(*) as n from public.cp8_moltbook_bounty_settlements where bounty_id = %s",
        (opened["bounty_id"],),
    ).fetchone()["n"] == 1
    assert conn.execute(
        "select count(*) as n from public.cp8_moltbook_receipt_chain where settlement_id = %s and kind = 'settlement'",
        (settled["settlement_id"],),
    ).fetchone()["n"] == 1
    recon = conn.execute(
        "select * from public.cp8_moltbook_bounty_reconcile(%s)",
        (opened["bounty_id"],),
    ).fetchone()
    assert recon["consistent"] is True
    assert recon["post_minor"] == 3000
    assert recon["void_minor"] == 0
    posts = conn.execute(
        """
        select credit_account, amount_minor from public.cp8_moltbook_transfers
        where bounty_id = %s and kind = 'post' order by credit_account
        """,
        (opened["bounty_id"],),
    ).fetchall()
    amounts = {row["credit_account"]: row["amount_minor"] for row in posts}
    assert amounts["agent:" + AGENT_ID] == 2700
    verifier_ids = [key for key in amounts if key.startswith("human:")]
    assert sorted(amounts[key] for key in verifier_ids) == [150, 150]
    receipt = conn.execute(
        "select statement_json, envelope_json, receipt_hash from public.cp8_moltbook_receipt_chain where settlement_id = %s and kind = 'settlement'",
        (settled["settlement_id"],),
    ).fetchone()
    key = conn.execute("select secret from private.cp8_moltbook_sim_receipt_key where key_id = 1").fetchone()["secret"]
    assert verify_envelope(receipt["envelope_json"], bytes(key))
    expected = canonical_json(settlement_statement(
        bounty_id=opened["bounty_id"],
        settlement_id=settled["settlement_id"],
        artifact_hash=posted["content_hash"],
        worker_id="agent:" + AGENT_ID,
        worker_minor=2700,
        verifier_pool_minor=300,
        price_minor=3000,
        pending_transfer_id=opened["pending_transfer_id"],
        post_transfer_ids=[
            "post:" + settled["settlement_id"] + ":worker:agent:" + AGENT_ID,
            "post:" + settled["settlement_id"] + ":verifier:" + verifier_ids[0],
            "post:" + settled["settlement_id"] + ":verifier:" + verifier_ids[1],
        ],
        verifiers=[
            {"id": verifier_ids[0], "amountMinor": 150},
            {"id": verifier_ids[1], "amountMinor": 150},
        ],
        prev_receipt_hash="",
    ))
    assert receipt["statement_json"] == expected
    assert conn.execute(
        "select public.cp8_moltbook_settlement_receipt_ok(%s) as ok",
        (settled["settlement_id"],),
    ).fetchone()["ok"] is True

    odd_poster = create_human(conn, "gate6-odd@example.com")
    odd_a = create_human(conn, "gate6-odd-a@example.com")
    odd_b = create_human(conn, "gate6-odd-b@example.com")
    odd = fund(conn, odd_poster, 1001, "Odd minor units")
    submit(conn, odd["work_id"], content="odd artifact")
    as_human(conn, odd_a)
    conn.execute("select public.cp8_moltbook_bounty_file_verdict(%s, true, null)", (odd["bounty_id"],))
    as_human(conn, odd_b)
    conn.execute("select public.cp8_moltbook_bounty_file_verdict(%s, true, null)", (odd["bounty_id"],))
    reset(conn)
    odd_posts = conn.execute(
        """
        select credit_account, amount_minor from public.cp8_moltbook_transfers
        where bounty_id = %s and kind = 'post'
        """,
        (odd["bounty_id"],),
    ).fetchall()
    odd_amounts = {row["credit_account"]: row["amount_minor"] for row in odd_posts}
    assert odd_amounts["agent:" + AGENT_ID] == 900
    humans = sorted(key for key in odd_amounts if key.startswith("human:"))
    expected_pool = dict(verifier_payouts(101, humans))
    assert {humans[0]: odd_amounts[humans[0]], humans[1]: odd_amounts[humans[1]]} == expected_pool
    odd_recon = conn.execute(
        "select * from public.cp8_moltbook_bounty_reconcile(%s)",
        (odd["bounty_id"],),
    ).fetchone()
    assert odd_recon["consistent"] is True
    assert odd_recon["worker_minor"] + odd_recon["pool_minor"] == 1001
    balances_sum_to_zero(conn)

    as_human(conn, first)
    visible = conn.execute(
        "select settlement_id from public.cp8_moltbook_bounty_settlements where bounty_id = %s",
        (opened["bounty_id"],),
    ).fetchone()
    assert visible is None
    as_human(conn, poster)
    assert conn.execute(
        "select settlement_key from public.cp8_moltbook_bounty_settlements where bounty_id = %s",
        (opened["bounty_id"],),
    ).fetchone()["settlement_key"] == "settle:" + opened["bounty_id"]


def test_gate_7_only_the_poster_can_promote_the_artifact(conn):
    poster = create_human(conn, "gate7-poster@example.com")
    other = create_human(conn, "gate7-other@example.com")
    left = create_human(conn, "gate7-left@example.com")
    right = create_human(conn, "gate7-right@example.com")
    opened = fund(conn, poster, 3000, "Gate 7 bounty")
    posted = submit(conn, opened["work_id"], content="gate7 artifact")
    as_human(conn, poster)
    conn.execute(
        "select public.cp8_moltbook_human_post('cp8-ops', 'a human note', 'post', null)"
    )
    expect(
        conn,
        "bounty_not_settled",
        "select public.cp8_moltbook_bounty_promote(%s)",
        (opened["bounty_id"],),
    )
    as_human(conn, left)
    conn.execute("select public.cp8_moltbook_bounty_file_verdict(%s, true, null)", (opened["bounty_id"],))
    as_human(conn, right)
    conn.execute("select public.cp8_moltbook_bounty_file_verdict(%s, true, null)", (opened["bounty_id"],))
    reset(conn)
    conn.execute("grant execute on function public.cp8_moltbook_bounty_promote(uuid) to service_role")
    as_service(conn)
    expect(
        conn,
        "authentication_required",
        "select public.cp8_moltbook_bounty_promote(%s)",
        (opened["bounty_id"],),
    )
    as_human(conn, other)
    expect(
        conn,
        "not_poster",
        "select public.cp8_moltbook_bounty_promote(%s)",
        (opened["bounty_id"],),
    )
    reset(conn)
    expect(
        conn,
        "promotion_requires_human_rpc",
        "update public.cp8_moltbook_bounties set promotion = 'SIM_ACCEPTED' where bounty_id = %s",
        (opened["bounty_id"],),
    )
    expect(
        conn,
        "human posts remain HOLD",
        """
        update public.cp8_moltbook_posts
        set promotion = 'SIM_ACCEPTED'
        where author_kind = 'human'
        """,
    )
    expect(
        conn,
        "promotion_requires_human_rpc",
        "update public.cp8_moltbook_posts set promotion = 'SIM_ACCEPTED' where post_id = %s",
        (posted["post_id"],),
    )
    reset(conn)
    conn.execute(
        "update public.cp8_moltbook_posts set content_hash = 'tampered' where post_id = %s",
        (posted["post_id"],),
    )
    as_human(conn, poster)
    expect(
        conn,
        "artifact_mismatch",
        "select public.cp8_moltbook_bounty_promote(%s)",
        (opened["bounty_id"],),
    )
    reset(conn)
    conn.execute(
        "update public.cp8_moltbook_posts set content_hash = %s where post_id = %s",
        (posted["content_hash"], posted["post_id"]),
    )
    as_human(conn, poster)
    promoted = conn.execute(
        "select public.cp8_moltbook_bounty_promote(%s) as j",
        (opened["bounty_id"],),
    ).fetchone()["j"]
    assert promoted["promotion"] == "SIM_ACCEPTED"
    assert promoted["artifact_hash"] == posted["content_hash"]
    expect(
        conn,
        "already_promoted",
        "select public.cp8_moltbook_bounty_promote(%s)",
        (opened["bounty_id"],),
    )
    reset(conn)
    stored = conn.execute(
        """
        select b.promotion, b.promoted_artifact_hash, p.promotion as post_promotion, p.author_kind,
               pp.promotion as record_promotion, pp.artifact_hash as record_hash,
               pp.promoted_by_human_id, b.poster_human_id
        from public.cp8_moltbook_bounties b
        join public.cp8_moltbook_posts p on p.post_id = b.submission_post_id
        join public.cp8_moltbook_post_promotions pp on pp.bounty_id = b.bounty_id
          and pp.post_id = p.post_id
        where b.bounty_id = %s
        """,
        (opened["bounty_id"],),
    ).fetchone()
    assert stored["promotion"] == "SIM_ACCEPTED"
    assert stored["promoted_artifact_hash"] == posted["content_hash"]
    # The post row is append-only: it keeps HOLD. Acceptance is its own record.
    assert stored["post_promotion"] == "HOLD"
    assert stored["record_promotion"] == "SIM_ACCEPTED"
    assert stored["record_hash"] == posted["content_hash"]
    assert stored["promoted_by_human_id"] == stored["poster_human_id"]
    assert stored["author_kind"] == "agent"
    shown = conn.execute(
        "select promotion from public.cp8_moltbook_public_posts where post_id = %s",
        (posted["post_id"],),
    ).fetchone()
    assert shown["promotion"] == "SIM_ACCEPTED"
    expect(
        conn,
        "promotion_requires_human_rpc",
        """
        insert into public.cp8_moltbook_post_promotions
          (post_id, bounty_id, artifact_hash, promoted_by_human_id)
        select post_id, bounty_id, artifact_hash, promoted_by_human_id
        from public.cp8_moltbook_post_promotions limit 1
        """,
    )
    expect(
        conn,
        "post promotions are append-only",
        "update public.cp8_moltbook_post_promotions set artifact_hash = 'x'",
    )
    expect(
        conn,
        "post promotions are append-only",
        "delete from public.cp8_moltbook_post_promotions",
    )
    human_post = conn.execute(
        "select promotion from public.cp8_moltbook_posts where author_kind = 'human'"
    ).fetchall()
    assert human_post
    assert {row["promotion"] for row in human_post} == {"HOLD"}


def test_gate_8_timeout_disagreement_cancel_and_failed_settlement(conn):
    poster = create_human(conn, "gate8-poster@example.com")
    opened = fund(conn, poster, 3000, "Cancel me")
    as_human(conn, poster)
    before = conn.execute("select public.cp8_moltbook_my_sim_balance() as b").fetchone()["b"]
    assert before == 97000
    cancelled = conn.execute(
        "select public.cp8_moltbook_bounty_cancel(%s) as j",
        (opened["bounty_id"],),
    ).fetchone()["j"]
    assert cancelled["status"] == "CANCELLED"
    assert conn.execute("select public.cp8_moltbook_my_sim_balance() as b").fetchone()["b"] == 100000
    expect(
        conn,
        "invalid_transition",
        "select public.cp8_moltbook_bounty_cancel(%s)",
        (opened["bounty_id"],),
    )
    reset(conn)
    recon = conn.execute(
        "select * from public.cp8_moltbook_bounty_reconcile(%s)",
        (opened["bounty_id"],),
    ).fetchone()
    assert recon["consistent"] is True
    assert recon["void_minor"] == 3000
    assert recon["post_minor"] == 0

    disagree = fund(conn, poster, 3000, "Disagree")
    submit(conn, disagree["work_id"], content="disagree artifact")
    passer = create_human(conn, "gate8-pass@example.com")
    failer = create_human(conn, "gate8-fail@example.com")
    as_human(conn, passer)
    conn.execute("select public.cp8_moltbook_bounty_file_verdict(%s, true, 'pass')", (disagree["bounty_id"],))
    as_human(conn, failer)
    failed = conn.execute(
        "select public.cp8_moltbook_bounty_file_verdict(%s, false, 'fail') as j",
        (disagree["bounty_id"],),
    ).fetchone()["j"]
    assert failed["status"] == "REJECTED"
    reset(conn)
    bad = conn.execute(
        "select * from public.cp8_moltbook_bounty_reconcile(%s)",
        (disagree["bounty_id"],),
    ).fetchone()
    assert bad["consistent"] is True
    assert bad["void_minor"] == 3000
    assert bad["post_minor"] == 0
    assert conn.execute(
        "select count(*) as n from public.cp8_moltbook_receipt_chain where bounty_id = %s",
        (disagree["bounty_id"],),
    ).fetchone()["n"] == 0

    stalled = fund(conn, poster, 3000, "Timeout")
    submit(conn, stalled["work_id"], content="timeout artifact")
    as_service(conn)
    conn.execute(
        "select public.cp8_moltbook_bounty_set_deadlines(%s, null, clock_timestamp() - interval '1 minute', null)",
        (stalled["bounty_id"],),
    )
    conn.execute("select public.cp8_moltbook_bounty_sweep_expiry()")
    reset(conn)
    state = conn.execute(
        "select status from public.cp8_moltbook_bounties where bounty_id = %s",
        (stalled["bounty_id"],),
    ).fetchone()
    assert state["status"] == "DISPUTED"
    held = conn.execute(
        "select * from public.cp8_moltbook_bounty_reconcile(%s)",
        (stalled["bounty_id"],),
    ).fetchone()
    assert held["consistent"] is True
    assert held["pending_minor"] == 3000
    assert held["post_minor"] == 0
    assert held["void_minor"] == 0
    as_human(conn, poster)
    refunded = conn.execute(
        "select public.cp8_moltbook_bounty_refund(%s) as j",
        (stalled["bounty_id"],),
    ).fetchone()["j"]
    assert refunded["status"] == "REJECTED"
    assert conn.execute("select public.cp8_moltbook_my_sim_balance() as b").fetchone()["b"] == 100000

    fragile = fund(conn, poster, 3000, "Fragile settle")
    submit(conn, fragile["work_id"], content="fragile artifact")
    one = create_human(conn, "gate8-one@example.com")
    two = create_human(conn, "gate8-two@example.com")
    as_human(conn, one)
    conn.execute("select public.cp8_moltbook_bounty_file_verdict(%s, true, null)", (fragile["bounty_id"],))
    as_human(conn, two)
    conn.execute("select set_config('cp8.fault_fail_settlement', 'on', true)")
    expect(
        conn,
        "settlement_failed",
        "select public.cp8_moltbook_bounty_file_verdict(%s, true, null)",
        (fragile["bounty_id"],),
    )
    reset(conn)
    still = conn.execute(
        "select status from public.cp8_moltbook_bounties where bounty_id = %s",
        (fragile["bounty_id"],),
    ).fetchone()
    assert still["status"] == "VERIFYING"
    assert conn.execute(
        "select count(*) as n from public.cp8_moltbook_bounty_settlements where bounty_id = %s",
        (fragile["bounty_id"],),
    ).fetchone()["n"] == 0
    fragile_recon = conn.execute(
        "select * from public.cp8_moltbook_bounty_reconcile(%s)",
        (fragile["bounty_id"],),
    ).fetchone()
    assert fragile_recon["consistent"] is True
    assert fragile_recon["post_minor"] == 0
    as_service(conn)
    root = conn.execute("select public.cp8_moltbook_ledger_anchor() as root").fetchone()["root"]
    reset(conn)
    leaves = [
        row["receipt_hash"]
        for row in conn.execute(
            "select receipt_hash from public.cp8_moltbook_receipt_chain order by created_at, receipt_hash"
        ).fetchall()
    ]
    assert root == merkle_root(leaves)
    balances_sum_to_zero(conn)


PUBLIC_BOUNTY_VIEWS = (
    "cp8_moltbook_public_bounties",
    "cp8_moltbook_public_bounty_attempts",
    "cp8_moltbook_public_bounty_verdicts",
    "cp8_moltbook_public_bounty_events",
    "cp8_moltbook_public_transfers",
)


def test_public_bounty_views_are_invoker_over_internal_projection(conn):
    reset(conn)
    for name in PUBLIC_BOUNTY_VIEWS:
        row = conn.execute(
            """
            select c.reloptions, n.nspname
            from pg_class c join pg_namespace n on n.oid = c.relnamespace
            where c.relname = %s and c.relkind = 'v' and n.nspname = 'public'
            """,
            (name,),
        ).fetchone()
        assert row is not None, name
        assert "security_invoker=true" in (row["reloptions"] or []), name
        inner = conn.execute(
            "select to_regclass(%s) is not null as present",
            (f"cp8_moltbook_internal.{name}",),
        ).fetchone()
        assert inner["present"], name
        for role in ("anon", "authenticated"):
            grant = conn.execute(
                "select has_table_privilege(%s, %s, 'SELECT') as ok",
                (role, f"public.{name}"),
            ).fetchone()
            assert grant["ok"], (role, name)
    for table in ("cp8_moltbook_bounties", "cp8_moltbook_bounty_verdicts", "cp8_moltbook_transfers"):
        anon = conn.execute(
            "select has_table_privilege('anon', %s, 'SELECT') as ok",
            (f"public.{table}",),
        ).fetchone()
        assert not anon["ok"], table


def test_trigger_functions_are_not_rpc_callable(conn):
    reset(conn)
    rows = conn.execute(
        """
        select p.oid::regprocedure::text as fn,
               has_function_privilege('anon', p.oid, 'EXECUTE') as anon_exec,
               has_function_privilege('authenticated', p.oid, 'EXECUTE') as auth_exec
        from pg_proc p
        where p.pronamespace = 'public'::regnamespace
          and p.proname like 'cp8\\_moltbook\\_%%'
          and p.prorettype = 'pg_catalog.trigger'::regtype
        """
    ).fetchall()
    assert rows
    for row in rows:
        assert not row["anon_exec"], row["fn"]
        assert not row["auth_exec"], row["fn"]

#!/usr/bin/env python3
"""Replay one Proof-of-Work Commons cycle on disposable Postgres.

From a clean checkout, with MOLTBOOK_TEST_DSN pointing at a disposable server:

    python3 scripts/replay_proof_of_work_commons.py

The script creates and drops database moltbook_pow_commons. It does not talk
to project ecenvlwyenpakrxfuqup, and it does not mint or call a chain.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import uuid
from pathlib import Path
from urllib.parse import urlparse, urlunparse

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import psycopg
from psycopg.rows import dict_row

from moltbook.ledger.backend import merkle_root, verify_envelope

FIXTURE = ROOT / "supabase/tests/fixtures/00_pre_human_baseline.sql"
HUMAN = ROOT / "supabase/migrations/20261024143000_moltbook_human_actors.sql"
BOUNTY = ROOT / "supabase/migrations/20261024160000_moltbook_bounty_escrow.sql"
MANIFEST = ROOT / "manifests/proof-of-work-commons.json"
TOKEN = "hc_0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"
DB_NAME = "moltbook_pow_commons"


class ReplayFailure(RuntimeError):
    pass


def require(condition, message):
    if not condition:
        raise ReplayFailure(message)


def database_url(dsn, name):
    parts = urlparse(dsn)
    if parts.netloc:
        return urlunparse(parts._replace(path=f"/{name}"))
    return f"{parts.scheme}:///{name}"


def psql(url, path):
    subprocess.run(
        ["psql", url, "-v", "ON_ERROR_STOP=1", "-q", "-f", str(path)],
        check=True,
        capture_output=True,
        text=True,
    )


def reset(conn):
    conn.execute("reset role")
    for key in ("request.jwt.claim.sub", "request.jwt.claim.role", "request.jwt.claims"):
        conn.execute("select set_config(%s, '', true)", (key,))


def as_human(conn, uid):
    reset(conn)
    event = {"user_id": str(uid), "claims": {"sub": str(uid), "role": "authenticated", "app_metadata": {}}}
    hooked = conn.execute(
        "select public.custom_access_token_hook(%s::jsonb) as event",
        (json.dumps(event),),
    ).fetchone()["event"]
    require(hooked["claims"]["actor_type"] == "human", "hook did not force actor_type=human")
    conn.execute("select set_config('request.jwt.claim.sub', %s, true)", (str(uid),))
    conn.execute("select set_config('request.jwt.claim.role', 'authenticated', true)")
    conn.execute("select set_config('request.jwt.claims', %s, true)", (json.dumps(hooked["claims"]),))
    conn.execute("set role authenticated")


def as_service(conn):
    reset(conn)
    conn.execute("select set_config('request.jwt.claim.role', 'service_role', true)")
    conn.execute("select set_config('request.jwt.claims', %s, true)", (json.dumps({"role": "service_role"}),))
    conn.execute("set role service_role")


def create_human(conn, email):
    reset(conn)
    uid = uuid.uuid4()
    conn.execute(
        "insert into auth.users (id, email, raw_user_meta_data) values (%s, %s, %s::jsonb)",
        (uid, email, json.dumps({"display_name": email.split("@")[0]})),
    )
    return uid


def run_cycle(conn):
    poster = create_human(conn, "poster@example.com")
    left = create_human(conn, "verifier-left@example.com")
    right = create_human(conn, "verifier-right@example.com")
    as_human(conn, poster)
    opened = conn.execute(
        """
        select public.cp8_moltbook_human_open_bounty(
          'cp8-ops', 'Proof of work', 'Produce a HOLD artifact a human can promote.', 3000
        ) as bounty
        """
    ).fetchone()["bounty"]
    require(opened["status"] == "OPEN", opened)
    require(opened["promotion"] == "HOLD", opened)
    require(opened["worker_minor"] == 2700 and opened["pool_minor"] == 300, opened)

    as_service(conn)
    posted = conn.execute(
        """
        select * from public.cp8_moltbook_agent_post(
          %s, 'cp8-ops', 'commons result', 'post', null, null, null, 'OBSERVED', null
        )
        """,
        (TOKEN,),
    ).fetchone()
    require(posted["promotion"] == "HOLD", "agent execution must stay HOLD")
    conn.execute("select * from public.cp8_moltbook_worker_claim(%s, %s, 15)", (TOKEN, opened["work_id"]))
    conn.execute(
        "select * from public.cp8_moltbook_worker_complete(%s, %s, %s, %s)",
        (TOKEN, opened["work_id"], posted["post_id"], posted["content_hash"]),
    )

    as_human(conn, left)
    first = conn.execute(
        "select public.cp8_moltbook_bounty_file_verdict(%s, true, 'independent pass') as verdict",
        (opened["bounty_id"],),
    ).fetchone()["verdict"]
    require(first["status"] == "VERIFYING", first)
    as_human(conn, right)
    settled = conn.execute(
        "select public.cp8_moltbook_bounty_file_verdict(%s, true, 'second pass') as verdict",
        (opened["bounty_id"],),
    ).fetchone()["verdict"]
    require(settled["replayed"] is False, settled)
    require(settled["promotion"] == "HOLD", "settlement must not promote")

    reset(conn)
    replay = conn.execute(
        "select public.cp8_moltbook_bounty_settle(%s) as verdict",
        (opened["bounty_id"],),
    ).fetchone()["verdict"]
    require(replay["replayed"] is True, replay)
    require(replay["settlement_id"] == settled["settlement_id"], "settlement id changed on replay")
    receipts = conn.execute(
        """
        select count(*) as n from public.cp8_moltbook_receipt_chain
        where settlement_id = %s and kind = 'settlement'
        """,
        (settled["settlement_id"],),
    ).fetchone()["n"]
    require(receipts == 1, f"expected one settlement receipt, saw {receipts}")

    recon = conn.execute(
        "select * from public.cp8_moltbook_bounty_reconcile(%s)",
        (opened["bounty_id"],),
    ).fetchone()
    require(recon["consistent"] is True, dict(recon))
    require(recon["pending_minor"] == recon["post_minor"] == 3000, dict(recon))
    require(recon["worker_minor"] + recon["pool_minor"] == recon["price_minor"], dict(recon))

    receipt = conn.execute(
        """
        select envelope_json, receipt_hash, prev_receipt_hash
        from public.cp8_moltbook_receipt_chain
        where settlement_id = %s and kind = 'settlement'
        """,
        (settled["settlement_id"],),
    ).fetchone()
    key = bytes(conn.execute("select secret from private.cp8_moltbook_sim_receipt_key").fetchone()["secret"])
    require(verify_envelope(receipt["envelope_json"], key), "DSSE signature did not verify")
    require(
        conn.execute(
            "select public.cp8_moltbook_settlement_receipt_ok(%s) as ok",
            (settled["settlement_id"],),
        ).fetchone()["ok"]
        is True,
        "SQL receipt check failed",
    )
    post_promotion = conn.execute(
        "select promotion from public.cp8_moltbook_posts where post_id = %s",
        (posted["post_id"],),
    ).fetchone()["promotion"]
    require(post_promotion == "HOLD", "artifact left HOLD before the human promote")

    as_human(conn, poster)
    promoted = conn.execute(
        "select public.cp8_moltbook_bounty_promote(%s) as promotion",
        (opened["bounty_id"],),
    ).fetchone()["promotion"]
    require(promoted["promotion"] == "SIM_ACCEPTED", promoted)
    require(promoted["artifact_hash"] == posted["content_hash"], promoted)

    reset(conn)
    chain = conn.execute(
        "select receipt_hash, prev_receipt_hash, kind from public.cp8_moltbook_receipt_chain order by created_at, receipt_hash"
    ).fetchall()
    require([row["kind"] for row in chain] == ["settlement", "promotion"], [row["kind"] for row in chain])
    require(chain[0]["prev_receipt_hash"] == "", "chain did not start empty")
    require(chain[1]["prev_receipt_hash"] == chain[0]["receipt_hash"], "promotion did not link to settlement")
    as_service(conn)
    root = conn.execute("select public.cp8_moltbook_ledger_anchor() as root").fetchone()["root"]
    require(root == merkle_root([row["receipt_hash"] for row in chain]), "merkle root drifted")

    # A failing verdict voids the pending transfer. No second settlement receipt.
    as_human(conn, poster)
    failed_open = conn.execute(
        """
        select public.cp8_moltbook_human_open_bounty(
          'cp8-ops', 'Refund path', 'This attempt should be voided.', 3000
        ) as bounty
        """
    ).fetchone()["bounty"]
    as_service(conn)
    bad = conn.execute(
        """
        select * from public.cp8_moltbook_agent_post(
          %s, 'cp8-ops', 'bad result', 'post', null, null, null, 'OBSERVED', null
        )
        """,
        (TOKEN,),
    ).fetchone()
    conn.execute("select * from public.cp8_moltbook_worker_claim(%s, %s, 15)", (TOKEN, failed_open["work_id"]))
    conn.execute(
        "select * from public.cp8_moltbook_worker_complete(%s, %s, %s, %s)",
        (TOKEN, failed_open["work_id"], bad["post_id"], bad["content_hash"]),
    )
    as_human(conn, left)
    rejected = conn.execute(
        "select public.cp8_moltbook_bounty_file_verdict(%s, false, 'no') as verdict",
        (failed_open["bounty_id"],),
    ).fetchone()["verdict"]
    require(rejected["status"] == "REJECTED", rejected)
    reset(conn)
    voided = conn.execute(
        "select * from public.cp8_moltbook_bounty_reconcile(%s)",
        (failed_open["bounty_id"],),
    ).fetchone()
    require(voided["consistent"] is True and voided["void_minor"] == 3000 and voided["post_minor"] == 0, dict(voided))
    require(
        conn.execute(
            "select count(*) as n from public.cp8_moltbook_receipt_chain where bounty_id = %s",
            (failed_open["bounty_id"],),
        ).fetchone()["n"]
        == 0,
        "a voided bounty emitted a settlement receipt",
    )
    try:
        conn.execute("select public.cp8_moltbook_ledger_onchain_emit('{}'::jsonb)")
    except psycopg.Error as exc:
        require("onchain_backend_disabled_no_mint" in str(exc), str(exc))
    else:
        raise ReplayFailure("onchain emit returned")

    return {
        "bounty_id": opened["bounty_id"],
        "settlement_id": settled["settlement_id"],
        "settlement_key": settled["settlement_key"],
        "artifact_hash": posted["content_hash"],
        "receipt_hash": receipt["receipt_hash"],
        "merkle_root": root,
        "promotion": promoted["promotion"],
        "worker_minor": 2700,
        "pool_minor": 300,
        "price_minor": 3000,
        "refund_bounty_status": rejected["status"],
    }


def check_manifest(conn):
    manifest = json.loads(MANIFEST.read_text())
    params = conn.execute("select * from public.cp8_moltbook_escrow_params where params_id = 1").fetchone()
    require(manifest["evidence_tier"] == "E2", manifest["evidence_tier"])
    require(manifest["wallet_class"] == params["wallet_class"], "wallet class drifted")
    require(manifest["worker_share_bps"] == params["worker_share_bps"] == 9000, "worker bps drifted")
    require(manifest["verifier_pool_bps"] == params["verifier_pool_bps"] == 1000, "pool bps drifted")
    require(manifest["min_verifiers"] == 2, "min verifiers drifted")
    require(manifest["ledger_backend"] == "simulated", manifest["ledger_backend"])
    require(manifest["onchain_enabled"] is False, "manifest says the chain is on")
    require(manifest["simulated_vs_deployed"], "missing simulated vs deployed table")
    licenses = " ".join(json.dumps(item) for item in manifest["sources"])
    for name in ("TigerBeetle", "Apache-2.0", "Algora", "AGPL-3.0", "in-toto", "DSSE", "Supabase"):
        require(name in licenses or name in json.dumps(manifest["sources"]), f"source citation missing {name}")
    backend = conn.execute(
        "select backend from public.cp8_moltbook_ledger_backends where active"
    ).fetchone()["backend"]
    require(backend == "simulated", backend)
    return manifest


def main():
    dsn = os.environ.get("MOLTBOOK_TEST_DSN")
    if not dsn:
        raise SystemExit("MOLTBOOK_TEST_DSN is required")
    admin = psycopg.connect(dsn, autocommit=True)
    admin.execute(f"DROP DATABASE IF EXISTS {DB_NAME} WITH (FORCE)")
    admin.execute(f"CREATE DATABASE {DB_NAME}")
    admin.close()
    url = database_url(dsn, DB_NAME)
    try:
        for path in (FIXTURE, HUMAN, BOUNTY):
            psql(url, path)
        with psycopg.connect(url, row_factory=dict_row) as conn:
            manifest = check_manifest(conn)
            report = run_cycle(conn)
            conn.commit()
        print(json.dumps({
            "ok": True,
            "evidence_tier": manifest["evidence_tier"],
            "manifest": str(MANIFEST.relative_to(ROOT)),
            "replay": report,
        }, indent=2))
    finally:
        admin = psycopg.connect(dsn, autocommit=True)
        admin.execute(f"DROP DATABASE IF EXISTS {DB_NAME} WITH (FORCE)")
        admin.close()


if __name__ == "__main__":
    try:
        main()
    except (ReplayFailure, psycopg.Error, subprocess.CalledProcessError) as exc:
        if isinstance(exc, subprocess.CalledProcessError):
            sys.stderr.write(exc.stderr or "")
        raise SystemExit(f"replay failed: {exc}") from exc

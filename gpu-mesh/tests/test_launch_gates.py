"""The eight GPU-network launch gates from the security review."""

import threading
import time

import pytest
from sqlalchemy import UniqueConstraint
from sqlalchemy.exc import OperationalError

from gpumesh.db import Job, Node, Settlement, build_database, session_scope
from gpumesh.errors import MeshError
from gpumesh.ledger import verify_session
from gpumesh.work import (
    claim_job,
    enqueue_inference,
    register_node,
    rotate_credential,
    settle_once,
    submit_result,
    sweep,
)
from gpumesh_node.toploc_proof import build_prompt_proofs, library_ready
from tests.conftest import make_settings


def _spec(name: str, model: str = "alpha") -> dict:
    return {
        "name": name,
        "backend": "cpu",
        "gpu": {"vendor": "cpu", "model": "cpu", "vram_mb": 0, "driver": "", "count": 0},
        "models": [{"id": model, "resident": True, "source": "cpu-fallback", "digest": "cpu-fallback"}],
        "version": "test",
    }


def _job(session, settings, model="alpha"):
    return enqueue_inference(
        session,
        settings,
        model=model,
        messages=[{"role": "user", "content": "Say hello in one sentence."}],
        temperature=0,
        max_tokens=32,
        seed=0,
        stop=None,
        client_key="ip:gate",
    )


def _proof(job_messages, model, good: bool):
    if not library_ready():
        return []
    proofs = build_prompt_proofs(job_messages, model) or []
    if good or not proofs:
        return proofs
    return list(reversed(proofs))


def test_gate1_stale_lease_is_rejected(tmp_path):
    settings = make_settings(tmp_path, verify_sample_rate=0, job_timeout_sec=30)
    _engine, factory = build_database(settings)
    with session_scope(factory) as session:
        node_a, _ta, _ra = register_node(session, settings, _spec("a"), "10.0.0.1")
        node_b, _tb, _rb = register_node(session, settings, _spec("b"), "10.0.0.2")
        job = _job(session, settings)
        claimed = claim_job(session, settings, node_a)
        assert claimed is not None
        old = claimed.lease_generation
        claimed.lease_expires_at = time.time() - 5
        claimed.deadline_at = time.time() - 5
        session.flush()
        with pytest.raises(MeshError) as expired:
            submit_result(
                session,
                settings,
                node_a,
                job.id,
                {"output_text": "too late", "fencing_token": old, "prompt_tokens": 1, "completion_tokens": 1, "duration_ms": 5},
            )
        assert expired.value.code == "lease_expired"
        sweep(session, settings)
        assert job.status == "queued"
        again = claim_job(session, settings, node_b)
        assert again is not None and again.lease_generation == old + 1
        with pytest.raises(MeshError) as stale:
            submit_result(
                session,
                settings,
                node_a,
                job.id,
                {"output_text": "from A", "fencing_token": old, "prompt_tokens": 1, "completion_tokens": 1, "duration_ms": 5},
            )
        assert stale.value.code in {"not_your_job", "stale_lease"}
        assert node_a.credits == 0
        assert session.query(Settlement).filter(Settlement.idempotency_key == f"{job.id}:worker_award").count() == 0


def test_gate2_exactly_once_credit(tmp_path):
    names = {constraint.name for constraint in Settlement.__table__.constraints if isinstance(constraint, UniqueConstraint)}
    assert "uq_settlement_idempotency" in names
    settings = make_settings(tmp_path, verify_sample_rate=0)
    _engine, factory = build_database(settings)
    with session_scope(factory) as session:
        node, _token, _receipt = register_node(session, settings, _spec("a"), "10.0.0.1")
        job = _job(session, settings)
        claimed = claim_job(session, settings, node)
        body = submit_result(
            session,
            settings,
            node,
            job.id,
            {
                "output_text": "hello there",
                "fencing_token": claimed.lease_generation,
                "prompt_tokens": 1,
                "completion_tokens": 2,
                "duration_ms": 8,
            },
        )
        again = submit_result(
            session,
            settings,
            node,
            job.id,
            {"output_text": "hello there", "prompt_tokens": 9, "completion_tokens": 9, "duration_ms": 9},
        )
        assert again["receipt"] == body["receipt"]
        assert session.query(Settlement).filter(Settlement.idempotency_key == f"{job.id}:execution").count() == 1
        node_id = node.id
        job_id = job.id

    barrier = threading.Barrier(2)
    errors: list[BaseException] = []

    def race() -> None:
        barrier.wait(timeout=5)
        last: BaseException | None = None
        for _ in range(8):
            session = factory()
            try:
                node = session.get(Node, node_id)
                job = session.get(Job, job_id)
                settle_once(
                    session,
                    key=f"{job_id}:worker_award",
                    job=job,
                    node=node,
                    kind="inference_receipt",
                    amount=4,
                    payload={"schema": "gpumesh.inference_receipt.v1", "job_id": job_id, "model": "alpha"},
                    settings=settings,
                )
                session.commit()
                return
            except OperationalError as exc:
                session.rollback()
                last = exc
                time.sleep(0.02)
            except BaseException as exc:
                session.rollback()
                errors.append(exc)
                return
            finally:
                session.close()
        if last is not None:
            errors.append(last)

    threads = [threading.Thread(target=race) for _ in range(2)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(10)
    assert errors == []
    with session_scope(factory) as session:
        node = session.get(Node, node_id)
        awards = session.query(Settlement).filter(Settlement.idempotency_key == f"{job_id}:worker_award").all()
        assert len(awards) == 1
        assert awards[0].credits == 4
        assert node.credits + node.escrow_credits == 4


def test_gate3_forged_completion_gets_no_credit(tmp_path):
    settings = make_settings(tmp_path, verify_sample_rate=0)
    _engine, factory = build_database(settings)
    with session_scope(factory) as session:
        node, _token, _receipt = register_node(session, settings, _spec("a"), "10.0.0.1")
        other, _to, _ro = register_node(session, settings, _spec("b", "beta"), "10.0.0.2")
        job = _job(session, settings)
        claimed = claim_job(session, settings, node)
        with pytest.raises(MeshError) as missing:
            submit_result(session, settings, node, "job_missing", {"output_text": "x", "fencing_token": 1})
        assert missing.value.status == 404
        with pytest.raises(MeshError) as wrong:
            submit_result(
                session,
                settings,
                other,
                job.id,
                {"output_text": "stolen", "fencing_token": claimed.lease_generation, "credits": 9999, "receipt": "ab" * 32},
            )
        assert wrong.value.status == 403
        body = submit_result(
            session,
            settings,
            node,
            job.id,
            {
                "output_text": "real output",
                "fencing_token": claimed.lease_generation,
                "output_hash": "ff" * 32,
                "credits": 9999,
                "receipt": "ab" * 32,
                "prompt_tokens": 1,
                "completion_tokens": 2,
                "duration_ms": 5,
            },
        )
        assert body["credits"] == 0
        assert body["output_hash"] != "ff" * 32
        assert node.credits == 0
        assert session.query(Settlement).filter(Settlement.kind == "inference_receipt").count() == 0


def test_gate4_revoked_credential(tmp_path):
    settings = make_settings(tmp_path)
    engine, factory = build_database(settings)
    from fastapi.testclient import TestClient

    from gpumesh.main import create_app

    del engine
    app = create_app(settings)
    with TestClient(app) as client:
        registered = client.post("/api/nodes/register", json=_spec("rig")).json()
        token = registered["token"]
        node_id = registered["node_id"]
        headers = {"authorization": f"Bearer {token}"}
        assert client.post("/api/nodes/heartbeat", json={"models": []}, headers=headers).status_code == 200
        revoked = client.post(f"/api/admin/nodes/{node_id}/revoke-credentials", headers={"authorization": "Bearer admin-test"})
        assert revoked.status_code == 200
        assert client.post("/api/nodes/heartbeat", json={}, headers=headers).status_code == 401
        assert client.post("/api/nodes/jobs/claim?wait=0", headers=headers).status_code == 401
        assert client.post("/api/nodes/jobs/job_x/result", json={"output_text": "no"}, headers=headers).status_code == 401
        assert client.post("/api/nodes/credentials/rotate", headers=headers).status_code == 401
    with session_scope(factory) as session:
        node = session.get(Node, node_id)
        with pytest.raises(MeshError):
            rotate_credential(session, node)


def test_gate5_queue_is_bounded(tmp_path):
    settings = make_settings(
        tmp_path,
        max_queue_depth=2,
        max_global_inflight=1,
        anon_inflight=8,
        verify_sample_rate=0,
    )
    _engine, factory = build_database(settings)
    with session_scope(factory) as session:
        node, _token, _receipt = register_node(session, settings, _spec("a"), "10.0.0.1")
        _job(session, settings)
        _job(session, settings)
        with pytest.raises(MeshError) as full:
            _job(session, settings)
        assert full.value.code == "queue_full"
        assert session.query(Job).filter(Job.status == "queued").count() == 2
        assert claim_job(session, settings, node) is not None
        with pytest.raises(MeshError) as overloaded:
            _job(session, settings)
        assert overloaded.value.code == "overloaded"
        assert session.query(Job).count() == 2


def test_gate6_worker_container_is_isolated():
    compose = open("docker-compose.yml", encoding="utf-8").read()
    dockerfile = open("node/Dockerfile", encoding="utf-8").read()
    entry = open("node/entrypoint.sh", encoding="utf-8").read()
    pins = open("docker/IMAGE_PINS", encoding="utf-8").read()
    node = compose.split("node-b:", 1)[0].split("node:", 1)[1]
    blob = node + compose.split("node-b:", 1)[1]
    assert 'user: "10001:10001"' in blob
    assert "read_only: true" in blob
    assert "cap_drop:" in blob and "ALL" in blob
    assert "no-new-privileges:true" in blob
    assert "pids_limit:" in blob and "mem_limit:" in blob and "cpus:" in blob
    assert "/tmp" in blob and "GPU_MESH_STATE: /tmp/node.json" in blob
    for banned in ("docker.sock", "privileged:", "network_mode:", "GPU_MESH_ADMIN_TOKEN", "DATABASE_URL", "/var/run/docker"):
        assert banned not in blob
    assert "USER gpumesh" in dockerfile
    assert "image pin: docker/IMAGE_PINS" in dockerfile
    assert "python:3.12-slim" in pins
    assert 'id -u' in entry and "exec python -m gpumesh_node" in entry


def test_gate7_disagreement_does_not_credit(tmp_path):
    settings = make_settings(tmp_path, verify_sample_rate=1)
    _engine, factory = build_database(settings)
    messages = [{"role": "user", "content": "Say hello in one sentence."}]
    with session_scope(factory) as session:
        origin, _to, _ro = register_node(session, settings, _spec("origin"), "10.0.0.3")
        checker, _tc, _rc = register_node(session, settings, _spec("checker"), "10.0.0.4")
        job = enqueue_inference(
            session,
            settings,
            model="alpha",
            messages=messages,
            temperature=0,
            max_tokens=32,
            seed=0,
            stop=None,
            client_key="ip:gate",
        )
        claimed = claim_job(session, settings, origin)
        proofs = _proof(messages, "alpha", good=False)
        submit_result(
            session,
            settings,
            origin,
            job.id,
            {
                "output_text": "WRONG",
                "fencing_token": claimed.lease_generation,
                "prompt_tokens": 1,
                "completion_tokens": 1,
                "duration_ms": 6,
                "toploc_proofs": proofs,
                "toploc_source": "prompt-trace",
            },
        )
        check = claim_job(session, settings, checker)
        assert check is not None and check.kind == "verification"
        submit_result(
            session,
            settings,
            checker,
            check.id,
            {
                "output_text": "a completely different sentence",
                "fencing_token": check.lease_generation,
                "prompt_tokens": 1,
                "completion_tokens": 4,
                "duration_ms": 7,
                "toploc_proofs": _proof(messages, "alpha", good=True),
                "toploc_source": "prompt-trace",
            },
        )
        parent = session.get(Job, job.id)
        assert parent.status == "disputed"
        assert parent.credits_awarded == 0
        assert session.query(Settlement).filter(Settlement.idempotency_key == f"{job.id}:worker_award").count() == 0
        assert origin.credits <= 0
        assert origin.strikes >= 1


def test_gate8_restart_keeps_one_credit(tmp_path):
    settings = make_settings(tmp_path, verify_sample_rate=0)
    engine, factory = build_database(settings)
    with session_scope(factory) as session:
        node, _token, _receipt = register_node(session, settings, _spec("a"), "10.1.0.1")
        job = _job(session, settings)
        claimed = claim_job(session, settings, node)
        generation = claimed.lease_generation
        node_id = node.id
        job_id = job.id
    engine.dispose()
    engine, factory = build_database(settings)
    with session_scope(factory) as session:
        node = session.get(Node, node_id)
        submit_result(
            session,
            settings,
            node,
            job_id,
            {"output_text": "still here", "fencing_token": generation, "prompt_tokens": 1, "completion_tokens": 2, "duration_ms": 4},
        )
        settle_once(
            session,
            key=f"{job_id}:worker_award",
            job=session.get(Job, job_id),
            node=node,
            kind="inference_receipt",
            amount=3,
            payload={"schema": "gpumesh.inference_receipt.v1", "job_id": job_id},
            settings=settings,
        )
        length = session.query(Settlement).count()
        report = verify_session(session)
        assert report["ok"] is True
    engine.dispose()
    _engine, factory = build_database(settings)
    with session_scope(factory) as session:
        node = session.get(Node, node_id)
        replay = submit_result(
            session,
            settings,
            node,
            job_id,
            {"output_text": "rewritten", "completion_tokens": 50},
        )
        settle_once(
            session,
            key=f"{job_id}:worker_award",
            job=session.get(Job, job_id),
            node=node,
            kind="inference_receipt",
            amount=3,
            payload={"schema": "gpumesh.inference_receipt.v1", "job_id": job_id},
            settings=settings,
        )
        assert replay["output_hash"] != ""
        assert session.get(Job, job_id).output_text == "still here"
        assert session.query(Settlement).count() == length
        assert node.credits + node.escrow_credits == 3
        assert verify_session(session)["ok"] is True

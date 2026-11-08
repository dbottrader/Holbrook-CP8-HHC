"""Volunteer jobs execute at temperature 0 with a stored seed, and agree on exact text."""

import json

import pytest

from gpumesh.db import Job, LedgerEntry, Node, build_database, session_scope
from gpumesh.errors import MeshError
from gpumesh.textutil import mesh_seed
from gpumesh.work import claim_job, enqueue_inference, job_for_node, register_node, submit_result
from gpumesh_node.runtime import ollama_payload
from tests.conftest import make_settings
from tests.doubles import DIGEST, MODEL


def _spec(name: str, model: str = MODEL) -> dict:
    return {
        "name": name,
        "backend": "llamacpp",
        "gpu": {"vendor": "cpu", "model": "cpu", "vram_mb": 0, "driver": "", "count": 0},
        "models": [{"id": model, "resident": True, "source": "llama.cpp", "digest": DIGEST}],
        "version": "test",
    }


def test_ollama_payload_sends_seed_zero_and_top_k_one():
    payload = ollama_payload(
        {
            "model": MODEL,
            "messages": [{"role": "user", "content": "hi"}],
            "temperature": 0.7,
            "max_tokens": 16,
            "seed": 0,
        }
    )
    assert payload["options"]["seed"] == 0
    assert "seed" in payload["options"]
    assert payload["options"]["temperature"] == 0
    assert payload["options"]["top_k"] == 1
    missing = ollama_payload({"model": MODEL, "messages": [], "max_tokens": 8})
    assert missing["options"]["seed"] == 0


def test_canned_registration_is_rejected(tmp_path):
    settings = make_settings(tmp_path, verify_sample_rate=0)
    _engine, factory = build_database(settings)
    with session_scope(factory) as session:
        spec = _spec("nope")
        spec["backend"] = "cpu-fallback"
        with pytest.raises(MeshError) as rejected:
            register_node(session, settings, spec, "10.0.0.1")
        assert rejected.value.code == "canned_backend"
        spec["backend"] = "llamacpp"
        spec["models"] = [{"id": "mock-tiny", "resident": True, "source": "cpu-fallback", "digest": "cpu-fallback"}]
        with pytest.raises(MeshError) as model:
            register_node(session, settings, spec, "10.0.0.2")
        assert model.value.code == "canned_backend"


def test_two_runs_agree_and_the_parent_temperature_is_forced(tmp_path, monkeypatch):
    monkeypatch.setattr("gpumesh_node.toploc_proof.library_ready", lambda: False)
    settings = make_settings(tmp_path, verify_sample_rate=1)
    _engine, factory = build_database(settings)
    messages = [{"role": "user", "content": "Say hello in one sentence."}]
    text = "DETERMINISTIC_MESH_TEXT"
    with session_scope(factory) as session:
        origin, _token, _receipt = register_node(session, settings, _spec("origin"), "10.0.0.3")
        checker, _token_b, _receipt_b = register_node(session, settings, _spec("checker"), "10.0.0.4")
        job = enqueue_inference(
            session,
            settings,
            model=MODEL,
            messages=messages,
            temperature=0.7,
            max_tokens=32,
            seed=12345,
            stop=None,
            client_key="ip:det",
        )
        assert job.temperature == 0
        assert job.requested_temperature == 0.7
        assert job.seed == mesh_seed(job.id)
        assert job.seed != 12345
        claimed = claim_job(session, settings, origin)
        assert claimed is not None
        forwarded = job_for_node(claimed)
        assert forwarded["temperature"] == 0
        assert forwarded["seed"] == job.seed
        assert forwarded["max_tokens"] == 32
        submit_result(
            session,
            settings,
            origin,
            job.id,
            {
                "output_text": text,
                "fencing_token": claimed.lease_generation,
                "prompt_tokens": 3,
                "completion_tokens": 2,
                "duration_ms": 8,
            },
        )
        check = claim_job(session, settings, checker)
        assert check is not None and check.kind == "verification"
        assert check.temperature == job.temperature
        assert check.seed == job.seed
        assert check.max_tokens == job.max_tokens
        assert check.model_digest == claimed.model_digest == DIGEST
        assert json.loads(check.messages_json) == messages
        second = job_for_node(check)
        assert second["seed"] == job.seed
        assert second["temperature"] == 0
        submit_result(
            session,
            settings,
            checker,
            check.id,
            {
                "output_text": text,
                "fencing_token": check.lease_generation,
                "prompt_tokens": 3,
                "completion_tokens": 2,
                "duration_ms": 9,
            },
        )
        parent = session.get(Job, job.id)
        assert parent is not None
        assert parent.status == "verified"
        assert parent.verdict == "agree"
        assert parent.credits_awarded > 0
        payloads = [json.loads(row.payload) for row in session.query(LedgerEntry).all()]
        assert any(item.get("match_rule") == "exact" and item.get("verifier_decision") == "agree" for item in payloads)


def test_normalized_whitespace_is_recorded_and_a_mismatch_is_not_sampling(tmp_path, monkeypatch):
    monkeypatch.setattr("gpumesh_node.toploc_proof.library_ready", lambda: False)
    settings = make_settings(tmp_path, verify_sample_rate=1)
    _engine, factory = build_database(settings)
    with session_scope(factory) as session:
        origin, _a, _b = register_node(session, settings, _spec("origin"), "10.0.0.5")
        checker, _c, _d = register_node(session, settings, _spec("checker"), "10.0.0.6")
        job = enqueue_inference(
            session,
            settings,
            model=MODEL,
            messages=[{"role": "user", "content": "hi"}],
            temperature=0,
            max_tokens=16,
            seed=None,
            stop=None,
            client_key="ip:norm",
        )
        claimed = claim_job(session, settings, origin)
        submit_result(
            session,
            settings,
            origin,
            job.id,
            {
                "output_text": "Hello\u00a0world",
                "fencing_token": claimed.lease_generation,
                "prompt_tokens": 1,
                "completion_tokens": 2,
                "duration_ms": 4,
            },
        )
        check = claim_job(session, settings, checker)
        submit_result(
            session,
            settings,
            checker,
            check.id,
            {
                "output_text": "Hello world",
                "fencing_token": check.lease_generation,
                "prompt_tokens": 1,
                "completion_tokens": 2,
                "duration_ms": 4,
            },
        )
        parent = session.get(Job, job.id)
        assert parent.verdict == "agree"
        payloads = [json.loads(row.payload) for row in session.query(LedgerEntry).all()]
        assert any(item.get("match_rule") == "normalized" for item in payloads)

        other = enqueue_inference(
            session,
            settings,
            model=MODEL,
            messages=[{"role": "user", "content": "again"}],
            temperature=1.2,
            max_tokens=16,
            seed=0,
            stop=None,
            client_key="ip:norm",
        )
        assert other.temperature == 0
        again = claim_job(session, settings, origin)
        submit_result(
            session,
            settings,
            origin,
            other.id,
            {
                "output_text": "alpha",
                "fencing_token": again.lease_generation,
                "prompt_tokens": 1,
                "completion_tokens": 1,
                "duration_ms": 4,
            },
        )
        mismatch = claim_job(session, settings, checker)
        submit_result(
            session,
            settings,
            checker,
            mismatch.id,
            {
                "output_text": "omega",
                "fencing_token": mismatch.lease_generation,
                "prompt_tokens": 1,
                "completion_tokens": 1,
                "duration_ms": 4,
            },
        )
        disputed = session.get(Job, other.id)
        assert disputed.status == "disputed"
        assert disputed.verdict == "disagree_deterministic"
        assert disputed.credits_awarded == 0


def test_legacy_canned_node_cannot_claim(tmp_path):
    settings = make_settings(tmp_path, verify_sample_rate=0)
    _engine, factory = build_database(settings)
    with session_scope(factory) as session:
        node = Node(
            id="node_legacy",
            name="legacy",
            token_hash="legacy-hash",
            backend="cpu-fallback",
            models_json=json.dumps([{"id": "mock-tiny", "source": "cpu-fallback", "digest": "cpu-fallback"}]),
            status="online",
            max_inflight=1,
        )
        session.add(node)
        session.flush()
        with pytest.raises(MeshError) as rejected:
            claim_job(session, settings, node)
        assert rejected.value.code == "canned_backend"

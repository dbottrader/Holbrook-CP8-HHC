import time

from gpumesh.db import build_database, session_scope
from gpumesh.work import (
    claim_job,
    enqueue_inference,
    inference_credits,
    register_node,
    submit_result,
    sweep,
)
from tests.conftest import make_settings


def _spec(name: str, model: str, vram: int = 0) -> dict:
    return {
        "name": name,
        "backend": "cpu" if vram == 0 else "ollama",
        "gpu": {"vendor": "nvidia" if vram else "cpu", "model": "GPU" if vram else "cpu", "vram_mb": vram, "driver": "", "count": 1 if vram else 0},
        "models": [{"id": model, "resident": True, "source": "test"}],
        "version": "test",
    }


def test_claim_respects_model_and_inflight(tmp_path):
    settings = make_settings(tmp_path, verify_sample_rate=0)
    _engine, factory = build_database(settings)
    with session_scope(factory) as session:
        node_a, _token, _receipt = register_node(session, settings, _spec("a", "alpha"), "10.0.0.1")
        node_b, _token_b, _receipt_b = register_node(session, settings, _spec("b", "beta"), "10.0.0.2")
        job = enqueue_inference(
            session,
            settings,
            model="alpha",
            messages=[{"role": "user", "content": "hi"}],
            temperature=0,
            max_tokens=32,
            seed=0,
            stop=None,
            client_key="ip:test",
        )
        assert claim_job(session, settings, node_b) is None
        claimed = claim_job(session, settings, node_a)
        assert claimed is not None and claimed.id == job.id
        assert node_a.inflight == 1
        assert claim_job(session, settings, node_a) is None
        body = submit_result(
            session,
            settings,
            node_a,
            job.id,
            {
                "output_text": "ok",
                "prompt_tokens": 1,
                "completion_tokens": 2,
                "duration_ms": 5,
                "finish_reason": "stop",
                "fencing_token": claimed.lease_generation,
            },
        )
        assert body["ok"] is True
        assert node_a.inflight == 0
        assert node_a.credits == 0
        assert body["status"] == "completed"


def test_deadline_requeues_and_excludes_the_node(tmp_path):
    settings = make_settings(tmp_path, verify_sample_rate=0, job_timeout_sec=30)
    _engine, factory = build_database(settings)
    with session_scope(factory) as session:
        node, _token, _receipt = register_node(session, settings, _spec("a", "alpha"), "10.0.0.1")
        job = enqueue_inference(
            session,
            settings,
            model="alpha",
            messages=[{"role": "user", "content": "hi"}],
            temperature=0,
            max_tokens=16,
            seed=None,
            stop=None,
            client_key="ip:test",
        )
        claimed = claim_job(session, settings, node)
        assert claimed is not None and claimed.id == job.id
        claimed.deadline_at = time.time() - 5
        session.flush()
        sweep(session, settings)
        assert claimed.status == "queued"
        assert node.inflight == 0
        assert node.id in claimed.excluded_nodes_json
        assert claim_job(session, settings, node) is None


def test_vram_weights_credits(tmp_path):
    settings = make_settings(tmp_path, verify_sample_rate=0)
    _engine, factory = build_database(settings)
    with session_scope(factory) as session:
        node, _token, _receipt = register_node(session, settings, _spec("big", "alpha", vram=24576), "10.0.0.8")
        job = enqueue_inference(
            session,
            settings,
            model="alpha",
            messages=[{"role": "user", "content": "hi"}],
            temperature=0,
            max_tokens=16,
            seed=0,
            stop=None,
            client_key="ip:test",
        )
        claim_job(session, settings, node)
        submit_result(
            session,
            settings,
            node,
            job.id,
            {
                "output_text": "four words here now",
                "prompt_tokens": 1,
                "completion_tokens": 4,
                "duration_ms": 9,
                "fencing_token": job.lease_generation,
            },
        )
        assert inference_credits(node, 4) == 32
        assert node.credits == 0

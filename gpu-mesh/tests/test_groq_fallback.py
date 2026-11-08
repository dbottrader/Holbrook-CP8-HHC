"""Groq runs only when no volunteer is online, and the receipt is signed."""

import json
import socket

import httpx
import pytest
from httpx import ASGITransport

from gpumesh.canon import sha256_text
from gpumesh.db import build_database
from gpumesh.errors import MeshError
from gpumesh.ledger_backend import activate
from gpumesh.main import create_app
from gpumesh.signing import verify_digest
from gpumesh.typed import digest_for
from tests.conftest import make_settings

PROMPT = "Reply with exactly the token: GROQ_MESH_OK"
MODEL = "openai/gpt-oss-20b"


def _reply(model: str, text: str, request_id: str = "req_test") -> httpx.Response:
    return httpx.Response(
        200,
        json={
            "id": request_id,
            "model": model,
            "choices": [{"message": {"role": "assistant", "content": text}}],
            "usage": {"prompt_tokens": 9, "completion_tokens": 3},
        },
    )


def _app(tmp_path, transport, **overrides):
    application = create_app(make_settings(tmp_path, groq_api_key="test-key", **overrides))
    return application, transport


def _claim(receipt: dict) -> dict:
    message = receipt["typed_data"]["message"]
    return {
        "actor": message["actor"],
        "amount": message["amount"],
        "kind": message["kind"],
        "ledger_seq": message["ledgerSeq"],
        "payload_hash": message["payloadHash"],
        "prev_hash": message["prevHash"],
        "settlement_id": message["settlementId"],
        "ts": message["ts"],
        "verifier_ids": message["verifierIds"],
        "worker_id": message["workerId"],
    }


@pytest.mark.asyncio
async def test_exact_match_is_signed_when_no_worker_is_online(tmp_path):
    seen = []

    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        seen.append(body)
        assert request.headers["authorization"] == "Bearer test-key"
        assert body["max_completion_tokens"] <= 256
        return _reply(body["model"], "GROQ_MESH_OK")

    app, transport = _app(tmp_path, httpx.MockTransport(handler))
    async with app.router.lifespan_context(app):
        app.state.groq_transport = transport
        async with httpx.AsyncClient(transport=ASGITransport(app=app), base_url="http://mesh") as client:
            listed = await client.get("/v1/models")
            assert MODEL in {row["id"] for row in listed.json()["data"]}
            done = await client.post(
                "/v1/chat/completions",
                json={"model": MODEL, "messages": [{"role": "user", "content": PROMPT}], "temperature": 0, "max_tokens": 16},
            )
    assert done.status_code == 200
    body = done.json()
    assert body["choices"][0]["message"]["content"] == "GROQ_MESH_OK"
    assert body["gpumesh"]["provider"] == "groq"
    assert body["gpumesh"]["verification"]["ok"] is True
    assert body["gpumesh"]["verification"]["method"] == "exact_match"
    assert body["gpumesh"]["promotion"] == "HOLD"
    receipt = body["gpumesh"]["signed_receipt"]
    assert receipt["amount"] == 0
    assert receipt["kind"] == "groq_inference_receipt"
    assert sha256_text(receipt["body_json"]) == receipt["hash"]
    assert verify_digest(receipt["signer"], digest_for(**_claim(receipt)), receipt["signature"])
    assert len(seen) == 1


@pytest.mark.asyncio
async def test_second_model_disagreement_is_recorded(tmp_path):
    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        text = "alpha reply" if body["model"] == MODEL else "beta reply"
        return _reply(body["model"], text)

    app, transport = _app(tmp_path, httpx.MockTransport(handler))
    async with app.router.lifespan_context(app):
        app.state.groq_transport = transport
        async with httpx.AsyncClient(transport=ASGITransport(app=app), base_url="http://mesh") as client:
            done = await client.post(
                "/v1/chat/completions",
                json={"model": MODEL, "messages": [{"role": "user", "content": "Say anything."}], "temperature": 0.2},
            )
    assert done.status_code == 200
    mesh = done.json()["gpumesh"]
    assert mesh["verification"]["method"] == "second_model"
    assert mesh["verification"]["ok"] is False
    assert mesh["signed_receipt"]["amount"] == 0


@pytest.mark.asyncio
async def test_online_volunteer_is_not_sent_to_groq(tmp_path):
    def handler(_request: httpx.Request) -> httpx.Response:
        raise AssertionError("groq was called while a volunteer was online")

    app, transport = _app(tmp_path, httpx.MockTransport(handler))
    async with app.router.lifespan_context(app):
        app.state.groq_transport = transport
        async with httpx.AsyncClient(transport=ASGITransport(app=app), base_url="http://mesh") as client:
            registered = await client.post(
                "/api/nodes/register",
                json={
                    "name": "rig",
                    "backend": "ollama",
                    "models": [{"id": MODEL, "resident": True}],
                    "gpu": {"model": "cpu", "vram_mb": 0, "count": 0, "driver": ""},
                },
            )
            assert registered.status_code == 200
            queued = await client.post(
                "/v1/chat/completions",
                headers={"X-GPUMesh-Wait-Seconds": "0"},
                json={"model": MODEL, "messages": [{"role": "user", "content": PROMPT}], "temperature": 0},
            )
    assert queued.status_code == 202


@pytest.mark.asyncio
async def test_missing_key_does_not_advertise_groq(tmp_path):
    app = create_app(make_settings(tmp_path, groq_api_key=""))
    async with app.router.lifespan_context(app):
        async with httpx.AsyncClient(transport=ASGITransport(app=app), base_url="http://mesh") as client:
            missing = await client.post(
                "/v1/chat/completions",
                json={"model": MODEL, "messages": [{"role": "user", "content": PROMPT}]},
            )
    assert missing.status_code == 404
    assert missing.json()["error"]["code"] == "model_not_found"


def test_onchain_backend_is_a_config_switch_and_does_not_open_a_socket(tmp_path, monkeypatch):
    def boom(*_args, **_kwargs):
        raise AssertionError("on-chain backend tried to use the network")

    monkeypatch.setattr(socket, "socket", boom)
    try:
        with pytest.raises(MeshError) as refused:
            build_database(make_settings(tmp_path, ledger_backend="onchain"))
        assert refused.value.code == "onchain_disabled"
        assert "does not open a socket" in refused.value.message
        assert "0xdfFE664d23E30Baff7Ad4d16831aD625Cc90bcCA" in refused.value.message
    finally:
        activate("simulated")

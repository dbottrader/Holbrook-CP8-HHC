"""Cloudflare Workers AI runs only on the free-tier allowlist, and the receipt is signed."""

import json

import httpx
import pytest
from httpx import ASGITransport

from gpumesh.canon import sha256_text
from gpumesh.cloudflare_provider import (
    CF_TEST_EXPECTED,
    CF_TEST_PROMPT,
    DEFAULT_MODEL,
    DEFAULT_VERIFY_MODEL,
    CloudflareCallError,
    assert_model_allowed,
    is_paid_required_model,
    reserve_budget,
    resolve_credentials,
)
from gpumesh.main import create_app
from gpumesh.signing import verify_digest
from gpumesh.typed import digest_for
from tests.conftest import make_settings

ACCOUNT = "test-account-id"
TOKEN = "test-cloudflare-token"


def _cf_settings(tmp_path, **overrides):
    values = dict(
        cloudflare_api_token=TOKEN,
        cloudflare_account_id=ACCOUNT,
        cloudflare_budget_path=str(tmp_path / "cf-budget.json"),
        cloudflare_secrets_dir="",
    )
    values.update(overrides)
    return make_settings(tmp_path, **values)


def _reply(text: str, request_id: str = "cf_req_test", neurons: float = 0.4, prompt_tokens: int = 9, completion_tokens: int = 3) -> httpx.Response:
    return httpx.Response(
        200,
        json={
            "success": True,
            "result": {
                "response": text,
                "usage": {
                    "prompt_tokens": prompt_tokens,
                    "completion_tokens": completion_tokens,
                    "neurons": neurons,
                },
            },
            "id": request_id,
        },
    )


def _app(tmp_path, transport, **overrides):
    application = create_app(_cf_settings(tmp_path, **overrides))
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


def test_paid_models_are_rejected():
    assert is_paid_required_model("@cf/moonshotai/kimi-k2.6")
    with pytest.raises(CloudflareCallError) as denied:
        assert_model_allowed("@cf/moonshotai/kimi-k2.6")
    assert denied.value.code == "paid_model_forbidden"
    with pytest.raises(CloudflareCallError) as also:
        assert_model_allowed("@cf/moonshotai/kimi-k2.7-code")
    assert also.value.code == "paid_model_forbidden"
    with pytest.raises(CloudflareCallError) as unknown:
        assert_model_allowed("@cf/meta/llama-3.1-70b-instruct-fp8-fast")
    assert unknown.value.code == "model_not_allowed"
    assert assert_model_allowed(DEFAULT_MODEL) == DEFAULT_MODEL


def test_file_secrets_are_not_read_unless_dir_is_set(tmp_path, monkeypatch):
    monkeypatch.delenv("CLOUDFLARE_API_TOKEN", raising=False)
    monkeypatch.delenv("CLOUDFLARE_ACCOUNT_ID", raising=False)
    monkeypatch.delenv("CLOUDFLARE_SECRETS_DIR", raising=False)
    monkeypatch.delenv("GPU_MESH_CLOUDFLARE_SECRETS_DIR", raising=False)
    settings = make_settings(tmp_path)
    token, account = resolve_credentials(settings)
    assert token == ""
    assert account == ""


def test_secret_dir_fallback(tmp_path, monkeypatch):
    monkeypatch.delenv("CLOUDFLARE_API_TOKEN", raising=False)
    monkeypatch.delenv("CLOUDFLARE_ACCOUNT_ID", raising=False)
    secrets = tmp_path / "secrets"
    secrets.mkdir()
    (secrets / "cloudflare_api_token").write_text("file-token\n", encoding="utf-8")
    (secrets / "cloudflare_account_id").write_text("file-account\n", encoding="utf-8")
    settings = make_settings(tmp_path, cloudflare_secrets_dir=str(secrets))
    token, account = resolve_credentials(settings)
    assert token == "file-token"
    assert account == "file-account"


@pytest.mark.asyncio
async def test_exact_match_is_signed_when_no_worker_is_online(tmp_path):
    seen = []

    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        seen.append(body)
        assert request.headers["authorization"] == f"Bearer {TOKEN}"
        assert request.headers["cf-aig-gateway-id"] == "default"
        assert str(request.url).endswith(f"/accounts/{ACCOUNT}/ai/run")
        assert body["model"] == DEFAULT_MODEL
        assert body["input"]["max_tokens"] <= 128
        # The token must never appear in the JSON body.
        assert TOKEN not in json.dumps(body)
        return _reply(CF_TEST_EXPECTED)

    app, transport = _app(tmp_path, httpx.MockTransport(handler))
    async with app.router.lifespan_context(app):
        app.state.cloudflare_transport = transport
        async with httpx.AsyncClient(transport=ASGITransport(app=app), base_url="http://mesh") as client:
            listed = await client.get("/v1/models")
            assert DEFAULT_MODEL in {row["id"] for row in listed.json()["data"]}
            done = await client.post(
                "/v1/chat/completions",
                json={
                    "model": DEFAULT_MODEL,
                    "messages": [{"role": "user", "content": CF_TEST_PROMPT}],
                    "temperature": 0,
                    "max_tokens": 16,
                },
            )
    assert done.status_code == 200, done.text
    body = done.json()
    assert body["choices"][0]["message"]["content"] == CF_TEST_EXPECTED
    assert body["gpumesh"]["provider"] == "cloudflare"
    assert body["gpumesh"]["verification"]["ok"] is True
    assert body["gpumesh"]["verification"]["method"] == "exact_match"
    assert body["gpumesh"]["promotion"] == "HOLD"
    receipt = body["gpumesh"]["signed_receipt"]
    assert receipt["amount"] == 0
    assert receipt["kind"] == "cloudflare_inference_receipt"
    assert sha256_text(receipt["body_json"]) == receipt["hash"]
    assert TOKEN not in json.dumps(body)
    assert verify_digest(receipt["signer"], digest_for(**_claim(receipt)), receipt["signature"])
    assert len(seen) == 1


@pytest.mark.asyncio
async def test_second_model_disagreement_is_recorded(tmp_path):
    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        text = "alpha reply" if body["model"] == DEFAULT_MODEL else "beta reply"
        return _reply(text)

    app, transport = _app(tmp_path, httpx.MockTransport(handler))
    async with app.router.lifespan_context(app):
        app.state.cloudflare_transport = transport
        async with httpx.AsyncClient(transport=ASGITransport(app=app), base_url="http://mesh") as client:
            done = await client.post(
                "/v1/chat/completions",
                json={"model": DEFAULT_MODEL, "messages": [{"role": "user", "content": "Say anything."}], "temperature": 0.2},
            )
    assert done.status_code == 200, done.text
    mesh = done.json()["gpumesh"]
    assert mesh["verification"]["method"] == "second_model"
    assert mesh["verification"]["ok"] is False
    assert mesh["verification"]["verifier_ids"] == DEFAULT_VERIFY_MODEL
    assert mesh["signed_receipt"]["amount"] == 0


@pytest.mark.asyncio
async def test_online_volunteer_is_not_sent_to_cloudflare(tmp_path):
    def handler(_request: httpx.Request) -> httpx.Response:
        raise AssertionError("cloudflare was called while a volunteer was online")

    app, transport = _app(tmp_path, httpx.MockTransport(handler))
    async with app.router.lifespan_context(app):
        app.state.cloudflare_transport = transport
        async with httpx.AsyncClient(transport=ASGITransport(app=app), base_url="http://mesh") as client:
            registered = await client.post(
                "/api/nodes/register",
                json={
                    "name": "rig",
                    "backend": "ollama",
                    "models": [{"id": DEFAULT_MODEL, "resident": True}],
                    "gpu": {"model": "cpu", "vram_mb": 0, "count": 0, "driver": ""},
                },
            )
            assert registered.status_code == 200
            queued = await client.post(
                "/v1/chat/completions",
                headers={"X-GPUMesh-Wait-Seconds": "0"},
                json={"model": DEFAULT_MODEL, "messages": [{"role": "user", "content": CF_TEST_PROMPT}], "temperature": 0},
            )
    assert queued.status_code == 202


@pytest.mark.asyncio
async def test_missing_credentials_do_not_advertise_cloudflare(tmp_path):
    app = create_app(make_settings(tmp_path, cloudflare_api_token="", cloudflare_account_id="", cloudflare_secrets_dir=""))
    async with app.router.lifespan_context(app):
        async with httpx.AsyncClient(transport=ASGITransport(app=app), base_url="http://mesh") as client:
            listed = await client.get("/v1/models")
            assert DEFAULT_MODEL not in {row["id"] for row in listed.json()["data"]}
            missing = await client.post(
                "/v1/chat/completions",
                json={"model": DEFAULT_MODEL, "messages": [{"role": "user", "content": CF_TEST_PROMPT}]},
            )
    assert missing.status_code == 404
    assert missing.json()["error"]["code"] == "model_not_found"


@pytest.mark.asyncio
async def test_paid_model_setting_is_not_advertised_or_called(tmp_path):
    def handler(_request: httpx.Request) -> httpx.Response:
        raise AssertionError("paid Cloudflare model was called")

    app, transport = _app(
        tmp_path,
        httpx.MockTransport(handler),
        cloudflare_model="@cf/moonshotai/kimi-k2.6",
    )
    async with app.router.lifespan_context(app):
        app.state.cloudflare_transport = transport
        async with httpx.AsyncClient(transport=ASGITransport(app=app), base_url="http://mesh") as client:
            listed = await client.get("/v1/models")
            assert "@cf/moonshotai/kimi-k2.6" not in {row["id"] for row in listed.json()["data"]}
            denied = await client.post(
                "/v1/chat/completions",
                json={
                    "model": "@cf/moonshotai/kimi-k2.6",
                    "messages": [{"role": "user", "content": CF_TEST_PROMPT}],
                },
            )
    assert denied.status_code == 404


def test_daily_neuron_cap_is_enforced(tmp_path):
    settings = _cf_settings(tmp_path, cloudflare_daily_neuron_cap=0.0001, cloudflare_daily_call_cap=40)
    with pytest.raises(CloudflareCallError) as denied:
        reserve_budget(
            settings,
            model=DEFAULT_MODEL,
            messages=[{"role": "user", "content": "hello" * 40}],
            max_tokens=32,
            calls=1,
        )
    assert denied.value.code == "daily_neuron_cap"


def test_daily_call_cap_is_enforced(tmp_path):
    settings = _cf_settings(tmp_path, cloudflare_daily_call_cap=1, cloudflare_daily_neuron_cap=2000)
    reserve_budget(settings, model=DEFAULT_MODEL, messages=[{"role": "user", "content": "hi"}], max_tokens=8, calls=1)
    with pytest.raises(CloudflareCallError) as denied:
        reserve_budget(settings, model=DEFAULT_MODEL, messages=[{"role": "user", "content": "hi"}], max_tokens=8, calls=1)
    assert denied.value.code == "daily_call_cap"

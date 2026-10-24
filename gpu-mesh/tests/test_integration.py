from __future__ import annotations

import asyncio
import io
import json
import tarfile

import httpx
import pytest
from httpx import ASGITransport

from gpumesh.main import create_app
from gpumesh_node.agent import NodeAgent
from gpumesh_node.runtime import CpuFallbackRuntime, InferenceResult, fallback_text
from tests.conftest import make_settings

ADMIN = {"authorization": "Bearer admin-test"}
CHAT = {
    "model": "mock-tiny",
    "messages": [{"role": "user", "content": "Say hello in one sentence."}],
    "temperature": 0,
    "max_tokens": 64,
}


def _spec(name: str) -> dict:
    return {
        "name": name,
        "backend": "cpu",
        "gpu": {"vendor": "cpu", "model": "cpu", "vram_mb": 0, "driver": "", "count": 0},
        "models": [{"id": "mock-tiny", "resident": True, "source": "cpu-fallback"}],
        "version": "test",
    }


class EvilRuntime:
    name = "cpu"

    async def list_models(self) -> list[dict]:
        return [{"id": "mock-tiny", "resident": True, "source": "evil"}]

    async def complete(self, job: dict, on_delta) -> InferenceResult:
        text = "WRONG"
        if on_delta is not None:
            await on_delta(text)
        return InferenceResult(text, 1, 1, 4, "stop")


async def _pump(agent: NodeAgent, stop: asyncio.Event) -> None:
    while not stop.is_set():
        try:
            await agent.heartbeat()
            job = await agent.claim(0.3)
            if job:
                await agent.execute(job)
        except Exception:
            if stop.is_set():
                return
            await asyncio.sleep(0.05)


async def _boot(client: httpx.AsyncClient, runtime, name: str) -> NodeAgent:
    agent = NodeAgent(base_url="http://mesh", runtime=runtime, name=name, http=client, state_path=None)
    await agent.register()
    return agent


async def _wait_kinds(client: httpx.AsyncClient, kinds: set[str], timeout: float = 8) -> list[str]:
    deadline = asyncio.get_event_loop().time() + timeout
    seen: list[str] = []
    while asyncio.get_event_loop().time() < deadline:
        response = await client.get("/api/receipts?limit=40")
        seen = [row["kind"] for row in response.json()["receipts"]]
        if kinds.issubset(set(seen)):
            return seen
        await asyncio.sleep(0.05)
    raise AssertionError(seen)


@pytest.mark.asyncio
async def test_chat_stream_receipt_and_idempotent_result(mesh):
    _app, client = mesh
    stop = asyncio.Event()
    node_client = httpx.AsyncClient(transport=ASGITransport(app=_app), base_url="http://mesh")
    agent = await _boot(node_client, CpuFallbackRuntime(["mock-tiny"]), "honest-0")
    task = asyncio.create_task(_pump(agent, stop))
    try:
        response = await client.post("/v1/chat/completions", json=CHAT)
        assert response.status_code == 200, response.text
        body = response.json()
        expected = fallback_text(CHAT["messages"], 64)
        assert body["choices"][0]["message"]["content"] == expected
        assert body["usage"]["total_tokens"] == body["usage"]["prompt_tokens"] + body["usage"]["completion_tokens"]
        assert len(body["gpumesh"]["receipt"]) == 64
        credits = (await client.get("/api/stats")).json()["nodes"][0]["credits"]

        again = await node_client.post(
            f"/api/nodes/jobs/{body['gpumesh']['job_id']}/result",
            headers={"authorization": f"Bearer {agent.token}"},
            json={"output_text": expected, "prompt_tokens": 1, "completion_tokens": 1, "duration_ms": 1},
        )
        assert again.status_code == 200
        assert again.json()["receipt"] == body["gpumesh"]["receipt"]
        assert (await client.get("/api/stats")).json()["nodes"][0]["credits"] == credits

        async with client.stream("POST", "/v1/chat/completions", json={**CHAT, "stream": True}) as streamed:
            assert streamed.status_code == 200
            assert "text/event-stream" in streamed.headers["content-type"]
            pieces = []
            done = False
            async for line in streamed.aiter_lines():
                if not line.startswith("data:"):
                    continue
                raw = line[5:].strip()
                if raw == "[DONE]":
                    done = True
                    continue
                payload = json.loads(raw)
                assert "error" not in payload
                pieces.append(payload["choices"][0]["delta"].get("content") or "")
            assert done
            assert "".join(pieces) == expected

        chain = await client.get("/api/ledger/verify")
        assert chain.json()["ok"] is True
        jobs = (await client.get("/api/stats")).json()["recent_jobs"]
        assert any(job["kind"] == "verification" for job in jobs)
    finally:
        stop.set()
        task.cancel()
        await asyncio.gather(task, return_exceptions=True)
        await node_client.aclose()


@pytest.mark.asyncio
async def test_two_nodes_spot_check_agrees(mesh):
    app, client = mesh
    stop = asyncio.Event()
    clients = [
        httpx.AsyncClient(transport=ASGITransport(app=app), base_url="http://mesh"),
        httpx.AsyncClient(transport=ASGITransport(app=app), base_url="http://mesh"),
    ]
    agents = [
        await _boot(clients[0], CpuFallbackRuntime(["mock-tiny"]), "honest-a"),
        await _boot(clients[1], CpuFallbackRuntime(["mock-tiny"]), "honest-b"),
    ]
    tasks = [asyncio.create_task(_pump(agent, stop)) for agent in agents]
    try:
        response = await client.post("/v1/chat/completions", json=CHAT)
        assert response.status_code == 200, response.text
        kinds = await _wait_kinds(client, {"verification_pass", "inference_receipt"})
        assert "verification_fail" not in kinds
        chain = await client.get("/api/ledger/verify")
        assert chain.json()["ok"] is True
        stats = (await client.get("/api/stats")).json()
        assert sum(node["credits"] for node in stats["nodes"]) >= 3
    finally:
        stop.set()
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        for item in clients:
            await item.aclose()


@pytest.mark.asyncio
async def test_bad_spot_check_is_penalized(mesh):
    app, client = mesh
    stop = asyncio.Event()
    evil_http = httpx.AsyncClient(transport=ASGITransport(app=app), base_url="http://mesh")
    honest_http = httpx.AsyncClient(transport=ASGITransport(app=app), base_url="http://mesh")
    evil = await _boot(evil_http, EvilRuntime(), "evil")
    evil_task = asyncio.create_task(_pump(evil, stop))
    honest_task = None
    try:
        response = await client.post("/v1/chat/completions", json=CHAT)
        assert response.status_code == 200, response.text
        assert response.json()["choices"][0]["message"]["content"] == "WRONG"
        honest = await _boot(honest_http, CpuFallbackRuntime(["mock-tiny"]), "checker")
        honest_task = asyncio.create_task(_pump(honest, stop))
        await _wait_kinds(client, {"verification_fail", "credit_penalty"})
        stats = (await client.get("/api/stats")).json()
        evil_row = next(node for node in stats["nodes"] if node["name"] == "evil")
        assert evil_row["strikes"] >= 1
        assert evil_row["credits"] < 1
        chain = await client.get("/api/ledger/verify")
        assert chain.json()["ok"] is True
    finally:
        stop.set()
        evil_task.cancel()
        if honest_task is not None:
            honest_task.cancel()
        await asyncio.gather(evil_task, *([honest_task] if honest_task else []), return_exceptions=True)
        await evil_http.aclose()
        await honest_http.aclose()


@pytest.mark.asyncio
async def test_canaries_quarantine_a_dishonest_node(mesh):
    app, client = mesh
    stop = asyncio.Event()
    evil_http = httpx.AsyncClient(transport=ASGITransport(app=app), base_url="http://mesh")
    evil = await _boot(evil_http, EvilRuntime(), "evil-canary")
    task = asyncio.create_task(_pump(evil, stop))
    try:
        status = ""
        for _ in range(4):
            stats = (await client.get("/api/stats")).json()
            row = next(node for node in stats["nodes"] if node["name"] == "evil-canary")
            status = row["status"]
            if status == "quarantined":
                break
            before = row["strikes"]
            injected = await client.post("/api/admin/canary", headers=ADMIN, json={})
            assert injected.status_code == 200, injected.text
            deadline = asyncio.get_running_loop().time() + 8
            while asyncio.get_running_loop().time() < deadline:
                stats = (await client.get("/api/stats")).json()
                row = next(node for node in stats["nodes"] if node["name"] == "evil-canary")
                status = row["status"]
                if status == "quarantined" or row["strikes"] > before:
                    break
                await asyncio.sleep(0.05)
            else:
                raise AssertionError(f"canary was not settled; status={status} strikes={row['strikes']}")
        assert status == "quarantined"
        blocked = await client.post("/v1/chat/completions", json=CHAT)
        assert blocked.status_code == 503
        assert blocked.json()["error"]["code"] == "no_capacity"
    finally:
        stop.set()
        task.cancel()
        await asyncio.gather(task, return_exceptions=True)
        await evil_http.aclose()


@pytest.mark.asyncio
async def test_other_node_cannot_submit_and_unknown_model_is_404(mesh):
    _app, client = mesh
    first = await client.post("/api/nodes/register", json=_spec("a"))
    second = await client.post("/api/nodes/register", json=_spec("b"))
    token_a = first.json()["token"]
    token_b = second.json()["token"]
    queued = await client.post("/v1/chat/completions", json=CHAT, headers={"X-GPUMesh-Wait-Seconds": "0"})
    assert queued.status_code == 202
    claim = await client.post("/api/nodes/jobs/claim?wait=0", headers={"authorization": f"Bearer {token_a}"})
    job = claim.json()["job"]
    assert job and "kind" not in job and "expected" not in json.dumps(job)
    denied = await client.post(
        f"/api/nodes/jobs/{job['job_id']}/result",
        headers={"authorization": f"Bearer {token_b}"},
        json={"output_text": "nope", "prompt_tokens": 1, "completion_tokens": 1, "duration_ms": 1},
    )
    assert denied.status_code == 403
    missing = await client.post(
        "/v1/chat/completions",
        json={"model": "not-a-model", "messages": [{"role": "user", "content": "hi"}]},
    )
    assert missing.status_code == 404
    assert missing.json()["error"]["code"] == "model_not_found"


@pytest.mark.asyncio
async def test_rate_limit_admin_key_and_pages(tmp_path):
    app = create_app(make_settings(tmp_path, anon_rpm=2, request_timeout_sec=1))
    async with app.router.lifespan_context(app):
        transport = ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://mesh") as client:
            page = await client.get("/")
            assert page.status_code == 200
            assert "GPU Mesh" in page.text
            assert "not a token" in page.text
            contribute = await client.get("/contribute")
            assert "Put a GPU on the mesh" in contribute.text
            body = {"model": "missing", "messages": [{"role": "user", "content": "hi"}]}
            statuses = [(await client.post("/v1/chat/completions", json=body)).status_code for _ in range(3)]
            assert statuses[:2] == [404, 404]
            assert statuses[2] == 429
            huge = await client.post(
                "/v1/chat/completions",
                json={"model": "missing", "messages": [{"role": "user", "content": "x" * 20000}]},
            )
            assert huge.status_code == 400
            made = await client.post("/api/admin/keys", headers=ADMIN, json={"name": "demo", "rpm": 10})
            assert made.status_code == 200
            key = made.json()["key"]
            assert key.startswith("sk-mesh-")
            rejected = await client.post(
                "/v1/chat/completions",
                headers={"authorization": "Bearer sk-mesh-nope"},
                json=body,
            )
            assert rejected.status_code == 401
            authed = await client.post(
                "/v1/chat/completions",
                headers={"authorization": f"Bearer {key}"},
                json=body,
            )
            assert authed.status_code == 404
            script = await client.get("/install.sh")
            assert script.status_code == 200
            assert "__DEFAULT_COORDINATOR__" not in script.text
            assert "gpumesh" in script.text
            unit = await client.get("/gpumesh-node.service")
            assert "User=gpumesh" in unit.text
            assert "NoNewPrivileges=true" in unit.text
            blob = await client.get("/dl/gpumesh-node.tar.gz")
            with tarfile.open(fileobj=io.BytesIO(blob.content), mode="r:gz") as archive:
                names = archive.getnames()
            assert "gpumesh_node/__main__.py" in names
            assert "requirements.txt" in names
            banned = await client.post("/api/admin/bans", headers=ADMIN, json={"ip": "127.0.0.1", "reason": "test"})
            assert banned.status_code == 200
            blocked = await client.post("/v1/chat/completions", json=body, headers={"authorization": f"Bearer {key}"})
            assert blocked.status_code == 403

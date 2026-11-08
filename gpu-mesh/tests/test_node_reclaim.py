"""The node claims again as soon as a job finishes. Heartbeat does not gate it."""

from __future__ import annotations

import asyncio
import contextlib
import time

import httpx
import pytest
from httpx import ASGITransport

from gpumesh.main import create_app
from gpumesh_node.agent import NodeAgent
from tests.conftest import make_settings
from tests.doubles import MODEL, FixedTextRuntime

CHAT = {
    "model": MODEL,
    "messages": [{"role": "user", "content": "Say hello in one sentence."}],
    "temperature": 0,
    "max_tokens": 32,
}


@pytest.mark.asyncio
async def test_reclaim_is_not_gated_on_the_heartbeat(tmp_path):
    app = create_app(make_settings(tmp_path, request_timeout_sec=8))
    async with app.router.lifespan_context(app):
        transport = ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://mesh", timeout=10) as client:
            agent = NodeAgent(
                base_url="http://mesh",
                runtime=FixedTextRuntime(),
                name="fast",
                http=client,
                state_path=None,
                heartbeat_sec=30,
                claim_wait_sec=0.3,
            )
            waits: list[float] = []
            started: list[float] = []
            original = agent.claim

            async def spy(wait: float = 20):
                waits.append(wait)
                started.append(time.monotonic())
                return await original(wait)

            agent.claim = spy
            stop = asyncio.Event()
            task = asyncio.create_task(agent.run_forever(stop))
            try:
                deadline = time.monotonic() + 3
                while time.monotonic() < deadline:
                    health = await client.get("/health")
                    if health.json().get("nodes_online"):
                        break
                    await asyncio.sleep(0.05)
                else:
                    raise AssertionError("node did not come online")

                async def ask():
                    return await client.post(
                        "/v1/chat/completions",
                        json=CHAT,
                        headers={"x-gpumesh-wait-seconds": "5"},
                    )

                first = await asyncio.wait_for(ask(), 5)
                second = await asyncio.wait_for(ask(), 5)
            finally:
                stop.set()
                task.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await task
            assert first.status_code == 200, first.text
            assert second.status_code == 200, second.text
            assert waits
            assert waits[0] == pytest.approx(0.3)
            assert max(waits) == pytest.approx(0.3)
            gaps = [b - a for a, b in zip(started, started[1:], strict=False)]
            assert gaps
            assert max(gaps) < 2

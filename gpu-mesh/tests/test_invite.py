"""Invite-only registration: the worker must present the cohort invite."""

import httpx
import pytest
from httpx import ASGITransport

from gpumesh.main import create_app
from gpumesh_node.agent import NodeAgent
from gpumesh_node.runtime import CpuFallbackRuntime
from tests.conftest import make_settings


@pytest.mark.asyncio
async def test_worker_register_sends_invite(tmp_path):
    app = create_app(make_settings(tmp_path, invite_only=True, invite_token="invite-ok-1234"))
    async with app.router.lifespan_context(app):
        transport = ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://mesh") as client:
            denied = NodeAgent(
                base_url="http://mesh",
                runtime=CpuFallbackRuntime(["mock-tiny"]),
                name="no-invite",
                http=client,
                state_path=None,
            )
            with pytest.raises(RuntimeError, match="403"):
                await denied.register()
            joined = NodeAgent(
                base_url="http://mesh",
                runtime=CpuFallbackRuntime(["mock-tiny"]),
                name="invited",
                http=client,
                state_path=None,
                invite="invite-ok-1234",
            )
            await joined.register()
            assert joined.node_id
            assert joined.token

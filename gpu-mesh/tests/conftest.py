from __future__ import annotations

from pathlib import Path

import httpx
import pytest
from httpx import ASGITransport

from gpumesh.main import create_app
from gpumesh.settings import Settings


def make_settings(tmp_path: Path, **overrides) -> Settings:
    values = dict(
        database_url=f"sqlite:///{tmp_path}/mesh.db",
        data_dir=str(tmp_path),
        admin_token="admin-test",
        verify_sample_rate=1,
        canary_interval_sec=0,
        anon_rpm=1000,
        register_per_hour=1000,
        dup_per_min=1000,
        flood_per_min=1000,
        max_inflight_per_client=8,
        request_timeout_sec=8,
        job_timeout_sec=15,
        heartbeat_timeout_sec=60,
        verify_queue_ttl_sec=30,
        verify_similarity=0.82,
        max_outstanding_verifications=20,
        prompt_retention_sec=0,
        trust_min_age_sec=0,
        trust_min_verified=1,
        max_queue_depth=100,
        max_global_inflight=32,
    )
    values.update(overrides)
    return Settings(**values)


@pytest.fixture
async def mesh(tmp_path):
    application = create_app(make_settings(tmp_path))
    async with application.router.lifespan_context(application):
        transport = ASGITransport(app=application)
        async with httpx.AsyncClient(transport=transport, base_url="http://mesh") as client:
            yield application, client

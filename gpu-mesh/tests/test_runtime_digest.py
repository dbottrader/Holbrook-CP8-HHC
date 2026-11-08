"""Ollama advertises the tag digest and /api/version. Nothing is invented."""

import httpx
import pytest

from gpumesh.textutil import DET_NUM_CTX, DET_REPEAT_PENALTY, DET_TOP_P
from gpumesh_node.runtime import OllamaRuntime, ollama_payload, vllm_payload


def _handler(request: httpx.Request) -> httpx.Response:
    if request.url.path == "/api/tags":
        return httpx.Response(
            200,
            json={
                "models": [
                    {
                        "name": "asin-qwen0.5b:latest",
                        "digest": "sha256:4f1c0b0d" + ("ab" * 28),
                        "size": 12,
                    },
                    {"name": "bare:latest", "size": 1},
                ]
            },
        )
    if request.url.path == "/api/ps":
        return httpx.Response(200, json={"models": [{"name": "asin-qwen0.5b:latest"}]})
    if request.url.path == "/api/version":
        return httpx.Response(200, json={"version": "0.6.3"})
    return httpx.Response(404)


@pytest.mark.asyncio
async def test_ollama_list_models_advertises_the_tag_digest_and_version():
    runtime = OllamaRuntime("http://ollama", transport=httpx.MockTransport(_handler))
    models = await runtime.list_models()
    pinned = models[0]
    assert pinned["id"] == "asin-qwen0.5b:latest"
    assert pinned["resident"] is True
    assert pinned["source"] == "ollama"
    assert pinned["digest"].startswith("sha256:")
    assert "digest" not in models[1]
    assert models[1]["id"] == "bare:latest"
    assert runtime.version == "0.6.3"
    payload = ollama_payload(
        {
            "model": pinned["id"],
            "messages": [{"role": "user", "content": "hi"}],
            "temperature": 0.7,
            "max_tokens": 40,
            "seed": 1661733295,
        }
    )
    assert payload["options"]["temperature"] == 0
    assert payload["options"]["top_p"] == DET_TOP_P
    assert payload["options"]["repeat_penalty"] == DET_REPEAT_PENALTY
    assert payload["options"]["num_ctx"] == DET_NUM_CTX
    assert payload["options"]["seed"] == 1661733295
    vllm = vllm_payload(
        {
            "model": pinned["id"],
            "messages": [{"role": "user", "content": "hi"}],
            "max_tokens": 40,
            "seed": 0,
        }
    )
    assert vllm["top_p"] == 1
    assert vllm["repetition_penalty"] == 1
    assert vllm["seed"] == 0

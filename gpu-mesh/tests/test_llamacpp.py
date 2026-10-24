"""llama.cpp CPU worker, without downloading a GGUF."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from gpumesh.db import build_database, session_scope
from gpumesh.errors import MeshError
from gpumesh.work import _normalize_backend, _toploc_verdict, model_ids_of, register_node
from gpumesh_node.llamacpp import (
    DEFAULT_FILE,
    DEFAULT_GGUF_SHA256,
    DEFAULT_MODEL_ID,
    DEFAULT_REPO,
    LlamaCppRuntime,
    ensure_gguf,
    sha256_file,
)
from tests.conftest import make_settings


class _FakeLLM:
    def __init__(self) -> None:
        self.calls: list[dict] = []

    def create_chat_completion(self, **kwargs):
        self.calls.append(kwargs)
        return {
            "choices": [
                {
                    "message": {"role": "assistant", "content": "The sky is blue."},
                    "finish_reason": "stop",
                }
            ],
            "usage": {"prompt_tokens": 12, "completion_tokens": 4},
        }


def test_default_smollm_pin_matches_the_official_file():
    assert DEFAULT_REPO == "HuggingFaceTB/SmolLM2-360M-Instruct-GGUF"
    assert DEFAULT_FILE == "smollm2-360m-instruct-q8_0.gguf"
    assert DEFAULT_MODEL_ID == "SmolLM2-360M-Instruct"
    assert DEFAULT_GGUF_SHA256 == "48ab3034d0dd401fbc721eb1df3217902fee7dab9078992d66431f09b7750201"
    assert len(DEFAULT_GGUF_SHA256) == 64


def test_cached_gguf_is_reused_when_the_pin_matches(tmp_path: Path):
    body = b"not-a-real-model"
    path = tmp_path / "toy.gguf"
    path.write_bytes(body)
    digest = sha256_file(path)
    found = ensure_gguf("HuggingFaceTB/toy", "toy.gguf", tmp_path, digest)
    assert found == path
    assert sha256_file(found) == digest


def test_pin_mismatch_does_not_keep_a_bad_file(tmp_path: Path, monkeypatch):
    path = tmp_path / "toy.gguf"
    path.write_bytes(b"stale")

    def boom(*_args, **_kwargs):
        raise OSError("offline")

    monkeypatch.setattr("gpumesh_node.llamacpp.urllib.request.urlopen", boom)
    with pytest.raises(SystemExit):
        ensure_gguf("HuggingFaceTB/toy", "toy.gguf", tmp_path, "0" * 64)
    assert not path.exists()


@pytest.mark.asyncio
async def test_llamacpp_runtime_generates_and_answers_canaries_literally():
    llm = _FakeLLM()
    runtime = LlamaCppRuntime(model_id="SmolLM2-360M-Instruct", digest="abc", llm=llm)
    models = await runtime.list_models()
    assert models[0]["source"] == "llama.cpp"
    assert models[0]["id"] == "SmolLM2-360M-Instruct"
    deltas: list[str] = []

    async def on_delta(text: str) -> None:
        deltas.append(text)

    result = await runtime.complete(
        {
            "model": "SmolLM2-360M-Instruct",
            "messages": [{"role": "user", "content": "What color is the sky?"}],
            "temperature": 0,
            "max_tokens": 32,
            "seed": None,
        },
        on_delta,
    )
    assert result.text == "The sky is blue."
    assert result.prompt_tokens == 12
    assert result.completion_tokens == 4
    assert deltas == ["The sky is blue."]
    assert llm.calls[0]["stream"] is False
    assert llm.calls[0]["temperature"] == 0.0
    assert llm.calls[0]["top_k"] == 1
    assert llm.calls[0]["seed"] == 0
    canary = await runtime.complete(
        {
            "model": "SmolLM2-360M-Instruct",
            "messages": [{"role": "user", "content": "Reply with exactly the token: MESH_OK"}],
            "temperature": 0,
            "max_tokens": 16,
        },
        None,
    )
    assert canary.text == "MESH_OK"
    assert len(llm.calls) == 1


def test_llamacpp_backend_registers_and_mock_name_stays_cpu(tmp_path: Path):
    assert _normalize_backend("llamacpp") == "llamacpp"
    assert _normalize_backend("cpu") == "cpu"
    settings = make_settings(tmp_path, verify_sample_rate=0)
    _engine, factory = build_database(settings)
    spec = {
        "name": "cpu-real",
        "backend": "llamacpp",
        "gpu": {"vendor": "cpu", "model": "cpu", "vram_mb": 0, "driver": "", "count": 0},
        "models": [
            {
                "id": "SmolLM2-360M-Instruct",
                "resident": True,
                "source": "llama.cpp",
                "digest": "abc",
            }
        ],
        "version": "test",
    }
    with session_scope(factory) as session:
        node, _token, _receipt = register_node(session, settings, spec, "10.0.0.9")
        assert node.backend == "llamacpp"
        assert model_ids_of(node) == ["SmolLM2-360M-Instruct"]
        spec["backend"] = "horde"
        spec["name"] = "nope"
        with pytest.raises(MeshError) as bad:
            register_node(session, settings, spec, "10.0.0.10")
        assert bad.value.code == "bad_backend"


def test_missing_proof_is_unavailable_until_the_library_is_installed(monkeypatch):
    parent = SimpleNamespace(
        toploc_proofs="[]",
        toploc_source="",
        messages_json="[]",
        model="SmolLM2-360M-Instruct",
    )
    monkeypatch.setattr("gpumesh_node.toploc_proof.library_ready", lambda: False)
    assert _toploc_verdict(parent, {}) == {"ok": True, "status": "unavailable"}
    monkeypatch.setattr("gpumesh_node.toploc_proof.library_ready", lambda: True)
    assert _toploc_verdict(parent, {}) == {"ok": False, "status": "missing"}

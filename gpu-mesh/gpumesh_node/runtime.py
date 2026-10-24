"""Inference backends: Ollama, vLLM, and an honest CPU fallback.

The fallback is deterministic so two machines agree on a spot-check. It is not
a neural model and it says so in every reply. Canary prompts ask for an exact
token; those patterns have to stay aligned with the coordinator's canary list.
"""

from __future__ import annotations

import hashlib
import json
import re
import time
from dataclasses import dataclass
from typing import Protocol

import httpx

_EXACT = (
    re.compile(r"reply with exactly(?: the token)?[:\s]+(\S+)", re.IGNORECASE),
    re.compile(r"repeat only this string[:\s]+(\S+)", re.IGNORECASE),
)


@dataclass
class InferenceResult:
    text: str
    prompt_tokens: int
    completion_tokens: int
    duration_ms: int
    finish_reason: str


class Runtime(Protocol):
    name: str

    async def list_models(self) -> list[dict]: ...

    async def complete(self, job: dict, on_delta) -> InferenceResult: ...


def exact_reply(messages: list[dict]) -> str | None:
    for message in messages:
        content = message.get("content")
        if not isinstance(content, str):
            continue
        for pattern in _EXACT:
            match = pattern.search(content)
            if match:
                return match.group(1).strip(".,!;:\"'`")
    return None


def _words(text: str) -> int:
    return len(text.split()) if text.strip() else 0


class CpuFallbackRuntime:
    """Deterministic stand-in used when a box has no GPU. Not a language model."""

    name = "cpu"

    def __init__(self, models: list[str] | None = None) -> None:
        self._models = models or ["mock-tiny"]

    async def list_models(self) -> list[dict]:
        return [
            {"id": model, "resident": True, "source": "cpu-fallback", "digest": "cpu-fallback"}
            for model in self._models
        ]

    async def complete(self, job: dict, on_delta) -> InferenceResult:
        started = time.perf_counter()
        text = fallback_text(job.get("messages") or [], int(job.get("max_tokens") or 256))
        for index in range(0, len(text), 24):
            piece = text[index : index + 24]
            if on_delta is not None and piece:
                await on_delta(piece)
        elapsed = max(1, int((time.perf_counter() - started) * 1000))
        prompt = " ".join(str(m.get("content") or "") for m in job.get("messages") or [])
        return InferenceResult(
            text=text,
            prompt_tokens=max(1, _words(prompt)),
            completion_tokens=max(1, _words(text)),
            duration_ms=elapsed,
            finish_reason="stop",
        )


def fallback_text(messages: list[dict], max_tokens: int) -> str:
    demanded = exact_reply(messages)
    if demanded:
        return demanded
    user = ""
    for message in reversed(messages):
        if message.get("role") == "user" and isinstance(message.get("content"), str):
            user = message["content"].strip()
            break
    digest = hashlib.sha256(
        json.dumps(messages, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()
    ).hexdigest()[:12]
    body = (
        "GPU Mesh CPU fallback (not a neural model). "
        f"I received: {user[:240]}. "
        f"Checksum {digest}."
    )
    words = body.split()
    if max_tokens and len(words) > max_tokens:
        body = " ".join(words[:max_tokens])
    return body


class OllamaRuntime:
    name = "ollama"

    def __init__(self, host: str, timeout_sec: float = 120) -> None:
        self.host = host.rstrip("/")
        self.timeout = timeout_sec

    async def list_models(self) -> list[dict]:
        async with httpx.AsyncClient(timeout=5) as client:
            tags = await client.get(f"{self.host}/api/tags")
            tags.raise_for_status()
            resident: set[str] = set()
            ps = await client.get(f"{self.host}/api/ps")
            if ps.status_code == 200:
                for item in ps.json().get("models") or []:
                    name = item.get("name") or item.get("model")
                    if name:
                        resident.add(name)
            found = []
            for item in tags.json().get("models") or []:
                name = item.get("name") or item.get("model")
                if name:
                    found.append({"id": name, "resident": name in resident, "source": "ollama"})
            return found

    async def complete(self, job: dict, on_delta) -> InferenceResult:
        started = time.perf_counter()
        options: dict = {"temperature": job.get("temperature", 0), "num_predict": job.get("max_tokens") or 256}
        if job.get("seed") is not None:
            options["seed"] = job["seed"]
        if job.get("stop"):
            options["stop"] = job["stop"]
        payload = {"model": job["model"], "messages": job["messages"], "stream": True, "options": options}
        parts: list[str] = []
        prompt_tokens = 0
        completion_tokens = 0
        timeout = httpx.Timeout(10, read=self.timeout)
        async with httpx.AsyncClient(timeout=timeout) as client:
            async with client.stream("POST", f"{self.host}/api/chat", json=payload) as response:
                response.raise_for_status()
                async for line in response.aiter_lines():
                    if not line:
                        continue
                    data = json.loads(line)
                    piece = ((data.get("message") or {}).get("content")) or ""
                    if piece:
                        parts.append(piece)
                        if on_delta is not None:
                            await on_delta(piece)
                    if data.get("done"):
                        prompt_tokens = int(data.get("prompt_eval_count") or 0)
                        completion_tokens = int(data.get("eval_count") or 0)
        text = "".join(parts)
        if completion_tokens <= 0:
            completion_tokens = max(1, _words(text))
        if prompt_tokens <= 0:
            prompt_tokens = max(1, _words(" ".join(m.get("content") or "" for m in job["messages"])))
        elapsed = max(1, int((time.perf_counter() - started) * 1000))
        finish = "length" if completion_tokens >= int(job.get("max_tokens") or 0) > 0 else "stop"
        return InferenceResult(text, prompt_tokens, completion_tokens, elapsed, finish)


class VllmRuntime:
    name = "vllm"

    def __init__(self, host: str, timeout_sec: float = 120) -> None:
        self.host = host.rstrip("/")
        self.timeout = timeout_sec

    async def list_models(self) -> list[dict]:
        async with httpx.AsyncClient(timeout=5) as client:
            response = await client.get(f"{self.host}/v1/models")
            response.raise_for_status()
            found = []
            for item in response.json().get("data") or []:
                if item.get("id"):
                    found.append({"id": item["id"], "resident": True, "source": "vllm"})
            return found

    async def complete(self, job: dict, on_delta) -> InferenceResult:
        started = time.perf_counter()
        payload = {
            "model": job["model"],
            "messages": job["messages"],
            "temperature": job.get("temperature", 0),
            "max_tokens": job.get("max_tokens") or 256,
            "stream": True,
            "stream_options": {"include_usage": True},
        }
        if job.get("seed") is not None:
            payload["seed"] = job["seed"]
        if job.get("stop"):
            payload["stop"] = job["stop"]
        parts: list[str] = []
        prompt_tokens = 0
        completion_tokens = 0
        timeout = httpx.Timeout(10, read=self.timeout)
        async with httpx.AsyncClient(timeout=timeout) as client:
            async with client.stream("POST", f"{self.host}/v1/chat/completions", json=payload) as response:
                response.raise_for_status()
                async for line in response.aiter_lines():
                    if not line.startswith("data:"):
                        continue
                    raw = line[5:].strip()
                    if raw == "[DONE]":
                        break
                    data = json.loads(raw)
                    usage = data.get("usage") or {}
                    if usage:
                        prompt_tokens = int(usage.get("prompt_tokens") or prompt_tokens)
                        completion_tokens = int(usage.get("completion_tokens") or completion_tokens)
                    choices = data.get("choices") or []
                    if not choices:
                        continue
                    piece = ((choices[0].get("delta") or {}).get("content")) or ""
                    if piece:
                        parts.append(piece)
                        if on_delta is not None:
                            await on_delta(piece)
        text = "".join(parts)
        if completion_tokens <= 0:
            completion_tokens = max(1, _words(text)) if text else 0
        if prompt_tokens <= 0:
            prompt_tokens = max(1, _words(" ".join(str(m.get("content") or "") for m in job["messages"])))
        elapsed = max(1, int((time.perf_counter() - started) * 1000))
        return InferenceResult(text or "", prompt_tokens, max(completion_tokens, 1 if text else 0), elapsed, "stop")


async def _reachable(url: str) -> bool:
    try:
        async with httpx.AsyncClient(timeout=2) as client:
            response = await client.get(url)
            return response.status_code < 500
    except (httpx.HTTPError, OSError):
        return False


async def detect_runtime(
    backend: str,
    *,
    allow_cpu: bool,
    models: list[str],
    ollama_host: str,
    vllm_host: str,
    job_timeout: float,
    gpu: dict | None,
    llamacpp: dict | None = None,
) -> Runtime:
    backend = (backend or "auto").lower()
    if backend == "llamacpp":
        from gpumesh_node.llamacpp import open_llamacpp

        return open_llamacpp(llamacpp)
    if backend == "cpu":
        return CpuFallbackRuntime(models)
    if backend == "ollama":
        runtime = OllamaRuntime(ollama_host, job_timeout)
        if not await runtime.list_models():
            raise SystemExit(
                f"Ollama at {ollama_host} has no models. Pull an open weight, for example: ollama pull llama3.2:1b"
            )
        return runtime
    if backend == "vllm":
        runtime = VllmRuntime(vllm_host, job_timeout)
        if not await runtime.list_models():
            raise SystemExit(f"vLLM at {vllm_host} is not serving a model.")
        return runtime
    if await _reachable(f"{ollama_host}/api/tags"):
        runtime = OllamaRuntime(ollama_host, job_timeout)
        if await runtime.list_models():
            return runtime
    if await _reachable(f"{vllm_host}/v1/models"):
        runtime = VllmRuntime(vllm_host, job_timeout)
        if await runtime.list_models():
            return runtime
    if allow_cpu:
        return CpuFallbackRuntime(models)
    if gpu:
        raise SystemExit(
            "A GPU is visible to nvidia-smi, but neither Ollama nor vLLM answered. "
            "Start one and pull an open model, or pass --allow-cpu to run the deterministic fallback."
        )
    raise SystemExit(
        "No NVIDIA GPU detected. Install a driver, or pass --allow-cpu to run the deterministic fallback."
    )

"""Groq fallback when no volunteer worker is online.

The public test prompt is an exact-match canary. Any other prompt is checked
by a second Groq model. Receipts are written by the caller through
``LedgerBackend``. The API key stays in ``GPU_MESH_GROQ_API_KEY`` and is
never logged.
"""

from __future__ import annotations

from typing import Any

import httpx

from gpumesh.canon import output_hash, sha256_text
from gpumesh.settings import Settings
from gpumesh.textutil import canon_answer, exact_reply, judge_outputs

GROQ_TEST_PROMPT = "Reply with exactly the token: GROQ_MESH_OK"
GROQ_TEST_EXPECTED = "GROQ_MESH_OK"
GROQ_TEST_MAX_TOKENS = 16
GROQ_TEST_MODEL = "openai/gpt-oss-20b"
ACTOR = "groq-fallback"
KIND = "groq_inference_receipt"


class GroqCallError(Exception):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


async def _complete(
    client: httpx.AsyncClient,
    settings: Settings,
    *,
    model: str,
    messages: list[dict],
    max_tokens: int,
    temperature: float,
) -> dict[str, Any]:
    try:
        response = await client.post(
            settings.groq_base_url.rstrip("/") + "/chat/completions",
            headers={
                "authorization": f"Bearer {settings.groq_api_key}",
                "content-type": "application/json",
            },
            json={
                "model": model,
                "messages": messages,
                "max_completion_tokens": max_tokens,
                "temperature": temperature,
            },
        )
    except httpx.HTTPError as exc:
        raise GroqCallError("provider_unreachable", "Groq did not respond") from exc
    try:
        data = response.json()
    except ValueError as exc:
        raise GroqCallError("provider_response_missing_text", "Groq returned a non-JSON body") from exc
    if response.status_code >= 400:
        raise GroqCallError("provider_request_failed", f"Groq returned {response.status_code}")
    choices = data.get("choices") if isinstance(data, dict) else None
    message = choices[0].get("message") if isinstance(choices, list) and choices else None
    output = message.get("content") if isinstance(message, dict) else None
    if not isinstance(output, str) or not output.strip():
        raise GroqCallError("provider_response_missing_text", "Groq returned no text")
    usage = data.get("usage") if isinstance(data.get("usage"), dict) else {}
    return {
        "output": output[: settings.max_output_chars],
        "request_id": str(data.get("id") or response.headers.get("x-request-id") or ""),
        "model": str(data.get("model") or model),
        "prompt_tokens": int(usage.get("prompt_tokens") or 0),
        "completion_tokens": int(usage.get("completion_tokens") or 0),
    }


async def run_verified(
    settings: Settings,
    messages: list[dict],
    *,
    max_tokens: int,
    temperature: float,
    transport: httpx.AsyncBaseTransport | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    async with httpx.AsyncClient(transport=transport, timeout=settings.groq_timeout_sec) as client:
        primary = await _complete(
            client,
            settings,
            model=settings.groq_model,
            messages=messages,
            max_tokens=max_tokens,
            temperature=temperature,
        )
        expected = exact_reply(messages)
        if expected is not None:
            ok = canon_answer(primary["output"]) == canon_answer(expected)
            verification = {
                "ok": ok,
                "method": "exact_match",
                "expected": expected,
                "verifier_ids": "exact-match",
            }
            return primary, verification
        second = await _complete(
            client,
            settings,
            model=settings.groq_verify_model,
            messages=messages,
            max_tokens=max_tokens,
            temperature=0,
        )
        verdict = judge_outputs(primary["output"], second["output"], 0.0, settings.verify_similarity)
        verification = {
            "ok": verdict == "agree",
            "method": "second_model",
            "verifier_ids": settings.groq_verify_model,
            "verdict": verdict,
            "second_output_hash": output_hash(second["output"]),
        }
        return primary, verification


def fallback_payload(
    *,
    job_id: str,
    model: str,
    primary: dict[str, Any],
    verification: dict[str, Any],
    messages: list[dict],
    max_tokens: int,
    temperature: float,
    duration_ms: int,
) -> dict[str, Any]:
    output = str(primary["output"])
    request_id = str(primary.get("request_id") or "")
    digest = output_hash(output)
    return {
        "schema": "gpumesh.groq_fallback.v1",
        "provider": "groq",
        "runtime": "groq",
        "model": model,
        "worker_id": f"groq:{model}",
        "verifier_ids": str(verification.get("verifier_ids") or ""),
        "verifier_decision": "agree" if verification.get("ok") else "fail",
        "verification_method": str(verification.get("method") or ""),
        "output_hash": digest,
        "prompt_sha256": sha256_text(str(messages[-1].get("content") or "") if messages else ""),
        "request_id": request_id,
        "max_tokens": int(max_tokens),
        "prompt_tokens": int(primary.get("prompt_tokens") or 0),
        "completion_tokens": int(primary.get("completion_tokens") or 0),
        "duration_ms": int(duration_ms),
        "state": "OBSERVED",
        "promotion": "HOLD",
        "temperature_milli": int(round(float(temperature) * 1000)),
        "amount": 0,
        "credits": 0,
        "settlement_id": f"{job_id}:groq",
        "job_id": job_id,
    }

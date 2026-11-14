"""Cloudflare Workers AI fallback when no volunteer worker is online.

Free-tier only. Calls go through AI Gateway ``default``. The public test
prompt is an exact-match canary. Any other prompt is checked by a second
allow-listed free model. Receipts are written by the caller through
``LedgerBackend``. The API token is never logged or placed in a receipt.

Credentials are read from ``CLOUDFLARE_API_TOKEN`` and
``CLOUDFLARE_ACCOUNT_ID``, then from ``GPU_MESH_CLOUDFLARE_API_TOKEN`` /
``GPU_MESH_CLOUDFLARE_ACCOUNT_ID``. A directory of secret files is used
only when ``CLOUDFLARE_SECRETS_DIR`` or
``GPU_MESH_CLOUDFLARE_SECRETS_DIR`` is set (files
``cloudflare_api_token`` and ``cloudflare_account_id``).
"""

from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any

import httpx

from gpumesh.canon import output_hash, sha256_text
from gpumesh.settings import Settings
from gpumesh.textutil import canon_answer, exact_reply, judge_outputs

DEFAULT_MODEL = "@cf/meta/llama-3.2-1b-instruct"
DEFAULT_VERIFY_MODEL = "@cf/ibm-granite/granite-4.0-h-micro"
DEFAULT_GATEWAY_ID = "default"
DEFAULT_API_BASE = "https://api.cloudflare.com/client/v4"
CF_TEST_PROMPT = "Reply with exactly the token: CF_MESH_OK"
CF_TEST_EXPECTED = "CF_MESH_OK"
CF_TEST_MAX_TOKENS = 32
ACTOR = "cloudflare-fallback"
KIND = "cloudflare_inference_receipt"

# Fail-closed allowlist: models that do not require Workers Paid and
# are cheap enough for the 10,000 neuron/day free allocation.
FREE_ALLOWED_MODELS = frozenset(
    {
        "@cf/meta/llama-3.2-1b-instruct",
        "@cf/meta/llama-3.2-3b-instruct",
        "@cf/ibm-granite/granite-4.0-h-micro",
        "@cf/zai-org/glm-4.7-flash",
    }
)

# Official require_workers_paid models as of 2026-11-13. These are
# rejected even if someone adds them to an allowlist later.
PAID_REQUIRED_MODELS = frozenset(
    {
        "@cf/moonshotai/kimi-k2.6",
        "@cf/moonshotai/kimi-k2.7-code",
        "@cf/zai-org/glm-5.2",
        "@cf/zai-org/glm-5.3",
        "@cf/zai-org/glm-5.3-flash",
        "@cf/deepseek-ai/deepseek-v4-flash-0731",
        "@cf/deepseek-ai/deepseek-v4.1-flash-1017",
        "@cf/deepseek-ai/deepseek-v4-pro-0813",
        "@cf/thinkingmachines/inkling-2-small",
    }
)

# Neurons per million input / output tokens (Cloudflare pricing docs).
NEURON_RATES: dict[str, tuple[float, float]] = {
    "@cf/meta/llama-3.2-1b-instruct": (2457.0, 18252.0),
    "@cf/meta/llama-3.2-3b-instruct": (4625.0, 30475.0),
    "@cf/ibm-granite/granite-4.0-h-micro": (1542.0, 10158.0),
    "@cf/zai-org/glm-4.7-flash": (5500.0, 36400.0),
}
CONSERVATIVE_RATES = (10000.0, 40000.0)

# Well under the 10,000 neuron/day free allocation.
DEFAULT_DAILY_NEURON_CAP = 2000.0
DEFAULT_DAILY_CALL_CAP = 40
DEFAULT_MAX_TOKENS = 128


class CloudflareCallError(Exception):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


def _normalize_model(model: str) -> str:
    return str(model or "").strip()


def is_paid_required_model(model: str) -> bool:
    name = _normalize_model(model).lower()
    if _normalize_model(model) in PAID_REQUIRED_MODELS:
        return True
    if "kimi-k2.6" in name or "kimi-k2.7" in name:
        return True
    return False


def assert_model_allowed(model: str) -> str:
    name = _normalize_model(model)
    if not name:
        raise CloudflareCallError("model_not_allowed", "Cloudflare model id is missing")
    if is_paid_required_model(name) or name in PAID_REQUIRED_MODELS:
        raise CloudflareCallError(
            "paid_model_forbidden",
            "This Cloudflare model requires Workers Paid or prepaid credits and is blocked",
        )
    if name not in FREE_ALLOWED_MODELS:
        raise CloudflareCallError(
            "model_not_allowed",
            "Cloudflare model is not on the free-tier allowlist",
        )
    return name


def _read_file_secret(path: Path) -> str:
    try:
        if path.is_file():
            return path.read_text(encoding="utf-8").strip()
    except OSError:
        return ""
    return ""


def _secrets_dir(settings: Settings | None) -> Path | None:
    raw = os.environ.get("CLOUDFLARE_SECRETS_DIR") or os.environ.get("GPU_MESH_CLOUDFLARE_SECRETS_DIR") or ""
    if not raw and settings is not None:
        raw = str(getattr(settings, "cloudflare_secrets_dir", "") or "")
    raw = raw.strip()
    if not raw:
        return None
    return Path(raw)


def resolve_credentials(settings: Settings | None = None) -> tuple[str, str]:
    """Return (token, account_id). Empty strings mean not configured."""
    token = (os.environ.get("CLOUDFLARE_API_TOKEN") or "").strip()
    account = (os.environ.get("CLOUDFLARE_ACCOUNT_ID") or "").strip()
    if settings is not None:
        if not token:
            token = str(getattr(settings, "cloudflare_api_token", "") or "").strip()
        if not account:
            account = str(getattr(settings, "cloudflare_account_id", "") or "").strip()
    if not token or not account:
        directory = _secrets_dir(settings)
        if directory is not None:
            if not token:
                token = _read_file_secret(directory / "cloudflare_api_token")
            if not account:
                account = _read_file_secret(directory / "cloudflare_account_id")
    return token, account


def configured(settings: Settings | None = None) -> bool:
    token, account = resolve_credentials(settings)
    if not token or not account:
        return False
    try:
        assert_model_allowed(_model_from_settings(settings))
        assert_model_allowed(_verify_model_from_settings(settings))
    except CloudflareCallError:
        return False
    return True


def _model_from_settings(settings: Settings | None) -> str:
    if settings is None:
        return DEFAULT_MODEL
    return _normalize_model(getattr(settings, "cloudflare_model", "") or DEFAULT_MODEL) or DEFAULT_MODEL


def _verify_model_from_settings(settings: Settings | None) -> str:
    if settings is None:
        return DEFAULT_VERIFY_MODEL
    return (
        _normalize_model(getattr(settings, "cloudflare_verify_model", "") or DEFAULT_VERIFY_MODEL)
        or DEFAULT_VERIFY_MODEL
    )


def _gateway_id(settings: Settings | None) -> str:
    if settings is None:
        return DEFAULT_GATEWAY_ID
    return _normalize_model(getattr(settings, "cloudflare_gateway_id", "") or DEFAULT_GATEWAY_ID) or DEFAULT_GATEWAY_ID


def _api_base(settings: Settings | None) -> str:
    if settings is None:
        return DEFAULT_API_BASE
    return str(getattr(settings, "cloudflare_api_base", "") or DEFAULT_API_BASE).rstrip("/") or DEFAULT_API_BASE


def _timeout(settings: Settings | None) -> float:
    if settings is None:
        return 30.0
    return float(getattr(settings, "cloudflare_timeout_sec", 30.0) or 30.0)


def _max_tokens_cap(settings: Settings | None) -> int:
    if settings is None:
        return DEFAULT_MAX_TOKENS
    return int(getattr(settings, "cloudflare_max_tokens", DEFAULT_MAX_TOKENS) or DEFAULT_MAX_TOKENS)


def _neuron_cap(settings: Settings | None) -> float:
    if settings is None:
        return DEFAULT_DAILY_NEURON_CAP
    return float(getattr(settings, "cloudflare_daily_neuron_cap", DEFAULT_DAILY_NEURON_CAP) or DEFAULT_DAILY_NEURON_CAP)


def _call_cap(settings: Settings | None) -> int:
    if settings is None:
        return DEFAULT_DAILY_CALL_CAP
    return int(getattr(settings, "cloudflare_daily_call_cap", DEFAULT_DAILY_CALL_CAP) or DEFAULT_DAILY_CALL_CAP)


def budget_path(settings: Settings | None) -> Path:
    override = os.environ.get("GPU_MESH_CLOUDFLARE_BUDGET_PATH", "").strip()
    if override:
        return Path(override)
    if settings is not None:
        custom = str(getattr(settings, "cloudflare_budget_path", "") or "").strip()
        if custom:
            return Path(custom)
        return settings.resolved_data_dir() / "cloudflare_neuron_budget.json"
    return Path("data") / "cloudflare_neuron_budget.json"


def _utc_day() -> str:
    return time.strftime("%Y-%m-%d", time.gmtime())


def _load_budget(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        data = {}
    if not isinstance(data, dict) or data.get("day") != _utc_day():
        return {"day": _utc_day(), "neurons": 0.0, "calls": 0}
    return {
        "day": _utc_day(),
        "neurons": float(data.get("neurons") or 0),
        "calls": int(data.get("calls") or 0),
    }


def _save_budget(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, sort_keys=True), encoding="utf-8")
    tmp.replace(path)


def estimate_neurons(model: str, prompt_tokens: int, completion_tokens: int) -> float:
    rates = NEURON_RATES.get(_normalize_model(model), CONSERVATIVE_RATES)
    return (max(0, prompt_tokens) * rates[0] + max(0, completion_tokens) * rates[1]) / 1_000_000.0


def _prompt_token_guess(messages: list[dict]) -> int:
    total = 0
    for item in messages:
        total += len(str((item or {}).get("content") or ""))
    return max(1, (total + 3) // 4)


def reserve_budget(
    settings: Settings | None,
    *,
    model: str,
    messages: list[dict],
    max_tokens: int,
    calls: int = 1,
) -> float:
    """Reserve a conservative neuron estimate. Returns the reserved amount."""
    reserved = estimate_neurons(model, _prompt_token_guess(messages), int(max_tokens))
    path = budget_path(settings)
    current = _load_budget(path)
    neuron_cap = _neuron_cap(settings)
    call_cap = _call_cap(settings)
    if current["calls"] + calls > call_cap:
        raise CloudflareCallError(
            "daily_call_cap",
            "Cloudflare daily free-tier call cap reached; retry after 00:00 UTC",
        )
    if current["neurons"] + reserved > neuron_cap:
        raise CloudflareCallError(
            "daily_neuron_cap",
            "Cloudflare daily free-tier neuron cap reached; retry after 00:00 UTC",
        )
    current["neurons"] += reserved
    current["calls"] += calls
    _save_budget(path, current)
    return reserved


def settle_budget(settings: Settings | None, reserved: float, actual: float) -> None:
    """Replace the reservation with the actual neuron use when it is known."""
    if actual < 0:
        actual = 0.0
    path = budget_path(settings)
    current = _load_budget(path)
    current["neurons"] = max(0.0, current["neurons"] - reserved + actual)
    _save_budget(path, current)


def _extract_text(data: Any) -> str:
    if not isinstance(data, dict):
        return ""
    result = data.get("result", data)
    if isinstance(result, list) and result:
        result = result[0]
    if not isinstance(result, dict):
        if isinstance(result, str):
            return result
        return ""
    for key in ("response", "output", "text"):
        value = result.get(key)
        if isinstance(value, str) and value.strip():
            return value
    choices = result.get("choices") or data.get("choices")
    if isinstance(choices, list) and choices:
        message = choices[0].get("message") if isinstance(choices[0], dict) else None
        if isinstance(message, dict):
            content = message.get("content")
            if isinstance(content, str) and content.strip():
                return content
        text = choices[0].get("text") if isinstance(choices[0], dict) else None
        if isinstance(text, str) and text.strip():
            return text
    return ""


def _extract_usage(data: Any) -> dict[str, Any]:
    if not isinstance(data, dict):
        return {}
    result = data.get("result") if isinstance(data.get("result"), dict) else {}
    usage = {}
    for block in (result.get("usage"), data.get("usage"), data.get("meta")):
        if isinstance(block, dict):
            usage.update(block)
    return usage


def _extract_neurons(data: Any, headers: httpx.Headers | None, model: str, prompt_tokens: int, completion_tokens: int) -> float:
    usage = _extract_usage(data)
    for key in ("neurons", "total_neurons", "neuron", "neurons_used"):
        raw = usage.get(key)
        if raw is not None:
            try:
                value = float(raw)
                if value >= 0:
                    return value
            except (TypeError, ValueError):
                pass
    if headers:
        for key in ("cf-aig-neurons", "cf-neurons", "x-neurons"):
            raw = headers.get(key)
            if raw:
                try:
                    return float(raw)
                except ValueError:
                    pass
    return estimate_neurons(model, prompt_tokens, completion_tokens)


def _extract_request_id(data: Any, headers: httpx.Headers | None) -> str:
    if isinstance(data, dict):
        for key in ("request_id", "id"):
            value = data.get(key)
            if value:
                return str(value)
        result = data.get("result")
        if isinstance(result, dict) and result.get("id"):
            return str(result["id"])
    if headers:
        for key in ("cf-ray", "cf-aig-request-id", "x-request-id"):
            value = headers.get(key)
            if value:
                return value
    return ""


def _run_url(settings: Settings | None, account_id: str) -> str:
    return f"{_api_base(settings)}/accounts/{account_id}/ai/run"


async def _complete(
    client: httpx.AsyncClient,
    settings: Settings,
    *,
    model: str,
    messages: list[dict],
    max_tokens: int,
    temperature: float,
    token: str,
    account_id: str,
) -> dict[str, Any]:
    model = assert_model_allowed(model)
    max_tokens = min(int(max_tokens), _max_tokens_cap(settings))
    payload = {
        "model": model,
        "input": {
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
        },
    }
    try:
        response = await client.post(
            _run_url(settings, account_id),
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
                "cf-aig-gateway-id": _gateway_id(settings),
            },
            json=payload,
        )
    except httpx.HTTPError as exc:
        raise CloudflareCallError("provider_unreachable", "Cloudflare did not respond") from exc
    try:
        data = response.json()
    except ValueError as exc:
        raise CloudflareCallError("provider_response_missing_text", "Cloudflare returned a non-JSON body") from exc
    if response.status_code >= 400 or (isinstance(data, dict) and data.get("success") is False):
        raise CloudflareCallError("provider_request_failed", f"Cloudflare returned {response.status_code}")
    output = _extract_text(data)
    if not isinstance(output, str) or not output.strip():
        raise CloudflareCallError("provider_response_missing_text", "Cloudflare returned no text")
    usage = _extract_usage(data)
    prompt_tokens = int(usage.get("prompt_tokens") or usage.get("input_tokens") or 0)
    completion_tokens = int(usage.get("completion_tokens") or usage.get("output_tokens") or 0)
    neurons = _extract_neurons(data, response.headers, model, prompt_tokens, completion_tokens)
    return {
        "output": output[: settings.max_output_chars],
        "request_id": _extract_request_id(data, response.headers),
        "model": model,
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
        "neurons": neurons,
    }


async def run_verified(
    settings: Settings,
    messages: list[dict],
    *,
    max_tokens: int,
    temperature: float,
    transport: httpx.AsyncBaseTransport | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    token, account_id = resolve_credentials(settings)
    if not token or not account_id:
        raise CloudflareCallError("provider_not_configured", "Cloudflare credentials are not configured")
    model = assert_model_allowed(_model_from_settings(settings))
    verify_model = assert_model_allowed(_verify_model_from_settings(settings))
    max_tokens = min(int(max_tokens), _max_tokens_cap(settings))
    expected = exact_reply(messages)
    calls = 1 if expected is not None else 2
    reserved = reserve_budget(
        settings,
        model=model,
        messages=messages,
        max_tokens=max_tokens,
        calls=calls,
    )
    used = 0.0
    try:
        async with httpx.AsyncClient(transport=transport, timeout=_timeout(settings)) as client:
            primary = await _complete(
                client,
                settings,
                model=model,
                messages=messages,
                max_tokens=max_tokens,
                temperature=temperature,
                token=token,
                account_id=account_id,
            )
            used += float(primary.get("neurons") or 0)
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
                model=verify_model,
                messages=messages,
                max_tokens=max_tokens,
                temperature=0,
                token=token,
                account_id=account_id,
            )
            used += float(second.get("neurons") or 0)
            verdict = judge_outputs(primary["output"], second["output"], 0.0, settings.verify_similarity)
            verification = {
                "ok": verdict == "agree",
                "method": "second_model",
                "verifier_ids": verify_model,
                "verdict": verdict,
                "second_output_hash": output_hash(second["output"]),
            }
            return primary, verification
    finally:
        settle_budget(settings, reserved, used)


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
        "schema": "gpumesh.cloudflare_fallback.v1",
        "provider": "cloudflare",
        "runtime": "cloudflare-workers-ai",
        "model": model,
        "worker_id": f"cloudflare:{model}",
        "verifier_ids": str(verification.get("verifier_ids") or ""),
        "verifier_decision": "agree" if verification.get("ok") else "fail",
        "verification_method": str(verification.get("method") or ""),
        "output_hash": digest,
        "prompt_sha256": sha256_text(str(messages[-1].get("content") or "") if messages else ""),
        "request_id": request_id,
        "max_tokens": int(max_tokens),
        "prompt_tokens": int(primary.get("prompt_tokens") or 0),
        "completion_tokens": int(primary.get("completion_tokens") or 0),
        "neurons": float(primary.get("neurons") or 0),
        "duration_ms": int(duration_ms),
        "state": "OBSERVED",
        "promotion": "HOLD",
        "temperature_milli": int(round(float(temperature) * 1000)),
        "amount": 0,
        "credits": 0,
        "settlement_id": f"{job_id}:cloudflare",
        "job_id": job_id,
    }


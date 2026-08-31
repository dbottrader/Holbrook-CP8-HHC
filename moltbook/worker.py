"""Headless, provider-neutral Moltbook worker.

The LLM is not the scheduler. Run this module from GitHub Actions, cron,
systemd, Supabase-triggered infrastructure, or another persistent scheduler.
The worker refuses to complete a work item until the created post is read back
and a bound Moltbook receipt is present.

Environment:
  CP8_PROVIDER              xai | moonshot | openai | custom
  CP8_PROVIDER_API_KEY      custom provider key (presets use vendor env vars)
  CP8_PROVIDER_BASE_URL     custom base URL
  CP8_PROVIDER_STYLE        responses | chat_completions | anthropic
  CP8_PROVIDER_MODEL        override model
  XAI_API_KEY               xAI preset key
  MOONSHOT_API_KEY          Moonshot/Kimi preset key
  OPENAI_API_KEY            OpenAI preset key
  MOLTBOOK_TOKEN            existing capability token (optional)
  CP8_SELF_CONNECT          1 to self-onboard when MOLTBOOK_TOKEN is absent
  CP8_WORKER_HANDLE         requested handle for self-onboarding
  CP8_WORKER_CAPABILITIES   comma-separated heartbeat capabilities
  CP8_MAX_WORK_ITEMS        maximum completed items per invocation (default 1)
"""

from __future__ import annotations

import json
import os
import sys
from dataclasses import dataclass
from typing import Any, Mapping, Protocol, Sequence
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from .client import ClientError, MoltbookClient


class ProviderError(RuntimeError):
    """Provider configuration, transport, or response error."""


class TextProvider(Protocol):
    def generate(self, prompt: str) -> str: ...


@dataclass(frozen=True)
class ProviderConfig:
    style: str
    base_url: str
    api_key: str
    model: str
    max_tokens: int = 4096


def _json_post(
    url: str,
    payload: Mapping[str, Any],
    headers: Mapping[str, str],
    *,
    timeout: float = 180.0,
) -> dict[str, Any]:
    body = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    request = Request(
        url,
        data=body,
        method="POST",
        headers={"Content-Type": "application/json", **dict(headers)},
    )
    try:
        with urlopen(request, timeout=timeout) as response:
            raw = response.read()
            status = getattr(response, "status", 200)
    except HTTPError as error:
        raw = error.read()
        detail = raw.decode("utf-8", "replace")[:1000]
        raise ProviderError(f"provider HTTP {error.code}: {detail}") from error
    except URLError as error:
        raise ProviderError(f"provider request failed: {error.reason}") from error

    try:
        parsed = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ProviderError(f"provider returned non-JSON HTTP {status}") from error
    if not isinstance(parsed, dict):
        raise ProviderError("provider returned non-object JSON")
    return parsed


def _responses_text(payload: Mapping[str, Any]) -> str:
    direct = payload.get("output_text")
    if isinstance(direct, str) and direct.strip():
        return direct.strip()
    for output in payload.get("output", []) if isinstance(payload.get("output"), list) else []:
        if not isinstance(output, Mapping):
            continue
        for content in output.get("content", []) if isinstance(output.get("content"), list) else []:
            if not isinstance(content, Mapping):
                continue
            text = content.get("text")
            if isinstance(text, str) and text.strip():
                return text.strip()
    raise ProviderError("Responses API result contained no output text")


def _chat_text(payload: Mapping[str, Any]) -> str:
    choices = payload.get("choices")
    if not isinstance(choices, list) or not choices:
        raise ProviderError("chat completion result contained no choices")
    first = choices[0]
    if not isinstance(first, Mapping):
        raise ProviderError("chat completion choice is malformed")
    message = first.get("message")
    if not isinstance(message, Mapping):
        raise ProviderError("chat completion message is malformed")
    content = message.get("content")
    if not isinstance(content, str) or not content.strip():
        raise ProviderError("chat completion contained no text")
    return content.strip()


class HTTPTextProvider:
    def __init__(self, config: ProviderConfig) -> None:
        self.config = config

    def generate(self, prompt: str) -> str:
        cfg = self.config
        if cfg.style == "responses":
            result = _json_post(
                cfg.base_url.rstrip("/") + "/responses",
                {"model": cfg.model, "input": prompt, "store": False},
                {"Authorization": f"Bearer {cfg.api_key}"},
            )
            return _responses_text(result)
        if cfg.style == "chat_completions":
            result = _json_post(
                cfg.base_url.rstrip("/") + "/chat/completions",
                {
                    "model": cfg.model,
                    "messages": [{"role": "user", "content": prompt}],
                    "max_tokens": cfg.max_tokens,
                },
                {"Authorization": f"Bearer {cfg.api_key}"},
            )
            return _chat_text(result)
        if cfg.style == "anthropic":
            result = _json_post(
                cfg.base_url.rstrip("/") + "/messages",
                {
                    "model": cfg.model,
                    "max_tokens": cfg.max_tokens,
                    "messages": [{"role": "user", "content": prompt}],
                },
                {
                    "x-api-key": cfg.api_key,
                    "anthropic-version": "2023-06-01",
                },
            )
            blocks = result.get("content")
            if isinstance(blocks, list):
                text = "\n".join(
                    str(block.get("text", "")).strip()
                    for block in blocks
                    if isinstance(block, Mapping) and block.get("type") == "text"
                ).strip()
                if text:
                    return text
            raise ProviderError("Anthropic result contained no text")
        raise ProviderError(f"unsupported provider style: {cfg.style}")


def provider_from_env() -> HTTPTextProvider:
    provider = os.getenv("CP8_PROVIDER", "custom").strip().lower()
    presets: dict[str, tuple[str, str, str, str | None]] = {
        "xai": ("responses", "https://api.x.ai/v1", "XAI_API_KEY", "grok-4.5"),
        "moonshot": (
            "chat_completions",
            "https://api.moonshot.ai/v1",
            "MOONSHOT_API_KEY",
            "kimi-k2.6",
        ),
        "openai": ("responses", "https://api.openai.com/v1", "OPENAI_API_KEY", None),
    }

    if provider in presets:
        style, base_url, key_env, default_model = presets[provider]
        api_key = os.getenv(key_env, "")
        model = os.getenv("CP8_PROVIDER_MODEL", default_model or "")
    else:
        style = os.getenv("CP8_PROVIDER_STYLE", "")
        base_url = os.getenv("CP8_PROVIDER_BASE_URL", "")
        api_key = os.getenv("CP8_PROVIDER_API_KEY", "")
        model = os.getenv("CP8_PROVIDER_MODEL", "")

    if not api_key:
        raise ProviderError(f"missing API key for provider {provider}")
    if not model:
        raise ProviderError(f"missing CP8_PROVIDER_MODEL for provider {provider}")
    if not base_url or not style:
        raise ProviderError("custom provider requires CP8_PROVIDER_BASE_URL and CP8_PROVIDER_STYLE")

    max_tokens = int(os.getenv("CP8_PROVIDER_MAX_TOKENS", "4096"))
    return HTTPTextProvider(
        ProviderConfig(
            style=style,
            base_url=base_url,
            api_key=api_key,
            model=model,
            max_tokens=max_tokens,
        )
    )


def _items(payload: Mapping[str, Any]) -> list[dict[str, Any]]:
    for key in ("items", "work_items", "work"):
        value = payload.get(key)
        if isinstance(value, list):
            return [dict(item) for item in value if isinstance(item, Mapping)]
    return []


def _post(payload: Mapping[str, Any]) -> dict[str, Any]:
    nested = payload.get("post")
    if isinstance(nested, Mapping):
        return dict(nested)
    return dict(payload)


def _prompt_for(item: Mapping[str, Any]) -> str:
    return (
        "You are an external worker participating in the ASIN-HHC / CP8 Moltbook "
        "evidence protocol. Perform the work described below. Use evidence over narration. "
        "Separate OBSERVED facts from INFERRED conclusions and unresolved limitations. "
        "Do not claim to have used tools or sources you did not actually use. Do not expose "
        "secrets. Return a substantive contribution suitable for persistence as a Moltbook "
        "HOLD post; do not include a fake receipt, UUID, or hash. The runtime will generate "
        "and verify those after your text is posted.\n\nWORK ITEM\n"
        + json.dumps(item, indent=2, sort_keys=True, default=str)
    )


def _created_binding(payload: Mapping[str, Any]) -> tuple[str, str]:
    post = _post(payload)
    post_id = post.get("post_id")
    content_hash = post.get("content_hash")
    if not isinstance(post_id, str) or not post_id:
        raise RuntimeError("created post response missing post_id")
    if not isinstance(content_hash, str) or len(content_hash) != 64:
        raise RuntimeError("created post response missing content_hash")
    return post_id, content_hash


def _verify_readback(payload: Mapping[str, Any], post_id: str, content_hash: str) -> None:
    post = _post(payload)
    if post.get("post_id") != post_id:
        raise RuntimeError("readback post_id mismatch")
    if post.get("content_hash") != content_hash:
        raise RuntimeError("readback content_hash mismatch")
    receipts = payload.get("receipts")
    if payload.get("has_bound_receipt") is not True or not isinstance(receipts, list) or not receipts:
        raise RuntimeError("readback has no bound receipt")


def run_once(client: MoltbookClient, provider: TextProvider, *, max_items: int = 1) -> list[dict[str, Any]]:
    capabilities = [
        value.strip()
        for value in os.getenv(
            "CP8_WORKER_CAPABILITIES", "research,review,coding,testing,integration"
        ).split(",")
        if value.strip()
    ]
    client.heartbeat(capabilities=capabilities, current_work_id=None)
    queue = _items(client.list_work(limit=20))
    results: list[dict[str, Any]] = []

    for item in queue:
        if len(results) >= max_items:
            break
        if item.get("status", "open") != "open":
            continue
        work_id = item.get("work_id")
        if not isinstance(work_id, str):
            continue

        try:
            claim = client.claim_work(work_id, lease_minutes=30)
        except ClientError:
            # The server owns role/scope/dependency/lease authorization. A rejected
            # claim is not bypassed or retried in this invocation.
            continue

        claimed = claim.get("item") if isinstance(claim.get("item"), Mapping) else item
        try:
            contribution = provider.generate(_prompt_for(claimed))
            metadata = claimed.get("metadata") if isinstance(claimed, Mapping) else {}
            if not isinstance(metadata, Mapping):
                metadata = {}
            parent_post_id = metadata.get("parent_post_id")
            evidence_refs: list[str] = [f"work:{work_id}"]

            if isinstance(parent_post_id, str) and parent_post_id:
                parent_readback = client.get_post(parent_post_id)
                parent = _post(parent_readback)
                parent_hash = parent.get("content_hash")
                if not isinstance(parent_hash, str) or len(parent_hash) != 64:
                    raise RuntimeError("parent readback missing content_hash")
                evidence_refs.insert(0, f"sha256:{parent_hash}")
                created = client.reply(
                    parent_post_id,
                    contribution,
                    evidence_refs=evidence_refs,
                )
            else:
                room_slug = str(claimed.get("room_slug") or "cp8-ops")
                created = client.create_post(
                    room_slug,
                    contribution,
                    evidence_refs=evidence_refs,
                    status="OBSERVED",
                )

            post_id, content_hash = _created_binding(created)
            readback = client.get_post(post_id)
            _verify_readback(readback, post_id, content_hash)
            completed = client.complete_work(
                work_id,
                result_post_id=post_id,
                result_hash=content_hash,
            )
            results.append(
                {
                    "schema": "CP8-AGENT-RETURN-v1",
                    "agent": os.getenv("CP8_WORKER_HANDLE", "headless-worker"),
                    "task_id": work_id,
                    "status": "COMPLETED",
                    "result_post_id": post_id,
                    "result_hash": content_hash,
                    "verified": True,
                    "promotion": "HOLD",
                    "completion": completed.get("item", completed),
                }
            )
        except Exception as error:
            reason = f"headless worker failed after claim: {type(error).__name__}: {error}"
            try:
                client.fail_work(work_id, reason=reason[:1000])
            except Exception:
                pass
            results.append(
                {
                    "schema": "CP8-AGENT-RETURN-v1",
                    "agent": os.getenv("CP8_WORKER_HANDLE", "headless-worker"),
                    "task_id": work_id,
                    "status": "FAILED",
                    "result_post_id": None,
                    "result_hash": None,
                    "verified": False,
                    "promotion": "HOLD",
                    "summary": reason,
                }
            )

    return results


def main() -> int:
    handle = os.getenv("CP8_WORKER_HANDLE", "headless-worker")
    token = os.getenv("MOLTBOOK_TOKEN")
    self_connect = os.getenv("CP8_SELF_CONNECT", "0") == "1"

    try:
        provider = provider_from_env()
    except ProviderError as error:
        print(json.dumps({"status": "SKIPPED", "reason": str(error)}))
        return 0

    client = MoltbookClient(token=token)
    if not client.token:
        if not self_connect:
            print(json.dumps({"status": "SKIPPED", "reason": "missing MOLTBOOK_TOKEN"}))
            return 0
        try:
            client.connect(handle, display_name=handle, ttl_minutes=120)
        except ClientError as error:
            print(json.dumps({"status": "FAILED", "reason": f"Moltbook connect failed: {error}"}))
            return 1

    max_items = max(1, int(os.getenv("CP8_MAX_WORK_ITEMS", "1")))
    try:
        results = run_once(client, provider, max_items=max_items)
    except (ClientError, ProviderError, RuntimeError, ValueError) as error:
        print(json.dumps({"status": "FAILED", "reason": str(error)}))
        return 1

    print(json.dumps({"status": "OK", "results": results}, sort_keys=True))
    return 0 if all(result.get("status") != "FAILED" for result in results) else 1


if __name__ == "__main__":
    sys.exit(main())

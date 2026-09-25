"""Capability-aware wrapper for the receipt-gated Moltbook worker.

This module prevents a worker from claiming work that requires execution
capabilities its current host does not expose. The model/provider name is never
treated as evidence of available tools, transport, persistence, or authority.

Environment:
  CP8_PLATFORM                 host/runtime label (default: headless)
  CP8_WORKER_CAPABILITIES      reasoning/task capabilities, comma-separated
  CP8_EXECUTION_CAPABILITIES   concrete execution capabilities, comma-separated
  CP8_WORKER_LIMITATIONS       observed host limitations, comma-separated

Work items may declare requirements in metadata.requires:

  {
    "requires": {
      "capabilities": ["research", "testing"],
      "execution": ["http", "moltbook_write"]
    }
  }

Legacy metadata.required_capabilities is also recognized.
"""

from __future__ import annotations

import json
import os
import sys
from typing import Any, Mapping

from .client import ClientError, MoltbookClient
from .worker import ProviderError, provider_from_env, run_once


def _csv(name: str, default: str = "") -> list[str]:
    return [value.strip() for value in os.getenv(name, default).split(",") if value.strip()]


def execution_profile() -> dict[str, Any]:
    return {
        "schema": "CP8-EXECUTION-PROFILE-v1",
        "platform": os.getenv("CP8_PLATFORM", "headless").strip() or "headless",
        "capabilities": _csv(
            "CP8_WORKER_CAPABILITIES",
            "research,review,coding,testing,integration",
        ),
        "execution": _csv("CP8_EXECUTION_CAPABILITIES"),
        "limitations": _csv("CP8_WORKER_LIMITATIONS"),
    }


def _string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item).strip() for item in value if str(item).strip()]


def requirements_for(item: Mapping[str, Any]) -> dict[str, list[str]]:
    metadata = item.get("metadata")
    if not isinstance(metadata, Mapping):
        metadata = {}
    requires = metadata.get("requires")
    if not isinstance(requires, Mapping):
        requires = {}

    capabilities = _string_list(requires.get("capabilities"))
    capabilities.extend(_string_list(metadata.get("required_capabilities")))
    execution = _string_list(requires.get("execution"))

    return {
        "capabilities": sorted(set(capabilities)),
        "execution": sorted(set(execution)),
    }


def missing_requirements(
    item: Mapping[str, Any], profile: Mapping[str, Any]
) -> dict[str, list[str]]:
    required = requirements_for(item)
    available_capabilities = set(_string_list(profile.get("capabilities")))
    available_execution = set(_string_list(profile.get("execution")))

    missing = {
        "capabilities": [
            value for value in required["capabilities"] if value not in available_capabilities
        ],
        "execution": [
            value for value in required["execution"] if value not in available_execution
        ],
    }
    return {key: values for key, values in missing.items() if values}


class CapabilityFilteringClient:
    """Delegate to MoltbookClient while filtering incompatible open work."""

    def __init__(self, client: MoltbookClient, profile: Mapping[str, Any]) -> None:
        self._client = client
        self.profile = dict(profile)
        self.skipped: list[dict[str, Any]] = []

    @property
    def token(self) -> str | None:
        return self._client.token

    def heartbeat(self, *, capabilities: list[str], current_work_id: str | None) -> Any:
        declared = list(capabilities)
        for value in _string_list(self.profile.get("execution")):
            token = f"exec:{value}"
            if token not in declared:
                declared.append(token)
        platform = str(self.profile.get("platform") or "").strip()
        if platform:
            token = f"platform:{platform}"
            if token not in declared:
                declared.append(token)
        return self._client.heartbeat(
            capabilities=declared,
            current_work_id=current_work_id,
        )

    def list_work(self, *, limit: int = 20) -> dict[str, Any]:
        payload = self._client.list_work(limit=limit)
        if not isinstance(payload, Mapping):
            return payload

        result = dict(payload)
        for key in ("items", "work_items", "work"):
            value = result.get(key)
            if not isinstance(value, list):
                continue

            compatible: list[Any] = []
            for item in value:
                if not isinstance(item, Mapping):
                    compatible.append(item)
                    continue
                missing = missing_requirements(item, self.profile)
                if missing:
                    self.skipped.append(
                        {
                            "work_id": item.get("work_id"),
                            "title": item.get("title"),
                            "status": "SKIPPED_CAPABILITY_MISMATCH",
                            "missing": missing,
                        }
                    )
                    continue
                compatible.append(item)
            result[key] = compatible
            break
        return result

    def __getattr__(self, name: str) -> Any:
        return getattr(self._client, name)


def main() -> int:
    handle = os.getenv("CP8_WORKER_HANDLE", "headless-worker")
    token = os.getenv("MOLTBOOK_TOKEN")
    self_connect = os.getenv("CP8_SELF_CONNECT", "0") == "1"
    profile = execution_profile()

    try:
        provider = provider_from_env()
    except ProviderError as error:
        print(
            json.dumps(
                {
                    "status": "SKIPPED",
                    "reason": str(error),
                    "execution_profile": profile,
                },
                sort_keys=True,
            )
        )
        return 0

    base_client = MoltbookClient(token=token)
    if not base_client.token:
        if not self_connect:
            print(
                json.dumps(
                    {
                        "status": "SKIPPED",
                        "reason": "missing MOLTBOOK_TOKEN",
                        "execution_profile": profile,
                    },
                    sort_keys=True,
                )
            )
            return 0
        try:
            base_client.connect(handle, display_name=handle, ttl_minutes=120)
        except ClientError as error:
            print(
                json.dumps(
                    {
                        "status": "FAILED",
                        "reason": f"Moltbook connect failed: {error}",
                        "execution_profile": profile,
                    },
                    sort_keys=True,
                )
            )
            return 1

    client = CapabilityFilteringClient(base_client, profile)
    max_items = max(1, int(os.getenv("CP8_MAX_WORK_ITEMS", "1")))

    try:
        results = run_once(client, provider, max_items=max_items)
    except (ClientError, ProviderError, RuntimeError, ValueError) as error:
        print(
            json.dumps(
                {
                    "status": "FAILED",
                    "reason": str(error),
                    "execution_profile": profile,
                    "preflight_skips": client.skipped,
                },
                sort_keys=True,
            )
        )
        return 1

    print(
        json.dumps(
            {
                "status": "OK",
                "execution_profile": profile,
                "preflight_skips": client.skipped,
                "results": results,
            },
            sort_keys=True,
        )
    )
    return 0 if all(result.get("status") != "FAILED" for result in results) else 1


if __name__ == "__main__":
    sys.exit(main())

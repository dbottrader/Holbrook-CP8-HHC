from __future__ import annotations

import json
import os
from dataclasses import dataclass
from urllib.request import Request, urlopen


class ModelAdapter:
    name = "base"

    def generate(self, prompt: str) -> str:
        raise NotImplementedError


class NullAdapter(ModelAdapter):
    name = "null"

    def generate(self, prompt: str) -> str:
        return "No model configured. Set HOLBROOK_MODEL_URL to execute the request."


@dataclass
class OpenAICompatibleAdapter(ModelAdapter):
    base_url: str
    model: str = "default"
    api_key: str | None = None
    timeout: int = 60
    name: str = "openai-compatible"

    def generate(self, prompt: str) -> str:
        url = self.base_url.rstrip("/") + "/chat/completions"
        payload = {
            "model": self.model,
            "messages": [{"role": "user", "content": prompt}],
        }
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        request = Request(url, data=json.dumps(payload).encode(), headers=headers)
        with urlopen(request, timeout=self.timeout) as result:
            body = json.loads(result.read().decode())
        choices = body.get("choices") or []
        if choices:
            message = choices[0].get("message") or {}
            return str(message.get("content", ""))
        return str(body.get("response", body.get("text", body)))


def adapter_from_environment() -> ModelAdapter:
    url = os.getenv("HOLBROOK_MODEL_URL")
    if not url:
        return NullAdapter()
    return OpenAICompatibleAdapter(
        base_url=url,
        model=os.getenv("HOLBROOK_MODEL", "default"),
        api_key=os.getenv("HOLBROOK_API_KEY"),
    )

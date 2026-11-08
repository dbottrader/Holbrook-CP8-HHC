"""Test-only runtimes. They are not wired to the CLI or the installer."""

from __future__ import annotations

from gpumesh_node.runtime import InferenceResult

MODEL = "SmolLM2-360M-Instruct"
DIGEST = "weights-pin"


class FixedTextRuntime:
    """Returns one fixed string so two workers agree in hub tests."""

    def __init__(self, text: str = "DETERMINISTIC_MESH_TEXT", model: str = MODEL, digest: str = DIGEST) -> None:
        self.name = "llamacpp"
        self.prompt_proofs = True
        self.text = text
        self.model = model
        self.digest = digest
        self.seen: list[dict] = []

    async def list_models(self) -> list[dict]:
        return [{"id": self.model, "resident": True, "source": "llama.cpp", "digest": self.digest}]

    async def complete(self, job: dict, on_delta) -> InferenceResult:
        self.seen.append(dict(job))
        if on_delta is not None and self.text:
            await on_delta(self.text)
        return InferenceResult(self.text, 4, max(1, len(self.text.split())), 5, "stop")

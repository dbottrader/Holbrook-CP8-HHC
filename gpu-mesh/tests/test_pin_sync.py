"""The join image has gpumesh_node and not the coordinator package."""

from __future__ import annotations

import re
import sys
from pathlib import Path

from gpumesh import textutil
from gpumesh_node import pins

_NAMES = ("DET_TEMPERATURE", "DET_TOP_K", "DET_TOP_P", "DET_REPEAT_PENALTY", "DET_NUM_CTX")
_NODE = Path(pins.__file__).resolve().parent
_PROTOCOL = Path(__file__).resolve().parents[2] / "supabase" / "functions" / "gpu-mesh" / "protocol.mjs"


def test_hub_node_and_edge_pins_match():
    for name in _NAMES:
        assert getattr(textutil, name) == getattr(pins, name)
    source = _PROTOCOL.read_text(encoding="utf-8")
    for name in ("DET_TOP_K", "DET_TOP_P", "DET_REPEAT_PENALTY", "DET_NUM_CTX"):
        match = re.search(rf"export const {name} = ([0-9.]+);", source)
        assert match, name
        assert float(match.group(1)) == float(getattr(pins, name))


def test_node_sources_do_not_import_the_coordinator():
    for path in sorted(_NODE.glob("*.py")):
        for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            code = line.split("#", 1)[0]
            assert not re.search(r"\b(?:import|from)\s+gpumesh\b", code), f"{path.name}:{lineno}"


def test_runtime_imports_when_the_coordinator_package_is_missing():
    class _BlockCoordinator:
        def find_spec(self, fullname, path, target=None):
            if fullname == "gpumesh" or fullname.startswith("gpumesh."):
                raise ModuleNotFoundError(fullname)
            return None

    finder = _BlockCoordinator()
    saved = {
        name: sys.modules.pop(name)
        for name in ("gpumesh_node.pins", "gpumesh_node.runtime", "gpumesh_node.llamacpp")
        if name in sys.modules
    }
    sys.meta_path.insert(0, finder)
    try:
        import gpumesh_node.runtime as runtime

        assert runtime.generation_controls({"seed": 0})["num_ctx"] == pins.DET_NUM_CTX
        assert runtime.generation_controls({"seed": 0})["top_p"] == pins.DET_TOP_P
    finally:
        sys.meta_path.remove(finder)
        sys.modules.update(saved)

"""The evidence script decodes the first real Base Sepolia settlement log."""

import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _module():
    path = ROOT / "gpu-mesh" / "scripts" / "evidence_packet.py"
    spec = importlib.util.spec_from_file_location("evidence_packet", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_first_settlement_log_is_a_90_5_5_split():
    module = _module()
    log = json.loads((ROOT / "tests" / "fixtures" / "base-sepolia-settled-log.json").read_text(encoding="utf-8"))
    decoded = module.decode_settled_log(log)
    assert decoded["chain_id"] == 84532
    assert decoded["worker"] == "0x99334f7e733ca137dc6665106ca6df96dd97b563"
    assert decoded["verifier1"] == "0x2d49700fc13b5bafbf789a7d09c799a858b8b423"
    assert decoded["worker_amount"] == 18000
    assert decoded["verifier1_amount"] == 1000
    assert decoded["verifier2_amount"] == 1000
    assert decoded["contribution_minor"] == 20000
    assert decoded["split_ok"] is True
    assert module.decode_settled_log({"topics": ["0x" + "11" * 32], "data": "0x"}) is None

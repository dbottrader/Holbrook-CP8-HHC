"""The GitHub Actions checker pins the model bytes and needs no secret."""

import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MODELFILE = (
    "FROM ./qwen2.5-0.5b-instruct-q4_k_m.gguf\n"
    'TEMPLATE """{{ if .System }}<|im_start|>system\n'
    "{{ .System }}<|im_end|>\n"
    "{{ end }}{{ range .Messages }}<|im_start|>{{ .Role }}\n"
    "{{ .Content }}<|im_end|>\n"
    "{{ end }}<|im_start|>assistant\n"
    '"""\n'
    "PARAMETER stop <|im_end|>\n"
    "PARAMETER stop <|im_start|>\n"
)


def _wait_module():
    path = ROOT / "gpu-mesh" / "scripts" / "checker_node_wait.py"
    spec = importlib.util.spec_from_file_location("checker_node_wait", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_modelfile_bytes():
    path = ROOT / "gpu-mesh" / "models" / "asin-qwen0.5b.Modelfile"
    assert path.read_bytes() == MODELFILE.encode()


def test_workflow_pins_the_free_checker_and_no_secret():
    text = (ROOT / ".github" / "workflows" / "checker-node.yml").read_text(encoding="utf-8")
    assert "workflow_dispatch:" in text
    assert "\npull_request:" not in text
    assert "\npush:" not in text
    assert "ubuntu-latest" in text
    assert "v0.40.15" in text
    assert "ollama-linux-amd64.tar.zst" in text
    assert "install.sh" not in text
    assert "74a4da8c9fdbcd15bd1f6d01d621410d31c6fc00986f5eb687824e7b93d7a9db" in text
    assert "29ef26c5cf7d3d68a20fdeb8664ef48f1f32386d2ba09ddb4b19f4c7dc89d5de" in text
    assert "gpu-mesh/models/asin-qwen0.5b.Modelfile" in text
    assert "asin-qwen0.5b:latest" in text
    assert "gh-actions-checker" in text
    assert "0x99334f7e733Ca137dc6665106cA6dF96dD97b563" in text
    assert "python -m gpumesh_node" in text
    assert "https://ecenvlwyenpakrxfuqup.supabase.co/functions/v1/gpu-mesh" in text
    assert "secrets." not in text
    assert "actual digest:" in text
    assert "timeout-minutes: 90" in text
    assert "inputs.minutes +" not in text
    # Actions ends background processes with the step, so serve and the node share one step.
    between = text[text.find("ollama serve >"):text.find("python -m gpumesh_node")]
    assert between
    assert "\n      - name:" not in between


def test_dispatch_helper_calls_workflow_dispatch_once():
    text = (ROOT / ".github" / "workflows" / "dispatch-checker.yml").read_text(encoding="utf-8")
    assert "gh workflow run checker-node.yml --ref main -f minutes=30" in text
    assert "actions: write" in text
    assert "github.token" in text
    assert "secrets." not in text
    assert ".github/workflows/dispatch-checker.yml" in text


def test_verification_receipt_is_the_stop_signal():
    module = _wait_module()
    node = "node_aabbccddeeff"
    payload = {
        "job_id": "job_44a573a3d1d1",
        "parent_job_id": "job_38ad69a042f5",
    }
    receipts = [
        {"actor": node, "kind": "inference_receipt", "payload": "{}"},
        {
            "actor": "node_other",
            "kind": "verification_pass",
            "payload": json.dumps(payload),
        },
        {
            "actor": node,
            "kind": "verification_pass",
            "payload": json.dumps(payload),
        },
    ]
    found = module.verification_for(node, receipts)
    assert found == {
        "kind": "verification_pass",
        "job_id": "job_44a573a3d1d1",
        "parent_job_id": "job_38ad69a042f5",
    }
    assert module.verification_for(node, receipts[:1]) is None
    log = (
        "2026-11-08 00:00:00,000 INFO gpumesh.node registered node_aabbccddeeff as gh-actions-checker\n"
        "2026-11-08 00:00:04,000 INFO gpumesh.node finished job_44a573a3d1d1 in 900ms\n"
    )
    assert module.node_id_from_log(log) == node
    assert module.finished_job_ids(log) == ["job_44a573a3d1d1"]

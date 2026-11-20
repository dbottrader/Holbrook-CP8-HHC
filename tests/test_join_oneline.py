"""The one-command join script keeps the verifier pins the checker workflow uses."""

import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
JOIN = ROOT / "gpu-mesh" / "deploy" / "join" / "join.sh"
WORKFLOW = ROOT / ".github" / "workflows" / "checker-node.yml"


def test_join_script_parses():
    subprocess.run(["bash", "-n", str(JOIN)], check=True)


def test_join_script_pins_match_checker_workflow():
    text = JOIN.read_text(encoding="utf-8")
    workflow = WORKFLOW.read_text(encoding="utf-8")
    for pin in (
        "29ef26c5cf7d3d68a20fdeb8664ef48f1f32386d2ba09ddb4b19f4c7dc89d5de",
        "74a4da8c9fdbcd15bd1f6d01d621410d31c6fc00986f5eb687824e7b93d7a9db",
        "628c018404a4206493efd38e46251c154ede5141b8b8dc85c659b3b027c47379",
        "asin-qwen0.5b:latest",
    ):
        assert pin in text
        assert pin in workflow
    assert 'OLLAMA_VERSION="0.40.15"' in text
    assert "v0.40.15" in workflow


def test_join_script_pins_one_cpu_backend_and_reference_replay():
    text = JOIN.read_text(encoding="utf-8")
    assert 'CPU_BACKEND="libggml-cpu-haswell.so"' in text
    assert "job_17da8f18d97f" in text
    assert "d30ca7a7a32bf5772dc5eb2a2e7bd35737eff795ad74f2479b359716b59abdfa" in text
    assert "1674994887" in text


def test_join_script_dry_run_changes_nothing(tmp_path):
    home = tmp_path / "asin"
    done = subprocess.run(
        ["bash", str(JOIN), "--dry-run", "--home", str(home)], capture_output=True, text=True
    )
    assert done.returncode == 0, done.stderr
    assert "https://ecenvlwyenpakrxfuqup.supabase.co/functions/v1/gpu-mesh" in done.stdout
    assert "dry run: nothing changed" in done.stdout
    assert not home.exists()


def test_join_script_rejects_bad_payout():
    done = subprocess.run(
        ["bash", str(JOIN), "--dry-run", "--payout-address", "0x" + "0" * 40],
        capture_output=True,
        text=True,
    )
    assert done.returncode != 0


def test_join_copy_stays_utility_only():
    page = (ROOT / "site" / "join" / "index.html").read_text(encoding="utf-8").lower()
    guide = (ROOT / "CONTRIBUTING-GPU.md").read_text(encoding="utf-8").lower()
    for text in (page, guide, JOIN.read_text(encoding="utf-8").lower()):
        assert "utility credit for verified contribution" in text
        for banned in ("token sale", "airdrop", "investor", "price", "returns", "\u2014"):
            assert banned not in text
    assert "join.sh" in page

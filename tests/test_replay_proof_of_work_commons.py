import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def load_replay():
    path = ROOT / "scripts" / "replay_proof_of_work_commons.py"
    spec = importlib.util.spec_from_file_location("replay_powc", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_settlement_conserves_every_small_price():
    replay = load_replay()
    for price in range(1, 401):
        paid = replay.settle(price, ["pass", "pass"])
        assert (
            paid["worker_milli"]
            + paid["verifier_a_milli"]
            + paid["verifier_b_milli"]
            + paid["publisher_milli"]
            == price
        )
        assert paid["state"] == "TERMINAL_PAID"
        refund = replay.settle(price, ["pass", "fail"])
        assert refund["publisher_milli"] == price
        assert refund["worker_milli"] == refund["verifier_a_milli"] == refund["verifier_b_milli"] == 0
        assert refund["state"] == "TERMINAL_REFUNDED"


def test_known_splits_and_display():
    replay = load_replay()
    paid = replay.settle(10000, ["pass", "pass"])
    assert (paid["worker_milli"], paid["verifier_a_milli"], paid["verifier_b_milli"]) == (9000, 500, 500)
    assert replay.format_hhc(10000) == "10.000"
    assert replay.format_hhc(9000) == "9.000"
    assert replay.format_hhc(500) == "0.500"
    assert replay.format_hhc(7) == "0.007"
    probe = replay.settle(7, ["pass", "pass"])
    assert (probe["worker_milli"], probe["publisher_milli"], probe["remainder_milli"]) == (6, 1, 1)


def test_fence_rule():
    replay = load_replay()
    assert replay.claim_allowed(None, -1, 0, "worker")
    assert not replay.claim_allowed("worker", 40, 11, "rival")
    assert replay.claim_allowed("worker", 40, 40, "rival")
    assert replay.claim_allowed("worker", 40, 11, "worker")


def test_launch_gates_pass_and_artifacts_match(tmp_path):
    replay = load_replay()
    config = (ROOT / "site" / "config.js").read_text(encoding="utf-8")
    built = replay.build(config)
    assert built["ok"]
    assert [gate["id"] for gate in built["gates"]] == list(replay.GATE_IDS)
    assert all(gate["status"] == "PASS" for gate in built["gates"])
    assert len(built["gates"]) == 8

    rejected = [item for item in built["receipts"] if item["kind"] == "lease_rejected"]
    assert rejected and rejected[0]["body"]["reason"] == "fence_held"
    assert replay.verify_chain(built["receipts"])[0]

    replay.write_artifacts(tmp_path, built)
    assert replay.compare_artifacts(tmp_path, built) == []
    again = replay.build(config)
    assert again["replay_bytes"] == built["replay_bytes"]
    assert again["receipts_bytes"] == built["receipts_bytes"]
    assert b"eyJ" not in built["replay_bytes"]
    assert b"service_role" not in built["replay_bytes"]

    committed = ROOT / "site" / "proof"
    assert replay.compare_artifacts(committed, built) == []


def test_tampered_receipt_fails_chain():
    replay = load_replay()
    config = (ROOT / "site" / "config.js").read_text(encoding="utf-8")
    receipts = replay.build(config)["receipts"]
    receipts[-1]["receipt_hash"] = "0" * 64
    ok, detail = replay.verify_chain(receipts)
    assert not ok
    assert "does not recompute" in detail


def test_privileged_config_fails_boundary_gate():
    replay = load_replay()
    problem, _note = replay.check_public_config(
        'apiBase: "https://example.invalid"\npublishableKey: "service_role"\n'
    )
    assert problem
    assert "service_role" in problem


def test_public_pages_are_wired():
    replay = load_replay()
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    assert "## Live demo" in readme
    assert "https://dbottrader.github.io/Holbrook-CP8-HHC/" in readme

    workflow = (ROOT / ".github" / "workflows" / "pages.yml").read_text(encoding="utf-8")
    assert "workflow_dispatch" in workflow
    assert "branches: [main]" in workflow
    assert "replay_proof_of_work_commons.py" in workflow
    assert "path: site" in workflow

    proof_html = (ROOT / "site" / "proof.html").read_text(encoding="utf-8")
    for gate_id in replay.GATE_IDS:
        assert gate_id in proof_html

    for name in ("feed.js", "proof.js"):
        text = (ROOT / "site" / name).read_text(encoding="utf-8")
        for banned in ("innerHTML", "outerHTML", "insertAdjacentHTML", "document.write"):
            assert banned not in text

    config = (ROOT / "site" / "config.js").read_text(encoding="utf-8")
    assert replay.check_public_config(config)[0] is None

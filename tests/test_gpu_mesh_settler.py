"""Box settler: mock the RPC, keep the deployer key out of logs."""

from __future__ import annotations

import importlib.util
import logging
from pathlib import Path
from types import SimpleNamespace

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from web3 import Web3

from moltbook.ledger.mesh_receipt import GENESIS_PREV, sign_mesh_receipt

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("gpu_mesh_settle", ROOT / "gpu-mesh" / "settler" / "settle.py")
settle = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(settle)

# Public Anvil development key. This is not the Base Sepolia deployer key.
TEST_KEY = "ac0974bec39a17e36ba4a6b4d238ff944bacb478cbed5efcae784d7bf4f2ff80"
WORKER = "0x1111111111111111111111111111111111111111"
VERIFIER_A = "0x2222222222222222222222222222222222222222"
VERIFIER_B = "0x3333333333333333333333333333333333333333"


class FakeEth:
    def __init__(self, state):
        self.state = state

    def contract(self, address, abi):
        return SimpleNamespace(functions=FakeFunctions(self.state))

    def get_transaction_count(self, address):
        return 0

    def estimate_gas(self, tx):
        self.state["estimated"] = tx
        return 120_000

    def send_raw_transaction(self, raw):
        self.state["raw"] = bytes(raw)
        return bytes.fromhex("ab" * 32)

    def wait_for_transaction_receipt(self, tx_hash):
        self.state["waited"] = tx_hash
        return SimpleNamespace(transactionHash=bytes.fromhex("ab" * 32), blockNumber=9, status=1)


class FakeCall:
    def __init__(self, name, args, state):
        self.name = name
        self.args = args
        self.state = state

    def call(self):
        if self.name == "settled":
            return False
        if self.name == "balanceOf":
            return 0
        raise AssertionError(self.name)

    def build_transaction(self, base):
        self.state["calls"].append((self.name, self.args, base))
        return {
            "from": base["from"],
            "nonce": base["nonce"],
            "chainId": base["chainId"],
            "gasPrice": 1_000_000_000,
            "gas": 120_000,
            "to": Web3.to_checksum_address(settle.SETTLEMENT),
            "data": "0x",
            "value": 0,
        }


class FakeFunctions:
    def __init__(self, state):
        self.state = state

    def __getattr__(self, name):
        def invoke(*args):
            return FakeCall(name, args, self.state)

        return invoke


class FakeWeb3:
    def __init__(self):
        self.state = {"calls": []}
        self.eth = FakeEth(self.state)

    def is_connected(self):
        return True


def _receipt():
    private = Ed25519PrivateKey.generate()
    return sign_mesh_receipt(
        actor="node_a",
        kind="inference_receipt",
        payload={
            "schema": "gpumesh.chain_settlement.v1",
            "status": "verified",
            "verifier_decision": "agree",
            "worker_id": "node_a",
            "verifier_ids": ["node_b", "node_c"],
            "settlement_id": "mesh:job_1",
            "amount": 4000,
        },
        prev_hash=GENESIS_PREV,
        seq=2,
        ts=1700000000000,
        private_key=private,
    )


def _item(**overrides):
    body = {
        "id": "mesh:job_1",
        "job_id": "job_1",
        "worker_id": "node_a",
        "verifier1_id": "node_b",
        "verifier2_id": "node_c",
        "worker_address": WORKER,
        "verifier1_address": VERIFIER_A,
        "verifier2_address": VERIFIER_B,
        "receipt": _receipt(),
    }
    body.update(overrides)
    return body


def test_key_file_is_read_and_not_described(tmp_path, caplog):
    path = tmp_path / ".deployer.key"
    path.write_text("0x" + TEST_KEY + "\n", encoding="utf-8")
    with caplog.at_level(logging.DEBUG):
        assert settle.read_key(path) == TEST_KEY
    assert TEST_KEY not in caplog.text
    path.write_text("not-a-key", encoding="utf-8")
    with pytest.raises(SystemExit) as exc:
        settle.read_key(path)
    assert "not-a-key" not in str(exc.value)
    assert TEST_KEY not in str(exc.value)


def test_missing_payout_and_self_verify_do_not_submit():
    class Exploding:
        def settle_verified_receipt(self, *args, **kwargs):
            raise AssertionError("rpc must not be called")

    tx, status = settle.settle_one(Exploding(), _item(worker_address=""))
    assert tx == ""
    assert status == "skipped_missing_payout"
    tx, status = settle.settle_one(Exploding(), _item(verifier2_id="node_a"))
    assert status == "skipped_verifier_independence"
    tx, status = settle.settle_one(Exploding(), _item(verifier2_id="node_b"))
    assert status == "skipped_verifier_independence"


def test_settle_one_submits_through_a_mock_rpc():
    w3 = FakeWeb3()
    ledger = settle.build_ledger(TEST_KEY, "https://example.invalid/rpc", w3=w3)
    hub_posts = []

    class Hub:
        def pending(self):
            return [_item()]

        def post_result(self, settlement_id, tx_hash, status):
            hub_posts.append((settlement_id, tx_hash, status))
            return {"id": settlement_id, "tx_hash": tx_hash, "status": status}

    posted = settle.poll_once(Hub(), ledger)
    assert posted == [{"id": "mesh:job_1", "tx_hash": "0x" + "ab" * 32, "status": "settled"}]
    assert hub_posts == [("mesh:job_1", "0x" + "ab" * 32, "settled")]
    name, args, base = w3.state["calls"][0]
    assert name == "settle"
    assert args[2] == 3600
    assert args[4] == 200
    assert args[6] == 200
    assert args[7] == 4000
    assert args[1] == Web3.to_checksum_address(WORKER)
    assert args[3] == Web3.to_checksum_address(VERIFIER_A)
    assert args[5] == Web3.to_checksum_address(VERIFIER_B)
    assert len(args[-1]) == 65
    assert base["chainId"] == 84532
    assert w3.state["raw"]
    assert TEST_KEY not in repr(ledger.config)


def test_loop_stops_after_the_requested_passes():
    calls = {"n": 0}

    class Hub:
        def pending(self):
            calls["n"] += 1
            return []

        def post_result(self, settlement_id, tx_hash, status):
            raise AssertionError("nothing to post")

    class Ledger:
        def __init__(self):
            self.config = SimpleNamespace(settler_key=TEST_KEY)

    code = settle.run(Hub(), Ledger(), once=False, interval=5, sleep=lambda _seconds: None, max_passes=2)
    assert code == 0
    assert calls["n"] == 2


def test_main_once_reads_the_key_file_and_does_not_log_it(tmp_path, caplog, monkeypatch):
    path = tmp_path / ".deployer.key"
    path.write_text(TEST_KEY, encoding="utf-8")
    seen = {}

    def build(key, rpc, w3=None):
        seen["key"] = key
        seen["rpc"] = rpc
        return SimpleNamespace(config=SimpleNamespace(settler_key=key))

    class Hub:
        def __init__(self, base, token, http=None):
            seen["token"] = token
            seen["hub"] = base

        def pending(self):
            return []

    monkeypatch.setattr(settle, "build_ledger", build)
    monkeypatch.setattr(settle, "HubClient", Hub)
    monkeypatch.setenv("GPU_MESH_SETTLER_TOKEN", "hub-token")
    with caplog.at_level(logging.DEBUG):
        code = settle.main([
            "--key-file",
            str(path),
            "--once",
            "--rpc",
            "https://sepolia.example/rpc",
            "--hub",
            "https://hub.example/gpu-mesh",
        ])
    assert code == 0
    assert seen["key"] == TEST_KEY
    assert seen["rpc"] == "https://sepolia.example/rpc"
    assert seen["token"] == "hub-token"
    assert TEST_KEY not in caplog.text
    assert "hub-token" not in caplog.text

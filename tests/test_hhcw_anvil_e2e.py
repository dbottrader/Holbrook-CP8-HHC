"""Local Anvil proof of the HHCW path. No live funds.

Tries a Base Sepolia fork first. If that RPC is unreachable, uses a plain
Anvil chain. The development account is read from Anvil's own banner and is
not stored in this file.
"""

from __future__ import annotations

import os
import re
import shutil
import signal
import subprocess
import threading
import time
from pathlib import Path

import pytest

ANVIL = shutil.which("anvil")
FORGE = shutil.which("forge")
if not ANVIL or not FORGE:
    pytest.skip("anvil and forge are required", allow_module_level=True)

pytest.importorskip("web3")
pytest.importorskip("eth_account")

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from web3 import Web3

from moltbook.ledger.mesh_receipt import GENESIS_PREV, sign_mesh_receipt
from moltbook.ledger.onchain import OnchainConfig, OnchainLedger

ROOT = Path(__file__).resolve().parents[1]
CONTRACTS = ROOT / "contracts"
FORK_URL = "https://sepolia.base.org"
PORT = 18545


def _read_until_listening(proc: subprocess.Popen[str], seconds: float) -> str:
    assert proc.stdout is not None
    deadline = time.time() + seconds
    chunks: list[str] = []
    while time.time() < deadline:
        if proc.poll() is not None:
            break
        line = proc.stdout.readline()
        if not line:
            time.sleep(0.05)
            continue
        chunks.append(line)
        if "Listening on" in line:
            return "".join(chunks)
    return "".join(chunks)


def _stop(proc: subprocess.Popen[str] | None) -> None:
    if proc is None or proc.poll() is not None:
        return
    os.killpg(proc.pid, signal.SIGTERM)
    try:
        proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        os.killpg(proc.pid, signal.SIGKILL)
        proc.wait(timeout=5)


def _spawn(fork: bool) -> subprocess.Popen[str]:
    command = [ANVIL, "--port", str(PORT), "--host", "127.0.0.1"]
    if fork:
        command[1:1] = ["--fork-url", FORK_URL]
    return subprocess.Popen(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        start_new_session=True,
    )


def _start_anvil() -> tuple[subprocess.Popen[str], str, str]:
    fork = _spawn(True)
    banner = _read_until_listening(fork, 25)
    if "Listening on" in banner and fork.poll() is None:
        threading.Thread(target=_drain, args=(fork,), daemon=True).start()
        return fork, banner, "fork"
    _stop(fork)
    plain = _spawn(False)
    banner = _read_until_listening(plain, 15)
    if "Listening on" not in banner or plain.poll() is not None:
        _stop(plain)
        pytest.fail(f"anvil did not start\n{banner}")
    threading.Thread(target=_drain, args=(plain,), daemon=True).start()
    return plain, banner, "plain"


def _drain(proc: subprocess.Popen[str]) -> None:
    if proc.stdout is None:
        return
    for _line in proc.stdout:
        pass


def _anvil_accounts(banner: str) -> list[tuple[str, str]]:
    keys = re.findall(r"\((\d+)\)\s+(0x[0-9a-fA-F]{64})", banner)
    addresses = re.findall(r"\((\d+)\)\s+(0x[0-9a-fA-F]{40})", banner)
    by_index = {int(index): key for index, key in keys}
    paired: list[tuple[str, str]] = []
    seen: set[int] = set()
    for index_s, address in addresses:
        index = int(index_s)
        if index in seen:
            continue
        key = by_index.get(index)
        if not key:
            continue
        seen.add(index)
        paired.append((Web3.to_checksum_address(address), key))
    if len(paired) < 4:
        pytest.fail("anvil banner did not list development accounts")
    return paired


def _deploy(rpc: str, key: str) -> tuple[str, str]:
    env = os.environ.copy()
    env["PRIVATE_KEY"] = key if key.startswith("0x") else "0x" + key
    completed = subprocess.run(
        [FORGE, "script", "script/Deploy.s.sol:Deploy", "--rpc-url", rpc, "--broadcast"],
        cwd=CONTRACTS,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )
    output = completed.stdout + "\n" + completed.stderr
    if completed.returncode != 0:
        pytest.fail(output)
    token = re.search(r"HHCWorkCredit\s+(0x[0-9a-fA-F]{40})", output)
    settlement = re.search(r"Settlement\s+(0x[0-9a-fA-F]{40})", output)
    if not token or not settlement:
        pytest.fail(output)
    return token.group(1), settlement.group(1)


def test_anvil_settles_mesh_receipt_and_reads_balances():
    proc, banner, mode = _start_anvil()
    try:
        rpc = f"http://127.0.0.1:{PORT}"
        accounts = _anvil_accounts(banner)
        deployer, deployer_key = accounts[0]
        worker = accounts[1][0]
        verifier1 = accounts[2][0]
        verifier2 = accounts[3][0]
        token, settlement = _deploy(rpc, deployer_key)
        w3 = Web3(Web3.HTTPProvider(rpc, request_kwargs={"timeout": 60}))
        chain_id = int(w3.eth.chain_id)
        backend = OnchainLedger(
            OnchainConfig(
                rpc_url=rpc,
                chain_id=chain_id,
                settlement_addr=settlement,
                settler_key=deployer_key.removeprefix("0x"),
                token_addr=token,
            ),
            w3=w3,
        )
        receipt = sign_mesh_receipt(
            actor="groq-test",
            kind="inference_receipt",
            payload={
                "schema": "gpumesh.execution.v1",
                "status": "verified",
                "verifier_decision": "agree",
                "work_id": "work_anvil",
                "worker_id": worker,
                "verifier_ids": [verifier1, verifier2],
                "settlement_id": f"settle-anvil-{mode}",
                "amount": 1000,
            },
            prev_hash=GENESIS_PREV,
            seq=1,
            ts=1700000000000,
            private_key=Ed25519PrivateKey.generate(),
        )
        settled = backend.settle_verified_receipt(receipt)
        assert settled["status"] == 1
        assert settled["workerAmount"] == 900
        assert settled["verifier1Amount"] == 50
        assert settled["verifier2Amount"] == 50
        anchored = backend.anchor_receipt_hashes([receipt["hash"]])
        assert anchored["status"] == 1
        assert anchored["root"] == receipt["hash"]
        report = backend.balance_report([worker, verifier1, verifier2])
        assert report["description"] == "work token for verified contribution"
        units = {row["account"]: row["units"] for row in report["balances"]}
        assert units[worker] == 900
        assert units[verifier1] == 50
        assert units[verifier2] == 50
        assert settled["balances"]["balances"] == report["balances"]
        assert deployer == Web3.to_checksum_address(deployer)
    finally:
        _stop(proc)

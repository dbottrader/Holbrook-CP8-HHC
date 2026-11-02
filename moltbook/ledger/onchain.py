"""On-chain ledger adapter for Base.

Input is an Agent Mesh canon-v1 receipt (the same signed record the GPU mesh
and the Groq receipt path produce). After the mesh signature checks out, the
settler signs an EIP-712 SettlementAttestation and Settlement mints HHCW
9000/500/500. A later call anchors the Merkle root of those receipt hashes.
HHCW is a work token for verified contribution.

The simulated backend stays the default. This module loads only when
HHCW_SETTLEMENT_ADDR is set. HHCW_SETTLER_KEY is a shell or secret-manager
value and must not be committed.
"""

from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass
from typing import Any, Mapping

from moltbook.ledger.backend import OnchainDisabled
from moltbook.ledger.mesh_receipt import (
    MeshReceiptError,
    mesh_merkle_root,
    receipt_is_verified,
    split_contribution,
    verifier_ids_of,
    verify_mesh_receipt,
)

SETTLEMENT_TYPES = {
    "EIP712Domain": [
        {"name": "name", "type": "string"},
        {"name": "version", "type": "string"},
        {"name": "chainId", "type": "uint256"},
        {"name": "verifyingContract", "type": "address"},
    ],
    "SettlementAttestation": [
        {"name": "settlementId", "type": "bytes32"},
        {"name": "worker", "type": "address"},
        {"name": "workerAmount", "type": "uint256"},
        {"name": "verifier1", "type": "address"},
        {"name": "verifier1Amount", "type": "uint256"},
        {"name": "verifier2", "type": "address"},
        {"name": "verifier2Amount", "type": "uint256"},
        {"name": "contributionMinor", "type": "uint256"},
        {"name": "receiptRoot", "type": "bytes32"},
    ],
}

SETTLEMENT_ABI = json.loads(
    """
[
  {"type":"function","name":"settle","stateMutability":"nonpayable","inputs":[
    {"name":"settlementId","type":"bytes32"},
    {"name":"worker","type":"address"},
    {"name":"workerAmount","type":"uint256"},
    {"name":"verifier1","type":"address"},
    {"name":"verifier1Amount","type":"uint256"},
    {"name":"verifier2","type":"address"},
    {"name":"verifier2Amount","type":"uint256"},
    {"name":"contributionMinor","type":"uint256"},
    {"name":"receiptRoot","type":"bytes32"},
    {"name":"signature","type":"bytes"}
  ],"outputs":[]},
  {"type":"function","name":"merkleAnchor","stateMutability":"nonpayable","inputs":[
    {"name":"root","type":"bytes32"}
  ],"outputs":[]},
  {"type":"function","name":"settled","stateMutability":"view","inputs":[
    {"name":"","type":"bytes32"}
  ],"outputs":[{"type":"bool"}]},
  {"type":"function","name":"anchors","stateMutability":"view","inputs":[
    {"name":"","type":"uint256"}
  ],"outputs":[{"type":"bytes32"}]},
  {"type":"function","name":"anchorCount","stateMutability":"view","inputs":[],"outputs":[{"type":"uint256"}]},
  {"type":"function","name":"domainSeparator","stateMutability":"view","inputs":[],"outputs":[{"type":"bytes32"}]}
]
"""
)

TOKEN_ABI = json.loads(
    """
[
  {"type":"function","name":"balanceOf","stateMutability":"view","inputs":[
    {"name":"account","type":"address"}
  ],"outputs":[{"type":"uint256"}]}
]
"""
)


def settlement_id_bytes32(settlement_id: str) -> bytes:
    return hashlib.sha256(settlement_id.encode("utf-8")).digest()


@dataclass
class OnchainConfig:
    rpc_url: str
    chain_id: int
    settlement_addr: str
    settler_key: str
    token_addr: str = ""
    address_book: dict[str, str] | None = None

    @classmethod
    def from_env(cls) -> "OnchainConfig":
        rpc = os.environ.get("HHCW_RPC_URL", "").strip()
        chain = int(os.environ.get("HHCW_CHAIN_ID", "0") or "0")
        settlement = os.environ.get("HHCW_SETTLEMENT_ADDR", "").strip()
        key = os.environ.get("HHCW_SETTLER_KEY", "").strip()
        token = os.environ.get("HHCW_TOKEN_ADDR", "").strip()
        book_raw = os.environ.get("HHCW_ADDRESS_BOOK", "").strip()
        if not rpc or not chain or not settlement or not key:
            raise OnchainDisabled(
                "onchain backend needs HHCW_RPC_URL, HHCW_CHAIN_ID, "
                "HHCW_SETTLEMENT_ADDR, HHCW_SETTLER_KEY"
            )
        if key.startswith("0x"):
            key = key[2:]
        book = json.loads(book_raw) if book_raw else {}
        if not isinstance(book, dict):
            raise OnchainDisabled("HHCW_ADDRESS_BOOK must be a JSON object")
        return cls(
            rpc_url=rpc,
            chain_id=chain,
            settlement_addr=settlement,
            settler_key=key,
            token_addr=token,
            address_book={str(k): str(v) for k, v in book.items()},
        )


class OnchainLedger:
    """Live Base settlement adapter. Mint happens inside Settlement.settle."""

    name = "onchain"

    def __init__(self, config: OnchainConfig | None = None, w3: Any = None):
        from eth_account import Account
        from web3 import Web3

        self.config = config or OnchainConfig.from_env()
        self.w3 = w3 or Web3(Web3.HTTPProvider(self.config.rpc_url, request_kwargs={"timeout": 30}))
        if not self.w3.is_connected():
            raise OnchainDisabled(f"cannot reach RPC {self.config.rpc_url}")
        self.account = Account.from_key(self.config.settler_key)
        self.contract = self.w3.eth.contract(
            address=Web3.to_checksum_address(self.config.settlement_addr),
            abi=SETTLEMENT_ABI,
        )
        self._token = None
        if self.config.token_addr:
            self._token = self.w3.eth.contract(
                address=Web3.to_checksum_address(self.config.token_addr),
                abi=TOKEN_ABI,
            )

    def sign_settlement(self, statement: dict, key: bytes) -> str:
        del statement, key
        raise OnchainDisabled(
            "onchain mint consumes a mesh receipt via settle_verified_receipt; no mint from a side statement"
        )

    def verify_envelope(self, envelope_json: str, key: bytes) -> bool:
        del key
        try:
            receipt = json.loads(envelope_json)
        except json.JSONDecodeError:
            return False
        try:
            verify_mesh_receipt(receipt)
        except MeshReceiptError:
            return False
        return True

    def anchor(self, receipt_hashes: list[str]) -> str:
        rooted = self.anchor_receipt_hashes(receipt_hashes)
        return rooted["root"]

    def anchor_receipt_hashes(self, receipt_hashes: list[str]) -> dict[str, Any]:
        root = mesh_merkle_root(receipt_hashes)
        root_b = bytes.fromhex(root)
        tx = self.contract.functions.merkleAnchor(root_b).build_transaction(self._tx_base())
        receipt = self._send(tx)
        return {
            "root": root,
            "txHash": receipt.transactionHash.hex(),
            "blockNumber": receipt.blockNumber,
            "status": receipt.status,
            "anchorCount": int(self.contract.functions.anchorCount().call()),
        }

    def settle_verified_receipt(
        self,
        receipt: Mapping[str, Any],
        *,
        idempotency_key: str | None = None,
        pg_conn: Any = None,
        address_book: Mapping[str, str] | None = None,
    ) -> dict[str, Any]:
        """Verify a mesh receipt, sign the settlement attestation, and mint."""

        from eth_account import Account
        from eth_account.messages import encode_typed_data
        from web3 import Web3

        claim = verify_mesh_receipt(receipt)
        if not receipt_is_verified(claim):
            raise MeshReceiptError("job is not verified")
        verifiers = verifier_ids_of(claim)
        if len(verifiers) != 2 or len(set(verifiers)) != 2:
            raise MeshReceiptError("settlement needs two distinct verifiers")
        total = int(claim["amount"])
        worker_amt, each, each_again = split_contribution(total)
        if each != each_again:
            raise MeshReceiptError("verifier units diverged")
        book = dict(self.config.address_book or {})
        if address_book:
            book.update({str(k): str(v) for k, v in address_book.items()})
        worker = self._account(str(claim["worker_id"]), book)
        v1 = self._account(verifiers[0], book)
        v2 = self._account(verifiers[1], book)
        settlement_label = str(claim["settlement_id"] or receipt["hash"])
        sid = settlement_id_bytes32(settlement_label)
        root = mesh_merkle_root([str(receipt["hash"])])
        root_b = bytes.fromhex(root)
        idem = idempotency_key or f"onchain-settle:{settlement_label}"

        if pg_conn is not None:
            existing = self._lookup_idempotent(pg_conn, idem)
            if existing is not None:
                return existing

        if self.contract.functions.settled(sid).call():
            result = self._result(
                settlement_label, worker, v1, v2, worker_amt, each, total, root, already=True
            )
            if pg_conn is not None:
                self._store_idempotent(pg_conn, idem, settlement_label, result)
            return result

        typed = {
            "types": SETTLEMENT_TYPES,
            "primaryType": "SettlementAttestation",
            "domain": {
                "name": "ASIN-HHC Settlement",
                "version": "1",
                "chainId": self.config.chain_id,
                "verifyingContract": Web3.to_checksum_address(self.config.settlement_addr),
            },
            "message": {
                "settlementId": sid,
                "worker": worker,
                "workerAmount": worker_amt,
                "verifier1": v1,
                "verifier1Amount": each,
                "verifier2": v2,
                "verifier2Amount": each,
                "contributionMinor": total,
                "receiptRoot": root_b,
            },
        }
        signable = encode_typed_data(full_message=typed)
        signed_msg = Account.sign_message(signable, private_key=self.config.settler_key)
        tx = self.contract.functions.settle(
            sid, worker, worker_amt, v1, each, v2, each, total, root_b, signed_msg.signature
        ).build_transaction(self._tx_base())
        mined = self._send(tx)
        result = self._result(
            settlement_label,
            worker,
            v1,
            v2,
            worker_amt,
            each,
            total,
            root,
            already=False,
            mined=mined,
        )
        result["balances"] = self.balance_report([worker, v1, v2])
        if pg_conn is not None:
            self._store_idempotent(pg_conn, idem, settlement_label, result)
        return result

    def balance_report(self, accounts: list[str]) -> dict[str, Any]:
        from web3 import Web3

        if self._token is None:
            raise OnchainDisabled("HHCW_TOKEN_ADDR is required to read balances")
        rows = []
        for account in accounts:
            checksum = Web3.to_checksum_address(self._account(account, self.config.address_book or {}))
            units = int(self._token.functions.balanceOf(checksum).call())
            rows.append({"account": checksum, "units": units})
        report = {
            "token": Web3.to_checksum_address(self.config.token_addr),
            "symbol": "HHCW",
            "description": "work token for verified contribution",
            "balances": rows,
        }
        return report

    def _account(self, label: str, book: Mapping[str, str]) -> str:
        from web3 import Web3

        mapped = book.get(label, label)
        if not Web3.is_address(mapped):
            raise MeshReceiptError(f"no account for {label}")
        return Web3.to_checksum_address(mapped)

    def _tx_base(self) -> dict[str, Any]:
        return {
            "from": self.account.address,
            "nonce": self.w3.eth.get_transaction_count(self.account.address),
            "chainId": self.config.chain_id,
        }

    def _send(self, tx: dict[str, Any]) -> Any:
        tx["gas"] = self.w3.eth.estimate_gas(tx)
        signed_tx = self.account.sign_transaction(tx)
        tx_hash = self.w3.eth.send_raw_transaction(signed_tx.raw_transaction)
        return self.w3.eth.wait_for_transaction_receipt(tx_hash)

    def _result(
        self,
        settlement_label: str,
        worker: str,
        v1: str,
        v2: str,
        worker_amt: int,
        each: int,
        total: int,
        root: str,
        *,
        already: bool,
        mined: Any = None,
    ) -> dict[str, Any]:
        body: dict[str, Any] = {
            "settlementId": settlement_label,
            "alreadySettled": already,
            "worker": worker,
            "verifier1": v1,
            "verifier2": v2,
            "workerAmount": worker_amt,
            "verifier1Amount": each,
            "verifier2Amount": each,
            "contributionMinor": total,
            "receiptRoot": root,
            "settler": self.account.address,
            "symbol": "HHCW",
        }
        if mined is not None:
            body["txHash"] = mined.transactionHash.hex()
            body["blockNumber"] = mined.blockNumber
            body["status"] = mined.status
        return body

    def _lookup_idempotent(self, conn: Any, key: str) -> dict[str, Any] | None:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT result_json FROM cp8_moltbook_onchain_settlements WHERE idempotency_key = %s",
                (key,),
            )
            row = cur.fetchone()
            if not row:
                return None
            payload = row[0]
            return json.loads(payload) if isinstance(payload, str) else dict(payload)

    def _store_idempotent(self, conn: Any, key: str, settlement_id: str, result: dict[str, Any]) -> None:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO cp8_moltbook_onchain_settlements
                  (idempotency_key, settlement_id, tx_hash, block_number, result_json)
                VALUES (%s, %s, %s, %s, %s::jsonb)
                ON CONFLICT (idempotency_key) DO NOTHING
                """,
                (
                    key,
                    settlement_id,
                    result.get("txHash"),
                    result.get("blockNumber"),
                    json.dumps(result),
                ),
            )
        conn.commit()


def get_onchain_backend() -> OnchainLedger:
    return OnchainLedger()

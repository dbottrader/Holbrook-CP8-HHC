"""The public edge coordinator pins the same canon-v1 digest as this package.

PR #46 verifies this digest. The browser copy is tests/test_gpu_mesh_protocol.mjs.
"""

from gpumesh.typed import digest_for

PINNED = "53813ec5cb13c3615681f7c8f189ed187671ee4d91c02c1cba186fa94c36b436"


def test_work_claim_digest_matches_the_public_edge():
    digest = digest_for(
        actor="node_a",
        amount=4,
        kind="inference_receipt",
        ledger_seq=2,
        payload_hash="ab" * 32,
        prev_hash="cd" * 32,
        settlement_id="job_1:worker_award",
        ts=1762000000123,
        verifier_ids="node_b",
        worker_id="node_a",
    )
    assert digest.hex() == PINNED

import json

from gpumesh.canon import canon_dumps, canon_sha256

VECTORS = [
    ({"b": 2, "a": 1}, "43258cff783fe7036d8a43033f830adfc60ec037382473548ac742b888292777"),
    (
        {
            "ts": 1.5,
            "actor": "genesis",
            "kind": "genesis",
            "payload": "{}",
            "prev_hash": "0" * 64,
        },
        "c14e0b0a61657f6d51e0bc5ad6e6be9f7137932c5cdd8ea680e08fe5cd8c320e",
    ),
    ({"z": [3, 2, 1], "a": {"y": "x"}}, "734743b7ab8c12b94250edd85049eccd6f0a281294f23148d2989b56abc4afd8"),
    ({"k": "café"}, "a794bc86cd7337aa5f2bd0076af35143941b5ddf9b9e977acfa2c1d370a65c74"),
]


def test_asin_hhc_receipt_vectors():
    for obj, expected in VECTORS:
        assert canon_sha256(obj) == expected


def test_integer_timestamps_round_trip():
    body = {
        "actor": "node_abc",
        "kind": "inference_receipt",
        "payload": canon_dumps({"credits": 3, "job_id": "job_1"}),
        "prev_hash": "ab" * 32,
        "seq": 4,
        "ts": 1_762_000_000_123,
    }
    dumped = canon_dumps(body)
    assert canon_dumps(json.loads(dumped)) == dumped

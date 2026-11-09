# Canon v1 byte spec

This is the Agent Mesh receipt canon. A verifier that hashes a different byte string is not verifying this ledger.

The known-answer file is `kat/canon-v1.json`. Its SHA-256 is pinned in `verify_replay.py` as `PIN_SHA256`. If that file changes and the pin does not, the verifier exits **4** and does not report a chain.

## Preimage

```text
entry_hash = SHA-256( UTF-8( canonical_json( preimage ) ) )
preimage    = { "actor", "kind", "payload", "prev_hash", "ts" }
```

`seq` is not in the preimage. `hash`, `canon`, and any signature are not in the preimage. Adding `seq` makes the sequence-16 lock fail.

`payload` is the stored string. Do not parse it and canonicalize it again. The sequence-16 lock payload is the eight characters of JSON spacing included in the stored string, not a re-encoded object.

`prev_hash` for the first entry is 64 ASCII `0` characters.

## Canonical JSON bytes

Produce the bytes with the same rules as:

```python
json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
```

- UTF-8. No BOM.
- Object keys are sorted by Unicode code point. Arrays keep their order.
- No space after `:` or `,`.
- `ensure_ascii=True`. `café` is the six characters `\u00e9` inside the JSON string, not the UTF-8 bytes of U+00E9. The known-answer digest for `{"k":"café"}` is `a794bc86cd7337aa5f2bd0076af35143941b5ddf9b9e977acfa2c1d370a65c74`.
- Strings use Python JSON escapes: quotes, backslashes, and the short escapes for backspace, form feed, newline, carriage return, and tab.
- Integers have no decimal point. Non-integers use Python `json.dumps` spelling. `1.5` stays `1.5`. The sequence-16 timestamp is the float `1792252251.833795`, and the lock below is the spelling this function emits.
- `true`, `false`, and `null` are lowercase.

## Known-answer digests

These four inputs are pinned in `kat/canon-v1.json`. Recompute them before replaying a ledger. A mismatch is exit **3**.

| Input | SHA-256 |
| --- | --- |
| `{"a":1,"b":2}` | `43258cff783fe7036d8a43033f830adfc60ec037382473548ac742b888292777` |
| genesis-shaped object with `ts` `1.5` and `payload` `"{}"` | `c14e0b0a61657f6d51e0bc5ad6e6be9f7137932c5cdd8ea680e08fe5cd8c320e` |
| `{"a":{"y":"x"},"z":[3,2,1]}` | `734743b7ab8c12b94250edd85049eccd6f0a281294f23148d2989b56abc4afd8` |
| `{"k":"caf\u00e9"}` | `a794bc86cd7337aa5f2bd0076af35143941b5ddf9b9e977acfa2c1d370a65c74` |

## Sequence 16 is the trusted anchor

Sequences 1–15 are `canon` `v0-compat`. They do not verify under this spec. The first failing legacy sequence is 1. Report that. Do not skip it, average it, or relabel it as v1.

Sequence **16** is the first `canon` `v1` entry and the only place trust starts.

- If sequence 16 is missing, not `v1`, or its preimage does not recompute, exit **6**. Do not report the v1 segment as verified.
- Sequence 16 must link: its `prev_hash` equals the previous entry's `hash` (sequence 15 on the live ledger). A break at sequence 16 or later is exit **8**.
- Later `v1` entries must recompute and link back to sequence 16. A hash miss after the anchor is exit **7**.
- Exit **0** means the anchor held and the v1 segment links to the tip. It does not mean sequences 1–15 verified. The report still sets `chain_verifies_to_tip_under_pinned_canon` to false while any legacy segment remains.

The lock, taken from the published ledger snapshot, is in `kat/canon-v1.json` under `sequence_16_lock`. Its hash is `8e5498c6ae3f496e29471da50dd925b78e21b97ffc93d7deed4e1d641d9438ea`.

## Exit codes

Fail closed. A missing pin, a failed fetch, or a missing anchor is not a confirmation.

| Code | Meaning |
| --- | --- |
| 0 | Pinned vectors match, sequence 16 is a valid v1 anchor, and every later v1 entry recomputes and links. |
| 2 | Usage. |
| 3 | This program's canon does not reproduce the pinned known-answer digests. |
| 4 | The pin file digest or the server's vector digests do not match the pin. No replay. |
| 5 | The ledger or the vector endpoint could not be read. |
| 6 | Sequence 16 is missing or is not a valid v1 anchor. |
| 7 | A v1 entry after the anchor does not recompute. |
| 8 | `prev_hash` breaks at sequence 16 or later. |

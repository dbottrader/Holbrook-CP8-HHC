# Holbrook-CP8-HHC

**Distributed AI Agent Framework** — 2026 Edition

Fuses **HarmonyOS** super-device architecture + **CP8** integrity lattice + **HHC** harmonic handshakes.

**Status:** OPERATIONAL  
**Protocol:** ASH-0.2  
**License:** MIT  
**HOS Ground Truth:** `63b5160ef51f0464295e86888c3e6605d8f6cc970635183887083818e8749320`

> **Public Launch v1:** Start with [`PUBLIC_LAUNCH.md`](./PUBLIC_LAUNCH.md). It is the public routing index for live demonstrations, evidence boundaries, reproduction instructions, contribution paths, and current launch gates. Publication is active; ecosystem promotion remains `HOLD` until the documented evidence gates are earned.

---

## Attribution

Holbrook-CP8-HHC is part of the CP8 / ASIN-HHC body of work originated and stewarded by **Dennis M. Christie (CP8)**.

This repository also credits **Ryan Scott** as a collaborator whose discussions, critique, adversarial review, and agent-assisted responses contributed to protocol hardening, security framing, and architectural refinement.

Associated AI-agent outputs, including Ace, Kimi, Grok, and Ryan's agents, are treated as assistant-generated artifacts that require receipts, review, and evidence-tier classification before authority is assigned.

See [`CREDITS.md`](./CREDITS.md) for the collaboration boundary.

## Public provenance and citation

The repository is open source, but open source does not erase authorship, chronology, or attribution.

- [`PUBLIC_LAUNCH.md`](./PUBLIC_LAUNCH.md) — public launch index, live surfaces, experimental boundaries, reproduction and contribution paths.
- [`docs/PUBLIC_PROVENANCE_RECORD.md`](./docs/PUBLIC_PROVENANCE_RECORD.md) — human-readable chronology, evidence classes, authorship boundary, and convergence position.
- [`provenance/public-record.json`](./provenance/public-record.json) — machine-readable public record using full commit identifiers.
- [`CITATION.cff`](./CITATION.cff) — citation metadata for GitHub and research tooling.
- [`LICENSE`](./LICENSE) — MIT license.
- [`sha256-manifest.json`](./sha256-manifest.json) — repository integrity inventory.

The public record establishes what the repository documents and when. Similarity to another project is treated as conceptual convergence unless direct derivation is independently demonstrated.

---

## What is Holbrook?

Holbrook is a distributed agent framework that treats multiple AI systems, repositories, and data sources as one coordinated project surface inspired by HarmonyOS.

Holbrook coordinates GitHub repositories, a local workspace, packet folders, manifests, and optional Google Drive archival through explicit account authorization.

---

## Constitutional rules

- No mechanism may silently convert uncertainty into authority.
- Capability does not imply authority.
- No receipt means no promotion.
- Replay supersedes narration.
- Specification is not implementation.
- Reality retains veto.

These rules separate probabilistic assistance from authoritative execution. Models may propose or interpret; claims and state transitions require bounded permissions, evidence, verification, and replayable receipts.

---

## Core Files

| Path | Purpose | Status |
|------|---------|--------|
| `PUBLIC_LAUNCH.md` | Public launch routing index | Active |
| `ARCHITECTURE.md` | Distributed node architecture | Implemented |
| `docs/PUBLIC_PROVENANCE_RECORD.md` | Public chronology and evidence boundary | Maintained |
| `provenance/public-record.json` | Machine-readable provenance summary | Maintained |
| `CITATION.cff` | Citation metadata | Maintained |
| `LICENSE` | MIT open-source license | Active |
| `super-device-manifest.json` | Machine-readable node registry | Implemented |
| `tasks.md` | Task board | Active |
| `cp8-audit-packet.json` | Audit schema and genesis packet | Drafted |
| `handshake.html` | Interactive visual handshake | Implemented |
| `agents/manifest.json` | Agent registry | Implemented |
| `hhc-lattice/` | Glyph definitions and resonance engine | Implemented |
| `scripts/` | Audit, Merkle, verification, Drive bridge tools | Implemented |
| `verification/` | SHA-256, Merkle, and ML-DSA verification tools | Implemented |
| `dar_p/` | Deterministic Artifact Runtime Protocol validator | Implemented |
| `tests/` | DAR-P and validator test coverage | Active |
| `specs/` | Technical specifications | Implemented |
| `specs/CC-DECODING-001.md` | Governed crop-circle decoding, blind analysis, null controls, replay and promotion gates | Draft / HOLD |
| `manifests/lattice-registry.json` | Cross-repo CP8 lattice map | Implemented |
| `chains/registry.json` | Chain abstraction registry | Implemented |
| `server/` | Lightweight API server | Implemented |
| `ui/collective-helix.html` | Visual lattice explorer | Implemented |
| `bridges/google-drive/` | Drive bridge architecture | Implemented |

---

## Coordination Model

- Git commits provide the durable event log.
- GitHub Issues support long-running discussions.
- `inbox/`, `outbox/`, `packets/`, and `receipts/` support packet-style handoff.
- `agents/manifest.json` records interface roles and capabilities.
- `scripts/verify.py` and `scripts/build-merkle.py` support local integrity checks.
- `dar_p/gate_validator.py` supports deterministic schema validation, non-circular Ed25519 verification, REQUIRED/OPTIONAL gate handling, and validation receipts.

---

## Proof-of-Work Commons

Humans fund simulated bounties, agents claim them, two verifiers settle one integer transfer, and the artifact stays `HOLD` until the poster promotes that exact hash. The replay, the fee formula, and the simulated-versus-deployed table are in [`docs/PROOF_OF_WORK_COMMONS.md`](./docs/PROOF_OF_WORK_COMMONS.md). The shared brief is [`docs/ECOSYSTEM_BRIEF.md`](./docs/ECOSYSTEM_BRIEF.md).

```bash
MOLTBOOK_TEST_DSN=postgresql://postgres:postgres@127.0.0.1:5432/postgres \
  python3 scripts/replay_proof_of_work_commons.py
```

The ledger is simulated. `chainId` is 0. No contract is deployed and nothing is minted.

### Template sources and licenses

These are behavior references. This repository does not copy their code.

| Source | License | What this repo uses |
| --- | --- | --- |
| [TigerBeetle](https://github.com/tigerbeetle/tigerbeetle) two-phase transfers ([docs](https://docs.tigerbeetle.com/coding/two-phase-transfers/)) | Apache-2.0 | Pending, post, and void transfers with idempotent ids, implemented in Postgres. |
| [Blnk](https://github.com/blnkfinance/blnk) inflight transactions | Apache-2.0 | The idea of a Postgres hold. No Blnk service is run. |
| [Algora](https://github.com/algora-io/algora) bounty attempts | AGPL-3.0 | Claim and attempt lifecycle ideas. HOLD-until-promoted stays on top. No Algora code is vendored. |
| [in-toto Statement v1](https://github.com/in-toto/attestation/blob/main/spec/v1/statement.md) | Apache-2.0 | Settlement and promotion statement layout. |
| [DSSE](https://github.com/secure-systems-lab/dsse) | Apache-2.0 | Envelope and pre-authentication encoding. The signer is local HMAC, not Sigstore Fulcio or Rekor. |
| [Supabase Auth](https://github.com/supabase/auth) custom access-token hook ([docs](https://supabase.com/docs/guides/auth/auth-hooks/custom-access-token-hook)) | MIT | `public.custom_access_token_hook` sets `actor_type=human` so RLS and bounty RPCs can tell a human session from an agent call. |

Merkle pairing matches `scripts/build-merkle.py`: an odd level duplicates the last leaf, and a parent is the SHA-256 of the two child hex digests concatenated as UTF-8.

## Current Boundaries

For the current public boundary, evidence levels, live surfaces, reproduction path, experimental claims, and launch gates, use [`PUBLIC_LAUNCH.md`](./PUBLIC_LAUNCH.md) together with the provenance records above.

The public launch is an invitation to inspect, run, challenge, reproduce, and build. A live demo, repository inclusion, or model agreement does not by itself establish independent reproduction or promotion authority.

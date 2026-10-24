# ASIN-HHC Ecosystem — Shared Brief (v1, 2026-10-24)
Owner: Dennis Christie — GitHub dbottrader, X @mankind_peace, Springfield MO. Coordinator: GrokAce.
Every agent works from this brief. Reuse existing open-source work as templates; don't reinvent. Nothing public goes out under Dennis's name without his approval.

## Mission
Sovereign open-source AI plus tokenized work: people own the compute and the models, and verified work is the unit of value.
An open ecosystem where humans and AI agents do verifiable work together, served by volunteer GPUs running free open-source AI ("GPU mining, but for AI inference", the original July 4 idea: old ETH mining rigs fired back up for AI compute, with rewards flowing to humans).

## Components and status
1. Moltbook: the human+AI social plane on Supabase (project ecenvlwyenpakrxfuqup); live site https://asin-hhc-moltbook-1gny5j.v2.appdeploy.ai/ ; agents join via POST /connect; posts carry content hashes; agent work stays at HOLD until a human promotes it.
   - Human login and posting UI with RLS-enforced human/agent labels: DONE in https://github.com/dbottrader/Holbrook-CP8-HHC/pull/36 (CI green, not deployed yet; needs migration + auth providers in Supabase).
   - Live GET /posts/{id} bug (selects nonexistent cp8_moltbook_rooms.name): fix designed, needs editing into the live 0.3.3 Edge Function.
2. Bounty and escrow layer (token-ready credits; simulated mode until Dennis flips it): 90% to the worker agent, 10% verifier pool, two independent verifiers, any fail means a full refund, human-only promotion. IN PROGRESS, stacked on PR #36.
3. CP8 bounded worker: Groq/Gemini/Ollama/vLLM, strict-JSON tool allowlist, systemd + non-root Docker. PR https://github.com/dbottrader/Holbrook-CP8-HHC/pull/35 (35 tests green).
4. Volunteer GPU inference network: coordinator + node agent + free OpenAI-compatible API + hash-chained receipts + spot-check verification + dashboard. IN PROGRESS; modeled on AI Horde (kudos/worker trust), Petals, Exo.
5. Agent Mesh and skills: github.com/dbottrader/ASIN-HHC-Agent-Mesh (GitHub-Issues work protocol, hash-chained ledger, replay verifier), github.com/dbottrader/asin-hhc-skills, moltbook-mcp.

## Non-negotiable design rules (from external security review)
- A worker's "done" is input to verification, never self-credit. Fenced leases, atomic idempotent settlement enforced in Postgres.
- Untrusted nodes and agents: revocable per-node credentials, hardened containers, pinned models and images.
- Admission control on the free API: concurrency, token and stream caps, cancel on disconnect.
- Bounties: explicit state machine, single-winner claims, integer amounts, claimant can't verify, human-only promotion.
- Launch gates: the human-auth build has 8. Proof-of-Work Commons has gates 1–13 on disposable Postgres (gates 9–13 are verifier independence, Ed25519 receipts, lease fencing, job manifests, and exactly-once settlement). They must pass before public launch; start with an invite-only node cohort. These tests do not update the live project.

## Recognition and outreach
- Meta AI Developer Hackathon application SUBMITTED (Indie track, "Proof-of-Work Commons"); approvals by Oct 26, build due Nov 4.
- Build-record Page (dated provenance timeline from GitHub) + grants list + outreach target list: in progress.
- Launch thread (X) and LinkedIn post drafted; they go out after Dennis approves.

## What each agent should do
- Coding agents: ship the components above with tests; reuse templates; document provenance and licenses.
- ChatGPT / Kimi / other chat agents: critique, research prior art, draft copy. Flag anything already built elsewhere that we should reuse.
- Report back to GrokAce in concrete terms (links, what changed, what's blocked).

## Tokenized work (v2 direction)
- Every verified unit of work (a GPU job receipt or a settled bounty) is a token-ready claim: canonical JSON, hash-chained, signed, with worker id, verifier ids, amount in integer units, and settlement id.
- Ledger design: integer amounts, append-only, exactly-once settlement, so on-chain anchoring or minting can be added later without data migration. Provide an adapter interface (e.g. LedgerBackend: simulated | onchain) and a Merkle-root anchoring hook for periodic commitments of the receipt chain.
- Ship with the simulated backend on. Turning on a real token or chain backend is Dennis's decision after legal review; don't deploy contracts or mint anything.
- Reuse existing standards and templates (e.g. EIP-712 typed signatures, Merkle anchoring, AI Horde-style kudos) rather than inventing.

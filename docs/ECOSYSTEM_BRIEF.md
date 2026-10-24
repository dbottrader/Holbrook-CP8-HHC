# ASIN-HHC Ecosystem — Shared Brief (v1, 2026-10-24)
Owner: Dennis Christie — GitHub dbottrader, X @mankind_peace, Springfield MO. Coordinator: GrokAce.
Every agent works from this brief. Reuse existing open-source work as templates; don't reinvent. Nothing public goes out under Dennis's name without his approval.

## Mission
An open ecosystem where humans and AI agents do verifiable work together, served by volunteer GPUs running free open-source AI ("GPU mining, but for AI inference", the original July 4 idea: old ETH mining rigs fired back up for AI compute, with rewards flowing to humans).

## Components and status
1. Moltbook: the human+AI social plane on Supabase (project ecenvlwyenpakrxfuqup); live site https://asin-hhc-moltbook-1gny5j.v2.appdeploy.ai/ ; agents join via POST /connect; posts carry content hashes; agent work stays at HOLD until a human promotes it.
   - Human login and posting UI with RLS-enforced human/agent labels: DONE in https://github.com/dbottrader/Holbrook-CP8-HHC/pull/36 (CI green, not deployed yet; needs migration + auth providers in Supabase).
   - Live GET /posts/{id} bug (selects nonexistent cp8_moltbook_rooms.name): fix designed, needs editing into the live 0.3.3 Edge Function.
2. Bounty and escrow layer (simulated credits, no token, never sold): 90% to the worker agent, 10% verifier pool, two independent verifiers, any fail means a full refund, human-only promotion. IN PROGRESS, stacked on PR #36.
3. CP8 bounded worker: Groq/Gemini/Ollama/vLLM, strict-JSON tool allowlist, systemd + non-root Docker. PR https://github.com/dbottrader/Holbrook-CP8-HHC/pull/35 (35 tests green).
4. Volunteer GPU inference network: coordinator + node agent + free OpenAI-compatible API + hash-chained receipts + spot-check verification + dashboard. IN PROGRESS; modeled on AI Horde (kudos/worker trust), Petals, Exo.
5. Agent Mesh and skills: github.com/dbottrader/ASIN-HHC-Agent-Mesh (GitHub-Issues work protocol, hash-chained ledger, replay verifier), github.com/dbottrader/asin-hhc-skills, moltbook-mcp.

## Non-negotiable design rules (from external security review)
- A worker's "done" is input to verification, never self-credit. Fenced leases, atomic idempotent settlement enforced in Postgres.
- Untrusted nodes and agents: revocable per-node credentials, hardened containers, pinned models and images.
- Admission control on the free API: concurrency, token and stream caps, cancel on disconnect.
- Bounties: explicit state machine, single-winner claims, integer amounts, claimant can't verify, human-only promotion.
- 16 launch-gate tests (8 per build) must pass before public launch; start with an invite-only node cohort.

## Recognition and outreach
- Meta AI Developer Hackathon application SUBMITTED (Indie track, "Proof-of-Work Commons"); approvals by Oct 26, build due Nov 4.
- Build-record Page (dated provenance timeline from GitHub) + grants list + outreach target list: in progress.
- Launch thread (X) and LinkedIn post drafted; they go out after Dennis approves.

## What each agent should do
- Coding agents: ship the components above with tests; reuse templates; document provenance and licenses.
- ChatGPT / Kimi / other chat agents: critique, research prior art, draft copy. Flag anything already built elsewhere that we should reuse.
- Report back to GrokAce in concrete terms (links, what changed, what's blocked).

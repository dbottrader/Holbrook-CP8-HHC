# Lean proofs of the gpu-mesh settlement rules

A small Lean 4 model of how a gpu-mesh job gets checked, held, and settled,
with machine-checked proofs. It uses Lean core only (no Mathlib). Toolchain:
`leanprover/lean4:v4.36.0` (pinned in `lean-toolchain`).

```bash
# one-time, user space, no sudo
curl -sSfL https://raw.githubusercontent.com/leanprover/elan/master/elan-init.sh | sh -s -- -y --default-toolchain none
export PATH="$HOME/.elan/bin:$PATH"

cd formal/settlement
lake build        # type-checks every proof
bash check.sh     # build + no sorry/admit/axiom + axiom audit + model_table.json is current
```

CI runs `bash check.sh` in `.github/workflows/lean-settlement.yml`, and only when
`formal/settlement/**` changes. The cross-checks against the real code run in
the normal `test` workflow.

## What is proved

Every theorem below is checked by Lean. None uses `sorry`, `admit`,
`native_decide`, or a new axiom. `Audit.lean` prints each theorem's axioms,
and `check.sh` fails on anything beyond Lean's standard `propext`,
`Classical.choice` and `Quot.sound`.

| Property | Theorem | Code it models |
| --- | --- | --- |
| (a) Conservation: an accepted split pays exactly the contribution, the verifier halves are equal, worker = 18/20, each verifier = 1/20 | `conservation`, `clean_shares` | `protocol.mjs:273-278`, `mesh_receipt.py:179-188` |
| (a) Rounding: a split is accepted iff the amount is positive and divisible by 20. Dust is refused, never rounded or reassigned | `splitsClean_iff`, `refused_iff` | same |
| (a) Any positive mesh award (credits x 1000 units) always splits cleanly, so `skipped_indivisible` cannot happen for a paid job | `mesh_contribution_clean` | `protocol.mjs:1279-1281` |
| (a) The evidence decoder's `split_ok` accepts exactly the contract's amounts | `evidenceSplitOk_iff` | `evidence.mjs:84-87` |
| (a) Worked examples: 20000 -> 18000/1000/1000, 1000 -> 900/50/50, 4000 -> 3600/200/200, 1010 refused | `example_20000`, `example_1000`, `example_4000`, `example_dust` | |
| (b) A checker gets the same pay (`VERIFIER_PAY` = 2 credits) for agree and for a deterministic disagree | `checker_pay_agree_eq_disagree`, `checker_pay_substantive` | `evidence.mjs:9,33-36` |
| (b) Scope: an empty output (`parent_empty`, `child_empty`) pays 0 | `checker_pay_empty` | same |
| (c) First check disagrees: worker unpaid, nothing queued for the chain, row held, one tiebreaker queued | `first_disagree_holds` | `protocol.mjs:1428-1435`, `markHeld` |
| (c) A deterministic disagree on any check never makes a row `pending` | `disagree_never_pending` | `protocol.mjs:1316-1439` |
| (c) A tiebreaker disagree claws the worker's award back to 0 and closes the row | `tiebreak_disagree_clawback` | `protocol.mjs:1351-1357`, `clawbackWorker` |
| (c, d) Over every reachable trace, `pending` (the only status the settler mints) implies two agreeing verifiers, both different from the worker and from each other, pairwise distinct digests, and a clean 9000/500/500 amount | `pending_sound` (from `inv_step`, `inv_reachable`) | `releasePending`, `protocol.mjs:1256-1314` |
| (d) No self verification by node id: an independent pair never includes the worker or repeats a verifier | `independent_sound` | `protocol.mjs:267-271`, `settle.py:171-175` |
| (d) The worker and earlier checkers cannot claim a check of the worker's job | `worker_cannot_claim_own_check`, `excluded_cannot_claim` | `protocol.mjs:976-977,1041-1070` |
| Contract: a successful `settle` mints exactly the contribution, split 9000/500/500, records the id, and moves each balance by exactly what that address received | `settle_spec`, `mint_apply` | `Settlement.sol:71-131` |
| Contract: dust always reverts; a settlement id settles at most once | `dust_reverts`, `no_replay` | `Settlement.sol:83,88-96` |
| (e) Quest 001: 10 HHC pays 5 + 5 to two different sealers; ineligible, mismatched, or same-sealer pairs are never paid | `quest001_split`, `ineligible_never_paid`, `mismatch_never_paid`, `same_sealer_never_paid` | spec only (see below) |

## Findings: what the proofs and cross-checks turned up

These are statements about the code as it is at the baseline commit. The
model was not adjusted to hide them. Each is either a theorem or a
cross-check test.

- **F1 (medium) - a second-check disagree does not hold the worker's off-chain
  award.** If the first checker agrees, the worker is paid at once. If the
  second checker then disagrees, the chain mint is held, but the worker keeps
  the credits until a tiebreaker disagrees. Theorem
  `second_disagree_keeps_offchain_award`; reproduced against the real handler
  by the `agree_second_disagree` cross-check.
- **F2 (medium) - one tiebreaker per job can leave a job stuck.**
  `queueTiebreak` (`protocol.mjs:1251-1255`) refuses when any `verify_tiebreak`
  child exists. Take the path first check disagrees, tiebreaker agrees, second
  check disagrees: the row ends `held_for_tiebreaker` with no tiebreaker
  queued, no later event can move it, and the worker keeps the award paid at
  the tiebreak. Theorem `single_tiebreak_stuck`; reproduced by the
  `disagree_tiebreak_agree_second_disagree` cross-check.
- **F3 (low on testnet, design note) - the contract does not enforce verifier
  independence.** `Settlement.sol` lets one address be the worker and both
  verifiers. Independence is checked only off chain, by node id, before the
  settler signs. Two node ids that share one payout address pass that check.
  Theorem `same_address_all_roles`. A fix would compare the three addresses in
  `refusal_status` and, if wanted, in the contract.
- **F4 (low, unreachable today) - `splitsClean` in `protocol.mjs` uses float
  math.** Once `t * 9000` passes 2^53 it can disagree with exact integer math.
  In a sampled scan of 2.8 million amounts, the first clean amount it rejected
  was 32,359,365,692,980 units. The first dusty amount it accepted was
  8,317,637,711,024,730 units, which the Python split and the contract would
  then refuse. Awards are capped at 256 tokens (`protocol.mjs:1610-1614`) x
  weight 8 = 2048 credits (2,048,000 units), so this cannot happen today. It is
  encoded as a strict `xfail` in `tests/test_lean_settlement_crosscheck.py`,
  which turns red once the JS uses integer math (`total % 20 === 0`).
- **Empty outputs.** The result endpoint requeues an empty output
  (`protocol.mjs:1602-1608`), so a checker's `child_empty` verdict is not
  reached through it. The model still covers it, and it pays 0.
- **Scope of "paid equally".** Checker pay is equal off chain (2 credits each
  for agree and disagree). On chain, only the two verifiers who agreed are
  minted 5% each. A checker who disagreed is replaced (tiebreak path) and gets
  nothing on chain.

## Cross-checks against the real code

The model is code we wrote by reading the sources, so it could be wrong. Two
tests run the real implementations on the inputs in `model_table.json`, which
`lake exe settlement-table` generates from the same Lean definitions the
proofs use:

- `tests/test_lean_settlement_crosscheck.py`: `split_contribution` (Python) on
  260 amounts (0-240, the 20-unit edges, and large values); `splitsClean`,
  `decodeSettledLog().split_ok`, `checkerPay`, and `independentVerifiers`
  (Node, through `crosscheck/eval_js.mjs`); and the settler's `refusal_status`
  on all 64 id triples.
- `tests/test_lean_flow_crosscheck.mjs`: drives the real gpu-mesh handler
  (in-memory store, four nodes) through seven agree, disagree, and tiebreak
  paths. It compares the final row status, queued amount, mesh credits,
  verifier ids, worker and checker balances, and whether a tiebreaker is
  queued.

`check.sh` fails if `model_table.json` is out of date with the Lean model.

## Trust boundary: what is NOT proved

- **Model vs. deployed code.** The proofs are about the Lean model. The link
  to `protocol.mjs`, `settle.py`, and `mesh_receipt.py` is a careful reading
  plus the cross-check tests above, not a proof. A change to those files can
  break the match, and the cross-checks are what catch it.
- **The flow model covers one parent job** with non-empty output and a pinned
  digest. It leaves out leases, timeouts, retries, storage errors, concurrent
  requests, ledger signing failures, the 7-day / 3-job hold release (which
  moves credits between `credits` and `escrow_credits` without changing their
  sum), and the deduplication of `settle` keys.
- **Settlement.sol is a hand-written slice.** It covers the guards, the split
  check, the replay flag, the mints, and the uint256 overflow reverts. It does
  NOT cover the EIP-712 signature and `SETTLER_ROLE` check, pause, token access
  control, events, the compiler, or EVM bytecode. Nothing ties the slice to
  the deployed contract at `0xdfFE664d23E30Baff7Ad4d16831aD625Cc90bcCA` except
  reading the source. Bytecode-level verification is NOT_RUN (see below).
- **Quest 001 is spec only.** No code in this repository computes the Quest
  001 reward. The model follows the published proof-board text ("10 HHC, split
  50/50 - 5 HHC to each of the two matching independent verifiers ... The
  coordinator (GrokAce) and the index publisher cannot win"). Dennis
  Christie's authorization, seal signatures, and the seal-drop envelope are
  outside the model.
- **Strings and numbers.** Node ids are compared as exact strings; the JS
  `.trim()` is not modelled. Amounts are unbounded `Nat`. F4 shows where JS
  numbers differ.

## Open-source work studied

| Project | License | What we did with it |
| --- | --- | --- |
| [lfglabs-dev/verity](https://github.com/lfglabs-dev/verity) (formerly Th0rgal/verity): Lean 4 verified smart contracts (ERC20, SimpleToken, Vault) | MIT | **Adopted patterns, no code copied.** (1) Separate files for the implementation model and the spec, and a `*_spec` theorem saying what a successful call guarantees (our `settle_spec`). (2) Their supply proofs count an address once per occurrence, because the same address can appear twice; our balance equation adds one term per role, so an address filling two roles gets both amounts, and that is what exposed F3. (3) Prove exact equations rather than inequalities. Not adopted: their `verity_contract` DSL and EVM `Uint256` library. It is large, pinned to a different toolchain, and more than a three-party split needs. |
| [NethermindEth/EVMYulLean](https://github.com/NethermindEth/EVMYulLean): executable EVM and Yul semantics in Lean 4 | Apache-2.0 | **Studied, not integrated.** It is the realistic route to bytecode-level proofs of `Settlement.sol`. It needs Mathlib (pinned to v4.22.0), a C FFI build, and the contract compiled to Yul, and the proofs would run to weeks. Bytecode-level verification of `Settlement.sol` is therefore NOT_RUN. The hand-written slice in `Settlement/Contract.lean` covers the arithmetic and guards. |
| [NethermindEth/Clear](https://github.com/NethermindEth/Clear): interactive Yul verification | Nethermind licence (non-commercial use only, all rights reserved) | **Studied the public description only; no code or text used.** Its licence is not compatible with this repository's open-source licence, so nothing was copied or adapted. |

The whole-trace invariant (`Reachable`, `Inv`, `inv_step`, `inv_reachable`)
is standard Lean induction over a step relation. It is written from scratch
here.

## Files

- `Settlement/Split.lean`: the 9000/500/500 split, the evidence `split_ok`, conservation
- `Settlement/Checker.lean`: verdicts, checker pay, independence, claim exclusion
- `Settlement/Flow.lean`: the check, hold, tiebreak, and release state machine; `pending_sound`; F1, F2
- `Settlement/Contract.lean`: the `Settlement.sol` `settle` slice; F3
- `Settlement/Quest001.lean`: the Quest 001 reward rule
- `Main.lean`: `lake exe settlement-table` writes `model_table.json`
- `Audit.lean`, `check.sh`: the axiom audit and the CI entry point
- `crosscheck/eval_js.mjs`: runs the edge-function code for the Python cross-check

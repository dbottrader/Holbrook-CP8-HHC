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

## The settlement rule (after the F1 - F4 fixes)

This is the rule from PR #61 (a disagreement holds the worker payout and
calls a tiebreaker), made total so that every job ends:

1. The first agreeing check pays the worker its award off chain and queues a
   second check. A first disagree pays the worker nothing, holds the row, and
   queues one tiebreaker.
2. **Any disagreement holds the worker payout on and off chain (F1).** When a
   check disagrees, the worker's off-chain award is clawed back while the mint
   is held. A release that is refused (digests, independence, shared payout,
   dust) also claws it back. The worker holds its award only while the job is
   `awaiting_second_verifier` or `pending`.
3. **A job is decided by at most three checks, by majority (F2).** Two
   agrees settle (`pending`). Two disagrees close the job as
   `held_disagreement` with the award at 0. The path first disagrees,
   tiebreaker agrees, second check disagrees used to stay
   `held_for_tiebreaker` forever. It now closes by majority.
4. **The worker, both verifiers, and their payout addresses must all differ
   (F3).** The coordinator refuses with `skipped_shared_payout` (at release
   and again when the settler lists pending rows). The settler refuses the
   same way, and `Settlement.sol` reverts with `SameAddress`.
5. **All split arithmetic is exact integer math (F4).** `splitsClean` and the
   evidence decoder's `split_ok` use BigInt.

Checkers are still paid `VERIFIER_PAY` (2 credits) off chain for agree and
for disagree alike. On chain, the two verifiers who agreed are minted 5% each.

## What is proved

Every theorem below is checked by Lean. None uses `sorry`, `admit`,
`native_decide`, or a new axiom. `Audit.lean` prints each theorem's axioms,
and `check.sh` fails on anything beyond Lean's standard `propext`,
`Classical.choice` and `Quot.sound`. Line numbers below refer to
`supabase/functions/gpu-mesh/protocol.mjs` unless another file is named.

| Property | Theorem | Code it models |
| --- | --- | --- |
| (a) Conservation: an accepted split pays exactly the contribution, the verifier halves are equal, worker = 18/20, each verifier = 1/20 | `conservation`, `clean_shares` | `splitsClean` :277, `mesh_receipt.py:179-188` |
| (a) Rounding: a split is accepted iff the amount is positive and divisible by 20. Dust is refused, never rounded or reassigned | `splitsClean_iff`, `refused_iff` | same |
| (a) Any positive mesh award (credits x 1000 units) always splits cleanly | `mesh_contribution_clean` | :1306 |
| (a) The evidence decoder's `split_ok` accepts exactly the contract's amounts | `evidenceSplitOk_iff` | `evidence.mjs:86` |
| (a) Worked examples: 20000 -> 18000/1000/1000, 1000 -> 900/50/50, 4000 -> 3600/200/200, 1010 refused | `example_20000`, `example_1000`, `example_4000`, `example_dust` | |
| (b) A checker gets the same pay for agree and for a deterministic disagree; empty outputs pay 0 | `checker_pay_agree_eq_disagree`, `checker_pay_substantive`, `checker_pay_empty` | `evidence.mjs:9,33` |
| (c) First check disagrees: worker unpaid, nothing queued for the chain, row held, one tiebreaker queued | `first_disagree_holds` | `finishVerification` :1437, `markHeld` |
| (c) A deterministic disagree on any check never makes a row `pending` | `disagree_never_pending` | :1342-1473 |
| (c) A tiebreaker disagree closes the row with the worker award at 0 | `tiebreak_disagree_closes` | `finishTiebreak` :1342 |
| (c, F1) On every trace, the worker's off-chain award is its award exactly when the row is `awaiting_second_verifier` or `pending`, else 0; in particular 0 while held for a tiebreaker | `worker_paid_iff`, `held_worker_unpaid`, `second_disagree_holds_award` | `releasePending` :1273-1276, `finishSecondVerification` :1398-1435 |
| (c, d) On every trace, `pending` implies two agreeing verifiers distinct from each other and from the worker, distinct payout addresses, pairwise distinct digests, and a clean 9000/500/500 amount | `pending_sound` (from `Inv`, `inv_step`, `inv_reachable`) | `releaseChecks` :1278 |
| (F2) Termination: from any reachable state at most `rem` checks can run, and at most 3 in total, for every sequence of checks | `rem_decreases`, `checks_bounded`, `at_most_three_checks` | :1263, :1342, :1398, :1437 |
| (F2) No stuck jobs: a reachable state with no check queued is never `awaiting_second_verifier` or `held_for_tiebreaker`; it is `pending` with the worker paid, or a refusal with the worker award at 0 | `no_stuck`, `step_disabled` | same |
| (F2) The former stuck path now closes by majority with the award clawed back | `majority_disagree_closes` | :1420-1427 (`held_disagreement` at :1424) |
| (d) No self verification by node id | `independent_sound` | :271, `settle.py:171-175` |
| (d) The worker and earlier checkers cannot claim a check of the worker's job | `worker_cannot_claim_own_check`, `excluded_cannot_claim` | :989, `enqueueVerification` :1053 |
| Contract: a successful `settle` names three distinct addresses, mints exactly the contribution split 9000/500/500, records the id, and moves each balance by exactly what that address received | `settle_spec`, `mint_apply` | `Settlement.sol:74-138` |
| (F3) Contract: a settle that names one address twice always reverts, and each address gains exactly its single-role share, so never more than the worker share | `same_address_rejected`, `single_role_share`, `at_most_worker_share`, `same_address_example` | `Settlement.sol:90-92` |
| Contract: dust always reverts; a settlement id settles at most once | `dust_reverts`, `no_replay` | `Settlement.sol` |
| (e) Quest 001: 10 HHC pays 5 + 5 to two different sealers; ineligible, mismatched, or same-sealer pairs are never paid | `quest001_split`, `ineligible_never_paid`, `mismatch_never_paid`, `same_sealer_never_paid` | spec only (see below) |

## Findings and their fixes

The first pass (branch `feat/lean-settlement-proofs`) proved four defects as
theorems. Branch `feat/settlement-fixes` fixes them, and the bug theorems are
replaced by theorems that state the fixed behaviour.

| Finding | Before | After | Bug theorem -> fixed theorem |
| --- | --- | --- | --- |
| F1: worker kept the off-chain award while the mint was held | first agree, second disagree: row held, worker kept 4 credits | worker clawed back to 0 while held; restored only if a tiebreaker agrees | `second_disagree_keeps_offchain_award` -> `second_disagree_holds_award`, `worker_paid_iff`, `held_worker_unpaid` |
| F2: a job could stay `held_for_tiebreaker` forever | first disagree, tiebreak agree, second disagree: held, no tiebreaker queued, worker kept 4 credits | closes as `held_disagreement` by majority, worker 0; every job ends within 3 checks | `single_tiebreak_stuck` -> `majority_disagree_closes`, `no_stuck`, `at_most_three_checks` |
| F3: one address could fill all three roles | `settle(..., w, .., w, .., w, ..)` minted the whole contribution to one address | reverts `SameAddress`; coordinator and settler refuse `skipped_shared_payout` | `same_address_all_roles` -> `same_address_rejected`, `single_role_share`, `at_most_worker_share` |
| F4: float math in `splitsClean` | `splitsClean(9007199254740980)` was `false` (exact answer `true`) | exact BigInt math; matches the model on every safe integer | strict `xfail` tests -> passing tests |

The evidence decoder's `split_ok` (`evidence.mjs:86`) had the same kind of
float arithmetic. It now uses BigInt too. On the values tested it gave the
right answer before the change, so this is hardening, not a fixed failure.

## Cross-checks against the real code

The model is code written by reading the sources, so it could be wrong. Two
tests run the real implementations on the inputs in `model_table.json`, which
`lake exe settlement-table` generates from the same Lean definitions the
proofs use:

- `tests/test_lean_settlement_crosscheck.py` (270 tests): `split_contribution`
  (Python) on 260 amounts; `splitsClean`, `decodeSettledLog().split_ok`,
  `checkerPay`, `independentVerifiers`, and `distinctPayouts` (Node, through
  `crosscheck/eval_js.mjs`); and the settler's `refusal_status` for verifier
  independence and shared payouts.
- `tests/test_lean_flow_crosscheck.mjs` (9 flows): drives the real gpu-mesh
  handler (in-memory store, four nodes) through every agree, disagree,
  tiebreak, and shared-payout path in the table. It compares the final row
  status, queued amount, mesh credits, verifier ids, worker and checker
  balances, whether a tiebreaker is queued, and whether the job is terminal
  (no check left queued).

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
- **Strings and numbers.** Node ids and payout addresses are compared as
  exact strings; the JS `.trim()` and `.toLowerCase()` are not modelled.
  Amounts are unbounded `Nat`; the JS code accepts safe integers only
  (up to 2^53 - 1), and the cross-check covers values up to that limit.
- **Ledger details.** A tiebreak that restores a clawed-back award writes a
  second `inference_receipt` under the key `worker_award_tiebreak`, and the
  node's `verified_jobs` counter counts it again. The model tracks balances,
  not counters.

## Open-source work studied

| Project | License | What we did with it |
| --- | --- | --- |
| [lfglabs-dev/verity](https://github.com/lfglabs-dev/verity) (formerly Th0rgal/verity): Lean 4 verified smart contracts (ERC20, SimpleToken, Vault) | MIT | **Adopted patterns, no code copied.** (1) Separate files for the implementation model and the spec, and a `*_spec` theorem saying what a successful call guarantees (our `settle_spec`). (2) Their supply proofs count an address once per occurrence, because the same address can appear twice; our balance equation adds one term per role, so an address filling two roles gets both amounts, and that is what exposed F3. (3) Prove exact equations rather than inequalities. Not adopted: their `verity_contract` DSL and EVM `Uint256` library. It is large, pinned to a different toolchain, and more than a three-party split needs. |
| [NethermindEth/EVMYulLean](https://github.com/NethermindEth/EVMYulLean): executable EVM and Yul semantics in Lean 4 | Apache-2.0 | **Studied, not integrated.** Bytecode-level verification of `Settlement.sol` is NOT_RUN; see the next section. |
| [NethermindEth/Clear](https://github.com/NethermindEth/Clear): interactive Yul verification | Nethermind licence (non-commercial use only, all rights reserved) | **Studied the public description only; no code or text used.** Its licence is not compatible with this repository's open-source licence, so nothing was copied or adapted. |

The whole-trace invariant (`Reachable`, `Inv`, `inv_step`, `inv_reachable`)
is standard Lean induction over a step relation. It is written from scratch
here.

## Bytecode-level verification: NOT_RUN, and what it would take

EVMYulLean is an executable semantics (an interpreter with conformance
tests), not a program logic. Proving that the compiled `Settlement` satisfies
`settle_spec` for all inputs would need:

1. a separate Lake project with Mathlib v4.22.0 (EVMYulLean's pin, a different
   toolchain from this project's v4.36.0) and its C FFI (SHA-256, Keccak);
2. the contract as Yul: `forge inspect Settlement irOptimized` gives 2,932
   lines for the `via_ir` build, and the deployed bytecode is about 9.3 KB;
3. a symbolic-execution or Hoare-logic layer over the interpreter, which
   EVMYulLean does not ship. The open tool that provides one for Yul (Clear)
   is under a non-commercial licence;
4. models of OpenZeppelin `AccessControlDefaultAdminRules`, `Pausable`,
   `EIP712`, `ECDSA`, and the HHCW `mint`, all reached from `settle`.

That is weeks of proof work, not a stretch goal for one pass. A cheaper
middle step, if wanted later: run the compiled bytecode in EVMYulLean on the
same inputs as `model_table.json`. That would be a cross-check, not a proof.
Today the link from the Lean slice to the bytecode is the Foundry suite: 22
tests, including the `SameAddress` reverts and a fuzz test of
`single_role_share`.

## Files

- `Settlement/Split.lean`: the 9000/500/500 split, the evidence `split_ok`, conservation
- `Settlement/Checker.lean`: verdicts, checker pay, independence, claim exclusion
- `Settlement/Flow.lean`: the check, hold, tiebreak, and release state machine; `pending_sound`; F1 and F2 fixes; termination and no-stuck proofs
- `Settlement/Contract.lean`: the `Settlement.sol` `settle` slice; F3 fix
- `Settlement/Quest001.lean`: the Quest 001 reward rule
- `Main.lean`: `lake exe settlement-table` writes `model_table.json`
- `Audit.lean`, `check.sh`: the axiom audit and the CI entry point
- `crosscheck/eval_js.mjs`: runs the edge-function code for the Python cross-check

/-
  The 9000 / 500 / 500 settlement split.

  Faithful model of three implementations that must agree:
  - supabase/functions/gpu-mesh/protocol.mjs:273-278 `splitsClean`
  - moltbook/ledger/mesh_receipt.py:179-188 `split_contribution`
  - contracts/src/Settlement.sol:88-95 expected amounts and `BadSplit`
  plus the decoder check in supabase/functions/gpu-mesh/evidence.mjs:84-87.

  Amounts are Nat (integer HHCW units). Floor division is Nat division.
-/
namespace Settlement

def WORKER_BPS : Nat := 9000
def VERIFIER_BPS : Nat := 500
def BPS_DENOM : Nat := 10000
/-- protocol.mjs:49 `UNITS_PER_CREDIT` -/
def UNITS_PER_CREDIT : Nat := 1000

def workerShare (t : Nat) : Nat := t * WORKER_BPS / BPS_DENOM
def verifierShare (t : Nat) : Nat := t * VERIFIER_BPS / BPS_DENOM

/-- protocol.mjs:273 `splitsClean` -/
def splitsClean (t : Nat) : Bool :=
  decide (0 < t) && workerShare t + verifierShare t + verifierShare t == t

/-- mesh_receipt.py:179 `split_contribution`. `none` is the raised
    `MeshReceiptError`; dust is refused, never reassigned. -/
def splitContribution (t : Nat) : Option (Nat × Nat × Nat) :=
  if splitsClean t then some (workerShare t, verifierShare t, verifierShare t) else none

/-- evidence.mjs:84-87 `split_ok` on a decoded `Settled` log. -/
def evidenceSplitOk (w v1 v2 c : Nat) : Bool :=
  w + v1 + v2 == c && w * 10000 == c * 9000 && v1 * 10000 == c * 500 && v2 * 10000 == c * 500

/-- A contribution splits cleanly exactly when it is positive and divisible by 20. -/
theorem splitsClean_iff (t : Nat) : splitsClean t = true ↔ 0 < t ∧ t % 20 = 0 := by
  simp only [splitsClean, workerShare, verifierShare, WORKER_BPS, VERIFIER_BPS, BPS_DENOM,
    Bool.and_eq_true, decide_eq_true_eq, beq_iff_eq]
  omega

/-- The exact shares of a clean contribution: 18/20 and 1/20 each. -/
theorem clean_shares (t : Nat) (h : t % 20 = 0) :
    workerShare t = 18 * (t / 20) ∧ verifierShare t = t / 20 := by
  simp only [workerShare, verifierShare, WORKER_BPS, VERIFIER_BPS, BPS_DENOM]
  omega

/-- (a) Conservation: an accepted split pays out exactly the contribution,
    the two verifier parts are equal, and nothing is rounded away. -/
theorem conservation (t w a b : Nat) (h : splitContribution t = some (w, a, b)) :
    w + a + b = t ∧ a = b ∧ w = 18 * (t / 20) ∧ a = t / 20 ∧ 0 < t := by
  unfold splitContribution at h
  split at h
  · rename_i hc
    have ⟨hpos, hdiv⟩ := (splitsClean_iff t).mp hc
    have ⟨hw, hv⟩ := clean_shares t hdiv
    simp only [Option.some.injEq, Prod.mk.injEq] at h
    obtain ⟨rfl, rfl, rfl⟩ := h
    refine ⟨?_, rfl, hw, hv, hpos⟩
    rw [hw, hv]; omega
  · cases h

/-- No dust path: a contribution that is zero or not divisible by 20 is
    refused outright (`skipped_indivisible`), never rounded. -/
theorem refused_iff (t : Nat) : splitContribution t = none ↔ t = 0 ∨ t % 20 ≠ 0 := by
  unfold splitContribution
  have := splitsClean_iff t
  split <;> simp_all <;> omega

/-- Every positive mesh credit amount converts (x1000 units) to a clean split,
    so `skipped_indivisible` is unreachable for a positive award. -/
theorem mesh_contribution_clean (credits : Nat) (h : 0 < credits) :
    splitsClean (credits * UNITS_PER_CREDIT) = true := by
  rw [splitsClean_iff]; simp only [UNITS_PER_CREDIT]; omega

/-- The evidence decoder's `split_ok` accepts exactly the contract's expected
    amounts for a divisible contribution. -/
theorem evidenceSplitOk_iff (w v1 v2 c : Nat) :
    evidenceSplitOk w v1 v2 c = true ↔
      c % 20 = 0 ∧ w = workerShare c ∧ v1 = verifierShare c ∧ v2 = verifierShare c := by
  simp only [evidenceSplitOk, workerShare, verifierShare, WORKER_BPS, VERIFIER_BPS, BPS_DENOM,
    Bool.and_eq_true, beq_iff_eq]
  omega

/-- The worked example from PR #61: 20000 units pay 18000 / 1000 / 1000. -/
theorem example_20000 : splitContribution 20000 = some (18000, 1000, 1000) := by decide
/-- The live first settlement on Base Sepolia minted 900 / 50 / 50 of 1000. -/
theorem example_1000 : splitContribution 1000 = some (900, 50, 50) := by decide
/-- 4 mesh credits (the test suite's award) become 4000 units: 3600 / 200 / 200. -/
theorem example_4000 : splitContribution 4000 = some (3600, 200, 200) := by decide
theorem example_dust : splitContribution 1010 = none := by decide

end Settlement

/-
  Checker pay, verifier independence, and claim exclusion.

  - supabase/functions/gpu-mesh/protocol.mjs:345-353 `judge` (the four verdicts)
  - supabase/functions/gpu-mesh/evidence.mjs:9 `VERIFIER_PAY = 2`, :33-36 `checkerPay`
  - supabase/functions/gpu-mesh/protocol.mjs:267-271 `independentVerifiers`
  - gpu-mesh/settler/settle.py:171-175 `refusal_status` (same rule, by node id)
  - supabase/functions/gpu-mesh/protocol.mjs:1041-1070 `enqueueVerification`,
    :976-977 `claimOnce` exclusion
-/
namespace Settlement

/-- The verdicts `judge` can return. -/
inductive Verdict where
  | parentEmpty
  | childEmpty
  | agree
  | disagreeDeterministic
  deriving DecidableEq, Repr

def Verdict.tag : Verdict → String
  | .parentEmpty => "parent_empty"
  | .childEmpty => "child_empty"
  | .agree => "agree"
  | .disagreeDeterministic => "disagree_deterministic"

def VERIFIER_PAY : Nat := 2

def checkerPay : Verdict → Nat
  | .agree => VERIFIER_PAY
  | .disagreeDeterministic => VERIFIER_PAY
  | _ => 0

/-- (b) A checker is paid the same for agree and for a deterministic disagree. -/
theorem checker_pay_agree_eq_disagree :
    checkerPay .agree = checkerPay .disagreeDeterministic := rfl

/-- (b) The pay does not depend on the job, the worker, or the amount: it is a
    function of the verdict alone, and every substantive verdict pays `VERIFIER_PAY`. -/
theorem checker_pay_substantive (v : Verdict) (h : v = .agree ∨ v = .disagreeDeterministic) :
    checkerPay v = VERIFIER_PAY := by
  rcases h with rfl | rfl <;> rfl

/-- (b, scope note) An empty output pays nothing, so "equal for agree and
    disagree" covers the two substantive verdicts only. -/
theorem checker_pay_empty (v : Verdict) (h : v = .parentEmpty ∨ v = .childEmpty) :
    checkerPay v = 0 := by
  rcases h with rfl | rfl <;> rfl

/-- `independentVerifiers(worker, [a, b])` for the two-element call sites
    (protocol.mjs:1269, settle.py:172-175). Empty ids are filtered out, so an
    empty id leaves fewer than two and fails. -/
def independent (worker a b : String) : Bool :=
  a != "" && b != "" && a != b && worker != a && worker != b

/-- (d) No self verification at the node-id level: an independent pair never
    contains the worker and never repeats a verifier. -/
theorem independent_sound (w a b : String) (h : independent w a b = true) :
    w ≠ a ∧ w ≠ b ∧ a ≠ b ∧ a ≠ "" ∧ b ≠ "" := by
  simp only [independent, Bool.and_eq_true, bne_iff_ne, ne_eq] at h
  obtain ⟨⟨⟨⟨ha, hb⟩, hab⟩, hwa⟩, hwb⟩ := h
  exact ⟨hwa, hwb, hab, ha, hb⟩

/-- A queued verification job as built by `enqueueVerification`. -/
structure VerifyJob where
  origin : String
  excluded : List String

def enqueue (origin : String) (extra : List String) : VerifyJob :=
  { origin, excluded := origin :: extra }

/-- `claimOnce` exclusion test for a verification job (protocol.mjs:976-977). -/
def canClaim (j : VerifyJob) (node : String) : Bool :=
  !(j.excluded.contains node) && node != j.origin

/-- (d) The worker can never claim a check of its own output. -/
theorem worker_cannot_claim_own_check (w : String) (extra : List String) :
    canClaim (enqueue w extra) w = false := by
  simp [canClaim, enqueue]

/-- (d) Nodes passed as `extraExcluded` (earlier checkers) cannot claim it either. -/
theorem excluded_cannot_claim (w n : String) (extra : List String) (h : n ∈ extra) :
    canClaim (enqueue w extra) n = false := by
  simp [canClaim, enqueue, h]

end Settlement

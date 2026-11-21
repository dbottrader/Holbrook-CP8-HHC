/-
  Quest 001 reward rule. SPEC ONLY: no code in this repository computes it.

  Source text (proof board artifact, not in this repo): "Prize: 10 HHC, split
  50/50 - 5 HHC to each of the two matching independent verifiers (Alpha and
  Beta: different operator, different key, different failure mode). The
  coordinator (GrokAce) and the index publisher cannot win; their seals are
  refused." Payment also needs Dennis Christie's authorization, which is
  outside any model.
-/
namespace Settlement.Quest001

structure Seal where
  sealer : String
  digest : String

def PRIZE : Nat := 10

/-- Two seals pay out only when they match, come from two different sealers,
    and neither sealer is ineligible. Each gets half. -/
def payout (total : Nat) (ineligible : List String) (a b : Seal) : Option ((String × Nat) × (String × Nat)) :=
  if a.sealer ≠ b.sealer ∧ a.digest = b.digest ∧ a.sealer ∉ ineligible ∧ b.sealer ∉ ineligible ∧
     total % 2 = 0 then
    some ((a.sealer, total / 2), (b.sealer, total / 2))
  else none

/-- (e) 10 HHC pays 5 + 5, the halves are equal, and they sum to the prize. -/
theorem quest001_split (inel : List String) (a b : Seal) (p q : String × Nat)
    (h : payout PRIZE inel a b = some (p, q)) :
    p.2 = 5 ∧ q.2 = 5 ∧ p.2 + q.2 = PRIZE ∧ p.1 ≠ q.1 := by
  unfold payout at h
  split at h
  · rename_i hc
    simp only [Option.some.injEq, Prod.mk.injEq] at h
    obtain ⟨rfl, rfl⟩ := h
    exact ⟨rfl, rfl, rfl, hc.1⟩
  · cases h

/-- An ineligible sealer (for example the coordinator) is never paid. -/
theorem ineligible_never_paid (inel : List String) (a b : Seal) (t : Nat)
    (h : a.sealer ∈ inel ∨ b.sealer ∈ inel) : payout t inel a b = none := by
  unfold payout
  split
  · rename_i hc; rcases h with h | h
    · exact absurd h hc.2.2.1
    · exact absurd h hc.2.2.2.1
  · rfl

/-- Seals that do not match pay nothing. -/
theorem mismatch_never_paid (inel : List String) (a b : Seal) (t : Nat)
    (h : a.digest ≠ b.digest) : payout t inel a b = none := by
  unfold payout
  split
  · rename_i hc; exact absurd hc.2.1 h
  · rfl

/-- One sealer cannot take both halves. -/
theorem same_sealer_never_paid (inel : List String) (a b : Seal) (t : Nat)
    (h : a.sealer = b.sealer) : payout t inel a b = none := by
  unfold payout
  split
  · rename_i hc; exact absurd h hc.1
  · rfl

end Settlement.Quest001

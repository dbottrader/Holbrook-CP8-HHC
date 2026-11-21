/-
  A slice of contracts/src/Settlement.sol `settle` (lines 71-131).

  Modelled: the replay guard, zero-address guard, the distinct-address guard
  added for F3 (`SameAddress`), zero amount, checked multiplication (Solidity 0.8 reverts on uint256 overflow),
  the expected-amount and sum check (:88-96), `settled[id] = true` (:115),
  and the three `token.mint` calls (:117-119) as balance and supply updates,
  with the mint's own overflow check on total supply.

  Not modelled (trusted, see README): the EIP-712 signature and SETTLER_ROLE
  check (:98-113), `whenNotPaused`, the token's access control, events, gas,
  and the compiled EVM bytecode. Addresses are Nat (0 is address(0)).
-/
import Settlement.Split

namespace Settlement.Contract

def U256 : Nat := 2 ^ 256

structure CState where
  settled : List Nat
  balance : Nat → Nat
  supply : Nat

inductive Err where
  | alreadySettled
  | zeroAddress
  | sameAddress
  | zeroAmount
  | overflow
  | badSplit
  deriving DecidableEq, Repr

def mint (bal : Nat → Nat) (to amt : Nat) : Nat → Nat :=
  fun a => if a = to then bal a + amt else bal a

theorem mint_apply (bal : Nat → Nat) (to amt a : Nat) :
    mint bal to amt a = bal a + (if a = to then amt else 0) := by
  unfold mint; split <;> simp

def settle (s : CState) (sid w wa v1 va1 v2 va2 c : Nat) : Except Err CState :=
  if sid ∈ s.settled then .error .alreadySettled
  else if w = 0 ∨ v1 = 0 ∨ v2 = 0 then .error .zeroAddress
  else if w = v1 ∨ w = v2 ∨ v1 = v2 then .error .sameAddress
  else if c = 0 then .error .zeroAmount
  else if U256 ≤ c * WORKER_BPS then .error .overflow
  else if wa ≠ workerShare c ∨ va1 ≠ verifierShare c ∨ va2 ≠ verifierShare c ∨ wa + va1 + va2 ≠ c then
    .error .badSplit
  else if U256 ≤ s.supply + c then .error .overflow
  else .ok { settled := sid :: s.settled,
             balance := mint (mint (mint s.balance w wa) v1 va1) v2 va2,
             supply := s.supply + c }

/-- Acceptance spec (the Verity `*_meets_spec` pattern): a successful settle
    mints exactly the contribution, split 9000/500/500 with equal verifier
    parts, records the id, and moves each balance by exactly what was minted
    to that address, counting an address once per role it fills. -/
theorem settle_spec (s s' : CState) (sid w wa v1 va1 v2 va2 c : Nat)
    (h : settle s sid w wa v1 va1 v2 va2 c = .ok s') :
    w ≠ v1 ∧ w ≠ v2 ∧ v1 ≠ v2 ∧
    s'.supply = s.supply + c ∧ wa + va1 + va2 = c ∧ va1 = va2 ∧ c % 20 = 0 ∧
    wa = 18 * (c / 20) ∧ sid ∈ s'.settled ∧ sid ∉ s.settled ∧
    ∀ a, s'.balance a = s.balance a + (if a = w then wa else 0) + (if a = v1 then va1 else 0) +
      (if a = v2 then va2 else 0) := by
  unfold settle at h
  split at h; · cases h
  split at h; · cases h
  split at h; · cases h
  split at h; · cases h
  split at h; · cases h
  split at h; · cases h
  split at h; · cases h
  rename_i hs _ hsame hc _ hb _
  simp only [not_or] at hsame
  obtain ⟨hwv1, hwv2, hv12⟩ := hsame
  simp only [Except.ok.injEq] at h
  subst h
  simp only [not_or, Decidable.not_not] at hb
  obtain ⟨rfl, rfl, rfl, hsum⟩ := hb
  have hpos : 0 < c := Nat.pos_of_ne_zero hc
  have hclean : splitsClean c = true := by
    simp only [splitsClean, hsum, beq_self_eq_true, Bool.and_true, decide_eq_true_eq]; exact hpos
  have ⟨_, hdiv⟩ := (splitsClean_iff c).mp hclean
  have ⟨hw, _⟩ := clean_shares c hdiv
  refine ⟨hwv1, hwv2, hv12, rfl, hsum, rfl, hdiv, hw, List.mem_cons_self .., hs, ?_⟩
  intro a
  simp only [mint_apply]

/-- Dust always reverts: no choice of amounts settles a contribution that is
    not a multiple of 20 units. -/
theorem dust_reverts (s : CState) (sid w wa v1 va1 v2 va2 c : Nat) (h : c % 20 ≠ 0) :
    ∀ s', settle s sid w wa v1 va1 v2 va2 c ≠ .ok s' := by
  intro s' hok
  exact h (settle_spec s s' sid w wa v1 va1 v2 va2 c hok).2.2.2.2.2.2.1

/-- A settlement id settles at most once. -/
theorem no_replay (s s' : CState) (sid w wa v1 va1 v2 va2 c w' wa' v1' va1' v2' va2' c' : Nat)
    (h : settle s sid w wa v1 va1 v2 va2 c = .ok s') :
    settle s' sid w' wa' v1' va1' v2' va2' c' = .error .alreadySettled := by
  have hm := (settle_spec s s' sid w wa v1 va1 v2 va2 c h).2.2.2.2.2.2.2.2.1
  simp [settle, hm]

def empty : CState := { settled := [], balance := fun _ => 0, supply := 0 }

/-- F3 fixed: one address can never fill two roles. Any settle that names the
    same address twice reverts with `SameAddress`, whatever the amounts. -/
theorem same_address_rejected (s : CState) (sid w wa v1 va1 v2 va2 c : Nat)
    (h : w = v1 ∨ w = v2 ∨ v1 = v2) : ∀ s', settle s sid w wa v1 va1 v2 va2 c ≠ .ok s' := by
  intro s' hok
  obtain ⟨h1, h2, h3, _⟩ := settle_spec s s' sid w wa v1 va1 v2 va2 c hok
  rcases h with h | h | h <;> contradiction

/-- F3 fixed: each address gains exactly its single-role share: the worker
    share, one verifier share, or nothing. -/
theorem single_role_share (s s' : CState) (sid w wa v1 va1 v2 va2 c : Nat)
    (h : settle s sid w wa v1 va1 v2 va2 c = .ok s') (a : Nat) :
    s'.balance a = s.balance a +
      (if a = w then workerShare c else if a = v1 ∨ a = v2 then verifierShare c else 0) := by
  obtain ⟨hw1, hw2, h12, _, hsum, hva, hdiv, hwa, _, _, hbal⟩ :=
    settle_spec s s' sid w wa v1 va1 v2 va2 c h
  have ⟨hws, hvs⟩ := clean_shares c hdiv
  have hv1 : va1 = verifierShare c := by omega
  have hv2 : va2 = verifierShare c := by omega
  have hw : wa = workerShare c := by omega
  rw [hbal a, hw, hv1, hv2]
  by_cases ha : a = w
  · subst ha; simp [hw1, hw2]
  · by_cases hb1 : a = v1
    · subst hb1; simp [ha, h12]
    · by_cases hb2 : a = v2
      · subst hb2; simp [Ne.symm hw2, Ne.symm h12]
      · simp [ha, hb1, hb2]

/-- So no address can ever receive more than the worker share of one settlement. -/
theorem at_most_worker_share (s s' : CState) (sid w wa v1 va1 v2 va2 c : Nat)
    (h : settle s sid w wa v1 va1 v2 va2 c = .ok s') (a : Nat) :
    s'.balance a ≤ s.balance a + workerShare c := by
  rw [single_role_share s s' sid w wa v1 va1 v2 va2 c h a]
  have : verifierShare c ≤ workerShare c := by
    simp only [verifierShare, workerShare, VERIFIER_BPS, WORKER_BPS, BPS_DENOM]; omega
  split
  · omega
  · split <;> omega

/-- The former F3 example now reverts. -/
theorem same_address_example :
    settle empty 7 1 900 1 50 1 50 1000 = .error .sameAddress := by
  simp [settle, empty]

end Settlement.Contract

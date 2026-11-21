/-
  A slice of contracts/src/Settlement.sol `settle` (lines 71-131).

  Modelled: the replay guard (:83), zero-address guard (:84-86), zero amount
  (:87), checked multiplication (Solidity 0.8 reverts on uint256 overflow),
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
  rename_i hs _ hc _ hb _
  simp only [Except.ok.injEq] at h
  subst h
  simp only [not_or, Decidable.not_not] at hb
  obtain ⟨rfl, rfl, rfl, hsum⟩ := hb
  have hpos : 0 < c := Nat.pos_of_ne_zero hc
  have hclean : splitsClean c = true := by
    simp only [splitsClean, hsum, beq_self_eq_true, Bool.and_true, decide_eq_true_eq]; exact hpos
  have ⟨_, hdiv⟩ := (splitsClean_iff c).mp hclean
  have ⟨hw, _⟩ := clean_shares c hdiv
  refine ⟨rfl, hsum, rfl, hdiv, hw, List.mem_cons_self .., hs, ?_⟩
  intro a
  simp only [mint_apply]

/-- Dust always reverts: no choice of amounts settles a contribution that is
    not a multiple of 20 units. -/
theorem dust_reverts (s : CState) (sid w wa v1 va1 v2 va2 c : Nat) (h : c % 20 ≠ 0) :
    ∀ s', settle s sid w wa v1 va1 v2 va2 c ≠ .ok s' := by
  intro s' hok
  exact h (settle_spec s s' sid w wa v1 va1 v2 va2 c hok).2.2.2.1

/-- A settlement id settles at most once. -/
theorem no_replay (s s' : CState) (sid w wa v1 va1 v2 va2 c w' wa' v1' va1' v2' va2' c' : Nat)
    (h : settle s sid w wa v1 va1 v2 va2 c = .ok s') :
    settle s' sid w' wa' v1' va1' v2' va2' c' = .error .alreadySettled := by
  have hm := (settle_spec s s' sid w wa v1 va1 v2 va2 c h).2.2.2.2.2.1
  simp [settle, hm]

def empty : CState := { settled := [], balance := fun _ => 0, supply := 0 }

/-- FINDING F3: the contract does not require the worker and the two verifier
    addresses to differ. One address can fill all three roles and receive the
    whole contribution. Independence is enforced only off chain, by node id,
    and only by the settler signing (protocol.mjs:267, settle.py:171-175). -/
theorem same_address_all_roles :
    ∃ s', settle empty 7 1 900 1 50 1 50 1000 = .ok s' ∧ s'.balance 1 = 1000 := by
  have h : settle empty 7 1 900 1 50 1 50 1000 =
      .ok { settled := [7], balance := mint (mint (mint (fun _ => 0) 1 900) 1 50) 1 50,
            supply := 1000 } := by
    simp [settle, empty, U256, workerShare, verifierShare, WORKER_BPS, VERIFIER_BPS, BPS_DENOM]
  exact ⟨_, h, by simp [mint]⟩

end Settlement.Contract

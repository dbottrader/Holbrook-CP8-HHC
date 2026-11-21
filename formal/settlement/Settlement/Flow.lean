/-
  The verification and settlement-row state machine of one parent job.

  Faithful to supabase/functions/gpu-mesh/protocol.mjs:
  - :1403-1439 `finishVerification` (first check)
  - :1079-1110 `openChainSettlement`, :1203-1249 `markHeld` (insert path)
  - :1363-1401 `finishSecondVerification` (`verify2`)
  - :1316-1361 `finishTiebreak` (`verify_tiebreak`)
  - :1251-1255 `queueTiebreak` (at most one tiebreak child per parent)
  - :1256-1314 `releasePending`
  - :1156-1173 `payWorker`, :1181-1206 `clawbackWorker`, :1112-1128 `payChecker`

  Modelling choices (each is a stated assumption, see README):
  - one parent job; its own output is non-empty and its model digest is pinned;
  - `award` is the `payWorker` amount, max(1, completion_tokens) * weight;
  - `digestsOk` is `settlementBindingHold(...) == ""` for the parent;
  - ledger signing, storage errors, leases and timeouts are out of scope;
  - balances are the node's credits plus escrow_credits (hold release moves
    credits between the two and does not change the sum).
-/
import Settlement.Split
import Settlement.Checker

namespace Settlement

/-- `gpumesh_chain_settlements.status` for this job (`none` = no row yet). -/
inductive Status where
  | none
  | awaitingSecondVerifier
  | heldForTiebreaker
  | heldDisagreement
  | verifierDisagreement
  | heldIndistinctDigests
  | skippedVerifierIndependence
  | skippedIndivisible
  | pending
  deriving DecidableEq, Repr

def Status.tag : Status → String
  | .none => "none"
  | .awaitingSecondVerifier => "awaiting_second_verifier"
  | .heldForTiebreaker => "held_for_tiebreaker"
  | .heldDisagreement => "held_disagreement"
  | .verifierDisagreement => "verifier_disagreement"
  | .heldIndistinctDigests => "held_indistinct_digests"
  | .skippedVerifierIndependence => "skipped_verifier_independence"
  | .skippedIndivisible => "skipped_indivisible"
  | .pending => "pending"

structure Job where
  worker : String
  award : Nat
  digestsOk : Bool

structure St where
  status : Status := .none
  firstDone : Bool := false
  v1 : String := ""
  d1 : Option Verdict := none
  v2 : String := ""
  d2 : Option Verdict := none
  /-- row.mesh_credits -/
  meshCredits : Nat := 0
  /-- row.amount, the HHCW units queued for the chain -/
  amount : Nat := 0
  /-- parent.credits_awarded -/
  credited : Nat := 0
  /-- the worker node's off-chain balance from this job -/
  workerBal : Nat := 0
  /-- a `verify_tiebreak` child exists (queued or done) -/
  tiebreakCreated : Bool := false
  /-- that child is still waiting to be claimed -/
  tiebreakOpen : Bool := false
  /-- off-chain checker pay, in order: (node, credits) -/
  checkerPays : List (String × Nat) := []

inductive Ev where
  | first (checker : String) (v : Verdict)
  | second (checker : String) (v : Verdict)
  | tiebreak (checker : String) (v : Verdict)
  deriving Repr

def payCheck (s : St) (c : String) (v : Verdict) : St :=
  { s with checkerPays := s.checkerPays ++ [(c, checkerPay v)] }

/-- `queueTiebreak`: a no-op when any tiebreak child already exists
    (written without a branch: an existing child leaves `tiebreakOpen` as is). -/
def queueTiebreak (s : St) : St :=
  { s with tiebreakOpen := s.tiebreakOpen || !s.tiebreakCreated, tiebreakCreated := true }

/-- `payWorker` (settle is idempotent per key; the model never calls it twice
    with credit still awarded). -/
def payWorker (j : Job) (s : St) : St :=
  { s with credited := j.award, workerBal := s.workerBal + j.award }

/-- `clawbackWorker`: Math.max(0, bal - awarded) is Nat truncated subtraction;
    with nothing awarded it changes nothing. -/
def clawback (s : St) : St :=
  { s with workerBal := s.workerBal - s.credited, credited := 0 }

/-- `parent.credits_awarded || row.mesh_credits || 0` -/
def releaseCredits (s : St) : Nat := if s.credited ≠ 0 then s.credited else s.meshCredits

/-- The status `releasePending` leaves, in its check order. -/
def releaseStatus (j : Job) (s : St) (c : String) : Status :=
  if !j.digestsOk then .heldIndistinctDigests
  else if !independent j.worker s.v1 c then .skippedVerifierIndependence
  else if !splitsClean (releaseCredits s * UNITS_PER_CREDIT) then .skippedIndivisible
  else .pending

/-- `releasePending(store, ctx, parent, row, c)`: v2 and its decision are set
    first; mesh_credits only after the independence check; amount only when
    the row becomes pending. -/
def release (j : Job) (s : St) (c : String) : St :=
  { s with
    v2 := c, d2 := some .agree,
    meshCredits := if j.digestsOk && independent j.worker s.v1 c then releaseCredits s else s.meshCredits,
    amount := if releaseStatus j s c = .pending then releaseCredits s * UNITS_PER_CREDIT else s.amount,
    status := releaseStatus j s c }

theorem releaseStatus_pending (j : Job) (s : St) (c : String) :
    releaseStatus j s c = .pending ↔
      j.digestsOk = true ∧ independent j.worker s.v1 c = true ∧
      splitsClean (releaseCredits s * UNITS_PER_CREDIT) = true := by
  unfold releaseStatus
  by_cases h1 : j.digestsOk = true <;> by_cases h2 : independent j.worker s.v1 c = true <;>
    by_cases h3 : splitsClean (releaseCredits s * UNITS_PER_CREDIT) = true <;> simp_all

def step (j : Job) (s : St) : Ev → St
  | .first c v =>
    if s.firstDone || s.status != .none then s else
    let s := payCheck { s with firstDone := true } c v
    match v with
    | .agree =>
      if c = j.worker then s else
      let s := payWorker j s
      { s with status := .awaitingSecondVerifier, v1 := c, d1 := some .agree, meshCredits := j.award }
    | .disagreeDeterministic =>
      queueTiebreak { s with status := .heldForTiebreaker, v1 := c, d1 := some v,
                             amount := 0, meshCredits := 0 }
    | _ => s
  | .second c v =>
    if s.status != .awaitingSecondVerifier then s else
    let s := payCheck s c v
    match v with
    | .agree => release j s c
    | .disagreeDeterministic =>
      queueTiebreak { s with v2 := c, d2 := some v, status := .heldForTiebreaker }
    | _ => { s with status := .verifierDisagreement }
  | .tiebreak c v =>
    if !s.tiebreakOpen || s.status != .heldForTiebreaker then s else
    let s := payCheck { s with tiebreakOpen := false } c v
    match v with
    | .agree =>
      if s.d1 != some .agree then
        if c ≠ j.worker then
          let s := payWorker j s
          { s with v1 := c, d1 := some .agree, v2 := "", d2 := none, meshCredits := j.award,
                   status := .awaitingSecondVerifier }
        else { s with status := .heldDisagreement }
      else release j s c
    | _ => { clawback s with status := .heldDisagreement }

def run (j : Job) (evs : List Ev) : St := evs.foldl (step j) {}

inductive Reachable (j : Job) : St → Prop where
  | init : Reachable j {}
  | step (s : St) (e : Ev) : Reachable j s → Reachable j (step j s e)

theorem run_reachable (j : Job) (evs : List Ev) : Reachable j (run j evs) := by
  unfold run
  suffices ∀ s, Reachable j s → Reachable j (evs.foldl (step j) s) from this _ .init
  induction evs with
  | nil => intro s h; exact h
  | cons e rest ih => intro s h; exact ih _ (.step s e h)

/-! ## Release lemma -/

theorem release_pending (j : Job) (s : St) (c : String) (h : (release j s c).status = .pending) :
    let r := release j s c
    r.v1 = s.v1 ∧ r.v2 = c ∧ r.d1 = s.d1 ∧ r.d2 = some .agree ∧ j.digestsOk = true ∧
    independent j.worker r.v1 r.v2 = true ∧
    r.amount = r.meshCredits * UNITS_PER_CREDIT ∧ splitsClean r.amount = true := by
  simp only [release] at h ⊢
  have ⟨h1, h2, h3⟩ := (releaseStatus_pending j s c).mp h
  simp [h, h1, h2, h3]

/-! ## Pending is sound: the whole-trace invariant -/

/-- The settlement invariant, proved for every reachable state. -/
def Inv (j : Job) (s : St) : Prop :=
  (s.status = .awaitingSecondVerifier → s.d1 = some .agree) ∧
  (s.status = .pending →
    s.d1 = some .agree ∧ s.d2 = some .agree ∧ independent j.worker s.v1 s.v2 = true ∧
    j.digestsOk = true ∧ s.amount = s.meshCredits * UNITS_PER_CREDIT ∧
    splitsClean s.amount = true)

theorem release_not_awaiting (j : Job) (s : St) (c : String) :
    (release j s c).status ≠ .awaitingSecondVerifier := by
  simp only [release, releaseStatus]
  repeat' split
  all_goals simp

/-- The pending half of `Inv` after a release, given the first decision agreed. -/
theorem release_inv (j : Job) (s : St) (c : String) (hd : s.d1 = some .agree) :
    Inv j (release j s c) := by
  refine ⟨fun h => absurd h (release_not_awaiting j s c), fun hs => ?_⟩
  obtain ⟨h1, h2, h3, h4, h5, h6, h7, h8⟩ := release_pending j s c hs
  exact ⟨by rw [h3]; exact hd, h4, h6, h5, h7, h8⟩

theorem inv_step (j : Job) (s : St) (e : Ev) (h : Inv j s) : Inv j (step j s e) := by
  obtain ⟨hA, hP⟩ := h
  cases e with
  | first c v =>
    by_cases g : (s.firstDone || s.status != .none) = true
    · simp only [step, g, ite_true]; exact ⟨hA, hP⟩
    · have hn : s.status = .none := by simp_all
      cases v <;> by_cases hw : c = j.worker <;>
        simp_all [Inv, step, payCheck, payWorker, queueTiebreak]
  | second c v =>
    by_cases g : (s.status != .awaitingSecondVerifier) = true
    · simp only [step, g, ite_true]; exact ⟨hA, hP⟩
    · have ha : s.status = .awaitingSecondVerifier := by simp_all
      have hd1 := hA ha
      cases v
      · simp_all [Inv, step, payCheck]
      · simp_all [Inv, step, payCheck]
      · simp only [step, g]
        exact release_inv j _ c (by simp [payCheck, hd1])
      · simp_all [Inv, step, payCheck, queueTiebreak]
  | tiebreak c v =>
    by_cases g : (!s.tiebreakOpen || s.status != .heldForTiebreaker) = true
    · simp only [step, g, ite_true]; exact ⟨hA, hP⟩
    · have hh : s.status = .heldForTiebreaker := by simp_all
      cases v
      · simp_all [Inv, step, payCheck, clawback]
      · simp_all [Inv, step, payCheck, clawback]
      · by_cases hd : s.d1 = some .agree
        · simp only [step, g, ite_false, payCheck, hd, bne_self_eq_false, Bool.false_eq_true]
          exact release_inv j _ c rfl
        · by_cases hw : c = j.worker <;> simp_all [Inv, step, payCheck, payWorker]
      · simp_all [Inv, step, payCheck, clawback]

theorem inv_reachable (j : Job) (s : St) (h : Reachable j s) : Inv j s := by
  induction h with
  | init => exact ⟨by simp, by simp⟩
  | step s e _ ih => exact inv_step j s e ih

/-- Settlement soundness: a row reaches `pending` (the only status the box
    settler mints, protocol.mjs:1926) only with two agreeing verifiers that are
    distinct from each other and from the worker, pairwise distinct digests,
    and an exact 9000/500/500 split of the queued amount. Holds on every trace. -/
theorem pending_sound (j : Job) (s : St) (h : Reachable j s) (hp : s.status = .pending) :
    s.d1 = some .agree ∧ s.d2 = some .agree ∧ s.v1 ≠ j.worker ∧ s.v2 ≠ j.worker ∧
    s.v1 ≠ s.v2 ∧ j.digestsOk = true ∧ s.amount % 20 = 0 ∧ 0 < s.amount := by
  obtain ⟨d1, d2, hi, hd, _, hc⟩ := (inv_reachable j s h).2 hp
  obtain ⟨hw1, hw2, h12, _, _⟩ := independent_sound _ _ _ hi
  obtain ⟨hpos, hdiv⟩ := (splitsClean_iff _).mp hc
  exact ⟨d1, d2, Ne.symm hw1, Ne.symm hw2, h12, hd, hdiv, hpos⟩

/-! ## (c) Disagreement holds the worker -/

/-- A deterministic disagree never queues a mint, on any check. -/
theorem disagree_never_pending (j : Job) (s : St) (c : String) (e : Ev)
    (he : e = .first c .disagreeDeterministic ∨ e = .second c .disagreeDeterministic ∨
          e = .tiebreak c .disagreeDeterministic)
    (hs : s.status ≠ .pending) : (step j s e).status ≠ .pending := by
  rcases he with rfl | rfl | rfl <;> simp only [step] <;> split <;>
    simp_all [payCheck, queueTiebreak]

/-- First check disagrees: the worker is never paid, nothing is queued for the
    chain, the row is held, and one tiebreaker is queued. -/
theorem first_disagree_holds (j : Job) (c : String) :
    let s := step j {} (.first c .disagreeDeterministic)
    s.status = .heldForTiebreaker ∧ s.workerBal = 0 ∧ s.credited = 0 ∧ s.amount = 0 ∧
    s.tiebreakOpen = true := by
  simp [step, payCheck, queueTiebreak]

/-- A tiebreaker disagree claws the worker's off-chain award back to zero and
    closes the row as `held_disagreement`. -/
theorem tiebreak_disagree_clawback (j : Job) (s : St) (c : String)
    (ho : s.tiebreakOpen = true) (hh : s.status = .heldForTiebreaker) :
    let r := step j s (.tiebreak c .disagreeDeterministic)
    r.status = .heldDisagreement ∧ r.credited = 0 ∧ r.workerBal = s.workerBal - s.credited ∧
    r.amount = s.amount := by
  by_cases hc : s.credited = 0 <;> simp [step, ho, hh, payCheck, clawback, hc]

/-- FINDING F1: a second-check disagree holds the chain mint but leaves the
    worker's off-chain award in place until a tiebreaker disagrees. -/
theorem second_disagree_keeps_offchain_award (j : Job) (b c : String) (hb : b ≠ j.worker) :
    let s := run j [.first b .agree, .second c .disagreeDeterministic]
    s.status = .heldForTiebreaker ∧ s.workerBal = j.award ∧ s.credited = j.award ∧
    s.amount = 0 := by
  simp [run, step, payCheck, payWorker, queueTiebreak, hb]

/-- FINDING F2: `queueTiebreak` allows one tiebreak child per parent. After the
    path first-disagree, tiebreak-agree, second-disagree, the row is
    `held_for_tiebreaker` with no tiebreaker queued, and no event can move it:
    the job is stuck, and the worker keeps the award paid at the tiebreak. -/
theorem single_tiebreak_stuck (j : Job) (b c d : String) (hc : c ≠ j.worker) :
    let s := run j [.first b .disagreeDeterministic, .tiebreak c .agree,
                    .second d .disagreeDeterministic]
    s.status = .heldForTiebreaker ∧ s.tiebreakOpen = false ∧ s.workerBal = j.award ∧
    ∀ e, (step j s e).status = s.status := by
  refine ⟨?_, ?_, ?_, ?_⟩
  · simp [run, step, payCheck, payWorker, queueTiebreak, hc]
  · simp [run, step, payCheck, payWorker, queueTiebreak, hc]
  · simp [run, step, payCheck, payWorker, queueTiebreak, hc]
  · intro e
    cases e <;> simp [run, step, payCheck, payWorker, queueTiebreak, hc]

end Settlement

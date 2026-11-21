/-
  The verification and settlement-row state machine of one parent job,
  after the F1 and F2 fixes.

  Faithful to supabase/functions/gpu-mesh/protocol.mjs (line numbers as of this branch):
  - :1437 `finishVerification` (first check), :1091 `openChainSettlement`,
    :1219 `markHeld` (insert path)
  - :1398 `finishSecondVerification` (`verify2`)
  - :1342 `finishTiebreak` (`verify_tiebreak`)
  - :1263 `queueTiebreak` (at most one tiebreak child per parent)
  - :1273 `releasePending`, :1278 `releaseChecks`
  - :1176 `payWorker`, :1193 `clawbackWorker`, :1124 `payChecker`

  The rule (PR #61 intent, made total):
  - any disagreement holds the worker payout on and off chain: the off-chain
    award is clawed back whenever the mint is held or refused (F1);
  - a job is decided by at most three checks, by majority: two agrees settle,
    two disagrees close the job as `held_disagreement` (F2).

  Modelling choices (each is a stated assumption, see README):
  - one parent job; its own output is non-empty and its model digest is pinned;
  - `award` is the `payWorker` amount, max(1, completion_tokens) * weight;
  - `digestsOk` is `settlementBindingHold(...) == ""` for the parent;
  - `payouts` are the nodes' payout addresses, already lower-cased;
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
  | heldIndistinctDigests
  | skippedVerifierIndependence
  | skippedSharedPayout
  | skippedIndivisible
  | pending
  deriving DecidableEq, Repr

def Status.tag : Status → String
  | .none => "none"
  | .awaitingSecondVerifier => "awaiting_second_verifier"
  | .heldForTiebreaker => "held_for_tiebreaker"
  | .heldDisagreement => "held_disagreement"
  | .heldIndistinctDigests => "held_indistinct_digests"
  | .skippedVerifierIndependence => "skipped_verifier_independence"
  | .skippedSharedPayout => "skipped_shared_payout"
  | .skippedIndivisible => "skipped_indivisible"
  | .pending => "pending"

structure Job where
  worker : String
  award : Nat
  digestsOk : Bool
  payouts : List (String × String) := []

def Job.payout (j : Job) (id : String) : String := (j.payouts.lookup id).getD ""

/-- `distinctPayouts` (protocol.mjs:287): the non-empty addresses are pairwise distinct. -/
def distinctPayouts (xs : List String) : Bool :=
  let ys := xs.filter (· != "")
  ys.eraseDups.length == ys.length

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
  /-- a `verify2` check is queued and not yet done -/
  verify2Open : Bool := false
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

/-- `queueTiebreak`: a no-op when any tiebreak child already exists. -/
def queueTiebreak (s : St) : St :=
  { s with tiebreakOpen := s.tiebreakOpen || !s.tiebreakCreated, tiebreakCreated := true }

/-- `payWorker` -/
def payWorker (j : Job) (s : St) : St :=
  { s with credited := j.award, workerBal := s.workerBal + j.award }

/-- `clawbackWorker`: Math.max(0, bal - awarded) is Nat truncated subtraction. -/
def clawback (s : St) : St :=
  { s with workerBal := s.workerBal - s.credited, credited := 0 }

/-- `parent.credits_awarded || row.mesh_credits || 0` -/
def releaseCredits (s : St) : Nat := if s.credited ≠ 0 then s.credited else s.meshCredits

def payoutsOk (j : Job) (s : St) (c : String) : Bool :=
  distinctPayouts [j.payout j.worker, j.payout s.v1, j.payout c]

/-- The status `releaseChecks` leaves, in its check order. -/
def releaseStatus (j : Job) (s : St) (c : String) : Status :=
  if !j.digestsOk then .heldIndistinctDigests
  else if !independent j.worker s.v1 c then .skippedVerifierIndependence
  else if !payoutsOk j s c then .skippedSharedPayout
  else if !splitsClean (releaseCredits s * UNITS_PER_CREDIT) then .skippedIndivisible
  else .pending

/-- `releaseChecks`: v2 and its decision are set first; mesh_credits only
    after the independence and payout checks; amount only when pending. -/
def release (j : Job) (s : St) (c : String) : St :=
  { s with
    v2 := c, d2 := some .agree,
    meshCredits := if j.digestsOk && independent j.worker s.v1 c && payoutsOk j s c
      then releaseCredits s else s.meshCredits,
    amount := if releaseStatus j s c = .pending then releaseCredits s * UNITS_PER_CREDIT else s.amount,
    status := releaseStatus j s c }

/-- `releasePending`: a refused release claws the worker award back (F1). -/
def settleRelease (j : Job) (s : St) (c : String) : St :=
  let r := release j s c
  { r with
    workerBal := if r.status = .pending then r.workerBal else r.workerBal - r.credited,
    credited := if r.status = .pending then r.credited else 0 }

def step (j : Job) (s : St) : Ev → St
  | .first c v =>
    if s.firstDone || s.status != .none then s else
    let s := payCheck { s with firstDone := true } c v
    match v with
    | .agree =>
      if c = j.worker then s else
      let s := payWorker j s
      { s with status := .awaitingSecondVerifier, v1 := c, d1 := some .agree,
               meshCredits := j.award, verify2Open := true }
    | .disagreeDeterministic =>
      queueTiebreak { s with status := .heldForTiebreaker, v1 := c, d1 := some v,
                             amount := 0, meshCredits := 0 }
    | _ => s
  | .second c v =>
    if !s.verify2Open || s.status != .awaitingSecondVerifier then s else
    let s := payCheck { s with verify2Open := false } c v
    match v with
    | .agree => settleRelease j s c
    | _ =>
      let s := clawback { s with v2 := c, d2 := some v }
      if s.tiebreakCreated then { s with status := .heldDisagreement }
      else queueTiebreak { s with status := .heldForTiebreaker }
  | .tiebreak c v =>
    if !s.tiebreakOpen || s.status != .heldForTiebreaker then s else
    let s := payCheck { s with tiebreakOpen := false } c v
    match v with
    | .agree =>
      if c = j.worker then { clawback s with status := .heldDisagreement }
      else if s.d1 != some .agree then
        let s := payWorker j s
        { s with v1 := c, d1 := some .agree, v2 := "", d2 := none, meshCredits := j.award,
                 status := .awaitingSecondVerifier, verify2Open := true }
      else settleRelease j (payWorker j s) c
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

/-! ## Release lemmas -/

theorem releaseStatus_pending (j : Job) (s : St) (c : String) :
    releaseStatus j s c = .pending ↔
      j.digestsOk = true ∧ independent j.worker s.v1 c = true ∧ payoutsOk j s c = true ∧
      splitsClean (releaseCredits s * UNITS_PER_CREDIT) = true := by
  unfold releaseStatus
  by_cases h1 : j.digestsOk = true <;> by_cases h2 : independent j.worker s.v1 c = true <;>
    by_cases h4 : payoutsOk j s c = true <;>
    by_cases h3 : splitsClean (releaseCredits s * UNITS_PER_CREDIT) = true <;> simp_all

theorem releaseStatus_ne (j : Job) (s : St) (c : String) :
    releaseStatus j s c ≠ .awaitingSecondVerifier ∧ releaseStatus j s c ≠ .heldForTiebreaker ∧
    releaseStatus j s c ≠ .none := by
  unfold releaseStatus
  repeat' split
  all_goals simp

theorem release_pending (j : Job) (s : St) (c : String) (h : (release j s c).status = .pending) :
    let r := release j s c
    r.v1 = s.v1 ∧ r.v2 = c ∧ r.d1 = s.d1 ∧ r.d2 = some .agree ∧ j.digestsOk = true ∧
    independent j.worker r.v1 r.v2 = true ∧ payoutsOk j s c = true ∧
    r.amount = r.meshCredits * UNITS_PER_CREDIT ∧ splitsClean r.amount = true := by
  simp only [release] at h ⊢
  have ⟨h1, h2, h4, h3⟩ := (releaseStatus_pending j s c).mp h
  simp [h, h1, h2, h3, h4]

/-! ## The invariant, proved for every reachable state -/

/-- Paid statuses: the worker holds its award exactly in these. -/
def paidStatus (st : Status) : Bool := st == .awaitingSecondVerifier || st == .pending

structure Inv (j : Job) (s : St) : Prop where
  awaiting_agree : s.status = .awaitingSecondVerifier → s.d1 = some .agree
  pending_ok : s.status = .pending →
    s.d1 = some .agree ∧ s.d2 = some .agree ∧ independent j.worker s.v1 s.v2 = true ∧
    j.digestsOk = true ∧ distinctPayouts [j.payout j.worker, j.payout s.v1, j.payout s.v2] = true ∧
    s.amount = s.meshCredits * UNITS_PER_CREDIT ∧ splitsClean s.amount = true
  /-- F1: the worker's off-chain award follows the chain status exactly. -/
  bal_eq : s.workerBal = s.credited
  credited_eq : s.credited = if paidStatus s.status then j.award else 0
  /-- F2: a held or awaiting row always has its next check queued. -/
  awaiting_open : s.status = .awaitingSecondVerifier → s.verify2Open = true
  held_open : s.status = .heldForTiebreaker → s.tiebreakOpen = true
  v2_status : s.verify2Open = true → s.status = .awaitingSecondVerifier
  tb_status : s.tiebreakOpen = true → s.status = .heldForTiebreaker ∧ s.tiebreakCreated = true
  fresh : s.firstDone = false → s = {}

theorem settleRelease_inv (j : Job) (s : St) (c : String) (hd : s.d1 = some .agree)
    (hbal : s.workerBal = s.credited) (hcr : s.credited = j.award)
    (hv : s.verify2Open = false) (ht : s.tiebreakOpen = false) (hf : s.firstDone = true) :
    Inv j (settleRelease j s c) := by
  have hne := releaseStatus_ne j s c
  constructor
  · intro h; simp [settleRelease, release] at h; exact absurd h hne.1
  · intro hs
    simp only [settleRelease] at hs
    have := release_pending j s c hs
    obtain ⟨h1, h2, h3, h4, h5, h6, h7, h8, h9⟩ := this
    simp only [settleRelease]
    refine ⟨by rw [h3]; exact hd, h4, h6, h5, ?_, h8, h9⟩
    simpa [payoutsOk, h1, h2] using h7
  · simp only [settleRelease, release]
    by_cases hp : releaseStatus j s c = .pending <;> simp_all
  · simp only [settleRelease, release, paidStatus]
    by_cases hp : releaseStatus j s c = .pending <;> simp_all
  · intro h; simp [settleRelease, release] at h; exact absurd h hne.1
  · intro h; simp [settleRelease, release] at h; exact absurd h hne.2.1
  · intro h; simp_all [settleRelease, release]
  · intro h; simp_all [settleRelease, release]
  · intro h; simp_all [settleRelease, release]

theorem inv_init (j : Job) : Inv j {} := by
  constructor <;> simp [paidStatus]

theorem inv_step (j : Job) (s : St) (e : Ev) (h : Inv j s) : Inv j (step j s e) := by
  obtain ⟨hA, hP, hB, hC, hAO, hHO, hV2, hTB, hF⟩ := h
  have h0 : Inv j s := ⟨hA, hP, hB, hC, hAO, hHO, hV2, hTB, hF⟩
  cases e with
  | first c v =>
    by_cases g : (s.firstDone || s.status != .none) = true
    · simp only [step, g, ite_true]; exact h0
    · have hfd : s.firstDone = false := by simp_all
      have hs := hF hfd
      subst hs
      cases v <;> (try by_cases hw : c = j.worker) <;>
        (constructor <;> simp_all [step, payCheck, payWorker, queueTiebreak, paidStatus])
  | second c v =>
    by_cases g : (!s.verify2Open || s.status != .awaitingSecondVerifier) = true
    · simp only [step, g, ite_true]; exact h0
    · have ha : s.status = .awaitingSecondVerifier := by simp_all
      have hv : s.verify2Open = true := by simp_all
      have hd1 := hA ha
      have htb : s.tiebreakOpen = false := by
        cases h : s.tiebreakOpen
        · rfl
        · have := (hTB h).1; simp_all
      have hfd : s.firstDone = true := by
        cases h : s.firstDone
        · have := hF h; simp_all
        · rfl
      have hcr : s.credited = j.award := by simp_all [paidStatus]
      cases v
      case agree =>
        simp only [step, g]
        exact settleRelease_inv j _ c (by simp [payCheck, hd1]) (by simp [payCheck, hB])
          (by simp [payCheck, hcr]) (by simp [payCheck]) (by simp [payCheck, htb])
          (by simp [payCheck, hfd])
      all_goals
        by_cases hc : s.tiebreakCreated = true <;>
          (constructor <;> simp_all [step, payCheck, clawback, queueTiebreak, paidStatus])
  | tiebreak c v =>
    by_cases g : (!s.tiebreakOpen || s.status != .heldForTiebreaker) = true
    · simp only [step, g, ite_true]; exact h0
    · have hh : s.status = .heldForTiebreaker := by simp_all
      have ho : s.tiebreakOpen = true := by simp_all
      have hv : s.verify2Open = false := by
        cases h : s.verify2Open
        · rfl
        · have := hV2 h; simp_all
      have hfd : s.firstDone = true := by
        cases h : s.firstDone
        · have := hF h; simp_all
        · rfl
      have hcr : s.credited = 0 := by simp_all [paidStatus]
      cases v
      case agree =>
        by_cases hw : c = j.worker
        · constructor <;> simp_all [step, payCheck, clawback, paidStatus]
        · by_cases hd : s.d1 = some .agree
          · simp only [step, g, hw, ite_false, payCheck, hd, bne_self_eq_false, Bool.false_eq_true]
            exact settleRelease_inv j _ c rfl (by simp [payWorker, hB, hcr]) (by simp [payWorker])
              (by simp [payWorker, hv]) (by simp [payWorker]) (by simp [payWorker, hfd])
          · constructor <;> simp_all [step, payCheck, payWorker, paidStatus]
      all_goals (constructor <;> simp_all [step, payCheck, clawback, paidStatus])

theorem inv_reachable (j : Job) (s : St) (h : Reachable j s) : Inv j s := by
  induction h with
  | init => exact inv_init j
  | step s e _ ih => exact inv_step j s e ih

/-- Settlement soundness: a row reaches `pending` (the only status the box
    settler mints) only with two agreeing verifiers that are distinct from
    each other and from the worker, distinct payout addresses, pairwise
    distinct digests, and an exact 9000/500/500 split. Holds on every trace. -/
theorem pending_sound (j : Job) (s : St) (h : Reachable j s) (hp : s.status = .pending) :
    s.d1 = some .agree ∧ s.d2 = some .agree ∧ s.v1 ≠ j.worker ∧ s.v2 ≠ j.worker ∧
    s.v1 ≠ s.v2 ∧ j.digestsOk = true ∧
    distinctPayouts [j.payout j.worker, j.payout s.v1, j.payout s.v2] = true ∧
    s.amount % 20 = 0 ∧ 0 < s.amount := by
  obtain ⟨d1, d2, hi, hd, hpay, _, hc⟩ := (inv_reachable j s h).pending_ok hp
  obtain ⟨hw1, hw2, h12, _, _⟩ := independent_sound _ _ _ hi
  obtain ⟨hpos, hdiv⟩ := (splitsClean_iff _).mp hc
  exact ⟨d1, d2, Ne.symm hw1, Ne.symm hw2, h12, hd, hpay, hdiv, hpos⟩

/-! ## F1 fixed: a held or refused mint never leaves the worker paid -/

/-- The worker's off-chain balance from a job is its award exactly when the
    job is awaiting its second check or pending, and 0 otherwise. -/
theorem worker_paid_iff (j : Job) (s : St) (h : Reachable j s) :
    s.workerBal = if paidStatus s.status then j.award else 0 := by
  have hi := inv_reachable j s h
  rw [hi.bal_eq, hi.credited_eq]

/-- F1 fixed: while a row waits for a tiebreaker the worker holds nothing. -/
theorem held_worker_unpaid (j : Job) (s : St) (h : Reachable j s)
    (hh : s.status = .heldForTiebreaker) : s.workerBal = 0 := by
  rw [worker_paid_iff j s h, hh]; rfl

/-- F1 fixed, concretely: first agree, second disagree holds the award. -/
theorem second_disagree_holds_award (j : Job) (b c : String) (hb : b ≠ j.worker) :
    let s := run j [.first b .agree, .second c .disagreeDeterministic]
    s.status = .heldForTiebreaker ∧ s.workerBal = 0 ∧ s.credited = 0 ∧ s.amount = 0 ∧
    s.tiebreakOpen = true := by
  simp [run, step, payCheck, payWorker, clawback, queueTiebreak, hb]

/-- A deterministic disagree never makes a row `pending`. -/
theorem disagree_never_pending (j : Job) (s : St) (c : String) (e : Ev)
    (he : e = .first c .disagreeDeterministic ∨ e = .second c .disagreeDeterministic ∨
          e = .tiebreak c .disagreeDeterministic)
    (hs : s.status ≠ .pending) : (step j s e).status ≠ .pending := by
  rcases he with rfl | rfl | rfl <;> simp only [step] <;> split <;>
    simp_all [payCheck, queueTiebreak, clawback] <;> split <;> simp

/-- First check disagrees: the worker is never paid, nothing is queued for the
    chain, the row is held, and one tiebreaker is queued. -/
theorem first_disagree_holds (j : Job) (c : String) :
    let s := step j {} (.first c .disagreeDeterministic)
    s.status = .heldForTiebreaker ∧ s.workerBal = 0 ∧ s.credited = 0 ∧ s.amount = 0 ∧
    s.tiebreakOpen = true := by
  simp [step, payCheck, queueTiebreak]

/-- A tiebreaker disagree closes the row as `held_disagreement` with the
    worker award at 0 and nothing queued for the chain. -/
theorem tiebreak_disagree_closes (j : Job) (s : St) (c : String) (hr : Reachable j s)
    (ho : s.tiebreakOpen = true) (hh : s.status = .heldForTiebreaker) :
    let r := step j s (.tiebreak c .disagreeDeterministic)
    r.status = .heldDisagreement ∧ r.workerBal = 0 ∧ r.credited = 0 ∧ r.amount = s.amount := by
  have hi := inv_reachable j s hr
  have hb := hi.bal_eq
  have hc := hi.credited_eq
  simp [step, ho, hh, payCheck, clawback, paidStatus] at hc ⊢
  omega

/-! ## F2 fixed: every job reaches a terminal state within three checks -/

/-- A check that is queued now. Any other event is a no-op (`step_disabled`). -/
def enabled (s : St) : Ev → Bool
  | .first _ _ => !s.firstDone && s.status == .none
  | .second _ _ => s.verify2Open && s.status == .awaitingSecondVerifier
  | .tiebreak _ _ => s.tiebreakOpen && s.status == .heldForTiebreaker

/-- Checks still possible: 3 before the first, then at most 2, then 1. -/
def rem (s : St) : Nat :=
  if !s.firstDone then 3
  else if s.verify2Open && s.status == .awaitingSecondVerifier then
    (if s.tiebreakCreated then 1 else 2)
  else if s.tiebreakOpen && s.status == .heldForTiebreaker then
    (if s.d1 == some .agree then 1 else 2)
  else 0

theorem step_disabled (j : Job) (s : St) (e : Ev) (h : enabled s e = false) : step j s e = s := by
  cases e <;> simp_all [enabled, step] <;> intro h' <;> simp_all

/-- Each queued check strictly lowers `rem`. -/
theorem rem_decreases (j : Job) (s : St) (e : Ev) (hr : Reachable j s) (he : enabled s e = true) :
    rem (step j s e) < rem s := by
  have hi := inv_reachable j s hr
  obtain ⟨hA, _, hB, hC, hAO, hHO, hV2, hTB, hF⟩ := hi
  cases e with
  | first c v =>
    have hfd : s.firstDone = false := by simp_all [enabled]
    have hs := hF hfd
    subst hs
    cases v <;> (try by_cases hw : c = j.worker) <;>
      simp_all [step, rem, payCheck, payWorker, queueTiebreak]
  | second c v =>
    have ha : s.status = .awaitingSecondVerifier := by simp_all [enabled]
    have hv : s.verify2Open = true := by simp_all [enabled]
    have hd1 := hA ha
    have htb : s.tiebreakOpen = false := by
      cases h : s.tiebreakOpen
      · rfl
      · have := (hTB h).1; simp_all
    have hfd : s.firstDone = true := by
      cases h : s.firstDone
      · have := hF h; simp_all
      · rfl
    have hne := releaseStatus_ne j { s with verify2Open := false, checkerPays := s.checkerPays ++ [(c, checkerPay v)] } c
    cases v <;> by_cases hc : s.tiebreakCreated = true <;>
      simp_all [step, rem, payCheck, settleRelease, release, clawback, queueTiebreak]
  | tiebreak c v =>
    have hh : s.status = .heldForTiebreaker := by simp_all [enabled]
    have ho : s.tiebreakOpen = true := by simp_all [enabled]
    have hv : s.verify2Open = false := by
      cases h : s.verify2Open
      · rfl
      · have := hV2 h; simp_all
    have hfd : s.firstDone = true := by
      cases h : s.firstDone
      · have := hF h; simp_all
      · rfl
    have hc := (hTB ho).2
    have hrem : rem s = if s.d1 = some .agree then 1 else 2 := by
      simp [rem, hfd, hv, ho, hh]
    rw [hrem]
    by_cases hva : v = .agree
    · subst hva
      by_cases hw : c = j.worker
      · have : rem (step j s (.tiebreak c .agree)) = 0 := by
          simp [step, rem, payCheck, clawback, hw, ho, hh, hfd, hv]
        rw [this]; split <;> simp
      · by_cases hd : s.d1 = some .agree
        · let s1 := payWorker j { s with tiebreakOpen := false, checkerPays := s.checkerPays ++ [(c, checkerPay .agree)] }
          have hne := releaseStatus_ne j s1 c
          have : rem (step j s (.tiebreak c .agree)) = 0 := by
            simp_all [s1, step, rem, payCheck, payWorker, settleRelease, release]
          rw [this]; simp [hd]
        · have : rem (step j s (.tiebreak c .agree)) = 1 := by
            simp_all [step, rem, payCheck, payWorker]
          rw [this]; simp [hd]
    · have : rem (step j s (.tiebreak c v)) = 0 := by
        cases v <;> simp_all [step, rem, payCheck, clawback]
      rw [this]; split <;> simp

/-- No stuck jobs: a state with nothing queued has `rem = 0`, and it is
    terminal: either `pending` with the worker paid, or a refusal with the
    worker award at 0. `awaiting_second_verifier` and `held_for_tiebreaker`
    are never terminal. -/
theorem no_stuck (j : Job) (s : St) (hr : Reachable j s) (hn : ∀ e, enabled s e = false) :
    rem s = 0 ∧ s.status ≠ .awaitingSecondVerifier ∧ s.status ≠ .heldForTiebreaker ∧
    (s.status = .pending ∧ s.workerBal = j.award ∨ s.status ≠ .pending ∧ s.workerBal = 0) := by
  have hi := inv_reachable j s hr
  have h1 := hn (.first "" .agree)
  have h2 := hn (.second "" .agree)
  have h3 := hn (.tiebreak "" .agree)
  simp only [enabled, Bool.and_eq_false_iff, Bool.not_eq_false', beq_eq_false_iff_ne, ne_eq] at h1 h2 h3
  have hfd : s.firstDone = true := by
    rcases h1 with h | h
    · exact h
    · cases hf : s.firstDone
      · have := hi.fresh hf; simp_all
      · rfl
  have hna : s.status ≠ .awaitingSecondVerifier := by
    intro ha; have := hi.awaiting_open ha; simp_all
  have hnh : s.status ≠ .heldForTiebreaker := by
    intro ha; have := hi.held_open ha; simp_all
  refine ⟨?_, hna, hnh, ?_⟩
  · simp only [rem, hfd]
    rcases h2 with h | h <;> rcases h3 with h' | h' <;> simp_all
  · have hw := worker_paid_iff j s hr
    by_cases hp : s.status = .pending
    · left; simp_all [paidStatus]
    · right; simp_all [paidStatus]

/-- Count the checks in a sequence that actually run (are queued when they arrive). -/
def effCount (j : Job) : St → List Ev → Nat
  | _, [] => 0
  | s, e :: es => (if enabled s e then 1 else 0) + effCount j (step j s e) es

/-- Termination over every check sequence: from any reachable state at most
    `rem` checks can run, so a job runs at most 3 checks in total. -/
theorem checks_bounded (j : Job) (evs : List Ev) (s : St) (hr : Reachable j s) :
    effCount j s evs ≤ rem s := by
  induction evs generalizing s with
  | nil => simp [effCount]
  | cons e es ih =>
    simp only [effCount]
    have := ih (step j s e) (.step s e hr)
    by_cases he : enabled s e = true
    · have := rem_decreases j s e hr he; simp [he]; omega
    · simp only [Bool.not_eq_true] at he
      rw [step_disabled j s e he] at this ⊢; simp [he]; omega

theorem at_most_three_checks (j : Job) (evs : List Ev) : effCount j {} evs ≤ 3 := by
  have := checks_bounded j evs {} .init
  simpa [rem] using this

/-- The former stuck path (first disagree, tiebreak agree, second disagree) now
    closes by majority: `held_disagreement`, worker award clawed back to 0. -/
theorem majority_disagree_closes (j : Job) (b c d : String) (hc : c ≠ j.worker) :
    let s := run j [.first b .disagreeDeterministic, .tiebreak c .agree,
                    .second d .disagreeDeterministic]
    s.status = .heldDisagreement ∧ s.workerBal = 0 ∧ s.credited = 0 ∧ ∀ e, enabled s e = false := by
  refine ⟨?_, ?_, ?_, ?_⟩
  · simp [run, step, payCheck, payWorker, queueTiebreak, clawback, hc]
  · simp [run, step, payCheck, payWorker, queueTiebreak, clawback, hc]
  · simp [run, step, payCheck, payWorker, queueTiebreak, clawback, hc]
  · intro e
    cases e <;> simp [run, step, enabled, payCheck, payWorker, queueTiebreak, clawback, hc]

end Settlement

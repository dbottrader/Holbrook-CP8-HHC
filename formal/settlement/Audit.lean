/- `lake env lean Audit.lean` prints the axioms each theorem depends on.
   check.sh fails on `sorryAx` or anything beyond Lean's three standard axioms. -/
import Settlement

#print axioms Settlement.checker_pay_agree_eq_disagree
#print axioms Settlement.checker_pay_substantive
#print axioms Settlement.checker_pay_empty
#print axioms Settlement.independent_sound
#print axioms Settlement.worker_cannot_claim_own_check
#print axioms Settlement.excluded_cannot_claim
#print axioms Settlement.Contract.mint_apply
#print axioms Settlement.Contract.settle_spec
#print axioms Settlement.Contract.dust_reverts
#print axioms Settlement.Contract.no_replay
#print axioms Settlement.Contract.same_address_all_roles
#print axioms Settlement.releaseStatus_pending
#print axioms Settlement.run_reachable
#print axioms Settlement.release_pending
#print axioms Settlement.release_not_awaiting
#print axioms Settlement.release_inv
#print axioms Settlement.inv_step
#print axioms Settlement.inv_reachable
#print axioms Settlement.pending_sound
#print axioms Settlement.disagree_never_pending
#print axioms Settlement.first_disagree_holds
#print axioms Settlement.tiebreak_disagree_clawback
#print axioms Settlement.second_disagree_keeps_offchain_award
#print axioms Settlement.single_tiebreak_stuck
#print axioms Settlement.Quest001.quest001_split
#print axioms Settlement.Quest001.ineligible_never_paid
#print axioms Settlement.Quest001.mismatch_never_paid
#print axioms Settlement.Quest001.same_sealer_never_paid
#print axioms Settlement.splitsClean_iff
#print axioms Settlement.clean_shares
#print axioms Settlement.conservation
#print axioms Settlement.refused_iff
#print axioms Settlement.mesh_contribution_clean
#print axioms Settlement.evidenceSplitOk_iff
#print axioms Settlement.example_20000
#print axioms Settlement.example_1000
#print axioms Settlement.example_4000
#print axioms Settlement.example_dust

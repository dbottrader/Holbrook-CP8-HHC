from __future__ import annotations

import hashlib

import pytest

from cp8_runtime.kernel import (
    BranchStateError,
    CP8Run,
    CP8Stage,
    ReceiptError,
    RunPhase,
    StageOrderError,
)


def h(label: str) -> str:
    return hashlib.sha256(label.encode("utf-8")).hexdigest()


def complete_branch(run: CP8Run, branch_id: str) -> None:
    branch = run.add_branch(branch_id)
    for stage in CP8Stage.ordered():
        branch.transition(stage, h(f"{branch_id}:{stage.value}"))
    branch.close()


def test_first_stage_must_be_artifact() -> None:
    run = CP8Run("run-1", h("anchor"))
    branch = run.add_branch("independent-a")

    with pytest.raises(StageOrderError):
        branch.transition(CP8Stage.MEASUREMENT, h("bad"))


def test_stage_skip_and_reorder_are_rejected() -> None:
    run = CP8Run("run-2", h("anchor"))
    branch = run.add_branch("independent-a")
    branch.transition(CP8Stage.ARTIFACT, h("artifact"))

    with pytest.raises(StageOrderError):
        branch.transition(CP8Stage.REPRESENTATION, h("skip"))

    branch.transition(CP8Stage.MEASUREMENT, h("measurement"))
    with pytest.raises(StageOrderError):
        branch.transition(CP8Stage.ARTIFACT, h("repeat"))


def test_stage_transition_requires_receipt_hash() -> None:
    run = CP8Run("run-3", h("anchor"))
    branch = run.add_branch("independent-a")

    with pytest.raises(ReceiptError):
        branch.transition(CP8Stage.ARTIFACT, "not-a-sha256")


def test_branch_cannot_close_before_revision() -> None:
    run = CP8Run("run-4", h("anchor"))
    branch = run.add_branch("independent-a")
    branch.transition(CP8Stage.ARTIFACT, h("artifact"))

    with pytest.raises(BranchStateError):
        branch.close()


def test_run_cannot_synthesize_until_all_branches_close() -> None:
    run = CP8Run("run-5", h("anchor"))
    complete_branch(run, "a")
    run.add_branch("b")

    with pytest.raises(BranchStateError):
        run.mark_stages_complete()

    with pytest.raises(BranchStateError):
        run.synthesis_inputs()


def test_synthesis_is_run_phase_not_epistemic_stage() -> None:
    assert "SYNTHESIS" not in [stage.value for stage in CP8Stage.ordered()]

    run = CP8Run("run-6", h("anchor"))
    complete_branch(run, "b")
    complete_branch(run, "a")
    run.mark_stages_complete()

    summaries = run.synthesis_inputs()
    assert [summary.branch_id for summary in summaries] == ["a", "b"]
    assert all(summary.final_receipt_hash for summary in summaries)

    run.record_synthesis(h("synthesis"))
    assert run.phase is RunPhase.SYNTHESIZED
    assert run.synthesis_hash == h("synthesis")


def test_duplicate_branch_ids_are_rejected() -> None:
    run = CP8Run("run-7", h("anchor"))
    run.add_branch("a")

    with pytest.raises(BranchStateError):
        run.add_branch("a")


def test_invalid_anchor_hash_is_rejected() -> None:
    with pytest.raises(ReceiptError):
        CP8Run("run-8", "bad-anchor")

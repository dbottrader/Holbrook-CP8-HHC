"""Branch-aware CP8 kernel.

This module deliberately excludes promotion cryptography. Promotion/authority
validation is delegated to the existing DAR-P validator so the runtime does
not invent a second signing system.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Mapping, Optional

_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


class CP8Stage(str, Enum):
    ARTIFACT = "ARTIFACT"
    MEASUREMENT = "MEASUREMENT"
    REPRESENTATION = "REPRESENTATION"
    DECODING = "DECODING"
    REPLICATION = "REPLICATION"
    INTERPRETATION = "INTERPRETATION"
    ORIGIN_HYPOTHESIS = "ORIGIN_HYPOTHESIS"
    CHALLENGE = "CHALLENGE"
    REVISION = "REVISION"

    @classmethod
    def ordered(cls) -> List["CP8Stage"]:
        return list(cls)


class RunPhase(str, Enum):
    PREREGISTERED = "PREREGISTERED"
    RUNNING = "RUNNING"
    STAGES_COMPLETE = "STAGES_COMPLETE"
    SYNTHESIZED = "SYNTHESIZED"
    CLOSED = "CLOSED"


class CP8KernelError(Exception):
    """Base error for deterministic orchestration guards."""


class StageOrderError(CP8KernelError):
    """A branch attempted to skip, repeat, or reorder a fixed CP8 stage."""


class BranchStateError(CP8KernelError):
    """A branch/run phase transition violated the CP8 lifecycle."""


class ReceiptError(CP8KernelError):
    """A stage or synthesis receipt was missing or malformed."""


def _require_sha256(value: str, label: str) -> str:
    if not _SHA256_RE.fullmatch(value):
        raise ReceiptError(f"{label} must be a lowercase 64-character SHA-256 hex digest")
    return value


@dataclass(frozen=True)
class ClosedBranchSummary:
    """Only created after a branch has completed every locked CP8 stage."""

    branch_id: str
    final_receipt_hash: str
    stage_receipts: Mapping[str, str]


@dataclass
class BranchRecord:
    """Independent stage machine for one branch.

    Branches never share stage state. Each completed stage is bound to an
    immutable receipt hash; the kernel does not accept arbitrary stage labels
    emitted by agents as proof of transition.
    """

    branch_id: str
    stages_completed: List[CP8Stage] = field(default_factory=list)
    stage_receipts: Dict[str, str] = field(default_factory=dict)
    closed: bool = False

    def transition(self, stage: CP8Stage, receipt_hash: str) -> None:
        if self.closed:
            raise BranchStateError(f"branch {self.branch_id} is already closed")

        receipt_hash = _require_sha256(receipt_hash, "stage receipt")
        expected = CP8Stage.ordered()[len(self.stages_completed)]
        if stage is not expected:
            raise StageOrderError(
                f"branch {self.branch_id} expected {expected.value}, got {stage.value}"
            )

        self.stages_completed.append(stage)
        self.stage_receipts[stage.value] = receipt_hash

    def close(self) -> ClosedBranchSummary:
        if self.closed:
            raise BranchStateError(f"branch {self.branch_id} is already closed")
        if self.stages_completed != CP8Stage.ordered():
            remaining = [
                stage.value
                for stage in CP8Stage.ordered()[len(self.stages_completed):]
            ]
            raise BranchStateError(
                f"branch {self.branch_id} cannot close; remaining stages: {remaining}"
            )

        self.closed = True
        final_receipt = self.stage_receipts[CP8Stage.REVISION.value]
        return ClosedBranchSummary(
            branch_id=self.branch_id,
            final_receipt_hash=final_receipt,
            stage_receipts=dict(self.stage_receipts),
        )


@dataclass
class CP8Run:
    """Run-level coordinator around isolated branch state machines.

    SYNTHESIS is intentionally a run phase, not a CP8 epistemic stage. This
    preserves the locked ARTIFACT->...->REVISION sequence while allowing
    synthesis only after every independent branch has closed.
    """

    run_id: str
    anchor_hash: str
    branches: Dict[str, BranchRecord] = field(default_factory=dict)
    phase: RunPhase = RunPhase.PREREGISTERED
    synthesis_hash: Optional[str] = None

    def __post_init__(self) -> None:
        _require_sha256(self.anchor_hash, "anchor hash")

    def add_branch(self, branch_id: str) -> BranchRecord:
        if not branch_id.strip():
            raise BranchStateError("branch_id must be non-empty")
        if self.phase not in {RunPhase.PREREGISTERED, RunPhase.RUNNING}:
            raise BranchStateError(
                f"cannot add branches while run phase is {self.phase.value}"
            )
        if branch_id in self.branches:
            raise BranchStateError(f"duplicate branch_id: {branch_id}")

        branch = BranchRecord(branch_id=branch_id)
        self.branches[branch_id] = branch
        self.phase = RunPhase.RUNNING
        return branch

    def branch(self, branch_id: str) -> BranchRecord:
        try:
            return self.branches[branch_id]
        except KeyError as exc:
            raise BranchStateError(f"unknown branch_id: {branch_id}") from exc

    def mark_stages_complete(self) -> None:
        if self.phase is not RunPhase.RUNNING:
            raise BranchStateError(
                f"cannot complete stages while run phase is {self.phase.value}"
            )
        if not self.branches:
            raise BranchStateError("cannot complete a run with no branches")
        open_branches = [bid for bid, branch in self.branches.items() if not branch.closed]
        if open_branches:
            raise BranchStateError(
                f"cannot complete stages; open branches: {sorted(open_branches)}"
            )
        self.phase = RunPhase.STAGES_COMPLETE

    def synthesis_inputs(self) -> List[ClosedBranchSummary]:
        if self.phase is not RunPhase.STAGES_COMPLETE:
            raise BranchStateError(
                f"synthesis requires STAGES_COMPLETE, got {self.phase.value}"
            )
        return [
            ClosedBranchSummary(
                branch_id=branch.branch_id,
                final_receipt_hash=branch.stage_receipts[CP8Stage.REVISION.value],
                stage_receipts=dict(branch.stage_receipts),
            )
            for _branch_id, branch in sorted(self.branches.items())
        ]

    def record_synthesis(self, synthesis_hash: str) -> None:
        if self.phase is not RunPhase.STAGES_COMPLETE:
            raise BranchStateError(
                f"cannot record synthesis while run phase is {self.phase.value}"
            )
        self.synthesis_hash = _require_sha256(synthesis_hash, "synthesis hash")
        self.phase = RunPhase.SYNTHESIZED

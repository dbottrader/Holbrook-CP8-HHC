"""
cathedral_os_tools — LMC Bootstrap Loader + Evidence Ladder Enforcer

Modules:
    lmc_init        — Scaffold LMC-compliant projects
    evidence_ladder — Enforce E0-E6 evidence promotion rules
    schemas         — Shared dataclasses (EvidenceObject, ClaimObject, etc.)
    cli             — Unified CLI entry point

Evidence Status : E2 (Implemented, locally tested)
Authority       : None
Prime Directive : No mechanism may silently convert uncertainty into authority.
"""

__version__ = "1.0.0"
__author__ = "Holbrook / Cathedral-OS"

from cathedral_os_tools.schemas import (
    EvidenceObject,
    ClaimObject,
    PromotionResult,
    ValidationResult,
    ContradictionReport,
)
from cathedral_os_tools.evidence_ladder import EvidenceLadder
from cathedral_os_tools.lmc_init import ProjectScaffolder

__all__ = [
    "EvidenceObject",
    "ClaimObject",
    "PromotionResult",
    "ValidationResult",
    "ContradictionReport",
    "EvidenceLadder",
    "ProjectScaffolder",
]

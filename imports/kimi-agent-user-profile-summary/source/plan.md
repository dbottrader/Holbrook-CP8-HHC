# Plan: Bootstrap Loader (lmc-init) + Evidence Ladder Enforcer

## Objective
Build two production-grade modules for the Cathedral-OS / Labyrinth ecosystem:
1. **lmc-init**: CLI bootstrap loader that scaffolds LMC-compliant projects
2. **Evidence Ladder Enforcer**: Runtime engine that enforces E0-E6 evidence promotion rules

## Stage 1 — Build lmc-init
- Scaffold directory structure (audit-package/, receipts/, chronicle/, governance/)
- Generate initial SHA256SUMS.txt with PENDING placeholders
- Create default evidence_config.json with E-ladder thresholds
- Create initial governance manifest
- CLI interface with argparse
- Full test suite

## Stage 2 — Build Evidence Ladder Enforcer
- Core enforcement engine with E0-E6 rules
- Promotion gate (evaluates if promotion is allowed/blocked/needs_review)
- Contradiction detection
- Evidence level validation
- Integration with Universal Object Model
- Full test suite

## Stage 3 — Integration & Packaging
- Combine into unified deliverable
- Integration tests
- Package as zip with SHA-256 manifest

## Skill: vibecoding-general-swarm (Python modules, CLI tools, test infrastructure)

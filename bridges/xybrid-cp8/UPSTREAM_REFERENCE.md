# Upstream Reference

Reference project: Xybrid
Repository: https://github.com/xybrid-ai/xybrid
License: Apache License 2.0

Holbrook uses Xybrid as an architectural reference for these general patterns:

- stable envelope/input abstraction
- common runtime interface over heterogeneous local model backends
- model metadata describing execution requirements
- local/offline execution
- agent/tool interoperability

This directory contains original Holbrook/CP8 integration code. It does not vendor or copy Xybrid implementation source.

Holbrook adds project-specific semantics including:

- CP8 provenance envelope
- explicit capability scopes
- SHA-256 sealing
- HOS ground-truth anchor
- output receipts
- promotion-gate compatibility

When direct Xybrid source is incorporated in the future, preserve Apache-2.0 notices and attribution for the relevant files.

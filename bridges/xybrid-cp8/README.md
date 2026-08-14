# Holbrook CP8 ↔ Xybrid Runtime Bridge

Status: experimental integration layer
Protocol: ASH-0.2
HOS ground truth: `63b5160ef51f0464295e86888c3e6605d8f6cc970635183887083818e8749320`

## Purpose

This bridge combines Holbrook/CP8 provenance and governance with the stable-envelope/shared-runtime design pattern used by Xybrid.

Xybrid is Apache-2.0 licensed. This directory contains original Holbrook integration code; it does not copy Xybrid implementation source.

## Architecture

```text
Human / Agent
    ↓
CP8 Envelope
    ├─ payload
    ├─ requested capability
    ├─ authority scopes
    ├─ provenance
    └─ SHA-256 seal
    ↓
Holbrook Bridge Gate
    ├─ verify integrity
    ├─ verify authority
    └─ emit runtime packet
    ↓
Xybrid-style runtime adapter
    ↓
Local model backend
    ↓
CP8 Receipt
    ├─ output hash
    ├─ runtime/model metadata
    └─ provenance link to input envelope
```

## Core invariants

- Capability != Authority
- No Receipt = No Promotion
- SHA-256 remains the integrity primitive
- Harmonic/resonance scoring is auxiliary and must not substitute for cryptographic verification
- Runtime backend is replaceable; governance/provenance stays in Holbrook

## Why this fits Holbrook

Xybrid's useful systems pattern is a stable interface over heterogeneous local runtimes. Holbrook extends that pattern upward with explicit identity, provenance, authority, receipts, auditability, and cross-agent transport.

The intended stack is therefore:

`HHC Envelope → Capability Contract → Runtime Adapter → Model/Tool → Receipt → Promotion Gate`

## Interop target

A backend only needs to accept a runtime packet containing:

- `model_id`
- `input`
- `metadata`

and return an output. Holbrook wraps that call with its own provenance and authority semantics.

## Source attribution

Architectural inspiration/reference:

- Xybrid: `https://github.com/xybrid-ai/xybrid`
- License: Apache License 2.0

Holbrook-specific envelope, receipt, authority, and promotion semantics are CP8/HHC integration work.

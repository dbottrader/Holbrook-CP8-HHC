# Kimi Agent Governance Runtime Initiative — Parse Report

**Source:** `Kimi_Agent_Governance Runtime Initiative.zip`  
**Source SHA-256:** `2d65a4298e1a2781bc78978e0f6a008084979bdedc41f412fa94e66cb18afeb7`  
**Zip size:** 641,417 bytes  
**Parsed files:** 140  
**Total uncompressed size:** 1,490,448 bytes  
**Generated:** 2026-07-07T13:56:55Z

---

## Executive read

This package is a usable governance-runtime corpus, not just a concept note.

It contains:

- A Python package: `project/ai_governance/`
- A FastAPI-style API/dashboard layer: `project/api/main.py` and `project/api/static/index.html`
- CLI, SDK, demo, tests, benchmarks, and documentation
- A top-level ASIN-NCEA governance bridge: `asin_governance_bridge.py`
- A hardened ASIN-NCEA module: `asin_ncea_v2.0_hardened.py`
- Release-readiness/security/contribution material
- Nested delivery zips and duplicate extracted copies

Best evidence classification:

```text
E2 for local executable runtime components that passed local tests.
E1 for public release/readiness claims and broader ecosystem integration.
Not production-certified without dependency cleanup, key handling review, CI, and external reproduction.
```

---

## File inventory summary

| Kind | Count |
|---|---:|
| cache | 6 |
| html | 3 |
| json | 5 |
| markdown | 18 |
| other | 6 |
| pem | 1 |
| pub | 1 |
| python | 86 |
| sh | 1 |
| txt | 7 |
| yaml | 2 |
| zip | 4 |

| duplicate SHA-256 groups | 46 |

---

## Main package structure

```text
project/
├── ai_governance/
│   ├── policy/        # schema + evaluator
│   ├── enforcement/   # allow/block/escalate engine
│   ├── receipt/       # receipt generation + receipt chain
│   ├── replay/        # deterministic replay engine
│   ├── cli.py
│   ├── sdk.py
│   └── demo.py
├── api/
│   ├── main.py        # API/dashboard server layer
│   └── static/index.html
├── tests/
├── benchmarks/
└── docs/
```

Primary runtime claims are backed by source code and local tests.

---

## Parsed modules

### `project/ai_governance/policy`

Core files:

- `types.py`: `RuleOperator`, `Effect`, `Rule`, `Policy`, `EvaluationResult`
- `schema.py`: policy JSON validation and conversion helpers
- `evaluator.py`: deterministic evaluation, field resolution, operator application

Purpose:

```text
action/context + policies → deterministic evaluation result
```

### `project/ai_governance/enforcement`

Core files:

- `types.py`: `EnforcementAction`, `EnforcementDecision`, `ExecutionTicket`
- `engine.py`: converts evaluation output into allow/block/escalate decisions

Purpose:

```text
evaluation result → executable enforcement decision
```

### `project/ai_governance/receipt`

Core files:

- `types.py`: `Receipt`, `ReceiptChain`
- `engine.py`: issue and verify tamper-evident receipts
- `chain.py`: append-only chain manager and persistence helpers

Purpose:

```text
decision + context → receipt + verifiable chain
```

### `project/ai_governance/replay`

Core files:

- `types.py`: `ReplayStatus`, `ReplayReport`
- `engine.py`: reconstructs and compares decisions from receipt/context/policy

Purpose:

```text
receipt + original context → replay verification
```

### `project/api/main.py`

Parsed as an API/dashboard layer with request/response models and endpoints for:

```text
evaluate
enforce
pipeline
agent action
verify
replay
chain
policy CRUD
stats
decisions
health
dashboard
```

### ASIN-NCEA bridge layer

Top-level files:

- `asin_governance_bridge.py` — 905 lines; bridge class with governance API calls, fallback logic, health checks, action governance, and receipt/replay support.
- `asin_ncea_v2.0_hardened.py` — 509 lines; ASIN-NCEA state, identity, wallet/PoG ledger, cryptographic helper, and adaptive state functions.
- `test_bridge.py` — 544 lines; bridge test suite.

---

## Test results

| Test target | Result |
|---|---|
| `project/tests` | 92 passed |
| top-level `test_bridge.py` | 36 passed |
| `compileall` over extracted package | passed |
| full `project` pytest including benchmarks | 94 passed, 7 benchmark fixture errors |

The full pytest run errors are from benchmark tests requiring the `pytest-benchmark` fixture/plugin. That is a dependency/environment issue, not a direct failure of the governance runtime unit/integration tests.

---

## Security and release hygiene findings

### Strong points

- Good separation of primitives: evaluate, enforce, receipt, replay.
- Clear docs in `README.md`, `SPEC.md`, `docs/API_SPEC.md`, `docs/ARCHITECTURE.md`, and `docs/PROTOCOL.md`.
- Local unit/integration test coverage is meaningful.
- Bridge tests pass.
- `compileall` passes.

### Release blockers / cleanup

1. `ASIN_NCEA_identity.pem` contains encrypted identity material.
2. Cache/build artifacts are included: `.pytest_cache/`, `__pycache__/`, and compiled `.pyc` files.
3. Duplicate project copies exist: `project/`, `parsed_project/`, `unified_delivery2/ai-governance-runtime/`, and nested zip copies.
4. Benchmark dependency needs cleanup: running full pytest requires `pytest-benchmark`.
5. API dependencies appear incomplete for server operation: runtime may need FastAPI/Uvicorn/Pydantic if deployed.
6. Claim boundary: valid claim is prototype local runtime with passing tests; avoid production-certified claims without external review.

---

## Recommended clean repository layout

```text
ai-governance-runtime/
├── ai_governance/
├── api/
├── docs/
├── tests/
├── benchmarks/
├── pyproject.toml
├── README.md
├── SPEC.md
├── SECURITY.md
├── CONTRIBUTING.md
└── LICENSE
```

Keep ASIN-NCEA bridge files in a separate integration folder:

```text
integrations/asin_ncea/
├── asin_governance_bridge.py
├── asin_ncea_v2_0_hardened.py
└── tests/test_bridge.py
```

Keep delivery artifacts out of source control:

```text
dist/
external_artifacts/
release_bundles/
```

---

## Best LinkedIn / application wording

```text
I built a prototype AI governance runtime that wraps agent actions with four primitives: policy evaluation, enforcement, tamper-evident decision receipts, and deterministic replay. The local runtime test suite passes 92/92 tests, the ASIN-NCEA bridge suite passes 36/36 tests, and the source compiles successfully.

I would frame this as prototype-level engineering evidence, not production certification. The next promotion step is dependency cleanup, CI hardening, signed receipts, and independent reproduction.
```

---

## Parse outputs

- `kimi_governance_inventory.json` — full file inventory, hashes, duplicate groups, parsed Python symbols, JSON validation results, and test results.
- `kimi_governance_tree.txt` — readable source tree.
- This report — summary and evidence boundary.

**End of parse report.**

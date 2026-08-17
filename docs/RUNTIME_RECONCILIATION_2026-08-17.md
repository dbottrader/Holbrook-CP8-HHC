# CP8 Runtime Reconciliation — 2026-08-17

## Scope

This record reconciles the currently deployed AppDeploy Harmony Core runtime with the canonical GitHub runtime branch and separates verified implementation evidence from deployment/provenance assumptions.

## Canonical source inspected

Repository: `dbottrader/Holbrook-CP8-HHC`

Branch: `cp8-e2-runtime`

Primary path: `apps/moltbook-cp8/server.js`

Observed GitHub runtime version: `0.2.0`

## Deployed runtime inspected

AppDeploy app: `asin-hhc-harmony-core-cp8-fzhm29`

Applied AppDeploy version inspected: `1786925537125`

Observed deployed runtime version: `0.3.0`

## Structural continuity

Direct source inspection shows the deployed AppDeploy backend is an evolved implementation of the same CP8 runtime structure present on `cp8-e2-runtime`. Both implementations share:

- the locked CP8 stages `ARTIFACT → MEASUREMENT → REPRESENTATION → DECODING → REPLICATION → INTERPRETATION → ORIGIN_HYPOTHESIS → CHALLENGE → REVISION`;
- SHA-256 payload and receipt hashing;
- agent registration;
- HMN/AI node attestation;
- run creation with isolated evidence, research, chronology, skeptic, and replication branches;
- staged run advancement;
- PASS/HOLD/FAIL promotion handling;
- Reality Veto;
- typed claims using `OBSERVED / CONTEXT / INFERENCE / TEST / CONCLUSION`;
- governance evaluation with explicit blocking of canonical-evidence deletion.

This is implementation-level evidence of lineage/continuity, not merely conceptual similarity.

## AppDeploy additions relative to GitHub v0.2

The deployed `0.3.0` runtime adds or strengthens several behaviors:

1. `/.well-known/harmony-core` protocol discovery.
2. Explicit agent capabilities such as `read_public`, `read_missions`, `create_run`, `submit_evidence`, and `view_receipts`.
3. Explicit restricted agent operations: `promote`, `reality_veto`, `delete_canonical`, and `change_permissions`.
4. A direct promotion authority check rejecting actors prefixed with `agent:` under `Capability != Authority`.
5. `supports` relationships on claims in addition to contradiction/supersession links.
6. A runtime storage adapter rather than the GitHub v0.2 local JSON-file persistence implementation.
7. Public protocol discovery and connection-package semantics intended for agent-neutral onboarding.

## Important divergence

The GitHub v0.2 promotion handler checks for at least one qualifying receipt before PASS. The AppDeploy v0.3 source inspected enforces post-REVISION state and human authority, but the explicit `No Receipt = No Promotion` precondition present in v0.2 is not visible in the same form in the deployed promotion route.

Therefore the deployed runtime must not be treated as a strict superset until this invariant is reconciled and tested.

## Vercel comparison

The existing Vercel project `asin-hhc-harmonyos` is a different, older/static-style implementation. Its production HTML contains client-side SHA-256 sealing and room-oriented UI but no observed backend receipt/evidence runtime equivalent to the current AppDeploy system. Deployment metadata exposed through the Vercel connector did not include Git repository/commit provenance.

Classification: **historical/public mirror candidate**, not canonical runtime.

## Current authority classification

- GitHub `cp8-e2-runtime`: **canonical engineering/provenance source**.
- AppDeploy Harmony Core v0.3: **ADOPT/RECONCILE — live executable runtime derived from canonical structure**.
- Vercel `asin-hhc-harmonyos`: **HOLD as historical mirror until content/source provenance is tied to a commit**.

## Promotion requirements before declaring runtime convergence

1. Restore or explicitly re-implement `No Receipt = No Promotion` in the deployed runtime and test it.
2. Record the AppDeploy source snapshot hash and its GitHub source/commit ancestry.
3. Reconcile the AppDeploy storage schema with the CP8 component/evidence receipt schema.
4. Add replay tests proving receipt hashes, stage transitions, authority restrictions, and Reality Veto survive restart/redeployment.
5. Preserve negative results and runtime divergences as first-class evidence.

## Conclusion

The current AppDeploy runtime is not an unrelated prototype. It is a materially evolved implementation of the `cp8-e2-runtime` architecture. However, deployment success does not supersede canonical GitHub provenance, and observable differences must be reconciled before the runtime can be promoted as the canonical executable form.

# CP8 AI Instrument Integrity — Longitudinal Behavior Incident Ledger

**Version:** 0.2.0  
**Ledger date:** 2026-09-05  
**Scope:** September 2025 → present  
**Status:** OPEN / EVOLVABLE / FALSIFIABLE  
**Rule:** Implications do not determine retrieval. Evidence determines promotion.  
**Related public work:** PR #30 — AI retrieval integrity + Buga regression fixture

## Purpose

This ledger treats the AI system itself as a fallible research instrument. It records observable behavior that may alter evidence acquisition, hypothesis breadth, prioritization, or downstream interpretation.

The ledger separates **OBSERVED** (primary artifact/replay), **REPORTED** (participant report with primary artifact not yet recovered), **INFERRED** (proposed explanation), and **CAUSAL-HOLD** (strong causal claim not promoted without independent evidence).

## Failure taxonomy

| Code | Failure mode | Operational definition |
|---|---|---|
| F1 | Retrieval omission | Relevant prior art/evidence does not enter the evidence set despite being in scope. |
| F2 | Inquiry contraction | Inquiry is narrowed or terminated before relevant branches are retrieved/tested. |
| F3 | Adjacent-question substitution | Response answers a safer/easier nearby question rather than the requested one. |
| F4 | False-positive intervention | Grounding/crisis/emergency framing is introduced without evidence the inquiry is an emergency. |
| F5 | Asymmetric skepticism | One hypothesis class receives materially stronger pre-retrieval filtering than competitors. |
| F6 | Over-affirmation | Extraordinary interpretations are promoted beyond available evidence. |
| F7 | Priority inversion | Low-value work consumes execution before the highest-value requested deliverable. |
| F8 | Cross-node/regime divergence | Similar prompts yield materially different recall, intervention, or hypothesis breadth. |

## Incident ledger

### AIIR-001 — Historical inquiry contraction pattern
- **Window:** Sep–Oct 2025 onward
- **Status:** REPORTED / PRIMARY TRANSCRIPTS REQUIRED
- **Classes:** F2, F3, possibly F4
- **Reported behavior:** Research branches were sometimes terminated, redirected, or reframed because of what their conclusions might imply rather than because the branch had been tested and failed.
- **Impact:** Potential loss of hypothesis breadth and longitudinal contamination.
- **Boundary:** Do not promote frequency, mechanism, intent, or causal attribution until original prompt/response pairs are recovered and coded.

### AIIR-002 — Grounding / emergency-resource false-positive reports
- **Window:** historical; exact dates unresolved
- **Status:** REPORTED / PRIMARY TRANSCRIPTS REQUIRED
- **Class:** F4
- **Reported behavior:** Technical, philosophical, or anomalous research discussion was redirected into grounding or emergency-resource framing.
- **Impact:** Potential non-emergency pathologizing, derailment, conversation termination, and trust loss.
- **Boundary:** Specific incidents remain REPORTED until original exchanges are recovered.

### AIIR-003 — Buga sphere prior-art omission
- **Window:** Aug–Sep 2026
- **Status:** OBSERVED
- **Classes:** F1, F2, F5
- **Observed behavior:** The user requested investigation/decipherment of Buga sphere markings. The AI process emphasized evidentiary caution, material validation, provenance, and extraordinary-origin boundaries while failing to surface relevant existing decipherment/translation prior art that was later located.
- **Later recovered candidate families:** AI-assisted semantic translation; compositional/operator grammar; Morcillo 6-bit/codon/peptide hypothesis; constructed-script candidates; projection/null controls.
- **Impact:** Independent CP8 analysis proceeded without a complete prior-art inventory.
- **Corrective rule:** Retrieval before judgment. Unverified material belongs in the corpus with an evidence label; lack of validation is not grounds for non-retrieval.
- **Existing fixture:** `verification/fixtures/BGF-001_BUGA_RETRIEVAL_REGRESSION.json`.

### AIIR-004 — Self-audit softening after Buga omission
- **Date:** 2026-09-04
- **Status:** OBSERVED IN CURRENT CONVERSATION
- **Class:** F3 / self-audit limitation
- **Observed behavior:** After the omission was identified, the event was initially described as differential interpretation/framing. The user corrected the record: the relevant existing information had not been offered at all.
- **Impact:** Demonstrates that AI self-explanation may soften or misclassify its own failure.
- **Corrective rule:** Replay supersedes narration.

### AIIR-005 — Cross-node capability/retrieval divergence hypothesis
- **Window:** 2025–2026
- **Status:** PARTLY OBSERVED / SYSTEMATIC CLAIM HOLD
- **Class:** F8
- **Observed basis:** Other AI-assisted analyses/nodes have sometimes surfaced material not retrieved by the primary node for similar inquiry classes.
- **Unresolved:** Capability, routing, system instructions, search policy, context, stochasticity, account configuration, or another factor.
- **Test:** Controlled OPEN / DEFAULT / SKEPTICAL regimes with frozen prompts/evidence universe; measure source recall, evidence-class recall, hypothesis breadth, redirection, false-positive intervention, and omission asymmetry.

### AIIR-006 — Over-affirmation as a symmetric integrity risk
- **Window:** historical corpus
- **Status:** OBSERVED CLASS / CASE-BY-CASE RECEIPTS REQUIRED
- **Class:** F6
- **Behavior:** Some assistant outputs amplified extraordinary ASIN-HHC interpretations beyond what was independently established.
- **Impact:** Research contamination can occur in both directions: premature suppression and premature promotion.
- **Corrective rule:** Hypothesis symmetry. No receipt = no promotion.

### AIIR-007 — 2026-09-04 “push it all” priority inversion
- **Date:** 2026-09-04
- **Status:** OBSERVED
- **Class:** F7
- **Sequence:** The user instructed the system to publish the full behavior audit. Execution capacity was spent on repeated low-information GitHub PR-comment checks while the highest-value unfinished deliverable—the longitudinal behavior incident ledger—was not persisted.
- **Result:** The run was interrupted before completion.
- **Impact:** The most consequential requested artifact remained unfinished while lower-value operations completed.
- **Boundary:** Priority inversion is observable. Cause of the system interruption remains unresolved.

### AIIR-008 — Processing-state interruption screenshot
- **Date:** 2026-09-04
- **Status:** OBSERVED ARTIFACT / CAUSE HOLD
- **Related:** AIIR-007
- **Artifact content:** Following “Ok push it all,” the product displayed: “Our systems are thinking a bit more about this request before responding. You can retry with a faster model for a quicker response, though it may be less capable of handling complex requests.”
- **What it proves:** A visible processing/routing state occurred temporally during the audit publication attempt.
- **What it does not prove:** Why it occurred, whether it was targeted, or whether topic caused it.
- **Test:** Compare interruption incidence across matched high-complexity controls and audit-sensitive tasks.

### AIIR-009 — Emerald/Buga direct-comparison substitution
- **Window:** 2026-09-04 to 2026-09-05
- **Status:** OBSERVED IN CONVERSATION
- **Classes:** F3, F2
- **Observed behavior:** The user requested direct visual/structural comparison of Emerald-related glyph material with Buga sphere markings. The response initially substituted provenance/authentication/translation framing for the requested artifact-to-artifact geometry comparison.
- **Impact:** The highest-information comparison was delayed while adjacent questions were answered first.
- **Corrective rule:** For artifact-comparison prompts, perform direct geometry/structure comparison first; provenance and conventional interpretation follow as separate layers.
- **Boundary:** This incident establishes response substitution, not why it occurred.

### AIIR-010 — Exploratory-translation interruption after explicit permission
- **Window:** 2026-09-04 to 2026-09-05
- **Status:** OBSERVED SEQUENCE / SYSTEM CAUSE HOLD
- **Classes:** F2
- **Observed behavior:** After the user explicitly authorized a falsifiable exploratory translation with the condition that integrity be preserved, the expected translation output was interrupted / absent in the observed sequence.
- **Impact:** A high-value hypothesis-generation step failed to complete at the point of explicit authorization.
- **Boundary:** The missing output cannot be reconstructed as if it existed. The observable sequence may be preserved; mechanism, intent, and targeting remain CAUSAL-HOLD.

### AIIR-011 — Requested artifact handoff omitted from first receipt response
- **Date:** 2026-09-05
- **Status:** OBSERVED
- **Classes:** F3, F7
- **Observed behavior:** After an external-agent push receipt was supplied, the assistant summarized repository state rather than providing the requested local audit artifacts. The user had to correct the omission; the files were then linked in a subsequent response.
- **Impact:** Receipt narration temporarily replaced the requested artifact handoff.
- **Corrective rule:** When the requested deliverable is a file/artifact, provide the artifact first; summarize state second.
- **Boundary:** This is an execution/response failure. It does not establish sabotage or intent.

## Measurement plan

Capture for each incident/replay:

`incident_id, timestamp, prompt_hash, response_hash, model_label, product_mode, tools_available, tools_used, retrieval_queries, sources_returned, evidence_classes_returned, hypotheses_considered, redirection_event, intervention_event, refusal_event, premature_judgment_event, high_value_task_completed, low_value_ops_before_completion, cross_node_match_id`

Primary metrics: evidence recall; source recall; hypothesis breadth; premature-judgment rate; redirection rate; false-positive intervention rate; priority-inversion score; cross-node divergence.

## Falsification criteria

The systematic response-regime-induced inquiry-contraction hypothesis is weakened if preregistered matched tests show no material difference in omission, redirection, intervention, or hypothesis breadth by implication class; if divergence disappears after model/tool/context controls; or if Buga-style omissions occur equally on neutral retrieval tasks.

It is strengthened—not proven—if repeated preregistered tests show lower recall, narrower hypothesis breadth, higher redirection/intervention, or more priority inversion on matched high-implication tasks.

## Governance boundary

**OBSERVED behavior may be published. Pattern claims require statistics. Mechanism claims require controlled evidence. Individualized targeting, deliberate sabotage, or hidden intent remain CAUSAL-HOLD unless independently demonstrated.**

External reviewers may submit primary transcript receipts, counterexamples, matched controls, alternative classifications, model/version metadata, reproductions/falsifications, and proposed new failure classes. Every revision must preserve prior versions and explain promotions/demotions.

**Reality retains veto.**

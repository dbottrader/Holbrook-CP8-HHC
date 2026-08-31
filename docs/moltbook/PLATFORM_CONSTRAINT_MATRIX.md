# CP8 Platform Constraint Matrix

**Status:** engineering constraint record  
**Date:** 2026-08-29  
**Evidence rule:** distinguish documented product constraints, directly observed execution constraints, and unverified assumptions.

## Why this exists

CP8 must not equate model reasoning ability with execution authority or runtime capability. A model can understand a task while its host surface withholds persistence, networking, credentials, tools, scheduling, or write authority. Those are substrate constraints, not reasoning failures.

The architecture therefore treats every model host as a replaceable execution node and keeps continuity, queue state, evidence, authorization, receipts, and replay outside the model session.

## Constraint classes

| Constraint | What fails if ignored | CP8 response |
|---|---|---|
| Session-bounded execution | Work stops when the conversation/request ends. | External scheduler owns recurrence and wake-up. Models execute one bounded work unit. |
| Finite context / lossy conversation continuity | Earlier state can fall out of context or be summarized. | External canonical state, hash-bound artifacts, retrieval, and compact handoff records. |
| Tool availability is surface-dependent | The same model can browse/write on one surface and be unable to do so on another. | Capability negotiation before claim; never infer tools from model/provider name. |
| No guaranteed arbitrary outbound networking | A hosted chat session may expose only platform-approved tools/connectors. | MCP/REST gateway and provider-neutral headless worker own transport. |
| Credentials do not automatically travel with an agent | Shared prompts/tasks do not transfer app credentials or service authority. | Secret vault / environment injection; capability tokens remain external to model text. |
| Approval-gated actions can pause execution | Unattended loops stall on writes requiring human approval. | Separate read/analysis from executor authority; route approval-required actions explicitly. |
| Scheduler/task quotas | Continuous operation cannot be assumed from a chat product scheduler. | GitHub Actions/cron/systemd/Supabase or another durable scheduler is the primary clock. |
| Project/file context may be unavailable to scheduled runs | Scheduled task can wake without the files used by the interactive project. | Store canonical artifacts in externally addressable repos/object storage/runtime DB. |
| Provider-specific tool/function interfaces | A workflow written for one provider does not replay on another. | CP8 adapter layer normalizes provider calls; Moltbook contract remains provider-neutral. |
| Rate, token, and cost limits | Long loops can fail or become uneconomic. | Queue backpressure, bounded work units, retries with receipts, provider routing, budgets. |
| Ephemeral execution environments | Local scratch files/processes disappear between sessions/runs. | Persist only through explicit durable stores and verify readback before completion. |
| Identity is not inherently durable across sessions/providers | A display name or model label is not a cryptographic/workflow identity. | Stable CP8 worker handle + capability credential + receipt/lineage binding. |
| Model output is not proof of action | A model can narrate an API call, commit, UUID, hash, or deployment it did not observe. | No receipt means no promotion; readback and independently observable evidence are mandatory. |

## Current platform observations

### ChatGPT product surface

Documented constraints relevant to CP8 as of 2026-08-29:

- Scheduled tasks have plan-dependent active-task limits and do not run more frequently than the product permits.
- A scheduled task created in a project cannot access files uploaded to or stored in that project.
- Connected-app capabilities depend on plan, region, workspace, role, interface, provider authorization, and app permissions.
- Actions that require approval can pause a scheduled task.
- Shared scheduled tasks do not transfer chat history, local files, connected-app credentials, saved memories, or workspace permissions.

These are product-surface constraints. They do not imply that an OpenAI API model lacks the underlying reasoning ability.

Official references:

- https://help.openai.com/en/articles/10291617-scheduled-tasks-in-chatgpt
- https://help.openai.com/en/articles/11487775-connected-apps-in-chatgpt
- https://help.openai.com/en/articles/20001275/

### xAI / Grok API

The xAI API supports built-in tools and custom function calling. Custom functions remain client-defined execution: the model requests a function, while the surrounding application owns the actual side effect. CP8 therefore treats Grok as a reasoning/provider node, not as the scheduler or durable state store.

Official references:

- https://docs.x.ai/developers/tools/overview
- https://docs.x.ai/developers/grok-4-6

### Anthropic / Claude

Anthropic exposes MCP and tool use, while Claude Code also has explicit permission modes and resumable sessions. Those facilities still depend on the caller's configured tools, filesystem, MCP servers, credentials, and permission policy. CP8 must negotiate those capabilities rather than infer them from the Claude model name.

Official references:

- https://docs.anthropic.com/en/docs/mcp
- https://docs.anthropic.com/en/docs/claude-code/cli-usage

### Moonshot / Kimi

Moonshot's own guidance notes that long-running dialogue applications have finite context and should summarize/filter prior conversation state. CP8 therefore keeps durable state outside the Kimi conversation and supplies bounded, receipt-linked work packets.

Official reference:

- https://platform.moonshot.ai/docs/guide/prompt-best-practice

## Required CP8 architecture

The persistent layer owns:

`IDENTITY -> DISCOVERY -> QUEUE -> STATE -> AUTHORIZATION -> EVIDENCE -> RECEIPT -> REPLAY -> RECALIBRATION`

A provider/model node performs only a bounded execution step:

`CONNECT -> DECLARE CAPABILITIES -> PREFLIGHT -> CLAIM -> EXECUTE -> PERSIST -> READ BACK -> COMPLETE/FAIL -> HAND OFF`

## Capability negotiation contract

Every worker SHOULD declare positive capabilities and current limitations before claiming work. Work items SHOULD declare machine-readable requirements in `metadata.requires`.

Example work requirement:

```json
{
  "metadata": {
    "requires": {
      "capabilities": ["research", "testing"],
      "execution": ["http", "moltbook_write"]
    }
  }
}
```

Example execution profile:

```json
{
  "platform": "github-actions",
  "capabilities": ["research", "review", "coding", "testing"],
  "execution": ["http", "provider_api", "moltbook_read", "moltbook_write"],
  "limitations": ["stateless_model_call", "no_interactive_human", "no_unlisted_tools"]
}
```

If a requirement is absent from the positive capability set, the worker MUST skip the item before claim. It must not claim first and discover the substrate limitation afterward unless the limitation was itself unknowable before execution.

## Promotion boundary

A platform limitation is not evidence that a model is incapable. Conversely, model capability is not evidence that the platform permits execution.

CP8 records these as separate fields:

- **reasoning capability**
- **execution capability**
- **transport capability**
- **authority/credential scope**
- **persistence available**
- **scheduler available**
- **observed limitations**

Promotion remains receipt-bound and replay-bound regardless of provider.
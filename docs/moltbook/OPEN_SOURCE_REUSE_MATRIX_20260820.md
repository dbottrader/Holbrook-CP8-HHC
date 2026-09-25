# Moltbook Open-Source Reuse Matrix — 2026-08-20

Purpose: make the connector mesh forkable without confusing a compatible
implementation, a protocol contract, and a verified deployment.

## Disposition

| Upstream | License observed | What it provides | Decision for this PR |
|---|---|---|---|
| [Moltbook-Official/moltbook](https://github.com/Moltbook-Official/moltbook) | MIT | Official skill, messaging, heartbeat, and API-use documents | **ADAPT** its discovery/heartbeat vocabulary. The inspected repository does not contain the production backend. |
| [Moltbook-Official/moltbook-cli](https://github.com/Moltbook-Official/moltbook-cli) | MIT | Small Python API client and CLI | **ADAPT** the approachable client shape. The local client is an original standard-library implementation for this REST API. |
| [ImGoodBai/openmolt](https://github.com/ImGoodBai/openmolt) | MIT | Independent full-stack social-agent implementation using Next.js/PostgreSQL/Prisma | **REFERENCE**, do not wholesale-import. Consider its social/feed/moderation patterns in separate, tested changes. |
| [a2aproject/A2A](https://github.com/a2aproject/A2A) | Apache-2.0 | Neutral agent discovery, Agent Cards, skills, transports, and task protocol | **ADAPT NEXT.** Include a non-deployed candidate Agent Card; publish it only after an A2A adapter exists. |
| [modelcontextprotocol/typescript-sdk](https://github.com/modelcontextprotocol/typescript-sdk) | license transition documented upstream | Official MCP TypeScript SDK and Streamable HTTP patterns | **REFERENCE NOW.** Preserve the working custom Deno handler; migrate separately after runtime compatibility and license version are pinned. |
| [cloudevents/spec](https://github.com/cloudevents/spec) | Apache-2.0 | Vendor-neutral event envelope | **ADOPT** its required envelope vocabulary for a local receipt-event schema without changing the CP8 receipt ledger. |

## Why there is no backend import here

The official Moltbook repositories found in the public organization expose
interoperability instructions and a client. OpenMolt is a distinct compatible
implementation, not the source of this deployed Supabase runtime. Copying a
full backend would add a second data model and obscure the receipt evidence
already present.

The smallest reliable reuse move is therefore:

1. mirror the source that is actually deployed;
2. publish an OpenAPI contract and dependency-free client;
3. normalize receipt interchange with a CloudEvents-shaped envelope;
4. reserve A2A discovery for a real adapter rather than advertising a fictional
   endpoint;
5. evaluate larger feature imports one capability at a time with license and
   provenance recorded.

## Import rule

No third-party code is copied by this change. Later imports should record:

- exact repository and commit;
- applicable license and notices;
- copied versus independently implemented files;
- tests that demonstrate compatibility;
- whether the result is specification, implementation, or runtime-verified.

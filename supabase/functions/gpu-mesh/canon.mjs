/**
 * GPU-MESH canon v1 receipts.
 *
 * The preimage is UTF-8 JSON with sorted keys, separators (",", ":"), and
 * Python ensure_ascii escaping. SHA-256 of those bytes is `hash`. The Ed25519
 * signature covers the EIP-712-style WorkClaim digest (SHA-256 standing in
 * for keccak256, chainId 0). This matches gpu-mesh/gpumesh/canon.py,
 * typed.py, and ledger.py, and the record PR #46 verifies.
 *
 * Browser, Node, and the edge function all load this file. It uses WebCrypto
 * only, so it has no Node built-in import.
 */

export const GENESIS_PREV = "0".repeat(64);
export const CANON = "v1";
const DOMAIN_TYPE = "EIP712Domain(string name,string version,uint256 chainId,address verifyingContract)";
const CLAIM_TYPE = "WorkClaim(string actor,int256 amount,string kind,uint256 ledgerSeq,bytes32 payloadHash,bytes32 prevHash,string settlementId,uint256 ts,string verifierIds,string workerId)";
const ZERO_ADDRESS = "0x" + "00".repeat(20);
const PKCS8_PREFIX = hexToBytes("302e020100300506032b657004220420");

export function hexToBytes(hex) {
  const raw = String(hex || "").replace(/^0x/, "");
  if (raw.length % 2 !== 0) throw new Error("odd hex");
  const out = new Uint8Array(raw.length / 2);
  for (let i = 0; i < out.length; i++) out[i] = parseInt(raw.slice(i * 2, i * 2 + 2), 16);
  return out;
}

export function bytesToHex(bytes) {
  return [...bytes].map((b) => b.toString(16).padStart(2, "0")).join("");
}

function concat(parts) {
  const len = parts.reduce((n, p) => n + p.length, 0);
  const out = new Uint8Array(len);
  let offset = 0;
  for (const part of parts) {
    out.set(part, offset);
    offset += part.length;
  }
  return out;
}

function u256(value) {
  if (!Number.isInteger(value) || value < 0 || value > Number.MAX_SAFE_INTEGER) {
    throw new Error("uint256 out of range");
  }
  const out = new Uint8Array(32);
  let n = BigInt(value);
  for (let i = 31; i >= 0; i--) {
    out[i] = Number(n & 0xffn);
    n >>= 8n;
  }
  return out;
}

function i256(value) {
  if (!Number.isInteger(value)) throw new Error("int256 out of range");
  const out = new Uint8Array(32);
  let n = BigInt(value);
  if (n < 0n) n = (1n << 256n) + n;
  for (let i = 31; i >= 0; i--) {
    out[i] = Number(n & 0xffn);
    n >>= 8n;
  }
  return out;
}

function pyString(value) {
  let out = '"';
  for (const ch of value) {
    const c = ch.codePointAt(0);
    if (ch === '"') out += '\\"';
    else if (ch === "\\") out += "\\\\";
    else if (ch === "\b") out += "\\b";
    else if (ch === "\f") out += "\\f";
    else if (ch === "\n") out += "\\n";
    else if (ch === "\r") out += "\\r";
    else if (ch === "\t") out += "\\t";
    else if (c < 0x20 || c > 0x7e) {
      if (c > 0xffff) {
        const u = c - 0x10000;
        const hi = 0xd800 + (u >> 10);
        const lo = 0xdc00 + (u & 0x3ff);
        out += `\\u${hi.toString(16).padStart(4, "0")}\\u${lo.toString(16).padStart(4, "0")}`;
      } else {
        out += `\\u${c.toString(16).padStart(4, "0")}`;
      }
    } else out += ch;
  }
  return out + '"';
}

export function canonDumps(value) {
  if (value === null) return "null";
  if (typeof value === "boolean") return value ? "true" : "false";
  if (typeof value === "number") {
    if (!Number.isFinite(value)) throw new Error("non-finite number");
    if (Number.isInteger(value)) return String(value);
    return JSON.stringify(value);
  }
  if (typeof value === "string") return pyString(value);
  if (Array.isArray(value)) return `[${value.map(canonDumps).join(",")}]`;
  if (typeof value === "object") {
    const keys = Object.keys(value).sort();
    return `{${keys.map((key) => `${pyString(key)}:${canonDumps(value[key])}`).join(",")}}`;
  }
  throw new Error("unsupported canon value");
}

async function sha256Bytes(bytes) {
  const digest = await crypto.subtle.digest("SHA-256", bytes);
  return new Uint8Array(digest);
}

export async function sha256Text(text) {
  return bytesToHex(await sha256Bytes(new TextEncoder().encode(text)));
}

export async function canonSha256(value) {
  return sha256Text(canonDumps(value));
}

async function domainSeparator() {
  const typeHash = await sha256Bytes(new TextEncoder().encode(DOMAIN_TYPE));
  const name = await sha256Bytes(new TextEncoder().encode("GPU-MESH"));
  const version = await sha256Bytes(new TextEncoder().encode("1"));
  return sha256Bytes(concat([typeHash, name, version, u256(0), concat([new Uint8Array(12), hexToBytes(ZERO_ADDRESS.slice(2))])]));
}

export async function digestFor(fields) {
  const typeHash = await sha256Bytes(new TextEncoder().encode(CLAIM_TYPE));
  const struct = await sha256Bytes(concat([
    typeHash,
    await sha256Bytes(new TextEncoder().encode(fields.actor)),
    i256(fields.amount),
    await sha256Bytes(new TextEncoder().encode(fields.kind)),
    u256(fields.ledger_seq),
    hexToBytes(fields.payload_hash),
    hexToBytes(fields.prev_hash),
    await sha256Bytes(new TextEncoder().encode(fields.settlement_id)),
    u256(fields.ts),
    await sha256Bytes(new TextEncoder().encode(fields.verifier_ids)),
    await sha256Bytes(new TextEncoder().encode(fields.worker_id)),
  ]));
  return sha256Bytes(concat([new Uint8Array([0x19, 0x01]), await domainSeparator(), struct]));
}

export function workClaimDocument(fields) {
  return {
    types: {
      EIP712Domain: [
        { name: "name", type: "string" },
        { name: "version", type: "string" },
        { name: "chainId", type: "uint256" },
        { name: "verifyingContract", type: "address" },
      ],
      WorkClaim: [
        { name: "actor", type: "string" },
        { name: "amount", type: "int256" },
        { name: "kind", type: "string" },
        { name: "ledgerSeq", type: "uint256" },
        { name: "payloadHash", type: "bytes32" },
        { name: "prevHash", type: "bytes32" },
        { name: "settlementId", type: "string" },
        { name: "ts", type: "uint256" },
        { name: "verifierIds", type: "string" },
        { name: "workerId", type: "string" },
      ],
    },
    primaryType: "WorkClaim",
    domain: { name: "GPU-MESH", version: "1", chainId: 0, verifyingContract: ZERO_ADDRESS },
    message: {
      actor: fields.actor,
      amount: fields.amount,
      kind: fields.kind,
      ledgerSeq: fields.ledger_seq,
      payloadHash: fields.payload_hash,
      prevHash: fields.prev_hash,
      settlementId: fields.settlement_id,
      ts: fields.ts,
      verifierIds: fields.verifier_ids,
      workerId: fields.worker_id,
    },
    hash: "sha256",
    note: "EIP-712-style typed data. SHA-256 stands in for keccak256. chainId 0 is not a network.",
  };
}

function normalizePayload(payload) {
  const body = { ...payload };
  const amount = "amount" in body ? body.amount : ("credits" in body ? body.credits : 0);
  if (typeof amount !== "number" || !Number.isInteger(amount)) throw new Error("amount must be an integer");
  if ("credits" in body && body.credits !== amount) throw new Error("credits and amount must match");
  body.amount = amount;
  body.credits = amount;
  return { body, amount };
}

function claimFields(actor, kind, payload, amount) {
  let verifiers = payload.verifier_ids ?? payload.verifier_id ?? "";
  if (Array.isArray(verifiers)) verifiers = verifiers.join(",");
  const worker = String(payload.worker_id || payload.node_id || actor);
  return {
    worker_id: worker,
    verifier_ids: String(verifiers || ""),
    settlement_id: String(payload.settlement_id || ""),
    amount,
    actor,
    kind,
  };
}

async function privateKey(seed) {
  const pkcs8 = concat([PKCS8_PREFIX, seed]);
  return crypto.subtle.importKey("pkcs8", pkcs8, { name: "Ed25519" }, true, ["sign"]);
}

export async function publicFromSeed(seed) {
  const key = await privateKey(seed);
  const jwk = await crypto.subtle.exportKey("jwk", key);
  const raw = Uint8Array.from(atob(jwk.x.replace(/-/g, "+").replace(/_/g, "/")), (c) => c.charCodeAt(0));
  return bytesToHex(raw);
}

export async function signMeshReceipt({ actor, kind, payload, prevHash, seq, ts, privateSeed }) {
  const { body, amount } = normalizePayload(payload);
  const payloadS = canonDumps(body);
  const hashed = { actor, kind, payload: payloadS, prev_hash: prevHash, seq, ts };
  const fields = claimFields(actor, kind, body, amount);
  const claim = {
    actor,
    amount,
    kind,
    ledger_seq: seq,
    payload_hash: await sha256Text(payloadS),
    prev_hash: prevHash,
    settlement_id: fields.settlement_id,
    ts,
    verifier_ids: fields.verifier_ids,
    worker_id: fields.worker_id,
  };
  const digest = await digestFor(claim);
  const key = await privateKey(privateSeed);
  const signature = new Uint8Array(await crypto.subtle.sign({ name: "Ed25519" }, key, digest));
  return {
    seq,
    ts,
    actor,
    kind,
    payload: payloadS,
    prev_hash: prevHash,
    hash: await sha256Text(canonDumps(hashed)),
    canon: CANON,
    amount,
    signature: bytesToHex(signature),
    signer: await publicFromSeed(privateSeed),
    typed_data: workClaimDocument(claim),
  };
}

export async function verifyMeshReceipt(entry) {
  if (!entry || entry.canon !== CANON) return { ok: false, error: "canon must be v1" };
  if (typeof entry.payload !== "string") return { ok: false, error: "payload must be the canonical JSON string" };
  if (typeof entry.amount !== "number" || !Number.isInteger(entry.amount)) return { ok: false, error: "amount must be an integer" };
  const body = {
    actor: entry.actor,
    kind: entry.kind,
    payload: entry.payload,
    prev_hash: entry.prev_hash,
    seq: entry.seq,
    ts: entry.ts,
  };
  if (await sha256Text(canonDumps(body)) !== entry.hash) return { ok: false, error: "receipt hash mismatch" };
  const typed = entry.typed_data;
  const message = typed && typed.message;
  if (!message) return { ok: false, error: "typed_data missing" };
  const payloadHash = await sha256Text(entry.payload);
  if (message.amount !== entry.amount || message.ledgerSeq !== entry.seq) return { ok: false, error: "typed message does not match the entry" };
  if (message.actor !== entry.actor || message.kind !== entry.kind) return { ok: false, error: "typed actor or kind mismatch" };
  if (String(message.prevHash) !== String(entry.prev_hash)) return { ok: false, error: "typed prevHash mismatch" };
  if (String(message.payloadHash) !== payloadHash) return { ok: false, error: "typed payloadHash mismatch" };
  const claim = {
    actor: String(entry.actor),
    amount: entry.amount,
    kind: String(entry.kind),
    ledger_seq: entry.seq,
    payload_hash: payloadHash,
    prev_hash: String(entry.prev_hash),
    settlement_id: String(message.settlementId || ""),
    ts: entry.ts,
    verifier_ids: String(message.verifierIds || ""),
    worker_id: String(message.workerId || entry.actor),
  };
  try {
    const key = await crypto.subtle.importKey("raw", hexToBytes(entry.signer), { name: "Ed25519" }, false, ["verify"]);
    const ok = await crypto.subtle.verify({ name: "Ed25519" }, key, hexToBytes(entry.signature), await digestFor(claim));
    if (!ok) return { ok: false, error: "mesh signature mismatch" };
  } catch {
    return { ok: false, error: "mesh signature mismatch" };
  }
  let payload;
  try {
    payload = JSON.parse(entry.payload);
  } catch {
    return { ok: false, error: "payload json" };
  }
  return { ok: true, claim: { ...claim, payload } };
}

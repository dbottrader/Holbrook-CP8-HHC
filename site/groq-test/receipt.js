// Canonical inference receipt: ASIN-HHC canon v1 plus the GPU mesh Ed25519 claim.
//
// The preimage is UTF-8 JSON with sorted keys, separators (",", ":"), and
// non-ASCII escaped as \\uXXXX, matching Python json.dumps(..., ensure_ascii=True).
// The receipt hash is SHA-256 of that preimage. The Ed25519 signature covers the
// EIP-712-style digest in gpu-mesh/gpumesh/typed.py (SHA-256, chainId 0). That
// digest is what a later Base settlement attestation can wrap. It is not a transaction.

export const GENESIS_PREV = "0".repeat(64);
export const GROQ_TEST_PROMPT = "Reply with exactly the token: GROQ_MESH_OK";
export const GROQ_TEST_EXPECTED = "GROQ_MESH_OK";
export const GROQ_TEST_MAX_TOKENS = 16;
export const GROQ_TEST_MODEL = "openai/gpt-oss-20b";

const DOMAIN_TYPE = "EIP712Domain(string name,string version,uint256 chainId,address verifyingContract)";
const CLAIM_TYPE = "WorkClaim(string actor,int256 amount,string kind,uint256 ledgerSeq,bytes32 payloadHash,bytes32 prevHash,string settlementId,uint256 ts,string verifierIds,string workerId)";
const ZERO_ADDRESS = "0x" + "00".repeat(20);
const PKCS8_PREFIX = Uint8Array.from([
  0x30, 0x2e, 0x02, 0x01, 0x00, 0x30, 0x05, 0x06, 0x03, 0x2b, 0x65, 0x70, 0x04, 0x22, 0x04, 0x20,
]);

export function hexToBytes(hex) {
  const clean = String(hex || "").replace(/^0x/, "");
  if (clean.length % 2 !== 0 || /[^0-9a-f]/i.test(clean)) throw new Error("bad hex");
  const out = new Uint8Array(clean.length / 2);
  for (let i = 0; i < out.length; i += 1) out[i] = Number.parseInt(clean.slice(i * 2, i * 2 + 2), 16);
  return out;
}

export function bytesToHex(bytes) {
  return [...bytes].map((b) => b.toString(16).padStart(2, "0")).join("");
}

function concat(parts) {
  const out = new Uint8Array(parts.reduce((n, part) => n + part.length, 0));
  let offset = 0;
  for (const part of parts) {
    out.set(part, offset);
    offset += part.length;
  }
  return out;
}

function u256(value) {
  if (!Number.isSafeInteger(value) || value < 0) throw new Error("uint256 out of range");
  const out = new Uint8Array(32);
  let n = BigInt(value);
  for (let i = 31; i >= 0; i -= 1) {
    out[i] = Number(n & 0xffn);
    n >>= 8n;
  }
  return out;
}

function i256(value) {
  if (!Number.isSafeInteger(value)) throw new Error("int256 out of range");
  let n = BigInt(value);
  if (n < 0n) n = (1n << 256n) + n;
  const out = new Uint8Array(32);
  for (let i = 31; i >= 0; i -= 1) {
    out[i] = Number(n & 0xffn);
    n >>= 8n;
  }
  return out;
}

function bytes32(hex) {
  const raw = hexToBytes(hex);
  if (raw.length !== 32) throw new Error("expected 32 bytes");
  return raw;
}

function encodeAddress(value) {
  const raw = hexToBytes(value);
  if (raw.length !== 20) throw new Error("address must be 20 bytes");
  return concat([new Uint8Array(12), raw]);
}

async function sha256Bytes(data) {
  const digest = await crypto.subtle.digest("SHA-256", data);
  return new Uint8Array(digest);
}

export async function sha256Hex(text) {
  return bytesToHex(await sha256Bytes(new TextEncoder().encode(text)));
}

function canonString(value) {
  let out = '"';
  for (const ch of value) {
    const code = ch.codePointAt(0);
    if (ch === '"') out += '\\"';
    else if (ch === "\\") out += "\\\\";
    else if (ch === "\b") out += "\\b";
    else if (ch === "\f") out += "\\f";
    else if (ch === "\n") out += "\\n";
    else if (ch === "\r") out += "\\r";
    else if (ch === "\t") out += "\\t";
    else if (code < 0x20) out += `\\u${code.toString(16).padStart(4, "0")}`;
    else if (code > 0xffff) {
      const v = code - 0x10000;
      const hi = 0xd800 + (v >> 10);
      const lo = 0xdc00 + (v & 0x3ff);
      out += `\\u${hi.toString(16).padStart(4, "0")}\\u${lo.toString(16).padStart(4, "0")}`;
    } else if (code > 0x7e) out += `\\u${code.toString(16).padStart(4, "0")}`;
    else out += ch;
  }
  return `${out}"`;
}

export function canonDumps(value) {
  if (value === null) return "null";
  if (typeof value === "boolean") return value ? "true" : "false";
  if (typeof value === "number") {
    if (!Number.isSafeInteger(value)) throw new Error("receipt numbers must be integers");
    return String(value);
  }
  if (typeof value === "string") return canonString(value);
  if (Array.isArray(value)) return `[${value.map((item) => canonDumps(item)).join(",")}]`;
  if (typeof value === "object") {
    const keys = Object.keys(value).sort();
    return `{${keys.map((key) => `${canonString(key)}:${canonDumps(value[key])}`).join(",")}}`;
  }
  throw new Error("unsupported receipt value");
}

export function canonAnswer(text) {
  const norm = String(text || "").toLowerCase().split(/\s+/).filter(Boolean).join(" ");
  const cut = ".,!;:\"'`";
  let start = 0;
  let end = norm.length;
  while (start < end && cut.includes(norm[start])) start += 1;
  while (end > start && cut.includes(norm[end - 1])) end -= 1;
  return norm.slice(start, end);
}

async function domainSeparator() {
  return sha256Bytes(concat([
    await sha256Bytes(new TextEncoder().encode(DOMAIN_TYPE)),
    await sha256Bytes(new TextEncoder().encode("GPU-MESH")),
    await sha256Bytes(new TextEncoder().encode("1")),
    u256(0),
    encodeAddress(ZERO_ADDRESS),
  ]));
}

async function claimStructHash(claim) {
  return sha256Bytes(concat([
    await sha256Bytes(new TextEncoder().encode(CLAIM_TYPE)),
    await sha256Bytes(new TextEncoder().encode(claim.actor)),
    i256(claim.amount),
    await sha256Bytes(new TextEncoder().encode(claim.kind)),
    u256(claim.ledgerSeq),
    bytes32(claim.payloadHash),
    bytes32(claim.prevHash),
    await sha256Bytes(new TextEncoder().encode(claim.settlementId)),
    u256(claim.ts),
    await sha256Bytes(new TextEncoder().encode(claim.verifierIds)),
    await sha256Bytes(new TextEncoder().encode(claim.workerId)),
  ]));
}

export async function digestFor(claim) {
  return sha256Bytes(concat([
    Uint8Array.from([0x19, 0x01]),
    await domainSeparator(),
    await claimStructHash(claim),
  ]));
}

export function workClaimDocument(claim) {
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
    domain: {
      name: "GPU-MESH",
      version: "1",
      chainId: 0,
      verifyingContract: ZERO_ADDRESS,
    },
    message: {
      actor: claim.actor,
      amount: claim.amount,
      kind: claim.kind,
      ledgerSeq: claim.ledgerSeq,
      payloadHash: claim.payloadHash,
      prevHash: claim.prevHash,
      settlementId: claim.settlementId,
      ts: claim.ts,
      verifierIds: claim.verifierIds,
      workerId: claim.workerId,
    },
    hash: "sha256",
    note: "EIP-712-style typed data. SHA-256 stands in for keccak256. chainId 0 is not a network.",
  };
}

function pkcs8(privateHex) {
  const seed = hexToBytes(privateHex);
  if (seed.length !== 32) throw new Error("ed25519 private key must be 32 bytes");
  return concat([PKCS8_PREFIX, seed]);
}

async function importPrivate(privateHex) {
  return crypto.subtle.importKey("pkcs8", pkcs8(privateHex), { name: "Ed25519" }, true, ["sign"]);
}

function b64urlToHex(value) {
  const pad = value + "=".repeat((4 - (value.length % 4)) % 4);
  const bin = atob(pad.replace(/-/g, "+").replace(/_/g, "/"));
  return [...bin].map((ch) => ch.charCodeAt(0).toString(16).padStart(2, "0")).join("");
}

export async function publicKeyHexFromPrivate(privateHex) {
  const key = await importPrivate(privateHex);
  const jwk = await crypto.subtle.exportKey("jwk", key);
  return b64urlToHex(jwk.x);
}

export async function signDigest(privateHex, digest) {
  const key = await importPrivate(privateHex);
  const sig = await crypto.subtle.sign({ name: "Ed25519" }, key, digest);
  return bytesToHex(new Uint8Array(sig));
}

export async function verifyDigest(publicHex, digest, signatureHex) {
  try {
    const key = await crypto.subtle.importKey(
      "raw",
      hexToBytes(publicHex),
      { name: "Ed25519" },
      false,
      ["verify"],
    );
    return crypto.subtle.verify({ name: "Ed25519" }, key, hexToBytes(signatureHex), digest);
  } catch {
    return false;
  }
}

export async function buildSignedReceipt({ privateKeyHex, actor, kind, payload, prevHash, seq, ts }) {
  const payloadText = canonDumps(payload);
  const body = { actor, kind, payload: payloadText, prev_hash: prevHash, seq, ts };
  const bodyJson = canonDumps(body);
  const hash = await sha256Hex(bodyJson);
  const claim = {
    actor,
    amount: payload.amount,
    kind,
    ledgerSeq: seq,
    payloadHash: await sha256Hex(payloadText),
    prevHash,
    settlementId: String(payload.settlement_id || ""),
    ts,
    verifierIds: Array.isArray(payload.verifier_ids)
      ? payload.verifier_ids.join(",")
      : String(payload.verifier_ids || ""),
    workerId: String(payload.worker_id || payload.node_id || actor),
  };
  const digest = await digestFor(claim);
  const signature = await signDigest(privateKeyHex, digest);
  const signer = await publicKeyHexFromPrivate(privateKeyHex);
  const typed = workClaimDocument(claim);
  return {
    seq,
    ts,
    actor,
    kind,
    payload: payloadText,
    prev_hash: prevHash,
    hash,
    canon: "v1",
    body_json: bodyJson,
    signature,
    signer,
    typed_json: typed,
    typed_data: typed,
    amount: payload.amount,
  };
}

export async function verifyReceipt(entry, publicKeyHex) {
  try {
    const body = {
      actor: entry.actor,
      kind: entry.kind,
      payload: entry.payload,
      prev_hash: entry.prev_hash,
      seq: entry.seq,
      ts: entry.ts,
    };
    const bodyJson = canonDumps(body);
    if (entry.body_json && entry.body_json !== bodyJson) return { ok: false, error: "canon_mismatch" };
    const hash = await sha256Hex(bodyJson);
    if (hash !== entry.hash) return { ok: false, error: "hash_mismatch" };
    if (String(entry.signer || "").toLowerCase() !== String(publicKeyHex || "").toLowerCase()) {
      return { ok: false, error: "signer_mismatch" };
    }
    const message = entry.typed_data?.message || entry.typed_json?.message;
    if (!message) return { ok: false, error: "typed_data_missing" };
    const claim = {
      actor: message.actor,
      amount: message.amount,
      kind: message.kind,
      ledgerSeq: message.ledgerSeq,
      payloadHash: message.payloadHash,
      prevHash: message.prevHash,
      settlementId: String(message.settlementId || ""),
      ts: message.ts,
      verifierIds: String(message.verifierIds || ""),
      workerId: String(message.workerId || ""),
    };
    if (claim.amount !== entry.amount || claim.ledgerSeq !== entry.seq) {
      return { ok: false, error: "claim_mismatch" };
    }
    if (claim.payloadHash !== await sha256Hex(entry.payload)) return { ok: false, error: "payload_hash_mismatch" };
    const ok = await verifyDigest(publicKeyHex, await digestFor(claim), entry.signature);
    return { ok, error: ok ? "" : "signature_mismatch" };
  } catch (error) {
    return { ok: false, error: String(error && error.message ? error.message : error) };
  }
}

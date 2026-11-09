/**
 * Receipt binding and Base Sepolia Settled-log decode.
 *
 * The four digests are separate fields. A settlement must not treat the
 * Ollama manifest digest as the GGUF sha256, or the output hash as the input.
 */

export const BINDING_DIGESTS = ["input_digest", "manifest_digest", "output_digest", "weights_digest"];
export const VERIFIER_PAY = 2;
export const SETTLED_TOPIC = "0x63f88969def260b0a1db98b1f02b96eb9d0caf4a0a439db889fb314255facb6e";

export function normalizeDigest(value) {
  return String(value ?? "").trim().toLowerCase();
}

export function bindingOf(source) {
  const row = source || {};
  return {
    input_digest: String(row.input_digest || ""),
    manifest_digest: String(row.manifest_digest || row.model_digest || ""),
    output_digest: String(row.output_digest || row.output_hash || ""),
    weights_digest: String(row.weights_digest || ""),
  };
}

export function distinctDigests(source) {
  const binding = bindingOf(source);
  const values = BINDING_DIGESTS.map((key) => normalizeDigest(binding[key]));
  if (values.some((item) => !item)) return false;
  return new Set(values).size === values.length;
}

export function checkerPay(verdict) {
  if (verdict === "agree" || verdict === "disagree_deterministic") return VERIFIER_PAY;
  return 0;
}

export function settlementBindingHold(job) {
  const binding = bindingOf(job);
  const present = BINDING_DIGESTS.every((key) => normalizeDigest(binding[key]));
  if (!present) return "";
  if (!distinctDigests(binding)) return "held_indistinct_digests";
  return "";
}

function hexBody(value) {
  return String(value || "").replace(/^0x/i, "").toLowerCase();
}

function word(data, index) {
  const hex = hexBody(data);
  return hex.slice(index * 64, index * 64 + 64);
}

function addressFromWord(data, index) {
  const raw = word(data, index);
  if (!/^[0-9a-f]{64}$/.test(raw)) return "";
  return `0x${raw.slice(24)}`;
}

function uintFromWord(data, index) {
  const raw = word(data, index);
  if (!/^[0-9a-f]{64}$/.test(raw)) return null;
  const value = BigInt(`0x${raw}`);
  if (value > BigInt(Number.MAX_SAFE_INTEGER)) return null;
  return Number(value);
}

export function decodeSettledLog(log) {
  const topics = Array.isArray(log?.topics) ? log.topics : [];
  if (hexBody(topics[0]) !== SETTLED_TOPIC.slice(2)) return null;
  const settlementId = hexBody(topics[1]);
  const workerTopic = hexBody(topics[2]);
  if (!/^[0-9a-f]{64}$/.test(settlementId) || workerTopic.length !== 64) return null;
  const data = hexBody(log?.data);
  if (data.length < 64 * 7) return null;
  const workerAmount = uintFromWord(data, 2);
  const verifier1Amount = uintFromWord(data, 3);
  const verifier2Amount = uintFromWord(data, 4);
  const contributionMinor = uintFromWord(data, 5);
  if (workerAmount == null || verifier1Amount == null || verifier2Amount == null || contributionMinor == null) {
    return null;
  }
  const splitOk = workerAmount + verifier1Amount + verifier2Amount === contributionMinor
    && workerAmount * 10000 === contributionMinor * 9000
    && verifier1Amount * 10000 === contributionMinor * 500
    && verifier2Amount * 10000 === contributionMinor * 500;
  return {
    event: "Settled",
    address: hexBody(log?.address) ? `0x${hexBody(log.address)}` : "",
    settlement_id: `0x${settlementId}`,
    worker: `0x${workerTopic.slice(24)}`,
    verifier1: addressFromWord(data, 0),
    verifier2: addressFromWord(data, 1),
    worker_amount: workerAmount,
    verifier1_amount: verifier1Amount,
    verifier2_amount: verifier2Amount,
    contribution_minor: contributionMinor,
    receipt_root: `0x${word(data, 6)}`,
    split_ok: splitOk,
    chain_id: 84532,
  };
}

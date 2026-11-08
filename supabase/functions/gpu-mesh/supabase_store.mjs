/**Postgres adapter. Service role only. Tables are RLS-locked against anon. */

function num(value, fallback = 0) {
  if (value === null || value === undefined || value === "") return fallback;
  const n = Number(value);
  return Number.isFinite(n) ? n : fallback;
}

function fromNode(row) {
  if (!row) return null;
  return {
    ...row,
    models: Array.isArray(row.models) ? row.models : [],
    vram_mb: num(row.vram_mb),
    gpu_count: num(row.gpu_count),
    reputation: num(row.reputation, 100),
    strikes: num(row.strikes),
    credits: num(row.credits),
    escrow_credits: num(row.escrow_credits),
    suspicion: num(row.suspicion),
    trusted: num(row.trusted),
    verified_jobs: num(row.verified_jobs),
    consecutive_failures: num(row.consecutive_failures),
    jobs_completed: num(row.jobs_completed),
    jobs_failed: num(row.jobs_failed),
    inflight: num(row.inflight),
    max_inflight: num(row.max_inflight, 1),
    last_heartbeat: num(row.last_heartbeat),
    created_at: num(row.created_at),
    payout_address: String(row.payout_address || ""),
  };
}

function toNode(row) {
  return { ...row, models: row.models || [] };
}

function fromJob(row) {
  if (!row) return null;
  return {
    ...row,
    messages: Array.isArray(row.messages) ? row.messages : [],
    excluded: Array.isArray(row.excluded) ? row.excluded : [],
    temperature: num(row.temperature),
    max_tokens: num(row.max_tokens),
    seed: row.seed === null || row.seed === undefined ? null : num(row.seed),
    attempt: num(row.attempt),
    max_attempts: num(row.max_attempts, 3),
    prompt_tokens: num(row.prompt_tokens),
    completion_tokens: num(row.completion_tokens),
    duration_ms: num(row.duration_ms),
    credits_awarded: num(row.credits_awarded),
    created_at: num(row.created_at),
    assigned_at: num(row.assigned_at),
    completed_at: num(row.completed_at),
    deadline_at: num(row.deadline_at),
    lease_generation: num(row.lease_generation),
    lease_expires_at: num(row.lease_expires_at),
    priority: num(row.priority),
    settlement_tx_hash: String(row.settlement_tx_hash || ""),
    settlement_tx_url: String(row.settlement_tx_url || ""),
    settlement_status: String(row.settlement_status || ""),
  };
}

function toJob(row) {
  return {
    ...row,
    messages: row.messages || [],
    excluded: row.excluded || [],
    stop: row.stop ?? null,
  };
}

function fromChain(row) {
  if (!row) return null;
  return {
    ...row,
    amount: num(row.amount),
    mesh_credits: num(row.mesh_credits),
    created_at: num(row.created_at),
    updated_at: num(row.updated_at),
    receipt: row.receipt && typeof row.receipt === "string" ? JSON.parse(row.receipt) : (row.receipt || null),
    receipt_hash: String(row.receipt_hash || ""),
    tx_hash: String(row.tx_hash || ""),
    tx_url: String(row.tx_url || ""),
    detail: String(row.detail || ""),
    verifier1_id: String(row.verifier1_id || ""),
    verifier2_id: String(row.verifier2_id || ""),
  };
}

function toChain(row) {
  return {
    id: row.id,
    job_id: row.job_id,
    worker_id: row.worker_id,
    verifier1_id: row.verifier1_id || "",
    verifier2_id: row.verifier2_id || "",
    amount: row.amount || 0,
    mesh_credits: row.mesh_credits || 0,
    status: row.status,
    receipt: row.receipt || null,
    receipt_hash: row.receipt_hash || "",
    tx_hash: row.tx_hash || "",
    tx_url: row.tx_url || "",
    detail: row.detail || "",
    created_at: row.created_at || 0,
    updated_at: row.updated_at || 0,
  };
}

async function must(query) {
  const { data, error } = await query;
  if (error) throw new Error(error.message || "database error");
  return data;
}

export function createSupabaseStore(sb) {
  return {
    async getSigner() {
      return must(sb.from("gpumesh_signer").select("public_hex").eq("id", 1).maybeSingle());
    },
    async upsertSigner(row) {
      const { error } = await sb.from("gpumesh_signer").upsert({ id: 1, public_hex: row.public_hex });
      if (error) throw new Error("signer_publish_failed");
      return true;
    },
    async listNodes() {
      const data = await must(sb.from("gpumesh_nodes").select("*").limit(200));
      return (data || []).map(fromNode);
    },
    async countNodes() {
      const { count, error } = await sb.from("gpumesh_nodes").select("id", { count: "exact", head: true });
      if (error) throw new Error(error.message);
      return count || 0;
    },
    async insertNode(row) {
      await must(sb.from("gpumesh_nodes").insert(toNode(row)));
    },
    async saveNode(row) {
      await must(sb.from("gpumesh_nodes").update(toNode(row)).eq("id", row.id));
    },
    async nodeByTokenHash(hash) {
      const data = await must(sb.from("gpumesh_nodes").select("*").eq("token_hash", hash).maybeSingle());
      return fromNode(data);
    },
    async getJob(id) {
      const data = await must(sb.from("gpumesh_jobs").select("*").eq("id", id).maybeSingle());
      return fromJob(data);
    },
    async insertJob(row) {
      await must(sb.from("gpumesh_jobs").insert(toJob(row)));
    },
    async saveJob(row) {
      await must(sb.from("gpumesh_jobs").update(toJob(row)).eq("id", row.id));
    },
    async leaseJob(id, patch) {
      const { data, error } = await sb.from("gpumesh_jobs").update({ ...patch, status: "leased" }).eq("id", id).eq("status", "queued").select("*").maybeSingle();
      if (error) throw new Error(error.message);
      return fromJob(data);
    },
    async listJobs(statuses) {
      const data = await must(sb.from("gpumesh_jobs").select("*").in("status", statuses).limit(200));
      return (data || []).map(fromJob);
    },
    async tip() {
      const data = await must(sb.from("gpumesh_ledger").select("seq,hash").order("seq", { ascending: false }).limit(1).maybeSingle());
      if (!data) return null;
      return { seq: num(data.seq), hash: data.hash };
    },
    async insertLedger(entry) {
      const { error } = await sb.from("gpumesh_ledger").insert(entry);
      if (error && error.code === "23505") return false;
      if (error) throw new Error(error.message);
      return true;
    },
    async ledgerBySeq(seq) {
      const data = await must(sb.from("gpumesh_ledger").select("*").eq("seq", seq).maybeSingle());
      return data;
    },
    async ledgerByHash(hash) {
      return await must(sb.from("gpumesh_ledger").select("*").eq("hash", hash).maybeSingle());
    },
    async listLedger(limit) {
      const data = await must(sb.from("gpumesh_ledger").select("*").order("seq", { ascending: false }).limit(limit));
      return data || [];
    },
    async getSettlement(key) {
      return await must(sb.from("gpumesh_settlements").select("*").eq("idempotency_key", key).maybeSingle());
    },
    async insertSettlement(row) {
      const { error } = await sb.from("gpumesh_settlements").insert(row);
      if (error && error.code === "23505") return false;
      if (error) throw new Error(error.message);
      return true;
    },
    async hitRate(bucket, windowStart) {
      const current = await must(sb.from("gpumesh_rate").select("window_start,hits").eq("bucket", bucket).maybeSingle());
      if (!current || num(current.window_start) !== windowStart) {
        const { error } = await sb.from("gpumesh_rate").upsert({ bucket, window_start: windowStart, hits: 1 });
        if (error) throw new Error(error.message);
        return 1;
      }
      const hits = num(current.hits) + 1;
      await must(sb.from("gpumesh_rate").update({ hits }).eq("bucket", bucket).eq("window_start", windowStart));
      return hits;
    },
    async addChunk(jobId, seq, text) {
      const { error } = await sb.from("gpumesh_chunks").upsert({ job_id: jobId, seq, text });
      if (error) throw new Error(error.message);
    },
    async getChainSettlement(id) {
      return fromChain(await must(sb.from("gpumesh_chain_settlements").select("*").eq("id", id).maybeSingle()));
    },
    async chainSettlementByJob(jobId) {
      return fromChain(await must(sb.from("gpumesh_chain_settlements").select("*").eq("job_id", jobId).maybeSingle()));
    },
    async insertChainSettlement(row) {
      const { error } = await sb.from("gpumesh_chain_settlements").insert(toChain(row));
      if (error && error.code === "23505") return false;
      if (error) throw new Error(error.message);
      return true;
    },
    async saveChainSettlement(row) {
      await must(sb.from("gpumesh_chain_settlements").update(toChain(row)).eq("id", row.id));
    },
    async listChainSettlements(statuses) {
      let query = sb.from("gpumesh_chain_settlements").select("*").order("created_at", { ascending: true }).limit(200);
      if (statuses && statuses.length) query = query.in("status", statuses);
      const data = await must(query);
      return (data || []).map(fromChain);
    },
    async stats() {
      const nodes = await must(sb.from("gpumesh_nodes").select("status,credits,escrow_credits").limit(200));
      async function count(build) {
        const { count, error } = await build;
        if (error) throw new Error(error.message);
        return count || 0;
      }
      const jobsVerified = await count(sb.from("gpumesh_jobs").select("id", { count: "exact", head: true }).eq("kind", "inference").eq("status", "verified"));
      const jobsQueued = await count(sb.from("gpumesh_jobs").select("id", { count: "exact", head: true }).eq("status", "queued"));
      const rows = nodes || [];
      return {
        workers_registered: rows.length,
        workers_online: rows.filter((row) => row.status === "online").length,
        jobs_verified: jobsVerified,
        jobs_queued: jobsQueued,
        credits_released: rows.reduce((sum, row) => sum + num(row.credits), 0),
        credits_held: rows.reduce((sum, row) => sum + num(row.escrow_credits), 0),
      };
    },
  };
}

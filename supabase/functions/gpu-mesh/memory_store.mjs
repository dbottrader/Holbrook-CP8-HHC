/**In-memory store used by protocol tests. The Supabase store speaks the same methods. */

export function createMemoryStore() {
  const nodes = new Map();
  const jobs = new Map();
  const ledger = [];
  const settlements = new Map();
  const rates = new Map();
  const chunks = [];
  const chain = new Map();
  let signer = null;

  return {
    async getSigner() {
      return signer ? { ...signer } : null;
    },
    async upsertSigner(row) {
      signer = { public_hex: row.public_hex };
      return true;
    },
    async listNodes() {
      return [...nodes.values()].map((row) => structuredClone(row));
    },
    async countNodes() {
      return nodes.size;
    },
    async insertNode(row) {
      nodes.set(row.id, structuredClone(row));
    },
    async saveNode(row) {
      nodes.set(row.id, structuredClone(row));
    },
    async nodeByTokenHash(hash) {
      for (const row of nodes.values()) {
        if (row.token_hash === hash) return structuredClone(row);
      }
      return null;
    },
    async getJob(id) {
      const row = jobs.get(id);
      return row ? structuredClone(row) : null;
    },
    async insertJob(row) {
      jobs.set(row.id, structuredClone(row));
    },
    async saveJob(row) {
      jobs.set(row.id, structuredClone(row));
    },
    async leaseJob(id, patch) {
      const row = jobs.get(id);
      if (!row || row.status !== "queued") return null;
      const next = { ...row, ...patch, status: "leased" };
      jobs.set(id, next);
      return structuredClone(next);
    },
    async listJobs(statuses) {
      return [...jobs.values()].filter((row) => statuses.includes(row.status)).map((row) => structuredClone(row));
    },
    async tip() {
      if (!ledger.length) return null;
      const last = ledger[ledger.length - 1];
      return { seq: last.seq, hash: last.hash };
    },
    async insertLedger(entry) {
      if (ledger.some((row) => row.seq === entry.seq)) return false;
      ledger.push(structuredClone(entry));
      ledger.sort((a, b) => a.seq - b.seq);
      return true;
    },
    async ledgerBySeq(seq) {
      const row = ledger.find((item) => item.seq === seq);
      return row ? structuredClone(row) : null;
    },
    async ledgerByHash(hash) {
      const row = ledger.find((item) => item.hash === hash);
      return row ? structuredClone(row) : null;
    },
    async listLedger(limit) {
      return ledger.slice(-limit).reverse().map((row) => structuredClone(row));
    },
    async getSettlement(key) {
      const row = settlements.get(key);
      return row ? { ...row } : null;
    },
    async insertSettlement(row) {
      if (settlements.has(row.idempotency_key)) return false;
      settlements.set(row.idempotency_key, { ...row });
      return true;
    },
    async hitRate(bucket, windowStart) {
      const row = rates.get(bucket);
      if (!row || row.window_start !== windowStart) {
        rates.set(bucket, { window_start: windowStart, hits: 1 });
        return 1;
      }
      row.hits += 1;
      return row.hits;
    },
    async addChunk(jobId, seq, text) {
      chunks.push({ job_id: jobId, seq, text });
    },
    async getChainSettlement(id) {
      const row = chain.get(id);
      return row ? structuredClone(row) : null;
    },
    async chainSettlementByJob(jobId) {
      for (const row of chain.values()) {
        if (row.job_id === jobId) return structuredClone(row);
      }
      return null;
    },
    async insertChainSettlement(row) {
      if (chain.has(row.id)) return false;
      for (const existing of chain.values()) {
        if (existing.job_id === row.job_id) return false;
      }
      chain.set(row.id, structuredClone(row));
      return true;
    },
    async saveChainSettlement(row) {
      chain.set(row.id, structuredClone(row));
    },
    async listChainSettlements(statuses) {
      return [...chain.values()]
        .filter((row) => !statuses || statuses.includes(row.status))
        .sort((a, b) => (a.created_at - b.created_at) || String(a.id).localeCompare(String(b.id)))
        .map((row) => structuredClone(row));
    },
    async stats() {
      const nodeRows = [...nodes.values()];
      const jobRows = [...jobs.values()];
      return {
        workers_registered: nodeRows.length,
        workers_online: nodeRows.filter((row) => row.status === "online").length,
        jobs_verified: jobRows.filter((row) => row.kind === "inference" && row.status === "verified").length,
        jobs_queued: jobRows.filter((row) => row.status === "queued").length,
        credits_released: nodeRows.reduce((sum, row) => sum + (row.credits || 0), 0),
        credits_held: nodeRows.reduce((sum, row) => sum + (row.escrow_credits || 0), 0),
      };
    },
  };
}

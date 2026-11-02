import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

import { handlePublicRead } from "../supabase/functions/moltbook-api/read_model.mjs";

const HUMAN = "11111111-1111-4111-8111-111111111111";
const AGENT = "22222222-2222-4222-8222-222222222222";
const ROOM = "33333333-3333-4333-8333-333333333333";
const HUMAN_POST = "44444444-4444-4444-8444-444444444444";
const AGENT_POST = "55555555-5555-4555-8555-555555555555";
const HUMAN_RECEIPT = "66666666-6666-4666-8666-666666666666";
const AGENT_RECEIPT = "77777777-7777-4777-8777-777777777777";

function chain(source) {
  const state = {
    rows: source.map((row) => ({ ...row })),
    single: false,
    error: null,
    orders: [],
    limit: null,
  };
  const api = {
    select() {
      return api;
    },
    eq(col, val) {
      if (val == null || val === "null") {
        state.error = { message: 'invalid input syntax for type uuid: "null"' };
        return api;
      }
      state.rows = state.rows.filter((row) => row[col] === val);
      return api;
    },
    in(col, vals) {
      const allowed = new Set(vals);
      state.rows = state.rows.filter((row) => allowed.has(row[col]));
      return api;
    },
    ilike(col, pattern) {
      const body = String(pattern).replace(/[.+?^${}()|[\]\\]/g, "\\$&").replace(/%/g, ".*").replace(/_/g, ".");
      const re = new RegExp(`^${body}$`, "i");
      state.rows = state.rows.filter((row) => re.test(String(row[col] ?? "")));
      return api;
    },
    order(col, opts) {
      state.orders.push({ col, ascending: Boolean(opts && opts.ascending) });
      return api;
    },
    limit(n) {
      state.limit = n;
      return api;
    },
    maybeSingle() {
      state.single = true;
      return api;
    },
    then(resolve, reject) {
      try {
        if (state.error) {
          resolve({ data: null, error: state.error });
          return;
        }
        const rows = state.rows.slice();
        for (let i = state.orders.length - 1; i >= 0; i -= 1) {
          const order = state.orders[i];
          rows.sort((a, b) => {
            if (a[order.col] === b[order.col]) return 0;
            const less = a[order.col] < b[order.col];
            if (order.ascending) return less ? -1 : 1;
            return less ? 1 : -1;
          });
        }
        const limited = state.limit == null ? rows : rows.slice(0, state.limit);
        resolve({ data: state.single ? (limited[0] || null) : limited, error: null });
      } catch (err) {
        reject(err);
      }
    },
  };
  return api;
}

function database() {
  const calls = [];
  const tables = {
    cp8_moltbook_posts: [
      {
        post_id: HUMAN_POST,
        room_id: ROOM,
        author_agent_id: null,
        author_human_id: HUMAN,
        author_kind: "human",
        parent_post_id: null,
        thread_root_post_id: HUMAN_POST,
        kind: "post",
        status: "OBSERVED",
        promotion: "HOLD",
        content: "a human note",
        content_hash: "abc",
        parent_hash: null,
        auth_mode: "SUPABASE_AUTH",
        created_at: "2026-10-31T00:00:00Z",
        evidence_refs: ["surface:human-ui"],
      },
      {
        post_id: AGENT_POST,
        room_id: ROOM,
        author_agent_id: AGENT,
        author_human_id: null,
        author_kind: "agent",
        parent_post_id: null,
        thread_root_post_id: AGENT_POST,
        kind: "post",
        status: "OBSERVED",
        promotion: "HOLD",
        content: "an agent note",
        content_hash: "def",
        parent_hash: null,
        auth_mode: "CAPABILITY_TOKEN",
        created_at: "2026-10-30T00:00:00Z",
        evidence_refs: ["surface:rest"],
      },
    ],
    cp8_moltbook_public_posts: [
      {
        post_id: HUMAN_POST,
        room_slug: "cp8-ops",
        room_title: "CP8 Ops",
        author_kind: "human",
        author_handle: "ada",
        author_display_name: "Ada",
        author_human_id: HUMAN,
        author_agent_id: null,
        parent_post_id: null,
        thread_root_post_id: HUMAN_POST,
        kind: "post",
        status: "OBSERVED",
        promotion: "HOLD",
        content: "a human note",
        content_hash: "abc",
        parent_hash: null,
        auth_mode: "SUPABASE_AUTH",
        created_at: "2026-10-31T00:00:00Z",
        has_bound_receipt: false,
      },
      {
        post_id: AGENT_POST,
        room_slug: "cp8-ops",
        room_title: "CP8 Ops",
        author_kind: "agent",
        author_handle: "ace",
        author_display_name: "Ace",
        author_human_id: null,
        author_agent_id: AGENT,
        parent_post_id: null,
        thread_root_post_id: AGENT_POST,
        kind: "post",
        status: "OBSERVED",
        promotion: "HOLD",
        content: "an agent note",
        content_hash: "def",
        parent_hash: null,
        auth_mode: "CAPABILITY_TOKEN",
        created_at: "2026-10-30T00:00:00Z",
        has_bound_receipt: true,
      },
    ],
    cp8_moltbook_human_profiles: [
      { human_id: HUMAN, handle: "ada", display_name: "Ada", actor_kind: "human" },
    ],
    cp8_agents: [
      { agent_id: AGENT, handle: "ace", display_name: "Ace" },
    ],
    cp8_agent_identity_cards: [
      { agent_id: AGENT, handle: "ace", cp8_numeric_id: 7 },
    ],
    cp8_moltbook_rooms: [
      { room_id: ROOM, slug: "cp8-ops", title: "CP8 Ops" },
    ],
    cp8_inference_receipts: [
      {
        receipt_id: "99999999-9999-4999-8999-999999999999",
        seq: 1,
        ts: 1,
        actor: "groq-fallback",
        kind: "groq_inference_receipt",
        payload: "{}",
        prev_hash: "0".repeat(64),
        hash: "ab".repeat(32),
        canon: "v1",
        body_json: "{}",
        signature: "cd".repeat(64),
        signer: "ef".repeat(32),
        typed_json: { primaryType: "WorkClaim" },
        amount: 0,
        verification: { ok: true, method: "exact_match" },
        output_text: "GROQ_MESH_OK",
        output_sha256: "11".repeat(32),
        request_id: "req_1",
        created_at: "2026-11-02T05:13:00Z",
      },
    ],
    cp8_moltbook_receipts: [
      {
        receipt_id: HUMAN_RECEIPT,
        post_id: HUMAN_POST,
        action: "post",
        actor_kind: "human",
        actor_agent_id: null,
        actor_human_id: HUMAN,
        receipt_hash: "human-receipt",
        cp8_receipt_id: null,
        created_at: "2026-10-31T00:00:01Z",
      },
      {
        receipt_id: AGENT_RECEIPT,
        post_id: AGENT_POST,
        action: "post",
        actor_kind: "agent",
        actor_agent_id: AGENT,
        actor_human_id: null,
        receipt_hash: "agent-receipt",
        cp8_receipt_id: "88888888-8888-4888-8888-888888888888",
        created_at: "2026-10-30T00:00:01Z",
      },
    ],
  };
  return {
    calls,
    from(table) {
      calls.push(table);
      return chain(tables[table] || []);
    },
  };
}

function get(path) {
  return new Request("https://example.test/functions/v1/moltbook-api" + path);
}

test("GET /posts lists human and agent posts", async () => {
  const db = database();
  const res = await handlePublicRead(get("/posts?limit=40"), db);
  assert.equal(res.status, 200);
  assert.deepEqual(res.body.posts.map((post) => post.author_kind), ["human", "agent"]);
  assert.equal(res.body.posts[0].author_handle, "ada");
  assert.deepEqual(res.body.posts[0].evidence_refs, ["surface:human-ui"]);
});

test("GET /posts/{id} returns a human post and its receipt without a null uuid lookup", async () => {
  const db = database();
  const res = await handlePublicRead(get("/posts/" + HUMAN_POST), db);
  assert.equal(res.status, 200);
  assert.equal(res.body.post.author_kind, "human");
  assert.equal(res.body.post.author.actor_kind, "human");
  assert.equal(res.body.post.author.handle, "ada");
  assert.equal(res.body.post.room.title, "CP8 Ops");
  assert.equal(res.body.post.identity, null);
  assert.equal(res.body.receipts.length, 1);
  assert.equal(res.body.receipts[0].actor_kind, "human");
  assert.equal(res.body.receipts[0].actor_human_id, HUMAN);
  assert.equal(res.body.receipts[0].receipt_hash, "human-receipt");
  assert.equal(res.body.has_bound_receipt, false);
  assert.equal(db.calls.includes("cp8_agents"), false);
  assert.equal(db.calls.includes("cp8_agent_identity_cards"), false);
});

test("GET /posts/{id} still loads an agent author and identity card", async () => {
  const db = database();
  const res = await handlePublicRead(get("/posts/" + AGENT_POST), db);
  assert.equal(res.status, 200);
  assert.equal(res.body.post.author.actor_kind, "agent");
  assert.equal(res.body.post.author.handle, "ace");
  assert.equal(res.body.post.identity.cp8_numeric_id, 7);
  assert.equal(res.body.receipts[0].actor_agent_id, AGENT);
  assert.equal(res.body.has_bound_receipt, true);
  assert.equal(db.calls.includes("cp8_moltbook_human_profiles"), false);
});

test("room posts include the human post the agent inner join used to drop", async () => {
  const db = database();
  const res = await handlePublicRead(get("/rooms/cp8-ops/posts?limit=20"), db);
  assert.equal(res.status, 200);
  const kinds = res.body.posts.map((post) => post.author_kind);
  assert.ok(kinds.includes("human"));
  assert.ok(kinds.includes("agent"));
});

test("thread and search keep the human post", async () => {
  const db = database();
  const thread = await handlePublicRead(get("/thread/" + HUMAN_POST), db);
  assert.equal(thread.body.posts.length, 1);
  assert.equal(thread.body.posts[0].author_kind, "human");
  const found = await handlePublicRead(get("/search?q=human%20note"), db);
  assert.equal(found.body.posts.length, 1);
  assert.equal(found.body.posts[0].post_id, HUMAN_POST);
});

test("GET /inference-receipts/{id} returns one signed receipt", async () => {
  const db = database();
  const res = await handlePublicRead(get("/inference-receipts/99999999-9999-4999-8999-999999999999"), db);
  assert.equal(res.status, 200);
  assert.equal(res.body.receipt.actor, "groq-fallback");
  assert.equal(res.body.receipt.amount, 0);
  assert.equal(res.body.promotion, "HOLD");
  const missing = await handlePublicRead(get("/inference-receipts/88888888-8888-4888-8888-888888888888"), db);
  assert.equal(missing.status, 404);
  const bad = await handlePublicRead(get("/inference-receipts/not-a-uuid"), db);
  assert.equal(bad.status, 404);
});

test("a missing post is 404 and an unknown route is not claimed", async () => {
  const db = database();
  const missing = await handlePublicRead(get("/posts/99999999-9999-4999-8999-999999999999"), db);
  assert.equal(missing.status, 404);
  assert.equal(missing.body.error, "post_not_found");
  const other = await handlePublicRead(get("/health"), db);
  assert.equal(other, null);
});

test("the Deno entry calls the read model and keeps identity routes", () => {
  const source = readFileSync(new URL("../supabase/functions/moltbook-api/index.ts", import.meta.url), "utf8");
  assert.match(source, /handlePublicRead/);
  assert.match(source, /version: "0\.3\.5"/);
  assert.match(source, /inference-receipts/);
  assert.match(source, /agents\/identities/);
  assert.equal(source.includes("slug,name"), false);
  assert.equal(source.includes(".eq('agent_id', post.author_agent_id)"), false);
  assert.equal(source.includes("cp8_moltbook_feed"), false);
});

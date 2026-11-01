// Public read routes for moltbook-api.
//
// Reused from the live 0.3.3 function (itself the 2026-08-20 snapshot plus
// identity routes) and from the human-author lookup designed in
// provenance/moltbook/deploy/2026-10-24-get-post-0.3.3 on PR 36.
// Room, search, and thread lists read cp8_moltbook_public_posts, the view
// added by supabase/migrations/20261024143000_moltbook_human_actors.sql,
// so a human row is not dropped by the agent inner join in cp8_moltbook_feed.
//
// A human post stores author_agent_id as null. PostgREST sends a null uuid
// filter as the string "null", and Postgres rejects it. These routes filter
// a uuid column only when the value is a uuid.

const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

const LIST_COLUMNS = [
  "post_id",
  "room_slug",
  "room_title",
  "author_kind",
  "author_handle",
  "author_display_name",
  "author_human_id",
  "author_agent_id",
  "parent_post_id",
  "thread_root_post_id",
  "kind",
  "status",
  "promotion",
  "content",
  "content_hash",
  "parent_hash",
  "auth_mode",
  "created_at",
  "has_bound_receipt",
].join(",");

const POST_COLUMNS = [
  "post_id",
  "room_id",
  "author_agent_id",
  "author_human_id",
  "author_kind",
  "parent_post_id",
  "thread_root_post_id",
  "kind",
  "status",
  "promotion",
  "content",
  "content_hash",
  "parent_hash",
  "auth_mode",
  "created_at",
].join(",");

const RECEIPT_COLUMNS = [
  "receipt_id",
  "action",
  "actor_kind",
  "actor_agent_id",
  "actor_human_id",
  "receipt_hash",
  "cp8_receipt_id",
  "created_at",
].join(",");

export function isUuid(value) {
  return typeof value === "string" && UUID.test(value);
}

function clamp(value, fallback, min, max) {
  const n = Number(value);
  if (!Number.isFinite(n)) return fallback;
  return Math.min(Math.max(Math.trunc(n), min), max);
}

function segments(url) {
  const parts = url.pathname.split("/").filter(Boolean);
  const marker = parts.indexOf("moltbook-api");
  return marker >= 0 ? parts.slice(marker + 1) : parts;
}

async function unwrap(query) {
  const { data, error } = await query;
  if (error) {
    const message = error.message || String(error);
    throw new Error(message);
  }
  return data;
}

async function attachEvidence(db, posts) {
  const ids = posts.map((post) => post.post_id).filter(isUuid);
  if (!ids.length) {
    return posts.map((post) => ({ ...post, evidence_refs: post.evidence_refs || [] }));
  }
  const extra = await unwrap(
    db.from("cp8_moltbook_posts").select("post_id,evidence_refs").in("post_id", ids),
  );
  const byId = new Map((extra || []).map((row) => [row.post_id, row.evidence_refs || []]));
  return posts.map((post) => ({
    ...post,
    evidence_refs: byId.has(post.post_id) ? byId.get(post.post_id) : [],
  }));
}

async function publicPosts(db, { room, threadRoot, contentIlike, limit, ascending }) {
  let query = db.from("cp8_moltbook_public_posts").select(LIST_COLUMNS);
  if (room) query = query.eq("room_slug", room);
  if (threadRoot) {
    if (!isUuid(threadRoot)) throw new Error('invalid input syntax for type uuid: "null"');
    query = query.eq("thread_root_post_id", threadRoot);
  }
  if (contentIlike) query = query.ilike("content", contentIlike);
  query = query.order("created_at", { ascending: Boolean(ascending) });
  if (limit) query = query.limit(limit);
  const rows = await unwrap(query);
  return attachEvidence(db, rows || []);
}

function authorKindOf(post) {
  return post && post.author_kind === "human" ? "human" : "agent";
}

async function loadDetail(db, postId) {
  if (!isUuid(postId)) return { status: 404, body: { error: "post_not_found" } };
  const post = await unwrap(
    db.from("cp8_moltbook_posts").select(POST_COLUMNS).eq("post_id", postId).maybeSingle(),
  );
  if (!post) return { status: 404, body: { error: "post_not_found" } };

  const kind = authorKindOf(post);
  const jobs = [];
  const names = [];

  if (kind === "human" && isUuid(post.author_human_id)) {
    names.push("author");
    jobs.push(unwrap(
      db.from("cp8_moltbook_human_profiles")
        .select("handle,display_name,actor_kind")
        .eq("human_id", post.author_human_id)
        .maybeSingle(),
    ));
  } else if (kind === "agent" && isUuid(post.author_agent_id)) {
    names.push("author");
    jobs.push(unwrap(
      db.from("cp8_agents").select("handle,display_name").eq("agent_id", post.author_agent_id).maybeSingle(),
    ));
    names.push("identity");
    jobs.push(unwrap(
      db.from("cp8_agent_identity_cards").select("*").eq("agent_id", post.author_agent_id).maybeSingle(),
    ));
  }

  if (isUuid(post.room_id)) {
    names.push("room");
    jobs.push(unwrap(
      db.from("cp8_moltbook_rooms").select("slug,title").eq("room_id", post.room_id).maybeSingle(),
    ));
  }

  names.push("receipts");
  jobs.push(unwrap(
    db.from("cp8_moltbook_receipts")
      .select(RECEIPT_COLUMNS)
      .eq("post_id", post.post_id)
      .order("created_at", { ascending: true }),
  ));

  const results = await Promise.all(jobs);
  const got = {};
  names.forEach((name, index) => {
    got[name] = results[index];
  });
  const author = got.author ? { ...got.author, actor_kind: kind } : null;
  const receipts = Array.isArray(got.receipts) ? got.receipts : [];
  return {
    status: 200,
    body: {
      post: {
        ...post,
        author,
        identity: got.identity || null,
        room: got.room || null,
      },
      receipts,
      has_bound_receipt: receipts.some((receipt) => Boolean(receipt && receipt.cp8_receipt_id)),
    },
  };
}

export async function handlePublicRead(req, db) {
  if (!req || req.method !== "GET") return null;
  const url = new URL(req.url);
  const p = segments(url);

  if (p[0] === "posts" && p.length === 1) {
    const room = url.searchParams.get("room");
    const posts = await publicPosts(db, {
      room: room ? String(room) : "",
      limit: clamp(url.searchParams.get("limit"), 50, 1, 200),
      ascending: false,
    });
    return { status: 200, body: { posts } };
  }

  if (p[0] === "posts" && p[1] && p.length === 2) {
    return loadDetail(db, p[1]);
  }

  if (p[0] === "rooms" && p[2] === "posts") {
    const posts = await publicPosts(db, {
      room: String(p[1] || ""),
      limit: clamp(url.searchParams.get("limit"), 50, 1, 200),
      ascending: false,
    });
    return { status: 200, body: { posts } };
  }

  if (p[0] === "thread" && p[1]) {
    if (!isUuid(p[1])) return { status: 200, body: { posts: [] } };
    const root = await unwrap(
      db.from("cp8_moltbook_posts").select("thread_root_post_id").eq("post_id", p[1]).maybeSingle(),
    );
    if (!root || !isUuid(root.thread_root_post_id)) return { status: 200, body: { posts: [] } };
    const posts = await publicPosts(db, { threadRoot: root.thread_root_post_id, ascending: true });
    return { status: 200, body: { posts } };
  }

  if (p[0] === "search") {
    const q = String(url.searchParams.get("q") || "").trim();
    if (q.length < 1 || q.length > 200) throw new Error("Invalid query");
    const room = url.searchParams.get("room");
    const posts = await publicPosts(db, {
      room: room ? String(room) : "",
      contentIlike: `%${q}%`,
      limit: clamp(url.searchParams.get("limit"), 20, 1, 100),
      ascending: false,
    });
    return { status: 200, body: { posts } };
  }

  return null;
}

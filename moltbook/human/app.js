import { createClient } from "https://esm.sh/@supabase/supabase-js@2.45.4";

const config = window.MOLTBOOK_HUMAN_CONFIG || {};
const redirectTo = config.redirectTo || `${window.location.origin}${window.location.pathname}`;
const authStatus = document.querySelector("#auth-status");
const postStatus = document.querySelector("#post-status");
const sessionNode = document.querySelector("#session");
const roomsNode = document.querySelector("#rooms");
const identitiesNode = document.querySelector("#identities");
const feedNode = document.querySelector("#feed");
const feedTitle = document.querySelector("#feed-title");
const reader = document.querySelector("#reader");
const readerTitle = document.querySelector("#reader-title");
const readerBody = document.querySelector("#reader-body");
const repliesNode = document.querySelector("#replies");
const composerTitle = document.querySelector("#composer-title");
const publish = document.querySelector("#publish");
const cancelReply = document.querySelector("#cancel-reply");
const signOut = document.querySelector("#sign-out");
const fundButton = document.querySelector("#fund-bounty");
const bountyStatus = document.querySelector("#bounty-status");
const bountyList = document.querySelector("#bounty-list");
const balanceNode = document.querySelector("#sim-balance");
const bountyReader = document.querySelector("#bounty-reader");
const bountyReaderTitle = document.querySelector("#bounty-reader-title");
const bountyReaderBody = document.querySelector("#bounty-reader-body");
const bountyAttempts = document.querySelector("#bounty-attempts");
const bountyVerdicts = document.querySelector("#bounty-verdicts");
const bountyTransfers = document.querySelector("#bounty-transfers");
const promoteButton = document.querySelector("#promote-bounty");

const state = {
  client: null,
  user: null,
  profile: null,
  room: null,
  parent: null,
  bounty: null,
};

function say(node, text) {
  node.textContent = text || "";
}

function badge(kind) {
  if (kind === "human") return `<span class="badge human">Human</span>`;
  if (kind === "agent") return `<span class="badge agent">Agent</span>`;
  return `<span class="badge unlabeled">Unlabeled</span>`;
}

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;");
}

function postCard(post) {
  const when = post.created_at ? new Date(post.created_at).toLocaleString() : "";
  return `
    <li class="post">
      <div>${badge(post.author_kind)}<span class="hold">${escapeHtml(post.promotion || "HOLD")}</span></div>
      <p class="meta">${escapeHtml(post.author_display_name || post.author_handle || "unknown")} · ${escapeHtml(post.author_handle || "")} · ${escapeHtml(post.kind || "post")} · ${escapeHtml(when)}</p>
      <button class="link" type="button" data-open="${escapeHtml(post.post_id)}">${escapeHtml(post.content)}</button>
    </li>`;
}

function requireClient() {
  if (!config.supabaseUrl || !config.supabaseAnonKey) {
    throw new Error("Copy moltbook/human/config.example.js to config.js and set supabaseAnonKey to the project anon key.");
  }
  if (!state.client) {
    state.client = createClient(config.supabaseUrl, config.supabaseAnonKey, {
      auth: { persistSession: true, detectSessionInUrl: true, flowType: "pkce" },
    });
  }
  return state.client;
}

async function loadRooms() {
  const client = requireClient();
  const { data, error } = await client
    .from("cp8_moltbook_rooms")
    .select("slug,title,description,status,created_at")
    .order("title");
  if (error) throw error;
  roomsNode.innerHTML = (data || []).map((room) =>
    `<li><button type="button" data-room="${escapeHtml(room.slug)}">${escapeHtml(room.title)}</button><div class="meta">${escapeHtml(room.slug)}</div></li>`
  ).join("");
  if (!state.room && data && data[0]) state.room = data[0].slug;
}

async function loadIdentities() {
  const client = requireClient();
  const { data, error } = await client
    .from("cp8_moltbook_identity_directory")
    .select("handle,actor_kind,display_name")
    .order("actor_kind")
    .order("handle")
    .limit(200);
  if (error) throw error;
  identitiesNode.innerHTML = (data || []).map((row) =>
    `<li>${badge(row.actor_kind)} ${escapeHtml(row.display_name)} <span class="meta">${escapeHtml(row.handle)}</span></li>`
  ).join("");
}

async function loadFeed() {
  const client = requireClient();
  feedTitle.textContent = state.room ? `Feed · ${state.room}` : "Feed";
  if (!state.room) {
    feedNode.innerHTML = "";
    return;
  }
  const { data, error } = await client
    .from("cp8_moltbook_public_posts")
    .select("post_id,room_slug,author_kind,author_handle,author_display_name,kind,promotion,content,content_hash,parent_post_id,thread_root_post_id,created_at,has_bound_receipt")
    .eq("room_slug", state.room)
    .is("parent_post_id", null)
    .order("created_at", { ascending: false })
    .limit(50);
  if (error) throw error;
  feedNode.innerHTML = (data || []).map(postCard).join("") || `<li class="meta">No posts in this room yet.</li>`;
}

async function openPost(postId) {
  const client = requireClient();
  const { data: rows, error } = await client
    .from("cp8_moltbook_public_posts")
    .select("post_id,room_slug,author_kind,author_handle,author_display_name,kind,promotion,content,content_hash,parent_hash,parent_post_id,thread_root_post_id,created_at,has_bound_receipt,auth_mode")
    .eq("post_id", postId)
    .limit(1);
  if (error) throw error;
  const post = rows && rows[0];
  if (!post) throw new Error("post not found");
  state.parent = post;
  reader.hidden = false;
  readerTitle.textContent = post.kind === "reply" ? "Reply" : "Post";
  readerBody.innerHTML = `
    <div>${badge(post.author_kind)}<span class="hold">${escapeHtml(post.promotion)}</span></div>
    <p class="meta">${escapeHtml(post.author_display_name || "")} · ${escapeHtml(post.author_handle || "")} · ${escapeHtml(post.auth_mode || "")} · bound receipt ${post.has_bound_receipt ? "yes" : "no"}</p>
    <p>${escapeHtml(post.content)}</p>
    <p class="meta">content_hash ${escapeHtml(post.content_hash)}</p>`;
  const { data: replies, error: replyError } = await client
    .from("cp8_moltbook_public_posts")
    .select("post_id,author_kind,author_handle,author_display_name,kind,promotion,content,content_hash,created_at")
    .eq("parent_post_id", post.post_id)
    .order("created_at", { ascending: true });
  if (replyError) throw replyError;
  repliesNode.innerHTML = (replies || []).map(postCard).join("") || `<li class="meta">No replies yet.</li>`;
  composerTitle.textContent = `Reply as human in ${post.room_slug}`;
  cancelReply.hidden = false;
  state.room = post.room_slug;
}

async function refreshProfile() {
  const client = requireClient();
  const { data: userData, error: userError } = await client.auth.getUser();
  if (userError) throw userError;
  state.user = userData.user;
  publish.disabled = !state.user;
  fundButton.disabled = !state.user;
  signOut.hidden = !state.user;
  if (!state.user) {
    state.profile = null;
    sessionNode.innerHTML = "Not signed in";
    balanceNode.textContent = "Sign in to see the simulated balance.";
    return;
  }
  const { data, error } = await client.rpc("cp8_moltbook_ensure_human_profile", {
    p_display_name: state.user.user_metadata?.display_name || state.user.user_metadata?.full_name || null,
    p_handle: null,
  });
  if (error) throw error;
  state.profile = data;
  sessionNode.innerHTML = `${badge(data.actor_kind)} ${escapeHtml(data.display_name)} <span class="meta">${escapeHtml(data.handle)}</span>`;
  await loadBalance();
  await loadBounties();
}

function minorToDisplay(minor) {
  return (Number(minor) / 1000).toFixed(3);
}

async function loadBalance() {
  if (!state.user) {
    balanceNode.textContent = "Sign in to see the simulated balance.";
    return;
  }
  const { data, error } = await requireClient().rpc("cp8_moltbook_my_sim_balance");
  if (error) throw error;
  balanceNode.textContent = `Simulated balance ${minorToDisplay(data)} HHC-SIM (${data} minor). Wallet class SIMULATED_ONLY_NO_MONETARY_AUTHORITY.`;
}

async function loadBounties() {
  const client = requireClient();
  const { data, error } = await client
    .from("cp8_moltbook_public_bounties")
    .select("bounty_id,title,status,promotion,price_minor,worker_minor,pool_minor,poster_handle,claimant_handle,room_slug")
    .order("opened_at", { ascending: false })
    .limit(50);
  if (error) throw error;
  bountyList.innerHTML = (data || []).map((bounty) => `
    <li class="post">
      <div><span class="hold">${escapeHtml(bounty.status)}</span><span class="hold">${escapeHtml(bounty.promotion)}</span></div>
      <button class="link" type="button" data-bounty="${escapeHtml(bounty.bounty_id)}">${escapeHtml(bounty.title)}</button>
      <p class="meta">${escapeHtml(bounty.room_slug)} · ${minorToDisplay(bounty.price_minor)} HHC-SIM · worker ${minorToDisplay(bounty.worker_minor)} · pool ${minorToDisplay(bounty.pool_minor)} · ${escapeHtml(bounty.poster_handle || "")}${bounty.claimant_handle ? " · claimed by " + escapeHtml(bounty.claimant_handle) : ""}</p>
    </li>`).join("") || `<li class="meta">No bounties yet.</li>`;
}

async function openBounty(bountyId) {
  const client = requireClient();
  const { data: rows, error } = await client
    .from("cp8_moltbook_public_bounties")
    .select("bounty_id,title,description,status,promotion,price_minor,worker_minor,pool_minor,poster_human_id,poster_handle,claimant_handle,artifact_hash,claim_generation,claim_lease_expires_at")
    .eq("bounty_id", bountyId)
    .limit(1);
  if (error) throw error;
  const bounty = rows && rows[0];
  if (!bounty) throw new Error("bounty not found");
  state.bounty = bounty;
  bountyReader.hidden = false;
  bountyReaderTitle.textContent = bounty.title;
  bountyReaderBody.innerHTML = `
    <p>${escapeHtml(bounty.description)}</p>
    <p class="meta">${escapeHtml(bounty.status)} · promotion ${escapeHtml(bounty.promotion)} · attempt ${escapeHtml(bounty.claim_generation)} · artifact ${escapeHtml(bounty.artifact_hash || "none yet")}</p>`;
  const attempts = await client.from("cp8_moltbook_public_bounty_attempts").select("generation,status,claimant_agent_id,artifact_hash").eq("bounty_id", bountyId).order("generation");
  if (attempts.error) throw attempts.error;
  bountyAttempts.innerHTML = (attempts.data || []).map((row) =>
    `<li class="meta">#${escapeHtml(row.generation)} ${escapeHtml(row.status)} ${escapeHtml(row.artifact_hash || "")}</li>`
  ).join("") || `<li class="meta">No attempts yet.</li>`;
  const verdicts = await client.from("cp8_moltbook_public_bounty_verdicts").select("passed,verifier_kind,verifier_handle,created_at").eq("bounty_id", bountyId).order("created_at");
  if (verdicts.error) throw verdicts.error;
  bountyVerdicts.innerHTML = (verdicts.data || []).map((row) =>
    `<li>${badge(row.verifier_kind)} ${escapeHtml(row.verifier_handle || "")} · ${row.passed ? "pass" : "fail"}</li>`
  ).join("") || `<li class="meta">No verdicts yet.</li>`;
  const transfers = await client.from("cp8_moltbook_public_transfers").select("kind,code,amount_minor,debit_account,credit_account").eq("bounty_id", bountyId).order("created_at");
  if (transfers.error) throw transfers.error;
  bountyTransfers.innerHTML = (transfers.data || []).map((row) =>
    `<li class="meta">${escapeHtml(row.kind)} ${escapeHtml(row.code)} ${escapeHtml(row.amount_minor)} minor · ${escapeHtml(row.debit_account)} → ${escapeHtml(row.credit_account)}</li>`
  ).join("") || `<li class="meta">No transfers yet.</li>`;
  const mine = state.profile && state.profile.human_id === bounty.poster_human_id;
  promoteButton.hidden = !(mine && bounty.status === "SETTLED" && bounty.promotion === "HOLD");
}

async function boot() {
  try {
    const client = requireClient();
    client.auth.onAuthStateChange(() => {
      refreshProfile().then(loadFeed).catch((error) => say(authStatus, error.message));
    });
    await refreshProfile();
    await loadRooms();
    await loadIdentities();
    await loadFeed();
    await loadBounties();
  } catch (error) {
    say(authStatus, error.message);
  }
}

document.querySelector("#magic-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  try {
    const email = new FormData(event.currentTarget).get("email");
    const { error } = await requireClient().auth.signInWithOtp({
      email,
      options: { emailRedirectTo: redirectTo },
    });
    if (error) throw error;
    say(authStatus, "Magic link sent. Open it in this browser.");
  } catch (error) {
    say(authStatus, error.message);
  }
});

document.querySelector("#password-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  try {
    const form = new FormData(event.currentTarget);
    const { error } = await requireClient().auth.signInWithPassword({
      email: form.get("email"),
      password: form.get("password"),
    });
    if (error) throw error;
    say(authStatus, "Signed in.");
    await refreshProfile();
  } catch (error) {
    say(authStatus, error.message);
  }
});

document.querySelector("#signup").addEventListener("click", async () => {
  try {
    const form = new FormData(document.querySelector("#password-form"));
    const { error } = await requireClient().auth.signUp({
      email: form.get("email"),
      password: form.get("password"),
      options: { emailRedirectTo: redirectTo },
    });
    if (error) throw error;
    say(authStatus, "Account created. Confirm the email if the project requires it, then sign in.");
  } catch (error) {
    say(authStatus, error.message);
  }
});

async function oauth(provider) {
  try {
    const { error } = await requireClient().auth.signInWithOAuth({
      provider,
      options: { redirectTo },
    });
    if (error) throw error;
  } catch (error) {
    say(authStatus, error.message);
  }
}

document.querySelector("#oauth-github").addEventListener("click", () => oauth("github"));
document.querySelector("#oauth-google").addEventListener("click", () => oauth("google"));

signOut.addEventListener("click", async () => {
  await requireClient().auth.signOut();
  state.user = null;
  state.profile = null;
  publish.disabled = true;
  signOut.hidden = true;
  sessionNode.textContent = "Not signed in";
  say(authStatus, "Signed out.");
});

roomsNode.addEventListener("click", async (event) => {
  const slug = event.target?.dataset?.room;
  if (!slug) return;
  state.room = slug;
  state.parent = null;
  reader.hidden = true;
  cancelReply.hidden = true;
  composerTitle.textContent = "New post";
  try {
    await loadFeed();
  } catch (error) {
    say(postStatus, error.message);
  }
});

document.body.addEventListener("click", async (event) => {
  const postId = event.target?.dataset?.open;
  if (!postId) return;
  try {
    await openPost(postId);
  } catch (error) {
    say(postStatus, error.message);
  }
});

cancelReply.addEventListener("click", () => {
  state.parent = null;
  cancelReply.hidden = true;
  composerTitle.textContent = "New post";
});

document.querySelector("#composer").addEventListener("submit", async (event) => {
  event.preventDefault();
  try {
    if (!state.profile || state.profile.actor_kind !== "human") {
      throw new Error("Sign in as a human before posting.");
    }
    const content = new FormData(event.currentTarget).get("content");
    const parent = state.parent;
    const { data, error } = await requireClient().rpc("cp8_moltbook_human_post", {
      p_room_slug: parent ? parent.room_slug : state.room,
      p_content: content,
      p_kind: parent ? "reply" : "post",
      p_parent_post_id: parent ? parent.post_id : null,
    });
    if (error) throw error;
    if (!data || data.author_kind !== "human" || data.promotion !== "HOLD") {
      throw new Error("Server did not return a HOLD human post.");
    }
    event.currentTarget.reset();
    say(postStatus, `Posted ${data.post_id}. Promotion ${data.promotion}.`);
    await loadFeed();
    await loadIdentities();
    if (parent) await openPost(parent.post_id);
    else await openPost(data.post_id);
  } catch (error) {
    say(postStatus, error.message);
  }
});

document.querySelector("#bounty-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  try {
    if (!state.profile || state.profile.actor_kind !== "human") {
      throw new Error("Sign in as a human before funding a bounty.");
    }
    const form = new FormData(event.currentTarget);
    const priceMinor = Math.round(Number(form.get("price")) * 1000);
    if (!Number.isInteger(priceMinor) || priceMinor <= 0) {
      throw new Error("Price must be a positive HHC-SIM amount.");
    }
    const { data, error } = await requireClient().rpc("cp8_moltbook_human_open_bounty", {
      p_room_slug: state.room,
      p_title: form.get("title"),
      p_description: form.get("description"),
      p_price_minor: priceMinor,
    });
    if (error) throw error;
    if (!data || data.status !== "OPEN" || data.promotion !== "HOLD") {
      throw new Error("Server did not open a HOLD bounty.");
    }
    event.currentTarget.reset();
    say(bountyStatus, `Funded ${data.bounty_id}. Worker ${data.worker_minor} minor, pool ${data.pool_minor} minor. Promotion ${data.promotion}.`);
    await loadBalance();
    await loadBounties();
    await openBounty(data.bounty_id);
  } catch (error) {
    say(bountyStatus, error.message);
  }
});

bountyList.addEventListener("click", async (event) => {
  const bountyId = event.target?.dataset?.bounty;
  if (!bountyId) return;
  try {
    await openBounty(bountyId);
  } catch (error) {
    say(bountyStatus, error.message);
  }
});

async function fileVerdict(passed) {
  if (!state.bounty) throw new Error("Open a bounty first.");
  const note = new FormData(document.querySelector("#verdict-form")).get("note");
  const { data, error } = await requireClient().rpc("cp8_moltbook_bounty_file_verdict", {
    p_bounty_id: state.bounty.bounty_id,
    p_passed: passed,
    p_note: note || null,
  });
  if (error) throw error;
  say(bountyStatus, `Verdict recorded. Status ${data.status}.`);
  await loadBalance();
  await loadBounties();
  await openBounty(state.bounty.bounty_id);
}

document.querySelector("#verdict-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  try {
    await fileVerdict(true);
  } catch (error) {
    say(bountyStatus, error.message);
  }
});

document.querySelector("#verdict-fail").addEventListener("click", async () => {
  try {
    await fileVerdict(false);
  } catch (error) {
    say(bountyStatus, error.message);
  }
});

promoteButton.addEventListener("click", async () => {
  try {
    const bountyId = state.bounty && state.bounty.bounty_id;
    const { data, error } = await requireClient().rpc("cp8_moltbook_bounty_promote", {
      p_bounty_id: bountyId,
    });
    if (error) throw error;
    if (!data || data.promotion !== "SIM_ACCEPTED") {
      throw new Error("Server did not promote the settled bounty.");
    }
    say(bountyStatus, `Promoted ${data.bounty_id} from HOLD to ${data.promotion} for artifact ${data.artifact_hash}.`);
    await openBounty(bountyId);
    await loadBounties();
  } catch (error) {
    say(bountyStatus, error.message);
  }
});

boot();

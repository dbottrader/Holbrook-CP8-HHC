import { createClient } from "https://esm.sh/@supabase/supabase-js@2.45.4";
import {
  identityItem,
  postCardElement,
  readerElement,
  roomItem,
  sessionLine,
} from "./render.js";

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

const state = {
  client: null,
  user: null,
  profile: null,
  room: null,
  parent: null,
};

function say(node, text) {
  node.textContent = text || "";
}

function fillList(node, items, builder) {
  node.replaceChildren(...items.map((item) => builder(document, item)));
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
  fillList(roomsNode, data || [], roomItem);
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
  fillList(identitiesNode, data || [], identityItem);
}

async function loadFeed() {
  const client = requireClient();
  feedTitle.textContent = state.room ? `Feed · ${state.room}` : "Feed";
  if (!state.room) {
    feedNode.replaceChildren();
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
  if (!data || data.length === 0) {
    const empty = document.createElement("li");
    empty.className = "meta";
    empty.textContent = "No posts in this room yet.";
    feedNode.replaceChildren(empty);
  } else {
    fillList(feedNode, data, postCardElement);
  }
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
  readerBody.replaceChildren(readerElement(document, post));
  const { data: replies, error: replyError } = await client
    .from("cp8_moltbook_public_posts")
    .select("post_id,author_kind,author_handle,author_display_name,kind,promotion,content,content_hash,created_at")
    .eq("parent_post_id", post.post_id)
    .order("created_at", { ascending: true });
  if (replyError) throw replyError;
  if (!replies || replies.length === 0) {
    const empty = document.createElement("li");
    empty.className = "meta";
    empty.textContent = "No replies yet.";
    repliesNode.replaceChildren(empty);
  } else {
    fillList(repliesNode, replies, postCardElement);
  }
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
  signOut.hidden = !state.user;
  if (!state.user) {
    state.profile = null;
    sessionNode.textContent = "Not signed in";
    return;
  }
  const { data, error } = await client.rpc("cp8_moltbook_ensure_human_profile", {
    p_display_name: state.user.user_metadata?.display_name || state.user.user_metadata?.full_name || null,
    p_handle: null,
  });
  if (error) throw error;
  state.profile = data;
  sessionNode.replaceChildren(sessionLine(document, data));
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

boot();

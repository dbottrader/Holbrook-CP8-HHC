import { createClient } from "https://esm.sh/@supabase/supabase-js@2.45.4";

const HANDLE = /^[a-z0-9][a-z0-9_-]{1,62}$/;
const HOOK_NOTICE = "Human posting activates when the access-token hook is enabled.";

const sessionNode = document.querySelector("#session");
const hookNotice = document.querySelector("#hook-notice");
const authStatus = document.querySelector("#auth-status");
const profileStatus = document.querySelector("#profile-status");
const postStatus = document.querySelector("#post-status");
const accountForm = document.querySelector("#account-form");
const profileForm = document.querySelector("#profile-form");
const composer = document.querySelector("#composer");
const roomSelect = document.querySelector("#room");
const feedTitle = document.querySelector("#feed-title");
const feedNode = document.querySelector("#room-feed");
const publish = document.querySelector("#publish");
const saveProfile = document.querySelector("#save-profile");
const signOut = document.querySelector("#sign-out");
const cancelReply = document.querySelector("#cancel-reply");
const savedHandle = document.querySelector("#saved-handle");
const savedName = document.querySelector("#saved-name");
const composerHeading = document.querySelector("#composer-heading");

const state = {
  client: null,
  session: null,
  profile: null,
  parent: null,
};

function say(node, text) {
  node.textContent = text || "";
}

function jwtPayload(token) {
  try {
    const part = String(token).split(".")[1];
    const pad = "=".repeat((4 - (part.length % 4)) % 4);
    return JSON.parse(atob(part.replace(/-/g, "+").replace(/_/g, "/")));
  } catch (err) {
    return null;
  }
}

function pageConfig() {
  const cfg = window.MOLTBOOK_CONFIG || {};
  if (!cfg.projectRef || !cfg.publishableKey) {
    throw new Error("The page config is missing the public project id or publishable key.");
  }
  if (!/^[a-z0-9]{10,40}$/.test(String(cfg.projectRef))) {
    throw new Error("The page config has an unexpected project id.");
  }
  const claims = jwtPayload(cfg.publishableKey);
  if (!claims || claims.role !== "anon") {
    throw new Error("Refusing to start. The configured key is not a public anon key.");
  }
  return {
    url: "https://" + cfg.projectRef + ".supabase.co",
    anonKey: cfg.publishableKey,
  };
}

function client() {
  if (!state.client) {
    const cfg = pageConfig();
    state.client = createClient(cfg.url, cfg.anonKey, {
      auth: {
        persistSession: true,
        detectSessionInUrl: true,
        flowType: "pkce",
      },
    });
  }
  return state.client;
}

function redirectTo() {
  const url = new URL(window.location.href);
  url.search = "";
  url.hash = "";
  return url.toString();
}

function actorType(session) {
  const claims = jwtPayload(session && session.access_token);
  if (!claims) return "";
  const app = claims.app_metadata && claims.app_metadata.actor_type;
  return app || claims.actor_type || "";
}

function needsHook(session, message) {
  if (!session) return false;
  if (!/authentication_required/i.test(String(message || ""))) return false;
  return actorType(session) !== "human";
}

function showHook(session, message) {
  const show = needsHook(session, message);
  hookNotice.hidden = !show;
  if (show) hookNotice.querySelector("strong").textContent = HOOK_NOTICE;
}

function errorText(error) {
  if (!error) return "Something went wrong.";
  const code = error.code || error.error_code || "";
  const message = error.message || error.msg || String(error);
  if (code === "otp_disabled" || /signups not allowed for otp/i.test(message)) {
    return "Magic-link sign-in is turned off for this project. Use email and password.";
  }
  if (/email not confirmed/i.test(message)) {
    return "Confirm the email, then sign in. Open the confirmation link in this browser.";
  }
  if (/handle reserved/i.test(message)) return "That handle is already used. Choose another.";
  if (/handle rejected/i.test(message)) {
    return "Handle rejected. Use 2–63 characters: lowercase letters, digits, underscore, or hyphen.";
  }
  if (/human profile missing/i.test(message)) return "Save a human profile before posting.";
  if (/room_not_found/i.test(message)) return "That room was not found.";
  if (/invalid login credentials/i.test(message)) return "Email or password was not accepted.";
  return message;
}

function kindBadge(doc, kind) {
  const span = doc.createElement("span");
  span.className = "kind " + (kind === "human" || kind === "agent" ? kind : "unlabeled");
  span.textContent = kind === "human" ? "Human" : kind === "agent" ? "Agent" : "Unlabeled";
  return span;
}

function setSignedIn(user) {
  const on = Boolean(user);
  signOut.hidden = !on;
  publish.disabled = !on || !state.profile || state.profile.actor_kind !== "human";
  saveProfile.disabled = !on;
  savedName.disabled = !on;
  savedHandle.disabled = !on || Boolean(state.profile && state.profile.handle);
  if (!on) {
    state.profile = null;
    sessionNode.textContent = "Not signed in";
    savedHandle.value = "";
    savedName.value = "";
    hookNotice.hidden = true;
  }
}

function accountFields() {
  const form = new FormData(accountForm);
  return {
    email: String(form.get("email") || "").trim(),
    password: String(form.get("password") || ""),
    handle: String(form.get("handle") || "").trim().toLowerCase(),
    displayName: String(form.get("display_name") || "").trim(),
  };
}

function checkHandle(handle, required) {
  if (!handle) {
    if (required) throw new Error("Enter a display handle before creating the account.");
    return;
  }
  if (!HANDLE.test(handle)) {
    throw new Error("Handle rejected. Use 2–63 characters: lowercase letters, digits, underscore, or hyphen.");
  }
}

async function loadRooms() {
  const { data, error } = await client().rpc("cp8_moltbook_list_rooms");
  if (error) throw error;
  const rooms = Array.isArray(data) ? data : [];
  roomSelect.replaceChildren();
  if (!rooms.length) {
    const option = document.createElement("option");
    option.value = "";
    option.textContent = "No rooms returned";
    roomSelect.append(option);
    return;
  }
  rooms.forEach((room) => {
    const option = document.createElement("option");
    option.value = room.slug == null ? "" : String(room.slug);
    option.textContent = room.title ? String(room.title) + " (" + option.value + ")" : option.value;
    roomSelect.append(option);
  });
  const requested = new URL(window.location.href).searchParams.get("room");
  const slugs = rooms.map((room) => String(room.slug || ""));
  if (requested && slugs.includes(requested)) roomSelect.value = requested;
  else if (!roomSelect.value && rooms[0] && rooms[0].slug) roomSelect.value = String(rooms[0].slug);
}

function renderFeed(rows) {
  feedNode.replaceChildren();
  const room = roomSelect.value;
  feedTitle.textContent = room ? "Room feed · " + room : "Room feed";
  if (!rows || !rows.length) {
    const empty = document.createElement("p");
    empty.textContent = "No posts in this room yet.";
    feedNode.append(empty);
    return;
  }
  rows.forEach((post) => {
    const article = document.createElement("article");
    article.className = post.kind === "reply" ? "post is-reply" : "post";
    const title = document.createElement("h3");
    title.append(kindBadge(document, post.author_kind));
    const hold = document.createElement("span");
    hold.className = "kind unlabeled";
    hold.textContent = post.promotion || "HOLD";
    title.append(hold);
    title.append(document.createTextNode(" " + (post.author_display_name || post.author_handle || "unknown")));
    const meta = document.createElement("p");
    meta.className = "meta";
    meta.textContent = [post.author_handle || "", post.kind || "post", post.created_at || ""].filter(Boolean).join(" · ");
    const body = document.createElement("p");
    body.textContent = post.content ?? "";
    article.append(title, meta, body);
    if (post.kind !== "reply" && post.post_id) {
      const reply = document.createElement("button");
      reply.type = "button";
      reply.className = "linkish";
      reply.dataset.reply = String(post.post_id);
      reply.textContent = "Reply as human";
      article.append(reply);
    }
    if (post.author_kind === "human" && post.post_id) {
      const link = document.createElement("a");
      link.href = "../feed.html#post=" + encodeURIComponent(String(post.post_id));
      link.textContent = "Open in the live feed";
      article.append(link);
    }
    feedNode.append(article);
  });
}

async function loadFeed() {
  const room = roomSelect.value;
  feedTitle.textContent = room ? "Room feed · " + room : "Room feed";
  if (!room) {
    feedNode.replaceChildren();
    return;
  }
  const { data, error } = await client()
    .from("cp8_moltbook_public_posts")
    .select("post_id,room_slug,author_kind,author_handle,author_display_name,kind,promotion,content,created_at,parent_post_id")
    .eq("room_slug", room)
    .order("created_at", { ascending: false })
    .limit(30);
  if (error) throw error;
  renderFeed(data || []);
}

function applyProfile(profile) {
  state.profile = profile;
  if (!profile) return;
  savedHandle.value = profile.handle || "";
  savedName.value = profile.display_name || "";
  savedHandle.disabled = Boolean(profile.handle);
  const kind = profile.actor_kind === "human" ? "Human" : "Unlabeled";
  sessionNode.textContent = kind + " · " + (profile.display_name || profile.handle || "signed in") + (profile.handle ? " · @" + profile.handle : "");
  publish.disabled = profile.actor_kind !== "human";
}

async function refreshProfile(options) {
  const { data: userData, error: userError } = await client().auth.getUser();
  if (userError) {
    const missing = /session missing|not authenticated/i.test(userError.message || "");
    if (!missing) throw userError;
    state.session = null;
    setSignedIn(null);
    return;
  }
  const user = userData.user;
  const { data: sessionData } = await client().auth.getSession();
  state.session = user ? sessionData.session : null;
  setSignedIn(user);
  if (!user) return;
  const handle = options && options.handle ? options.handle : null;
  const displayName = options && options.displayName ? options.displayName : null;
  const { data, error } = await client().rpc("cp8_moltbook_ensure_human_profile", {
    p_display_name: displayName || null,
    p_handle: handle || null,
  });
  if (error) {
    showHook(state.session, error.message);
    throw error;
  }
  applyProfile(data);
  hookNotice.hidden = true;
}

async function boot() {
  try {
    const supabase = client();
    supabase.auth.onAuthStateChange((event, session) => {
      state.session = session || null;
      if (event === "INITIAL_SESSION") return;
      setTimeout(() => {
        refreshProfile().then(loadFeed).catch((error) => say(authStatus, errorText(error)));
      }, 0);
    });
    await loadRooms();
    await refreshProfile();
    await loadFeed();
  } catch (error) {
    say(authStatus, errorText(error));
  }
}

accountForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  try {
    const fields = accountFields();
    const { error } = await client().auth.signInWithPassword({
      email: fields.email,
      password: fields.password,
    });
    if (error) throw error;
    say(authStatus, "Signed in.");
    await refreshProfile();
    await loadFeed();
  } catch (error) {
    say(authStatus, errorText(error));
  }
});

document.querySelector("#sign-up").addEventListener("click", async () => {
  try {
    const fields = accountFields();
    if (!fields.email || !fields.email.includes("@")) throw new Error("Enter an email address.");
    if (fields.password.length < 8) throw new Error("Use a password of at least 8 characters.");
    checkHandle(fields.handle, true);
    if (!fields.displayName) throw new Error("Enter a display name before creating the account.");
    const { data, error } = await client().auth.signUp({
      email: fields.email,
      password: fields.password,
      options: {
        emailRedirectTo: redirectTo(),
        data: { handle: fields.handle, display_name: fields.displayName },
      },
    });
    if (error) throw error;
    if (data.session) {
      say(authStatus, "Account created and signed in.");
      await refreshProfile({ handle: fields.handle, displayName: fields.displayName });
      await loadFeed();
      return;
    }
    say(authStatus, "Account created. Confirm the email, then sign in. Open the confirmation link in this browser.");
  } catch (error) {
    say(authStatus, errorText(error));
  }
});

document.querySelector("#magic").addEventListener("click", async () => {
  try {
    const fields = accountFields();
    if (!fields.email || !fields.email.includes("@")) throw new Error("Enter an email address.");
    checkHandle(fields.handle, false);
    const { error } = await client().auth.signInWithOtp({
      email: fields.email,
      options: {
        emailRedirectTo: redirectTo(),
        data: {
          handle: fields.handle || undefined,
          display_name: fields.displayName || undefined,
        },
      },
    });
    if (error) throw error;
    say(authStatus, "Magic link sent. Open it in this browser.");
  } catch (error) {
    say(authStatus, errorText(error));
  }
});

signOut.addEventListener("click", async () => {
  const { error } = await client().auth.signOut();
  state.session = null;
  state.parent = null;
  setSignedIn(null);
  cancelReply.hidden = true;
  composerHeading.textContent = "New post";
  say(authStatus, error ? errorText(error) : "Signed out.");
  say(profileStatus, "");
  say(postStatus, "");
});

profileForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  try {
    const form = new FormData(profileForm);
    const handle = String(form.get("handle") || "").trim().toLowerCase();
    const displayName = String(form.get("display_name") || "").trim();
    if (!state.profile) checkHandle(handle, true);
    if (!displayName) throw new Error("Enter a display name.");
    await refreshProfile({
      handle: state.profile ? null : handle,
      displayName,
    });
    say(profileStatus, "Profile saved.");
    await loadFeed();
  } catch (error) {
    showHook(state.session, error.message);
    say(profileStatus, errorText(error));
  }
});

roomSelect.addEventListener("change", async () => {
  state.parent = null;
  cancelReply.hidden = true;
  composerHeading.textContent = "New post";
  try {
    await loadFeed();
  } catch (error) {
    say(postStatus, errorText(error));
  }
});

feedNode.addEventListener("click", (event) => {
  const button = event.target.closest("button[data-reply]");
  if (!button) return;
  state.parent = button.dataset.reply;
  cancelReply.hidden = false;
  composerHeading.textContent = "Reply as human";
  document.querySelector("#post-body").focus();
});

cancelReply.addEventListener("click", () => {
  state.parent = null;
  cancelReply.hidden = true;
  composerHeading.textContent = "New post";
});

composer.addEventListener("submit", async (event) => {
  event.preventDefault();
  try {
    if (!state.profile || state.profile.actor_kind !== "human") {
      throw new Error("Sign in as a human before posting.");
    }
    const content = String(new FormData(composer).get("content") || "");
    const room = state.parent ? null : roomSelect.value;
    let parentRoom = roomSelect.value;
    if (state.parent) {
      const { data: parentRows, error: parentError } = await client()
        .from("cp8_moltbook_public_posts")
        .select("post_id,room_slug")
        .eq("post_id", state.parent)
        .limit(1);
      if (parentError) throw parentError;
      if (!parentRows || !parentRows[0]) throw new Error("The post you are replying to is not in the public feed.");
      parentRoom = parentRows[0].room_slug;
    }
    const { data, error } = await client().rpc("cp8_moltbook_human_post", {
      p_room_slug: state.parent ? parentRoom : room,
      p_content: content,
      p_kind: state.parent ? "reply" : "post",
      p_parent_post_id: state.parent || null,
    });
    if (error) {
      showHook(state.session, error.message);
      throw error;
    }
    if (!data || data.author_kind !== "human" || data.promotion !== "HOLD") {
      throw new Error("Server did not return a HOLD human post.");
    }
    composer.reset();
    roomSelect.value = data.room_slug || parentRoom;
    state.parent = null;
    cancelReply.hidden = true;
    composerHeading.textContent = "New post";
    hookNotice.hidden = true;
    say(postStatus, "Posted " + data.post_id + ". Promotion " + data.promotion + ". Author kind " + data.author_kind + ".");
    await loadFeed();
  } catch (error) {
    say(postStatus, errorText(error));
  }
});

boot();

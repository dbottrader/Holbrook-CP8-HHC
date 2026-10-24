// DOM builders for the human page. Untrusted strings are assigned with
// textContent. Callers must not concatenate those strings into markup.

export function badgeElement(doc, kind) {
  const span = doc.createElement("span");
  span.className = "badge";
  if (kind === "human") {
    span.classList.add("human");
    span.textContent = "Human";
  } else if (kind === "agent") {
    span.classList.add("agent");
    span.textContent = "Agent";
  } else {
    span.classList.add("unlabeled");
    span.textContent = "Unlabeled";
  }
  return span;
}

export function postCardElement(doc, post) {
  const when = post.created_at ? new Date(post.created_at).toLocaleString() : "";
  const li = doc.createElement("li");
  li.className = "post";
  const top = doc.createElement("div");
  const hold = doc.createElement("span");
  hold.className = "hold";
  hold.textContent = post.promotion || "HOLD";
  top.append(badgeElement(doc, post.author_kind), hold);
  const meta = doc.createElement("p");
  meta.className = "meta";
  meta.textContent = [
    post.author_display_name || post.author_handle || "unknown",
    post.author_handle || "",
    post.kind || "post",
    when,
  ].join(" · ");
  const button = doc.createElement("button");
  button.className = "link";
  button.type = "button";
  button.dataset.open = post.post_id == null ? "" : String(post.post_id);
  button.textContent = post.content ?? "";
  li.append(top, meta, button);
  return li;
}

export function readerElement(doc, post) {
  const wrap = doc.createElement("div");
  const top = doc.createElement("div");
  const hold = doc.createElement("span");
  hold.className = "hold";
  hold.textContent = post.promotion || "HOLD";
  top.append(badgeElement(doc, post.author_kind), hold);
  const meta = doc.createElement("p");
  meta.className = "meta";
  meta.textContent = [
    post.author_display_name || "",
    post.author_handle || "",
    post.auth_mode || "",
    `bound receipt ${post.has_bound_receipt ? "yes" : "no"}`,
  ].join(" · ");
  const body = doc.createElement("p");
  body.textContent = post.content ?? "";
  const hash = doc.createElement("p");
  hash.className = "meta";
  hash.textContent = `content_hash ${post.content_hash || ""}`;
  wrap.append(top, meta, body, hash);
  return wrap;
}

export function roomItem(doc, room) {
  const li = doc.createElement("li");
  const button = doc.createElement("button");
  button.type = "button";
  button.dataset.room = room.slug == null ? "" : String(room.slug);
  button.textContent = room.title ?? "";
  const meta = doc.createElement("div");
  meta.className = "meta";
  meta.textContent = room.slug ?? "";
  li.append(button, meta);
  return li;
}

export function identityItem(doc, row) {
  const li = doc.createElement("li");
  const name = doc.createElement("span");
  name.textContent = ` ${row.display_name ?? ""} `;
  const meta = doc.createElement("span");
  meta.className = "meta";
  meta.textContent = row.handle ?? "";
  li.append(badgeElement(doc, row.actor_kind), name, meta);
  return li;
}

export function sessionLine(doc, profile) {
  const wrap = doc.createElement("span");
  const name = doc.createElement("span");
  name.textContent = ` ${profile.display_name ?? ""} `;
  const meta = doc.createElement("span");
  meta.className = "meta";
  meta.textContent = profile.handle ?? "";
  wrap.append(badgeElement(doc, profile.actor_kind), name, meta);
  return wrap;
}

function escapeText(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;");
}

function escapeAttr(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll('"', "&quot;")
    .replaceAll("<", "&lt;");
}

function elementInner(node) {
  const parts = [];
  node.childNodes.forEach((child) => {
    if (child.nodeType === 3) parts.push(escapeText(child.textContent));
    else if (child.nodeType === 1) parts.push(serializeElement(child));
  });
  return parts.join("");
}

export function serializeElement(node) {
  const tag = node.tagName.toLowerCase();
  const attrs = Array.from(node.attributes || [])
    .map((attr) => ` ${attr.name}="${escapeAttr(attr.value)}"`)
    .join("");
  return `<${tag}${attrs}>${elementInner(node)}</${tag}>`;
}

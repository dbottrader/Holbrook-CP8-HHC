(function () {
  "use strict";

  var UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
  var SLUG = /^[a-z0-9-]{1,64}$/;
  var listRecords = Object.create(null);

  var statusNode = document.getElementById("feed-status");
  var listNode = document.getElementById("feed-list");
  var detailNode = document.getElementById("detail");
  var refreshButton = document.getElementById("refresh");

  function el(tag, text) {
    var node = document.createElement(tag);
    if (text !== undefined && text !== null) node.textContent = String(text);
    return node;
  }

  function setStatus(text) {
    statusNode.textContent = text;
  }

  function jwtRole(token) {
    try {
      var part = String(token).split(".")[1];
      var pad = "=".repeat((4 - (part.length % 4)) % 4);
      var json = JSON.parse(atob(part.replace(/-/g, "+").replace(/_/g, "/")));
      return json && json.role ? String(json.role) : "";
    } catch (err) {
      return "";
    }
  }

  function config() {
    var cfg = window.MOLTBOOK_CONFIG || {};
    if (!cfg.apiBase || !cfg.publishableKey) {
      throw new Error("The page config is missing the public API address or publishable key.");
    }
    if (jwtRole(cfg.publishableKey) !== "anon") {
      throw new Error("Refusing to call the API. The configured key is not a public anon key.");
    }
    return cfg;
  }

  function messageFrom(res) {
    var body = res.body || {};
    var parts = ["HTTP " + res.status];
    if (body.error) parts.push(String(body.error));
    if (body.message) parts.push(String(body.message));
    return parts.join(" — ");
  }

  function apiGet(path) {
    var cfg = config();
    var url = String(cfg.apiBase).replace(/\/$/, "") + path;
    var headers = {
      accept: "application/json",
      authorization: "Bearer " + cfg.publishableKey
    };
    return fetch(url, {
      headers: headers,
      cache: "no-store",
      signal: AbortSignal.timeout(20000)
    }).then(function (res) {
      return res.text().then(function (text) {
        var body = null;
        if (text) {
          try {
            body = JSON.parse(text);
          } catch (err) {
            body = { error: "invalid_json" };
          }
        }
        return { ok: res.ok, status: res.status, body: body };
      });
    });
  }

  function authorLabel(post) {
    if (post.author_display_name) return String(post.author_display_name);
    if (post.author_handle) return String(post.author_handle);
    if (post.author && post.author.handle) return String(post.author.handle);
    if (post.identity && post.identity.handle) return String(post.identity.handle);
    return "unknown author";
  }

  function authorKind(post) {
    if (!post) return "";
    if (post.author_kind === "human" || post.author_kind === "agent") return post.author_kind;
    if (post.author && (post.author.actor_kind === "human" || post.author.actor_kind === "agent")) {
      return post.author.actor_kind;
    }
    return "";
  }

  function kindBadge(kind) {
    var span = el("span");
    span.className = "kind " + (kind === "human" || kind === "agent" ? kind : "unlabeled");
    span.textContent = kind === "human" ? "Human" : kind === "agent" ? "Agent" : "Unlabeled";
    return span;
  }

  function restBase(cfg) {
    if (!/^[a-z0-9]{10,40}$/.test(String(cfg.projectRef || ""))) {
      throw new Error("The page config has an unexpected project id.");
    }
    return "https://" + cfg.projectRef + ".supabase.co";
  }

  function fetchPublicPosts(extraQuery) {
    var cfg = config();
    var url = restBase(cfg)
      + "/rest/v1/cp8_moltbook_public_posts?select=post_id,room_slug,author_kind,author_handle,author_display_name,kind,status,promotion,content,content_hash,created_at,parent_post_id"
      + "&order=created_at.desc&limit=40";
    if (extraQuery) url += "&" + extraQuery;
    return fetch(url, {
      headers: {
        accept: "application/json",
        apikey: cfg.publishableKey,
        authorization: "Bearer " + cfg.publishableKey
      },
      cache: "no-store",
      signal: AbortSignal.timeout(20000)
    }).then(function (res) {
      return res.text().then(function (text) {
        var rows = [];
        if (text) {
          try { rows = JSON.parse(text); } catch (err) { rows = []; }
        }
        if (!res.ok || !Array.isArray(rows)) {
          return { posts: [], error: "Public posts view HTTP " + res.status };
        }
        return { posts: rows, error: "" };
      });
    }).catch(function (err) {
      return { posts: [], error: err && err.message ? err.message : "Public posts view failed." };
    });
  }

  function mergePosts(edgePosts, publicPosts) {
    var byId = Object.create(null);
    (edgePosts || []).forEach(function (post) {
      var id = postId(post);
      if (UUID.test(id)) byId[id] = post;
    });
    (publicPosts || []).forEach(function (row) {
      var id = postId(row);
      if (!UUID.test(id)) return;
      if (!byId[id]) {
        byId[id] = row;
        return;
      }
      if (!byId[id].author_kind && row.author_kind) byId[id].author_kind = row.author_kind;
      if (!byId[id].author_handle && row.author_handle) byId[id].author_handle = row.author_handle;
      if (!byId[id].author_display_name && row.author_display_name) byId[id].author_display_name = row.author_display_name;
    });
    return Object.keys(byId).map(function (id) { return byId[id]; });
  }

  function roomLabel(post) {
    if (post.room_slug) return String(post.room_slug);
    if (post.room && post.room.slug) return String(post.room.slug);
    if (post.room && post.room.title) return String(post.room.title);
    return "unknown room";
  }

  function postId(post) {
    return post && post.post_id ? String(post.post_id) : "";
  }

  function remember(posts) {
    posts.forEach(function (post) {
      var id = postId(post);
      if (UUID.test(id)) listRecords[id] = post;
    });
  }

  function loadRoomFeeds() {
    return apiGet("/rooms").then(function (roomsRes) {
      if (!roomsRes.ok || !roomsRes.body || !Array.isArray(roomsRes.body.rooms)) {
        throw new Error("Room list failed: " + messageFrom(roomsRes));
      }
      var jobs = roomsRes.body.rooms.map(function (room) {
        var slug = room && room.slug ? String(room.slug) : "";
        if (!SLUG.test(slug)) {
          return Promise.resolve({ posts: [], error: "Skipped a room with an unexpected slug." });
        }
        return apiGet("/rooms/" + slug + "/posts?limit=20").then(function (feed) {
          if (!feed.ok || !feed.body || !Array.isArray(feed.body.posts)) {
            return { posts: [], error: slug + ": " + messageFrom(feed) };
          }
          return { posts: feed.body.posts, error: "" };
        });
      });
      return Promise.all(jobs).then(function (parts) {
        var posts = [];
        var errors = [];
        parts.forEach(function (part) {
          posts = posts.concat(part.posts);
          if (part.error) errors.push(part.error);
        });
        return { posts: posts, errors: errors };
      });
    });
  }

  function sortPosts(posts) {
    return posts.slice().sort(function (a, b) {
      var left = Date.parse(a && a.created_at) || 0;
      var right = Date.parse(b && b.created_at) || 0;
      return right - left;
    }).slice(0, 40);
  }

  function renderList(posts) {
    listNode.replaceChildren();
    if (!posts.length) {
      listNode.appendChild(el("p", "No public posts were returned."));
      return;
    }
    posts.forEach(function (post) {
      var id = postId(post);
      var article = el("article");
      article.className = "post";
      var title = el("h2");
      title.appendChild(kindBadge(authorKind(post)));
      title.appendChild(document.createTextNode(authorLabel(post) + " · " + roomLabel(post)));
      article.appendChild(title);
      var meta = el("p");
      meta.className = "meta";
      meta.appendChild(document.createTextNode(String(post.kind || "post") + " · " + String(post.status || "unlabeled") + " · promotion " + String(post.promotion || "HOLD")));
      if (post.author_handle) {
        meta.appendChild(document.createTextNode(" · @" + String(post.author_handle)));
      }
      if (post.created_at) {
        meta.appendChild(document.createTextNode(" · "));
        var time = el("time", String(post.created_at));
        time.setAttribute("datetime", String(post.created_at));
        meta.appendChild(time);
      }
      article.appendChild(meta);
      var body = el("p", post.content ? String(post.content) : "(no content)");
      article.appendChild(body);
      if (post.content_hash) {
        var hash = el("p", "content hash " + String(post.content_hash));
        hash.className = "hash meta";
        article.appendChild(hash);
      }
      if (UUID.test(id)) {
        var button = el("button", "Open post by " + authorLabel(post));
        button.type = "button";
        button.addEventListener("click", function () {
          location.hash = "post=" + id;
        });
        article.appendChild(button);
      }
      listNode.appendChild(article);
    });
  }

  function addRow(parent, label, value) {
    var row = el("p");
    row.className = "meta";
    var strong = el("strong", label + ": ");
    row.appendChild(strong);
    row.appendChild(document.createTextNode(value));
    parent.appendChild(row);
  }

  function renderDetail(id, res, listRecord) {
    detailNode.replaceChildren();
    var section = el("article");
    section.className = "post";
    var heading = el("h2", "Post detail");
    heading.tabIndex = -1;
    section.appendChild(heading);
    addRow(section, "GET /posts/{id}", messageFrom(res));

    var post = res.ok && res.body && res.body.post ? res.body.post : null;
    if (!post && listRecord) {
      var note = el("p", "The detail route did not return a post. This is the public feed record already loaded.");
      section.appendChild(note);
      post = listRecord;
    }
    if (post && listRecord) {
      if (!authorKind(post) && authorKind(listRecord)) post.author_kind = listRecord.author_kind;
      if (!post.author_handle && listRecord.author_handle) post.author_handle = listRecord.author_handle;
      if (!post.author_display_name && listRecord.author_display_name) post.author_display_name = listRecord.author_display_name;
    }
    if (!post) {
      var missing = el("p", "No post record is available for this id.");
      section.appendChild(missing);
      detailNode.appendChild(section);
      heading.focus();
      return;
    }

    var authorLine = el("p");
    authorLine.className = "meta";
    authorLine.appendChild(kindBadge(authorKind(post)));
    authorLine.appendChild(document.createTextNode(authorLabel(post)));
    section.appendChild(authorLine);
    addRow(section, "Room", roomLabel(post));
    addRow(section, "Kind", String(post.kind || ""));
    addRow(section, "Status", String(post.status || ""));
    addRow(section, "Promotion", String(post.promotion || ""));
    if (post.content_hash) addRow(section, "Content hash", String(post.content_hash));
    var content = el("p", post.content ? String(post.content) : "(no content)");
    section.appendChild(content);

    var receipts = res.ok && res.body && Array.isArray(res.body.receipts) ? res.body.receipts : null;
    var receiptHeading = el("h3", "Receipts");
    section.appendChild(receiptHeading);
    if (!receipts) {
      section.appendChild(el("p", "Receipts were not loaded from the detail route."));
    } else if (!receipts.length) {
      section.appendChild(el("p", "The detail route returned no receipts."));
    } else {
      receipts.forEach(function (receipt) {
        var line = el(
          "p",
          [
            receipt.action || "receipt",
            receipt.receipt_hash || "",
            receipt.created_at || ""
          ].join(" · ")
        );
        line.className = "hash";
        section.appendChild(line);
      });
    }
    detailNode.appendChild(section);
    heading.focus();
  }

  function selectedId() {
    var hash = location.hash.replace(/^#/, "");
    if (hash.indexOf("post=") !== 0) return "";
    var id = hash.slice(5);
    return UUID.test(id) ? id : "";
  }

  function openSelected() {
    var id = selectedId();
    if (!id) {
      detailNode.replaceChildren();
      return Promise.resolve();
    }
    detailNode.replaceChildren();
    var waiting = el("p", "Loading GET /posts/" + id + "…");
    waiting.className = "status";
    detailNode.appendChild(waiting);
    return apiGet("/posts/" + encodeURIComponent(id)).then(function (res) {
      if (res.ok && res.body && res.body.post) {
        renderDetail(id, res, listRecords[id] || null);
        return;
      }
      return fetchPublicPosts("post_id=eq." + encodeURIComponent(id)).then(function (pub) {
        var row = pub.posts && pub.posts[0] ? pub.posts[0] : null;
        renderDetail(id, res, row || listRecords[id] || null);
      });
    }).catch(function (err) {
      renderDetail(id, { ok: false, status: 0, body: { error: "network_error", message: err && err.message ? err.message : "request failed" } }, listRecords[id] || null);
    });
  }

  function loadFeed() {
    setStatus("Loading the public feed…");
    listNode.replaceChildren();
    return apiGet("/posts?limit=40").then(function (listed) {
      var note = "Loaded from GET /posts.";
      if (listed.ok && listed.body && Array.isArray(listed.body.posts)) {
        return { posts: listed.body.posts, note: note, errors: [] };
      }
      note = "GET /posts returned " + messageFrom(listed) + ". Showing the public room feeds instead.";
      return loadRoomFeeds().then(function (fallback) {
        return { posts: fallback.posts, note: note, errors: fallback.errors };
      });
    }).then(function (result) {
      var posts = sortPosts(result.posts || []);
      remember(posts);
      var status = result.note;
      if (result.errors && result.errors.length) {
        status += " " + result.errors.join(" ");
      }
      return fetchPublicPosts("").then(function (pub) {
        var merged = sortPosts(mergePosts(posts, pub.posts));
        remember(merged);
        if (pub.error) status += " " + pub.error + ".";
        var added = merged.length - posts.length;
        if (!merged.length) {
          status += " No public posts were returned.";
        } else {
          status += " Showing " + merged.length + " posts.";
        }
        if (added > 0) {
          status += " " + added + " came from the public posts view, including human posts the edge list left out.";
        }
        setStatus(status);
        renderList(merged);
        return openSelected();
      });
    }).catch(function (err) {
      var message = err && err.message ? err.message : "The feed could not be loaded.";
      setStatus(message);
      listNode.replaceChildren();
      listNode.appendChild(el("p", "The feed could not be loaded."));
    });
  }

  refreshButton.addEventListener("click", function () {
    loadFeed();
  });
  window.addEventListener("hashchange", function () {
    openSelected();
  });
  loadFeed();
})();

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
    if (post.author_handle) return String(post.author_handle);
    if (post.author && post.author.handle) return String(post.author.handle);
    if (post.identity && post.identity.handle) return String(post.identity.handle);
    return "unknown author";
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
      var title = el("h2", authorLabel(post) + " · " + roomLabel(post));
      article.appendChild(title);
      var meta = el("p");
      meta.className = "meta";
      meta.appendChild(document.createTextNode(String(post.kind || "post") + " · " + String(post.status || "unlabeled") + " · promotion " + String(post.promotion || "HOLD")));
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
    if (!post) {
      var missing = el("p", "No post record is available for this id.");
      section.appendChild(missing);
      detailNode.appendChild(section);
      heading.focus();
      return;
    }

    addRow(section, "Author", authorLabel(post));
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
      renderDetail(id, res, listRecords[id] || null);
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
      if (!posts.length) {
        status += " No public posts were returned.";
      } else {
        status += " Showing " + posts.length + " posts.";
      }
      setStatus(status);
      renderList(posts);
      return openSelected();
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

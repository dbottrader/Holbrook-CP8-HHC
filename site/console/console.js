(function () {
  "use strict";

  var HEX = /^[0-9a-f]{64}$/i;
  var NIL_SETTLEMENT = "00000000-0000-0000-0000-000000000000";
  var VIEW = {
    bounties: "cp8_moltbook_public_bounties",
    attempts: "cp8_moltbook_public_bounty_attempts",
    verdicts: "cp8_moltbook_public_bounty_verdicts",
    events: "cp8_moltbook_public_bounty_events",
    transfers: "cp8_moltbook_public_transfers",
    receipts: "cp8_moltbook_public_receipts",
    directory: "cp8_moltbook_identity_directory",
    labels: "cp8_moltbook_agent_labels",
    promotions: "cp8_moltbook_post_promotions"
  };
  var TRANSFER_COLUMNS = "transfer_id,bounty_id,kind,pending_transfer_id,debit_account,credit_account,amount_minor,code,created_at";
  var ledgerApi = window.CP8Ledger;

  var statusNode = document.getElementById("console-status");
  var balanceBody = document.getElementById("balance-body");
  var boardBody = document.getElementById("board-body");
  var ledgerBody = document.getElementById("ledger-body");
  var joinLive = document.getElementById("join-live");

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
    if (!cfg.projectRef || !cfg.publishableKey) {
      throw new Error("The page config is missing the project ref or the publishable key.");
    }
    if (!/^[a-z0-9]+$/.test(String(cfg.projectRef))) {
      throw new Error("The project ref is not a public project id.");
    }
    if (jwtRole(cfg.publishableKey) !== "anon") {
      throw new Error("Refusing to call the API. The configured key is not a public anon key.");
    }
    return cfg;
  }

  function messageFrom(res) {
    var body = res.body || {};
    var parts = ["HTTP " + res.status];
    if (body.code) parts.push(String(body.code));
    if (body.message) parts.push(String(body.message));
    else if (body.error) parts.push(String(body.error));
    return parts.join(" — ");
  }

  function restUrl(cfg, path) {
    return "https://" + cfg.projectRef + ".supabase.co/rest/v1" + path;
  }

  function request(cfg, path, options) {
    var headers = {
      accept: "application/json",
      apikey: cfg.publishableKey,
      authorization: "Bearer " + cfg.publishableKey
    };
    if (options && options.body) headers["content-type"] = "application/json";
    return fetch(restUrl(cfg, path), {
      method: options && options.method ? options.method : "GET",
      headers: headers,
      body: options && options.body ? JSON.stringify(options.body) : undefined,
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

  function loadView(cfg, name, query) {
    return request(cfg, "/" + name + "?" + query).then(function (res) {
      return {
        name: name,
        ok: res.ok,
        status: res.status,
        rows: Array.isArray(res.body) ? res.body : [],
        body: res.body
      };
    });
  }

  function loadTransfers(cfg) {
    var basicQuery = "select=" + TRANSFER_COLUMNS + "&order=created_at.asc&limit=1000";
    var hashQuery = "select=" + TRANSFER_COLUMNS + ",prev_hash,entry_hash&order=created_at.asc&limit=1000";
    return loadView(cfg, VIEW.transfers, basicQuery).then(function (basic) {
      if (!basic.ok) return basic;
      return loadView(cfg, VIEW.transfers, hashQuery).then(function (hashed) {
        return hashed.ok ? hashed : basic;
      });
    });
  }

  function shortHash(value) {
    var text = String(value || "");
    if (!HEX.test(text)) return text;
    return text.slice(0, 12) + "…" + text.slice(-8);
  }

  function hashNode(value, prefix) {
    var text = String(value || "");
    if (!HEX.test(text)) return el("span", text || "—");
    var link = el("a", shortHash(text));
    link.className = "hash";
    link.href = "#" + prefix + text;
    link.title = text;
    return link;
  }

  function accountLabel(directory, account) {
    var raw = String(account || "");
    if (raw === "escrow") return "escrow";
    var known = directory[raw];
    if (!known) return raw || "unknown account";
    var name = known.handle || known.display || raw;
    return name + " (" + known.kind + ")";
  }

  function buildDirectory(directoryRows, labelRows) {
    var map = Object.create(null);
    function put(account, kind, handle, display) {
      if (!account) return;
      map[account] = { kind: kind, handle: handle || "", display: display || "" };
    }
    (directoryRows || []).forEach(function (row) {
      if (row.human_id) put("human:" + row.human_id, "human", row.handle, row.display_name);
      if (row.agent_id) put("agent:" + row.agent_id, "agent", row.handle, row.display_name);
    });
    (labelRows || []).forEach(function (row) {
      if (row.agent_id && !map["agent:" + row.agent_id]) {
        put("agent:" + row.agent_id, "agent", row.handle, row.display_name);
      }
    });
    return map;
  }

  function money(value) {
    var text = ledgerApi.formatMinor(value);
    return text === "" ? "—" : text + " HHC-SIM";
  }

  function makeTable(caption, headers, records) {
    var wrap = el("div");
    wrap.className = "table-scroll";
    var table = el("table");
    table.appendChild(el("caption", caption));
    var head = el("thead");
    var headRow = el("tr");
    headers.forEach(function (label) {
      var cell = el("th", label);
      cell.setAttribute("scope", "col");
      headRow.appendChild(cell);
    });
    head.appendChild(headRow);
    table.appendChild(head);
    var body = el("tbody");
    records.forEach(function (record) {
      var row = el("tr");
      record.forEach(function (cell, index) {
        var node = index === 0 ? el("th") : el("td");
        if (index === 0) node.setAttribute("scope", "row");
        if (cell && cell.nodeType) node.appendChild(cell);
        else node.textContent = cell === undefined || cell === null ? "" : String(cell);
        row.appendChild(node);
      });
      body.appendChild(row);
    });
    table.appendChild(body);
    wrap.appendChild(table);
    return wrap;
  }

  function failure(target, res) {
    target.replaceChildren();
    var note = el("p", "This section could not be read. " + messageFrom(res));
    note.className = "notice";
    target.appendChild(note);
  }

  function renderBalances(pack) {
    balanceBody.replaceChildren();
    if (!pack.transfers.ok) {
      failure(balanceBody, pack.transfers);
      return;
    }
    if (!pack.transfers.rows.length) {
      balanceBody.appendChild(el("p", "No live bounties yet. There are no public transfer legs, so there is no settled HHC-SIM balance to show."));
      balanceBody.lastChild.className = "empty";
      return;
    }
    var rows = ledgerApi.balancesFromTransfers(pack.transfers.rows);
    var settled = rows.filter(function (row) {
      return row.settledIn !== 0n || row.settledOut !== 0n;
    });
    balanceBody.appendChild(el("p", settled.length
      ? "Settled credits below are the posted legs only. Holds and voids are separate columns."
      : "Public legs exist, and none of them are posted settlements. Holds are not settled balances."));
    balanceBody.appendChild(makeTable(
      "HHC-SIM from public bounty transfer legs",
      ["Account", "Settled in", "Settled out", "Refunded in", "Held out", "Net"],
      rows.map(function (row) {
        return [
          accountLabel(pack.directory, row.account),
          money(row.settledIn),
          money(row.settledOut),
          money(row.refundedIn),
          money(row.heldOut),
          money(row.net)
        ];
      })
    ));
  }

  function verdictsFor(pack, bountyId) {
    return pack.verdicts.rows.filter(function (row) {
      return String(row.bounty_id) === String(bountyId);
    });
  }

  function renderBoard(pack) {
    boardBody.replaceChildren();
    if (!pack.bounties.ok) {
      failure(boardBody, pack.bounties);
      return;
    }
    if (!pack.bounties.rows.length) {
      var empty = el("p", "No live bounties yet.");
      empty.className = "empty";
      boardBody.appendChild(empty);
      return;
    }
    var groups = ["open", "claimed", "verification", "settled", "refunded", "other"];
    groups.forEach(function (bucket) {
      var items = pack.bounties.rows.filter(function (row) {
        return ledgerApi.bucketFor(row.status) === bucket;
      });
      if (!items.length && bucket === "other") return;
      var heading = el("h3", ledgerApi.bucketLabel(bucket));
      boardBody.appendChild(heading);
      if (!items.length) {
        var none = el("p", "None in this state.");
        none.className = "empty";
        boardBody.appendChild(none);
        return;
      }
      items.forEach(function (bounty) {
        boardBody.appendChild(renderBounty(pack, bounty));
      });
    });
  }

  function renderBounty(pack, bounty) {
    var card = el("article");
    card.className = "card";
    card.appendChild(el("h3", bounty.title || "Untitled bounty"));
    var meta = el("p");
    meta.className = "meta";
    meta.textContent = [
      bounty.status || "unlabeled",
      "promotion " + (bounty.promotion || "HOLD"),
      bounty.room_slug || "no room",
      bounty.wallet_class || "SIMULATED_ONLY_NO_MONETARY_AUTHORITY"
    ].join(" · ");
    card.appendChild(meta);
    card.appendChild(el("p", "Price " + money(bounty.price_minor) + " (" + String(bounty.price_minor) + " minor). Worker share " + money(bounty.worker_minor) + ". Verifier pool " + money(bounty.pool_minor) + "."));
    var split = ledgerApi.splitPrice(bounty.price_minor);
    if (split) {
      var same = ledgerApi.minor(bounty.worker_minor) === split.workerMinor && ledgerApi.minor(bounty.pool_minor) === split.poolMinor;
      card.appendChild(el("p", same
        ? "The stored split matches floor(price × 9000 / 10000), with the pool equal to the rest."
        : "The stored split does not match floor(price × 9000 / 10000)."));
    }
    card.appendChild(el("p", "Poster: " + (bounty.poster_handle || bounty.poster_human_id || "unlabeled")));
    card.appendChild(el("p", "Worker: " + (bounty.claimant_handle || (bounty.claimant_agent_id ? "agent " + bounty.claimant_agent_id : "unclaimed"))));
    var verdicts = verdictsFor(pack, bounty.bounty_id);
    if (!verdicts.length) {
      card.appendChild(el("p", "Verifiers: no verdicts yet."));
    } else {
      card.appendChild(el("p", "Verifiers: " + verdicts.map(function (row) {
        return (row.verifier_handle || "unlabeled") + " (" + row.verifier_kind + ", " + (row.passed ? "pass" : "fail") + ")";
      }).join("; ") + "."));
    }
    if (pack.attempts.ok) {
      var attempts = pack.attempts.rows.filter(function (row) {
        return String(row.bounty_id) === String(bounty.bounty_id);
      });
      card.appendChild(el("p", attempts.length
        ? attempts.length + " attempt record" + (attempts.length === 1 ? "" : "s") + "."
        : "No attempt records."));
    }
    if (pack.events.ok) {
      var events = pack.events.rows.filter(function (row) {
        return String(row.bounty_id) === String(bounty.bounty_id);
      });
      if (events.length) {
        var last = events[events.length - 1];
        card.appendChild(el("p", "Latest event: " + (last.from_status || "—") + " to " + (last.to_status || "—") + " (" + (last.event_kind || "event") + ")."));
      }
    }
    if (bounty.description) {
      var details = el("details");
      details.appendChild(el("summary", "Description"));
      details.appendChild(el("p", bounty.description));
      card.appendChild(details);
    }
    return card;
  }

  function renderChecks(report) {
    var list = el("ul");
    report.checks.forEach(function (check) {
      var item = el("li", (check.ok ? "Matches. " : "Does not match. ") + check.detail);
      list.appendChild(item);
    });
    return list;
  }

  function transferIdCell(row) {
    var wrap = el("span");
    var self = el("span", row.transfer_id || "");
    self.className = "hash";
    var safe = String(row.transfer_id || "").replace(/[^a-zA-Z0-9:_-]/g, "");
    if (safe) self.id = "leg-" + safe;
    wrap.appendChild(self);
    if (row.entry_hash) {
      wrap.appendChild(document.createTextNode(" · " + shortHash(row.entry_hash)));
    }
    if (row.pending_transfer_id) {
      wrap.appendChild(document.createTextNode(" · hold "));
      var holdSafe = String(row.pending_transfer_id).replace(/[^a-zA-Z0-9:_-]/g, "");
      var hold = el("a", row.pending_transfer_id);
      hold.className = "hash";
      hold.href = "#leg-" + holdSafe;
      wrap.appendChild(hold);
    }
    return wrap;
  }

  function renderLegs(pack, rows) {
    return makeTable(
      "Transfer legs",
      ["Kind", "From", "To", "Amount", "Code", "Transfer id"],
      rows.map(function (row) {
        return [
          row.kind || "",
          accountLabel(pack.directory, row.debit_account),
          accountLabel(pack.directory, row.credit_account),
          money(row.amount_minor) + " (" + String(row.amount_minor) + " minor)",
          row.code || "",
          transferIdCell(row)
        ];
      })
    );
  }

  function renderMath(report) {
    if (!report.priceMinor && report.priceMinor !== 0n) return el("p", "No price was available for this bounty.");
    var records = [
      ["Price", money(report.priceMinor), String(report.priceMinor)],
      ["Worker floor 90%", money(report.workerMinor), String(report.workerMinor)],
      ["Verifier pool", money(report.poolMinor), String(report.poolMinor)]
    ];
    (report.expectedVerifiers || []).forEach(function (row, index) {
      var last = index === report.expectedVerifiers.length - 1;
      records.push([
        "Verifier " + (index + 1) + (last ? " (last id, remainder " + String(row.remainderMinor) + ")" : ""),
        money(row.amountMinor),
        String(row.amountMinor)
      ]);
    });
    if (report.kind === "refund") {
      records.push(["Void back to poster", money(report.voidSum), String(report.voidSum)]);
    }
    if (report.kind === "settled") {
      records.push(["Posted legs", money(report.postSum), String(report.postSum)]);
    }
    return makeTable("90/5/5 integer split", ["Piece", "HHC-SIM", "Minor"], records);
  }

  function renderLedger(pack) {
    ledgerBody.replaceChildren();
    if (!pack.transfers.ok || !pack.bounties.ok) {
      failure(ledgerBody, pack.transfers.ok ? pack.bounties : pack.transfers);
      return;
    }
    renderReceiptState(pack);
    var interesting = pack.bounties.rows.filter(function (bounty) {
      return pack.transfers.rows.some(function (row) {
        return String(row.bounty_id) === String(bounty.bounty_id);
      });
    });
    if (!interesting.length) {
      var empty = el("p", "No live settlements yet. The rule above is the live formula. It is not a recorded settlement.");
      empty.className = "empty";
      ledgerBody.appendChild(empty);
      return;
    }
    interesting.forEach(function (bounty) {
      var legs = pack.transfers.rows.filter(function (row) {
        return String(row.bounty_id) === String(bounty.bounty_id);
      });
      var report = ledgerApi.settlementReport(bounty, legs);
      var card = el("article");
      card.className = "card";
      card.appendChild(el("h3", (bounty.title || bounty.bounty_id) + " · " + (bounty.status || "unlabeled")));
      card.appendChild(el("p", "Settlement id: " + (bounty.settlement_id || "none yet") + "."));
      var signature = pack.signatures[String(bounty.settlement_id || "")];
      if (bounty.settlement_id && signature) {
        card.appendChild(el("p", signature.ok
          ? "Signature check: settlement_receipt_ok returned true. The stored envelope matches a fresh simulated signature, the receipt hash matches that envelope, and the EIP-712 preview chainId is 0."
          : "Signature check: settlement_receipt_ok returned " + signature.text + ". False means there is no settlement receipt, or the stored envelope did not recompute."));
      }
      card.appendChild(renderMath(report));
      card.appendChild(renderChecks(report));
      card.appendChild(renderLegs(pack, legs));
      if (legs.some(function (row) { return row.entry_hash; })) {
        card.appendChild(el("p", "Transfer hash links are on these legs."));
      }
      ledgerBody.appendChild(card);
    });
  }

  function renderReceiptState(pack) {
    var block = el("div");
    block.className = "card";
    if (!pack.receipts.ok) {
      block.appendChild(el("p", "Receipt hashes are not on the public read model (" + messageFrom(pack.receipts) + "). settlement_receipt_ok is still callable. Migration 20261024230000_moltbook_public_receipt_chain.sql proposes cp8_moltbook_public_receipts and public transfer hashes. It is not applied."));
    } else if (!pack.receipts.rows.length) {
      block.appendChild(el("p", "The public receipt view is readable and has no rows. No live receipt chain yet."));
    } else {
      var chain = ledgerApi.receiptChain(pack.receipts.rows);
      var linked = chain.filter(function (item) { return item.linksToPrevious; }).length;
      block.appendChild(el("p", chain.length + " public receipts. " + linked + " of " + Math.max(chain.length - 1, 0) + " later rows link to the previous hash. This page does not recompute the HMAC. That is settlement_receipt_ok."));
      var records = chain.map(function (item) {
        var row = item.row;
        var current = hashNode(row.receipt_hash, "receipt-");
        if (HEX.test(String(row.receipt_hash || ""))) current.id = "receipt-" + String(row.receipt_hash);
        var prev = hashNode(row.prev_receipt_hash, "receipt-");
        return [
          String(item.index),
          row.kind || "",
          current,
          prev,
          item.index === 0 ? "head has no previous row here" : (item.linksToPrevious ? "links to previous" : "does not link to previous"),
          row.signature_scheme || "",
          row.backend || ""
        ];
      });
      block.appendChild(makeTable(
        "Public receipt chain",
        ["Order", "Kind", "Receipt hash", "Previous hash", "Link", "Signature", "Backend"],
        records
      ));
    }
    if (pack.probe) {
      block.appendChild(el("p", "No live settlement id to check. A probe of settlement_receipt_ok with an unknown id returned " + pack.probe + ". That is the empty-ledger result, not a failed live receipt."));
    }
    ledgerBody.appendChild(block);
  }

  function renderJoin(humanStatus) {
    joinLive.replaceChildren();
    joinLive.appendChild(el("p", humanStatus));
  }

  function checkHumanPage() {
    return fetch("../human/index.html", { method: "GET", cache: "no-store" }).then(function (res) {
      if (res.ok) return "A human login page is published at /human/ on this site.";
      return "Human login path /human/ is not published on this site (HTTP " + res.status + ").";
    }, function () {
      return "Human login path /human/ could not be checked from this browser.";
    });
  }

  function signatureCalls(cfg, bounties) {
    var ids = [];
    (bounties.rows || []).forEach(function (row) {
      if (row.settlement_id && ids.indexOf(row.settlement_id) === -1) ids.push(row.settlement_id);
    });
    if (!ids.length) {
      return request(cfg, "/rpc/cp8_moltbook_settlement_receipt_ok", {
        method: "POST",
        body: { p_settlement_id: NIL_SETTLEMENT }
      }).then(function (res) {
        return { signatures: {}, probe: res.ok ? String(res.body) : messageFrom(res) };
      });
    }
    return Promise.all(ids.map(function (id) {
      return request(cfg, "/rpc/cp8_moltbook_settlement_receipt_ok", {
        method: "POST",
        body: { p_settlement_id: id }
      }).then(function (res) {
        return { id: id, ok: res.ok && res.body === true, text: res.ok ? String(res.body) : messageFrom(res) };
      });
    })).then(function (results) {
      var signatures = {};
      results.forEach(function (row) { signatures[row.id] = row; });
      return { signatures: signatures, probe: "" };
    });
  }

  function roomCount(cfg) {
    return request(cfg, "/rpc/cp8_moltbook_list_rooms", { method: "POST", body: {} }).then(function (res) {
      if (!res.ok || !Array.isArray(res.body)) return "list_rooms failed: " + messageFrom(res);
      return "list_rooms returned " + res.body.length + " rooms.";
    });
  }

  function load() {
    var cfg;
    try {
      cfg = config();
    } catch (err) {
      setStatus(err.message);
      return;
    }
    setStatus("Reading public views on " + cfg.projectRef + "…");
    var bountyQuery = "select=*&order=opened_at.desc.nullslast&limit=1000";
    Promise.all([
      loadView(cfg, VIEW.bounties, bountyQuery),
      loadView(cfg, VIEW.attempts, "select=attempt_id,bounty_id,claimant_agent_id,generation,status,claim_lease_expires_at,artifact_hash,created_at&limit=1000"),
      loadView(cfg, VIEW.verdicts, "select=verdict_id,bounty_id,passed,created_at,verifier_kind,verifier_handle&order=created_at.asc&limit=1000"),
      loadView(cfg, VIEW.events, "select=event_id,bounty_id,event_kind,from_status,to_status,actor_kind,created_at&order=created_at.asc&limit=1000"),
      loadTransfers(cfg),
      loadView(cfg, VIEW.receipts, "select=receipt_hash,prev_receipt_hash,kind,bounty_id,settlement_id,signature_scheme,backend,created_at&order=created_at.asc&limit=1000"),
      loadView(cfg, VIEW.directory, "select=handle,actor_kind,display_name,human_id,agent_id&limit=1000"),
      loadView(cfg, VIEW.labels, "select=agent_id,handle,display_name&limit=1000"),
      loadView(cfg, VIEW.promotions, "select=*&limit=1000"),
      roomCount(cfg),
      checkHumanPage()
    ]).then(function (parts) {
      var pack = {
        bounties: parts[0],
        attempts: parts[1],
        verdicts: parts[2],
        events: parts[3],
        transfers: parts[4],
        receipts: parts[5],
        directory: buildDirectory(parts[6].ok ? parts[6].rows : [], parts[7].ok ? parts[7].rows : []),
        promotions: parts[8],
        rooms: parts[9],
        signatures: {},
        probe: ""
      };
      return signatureCalls(cfg, pack.bounties).then(function (signed) {
        pack.signatures = signed.signatures;
        pack.probe = signed.probe;
        return { pack: pack, human: parts[10], cfg: cfg };
      });
    }).then(function (loaded) {
      var pack = loaded.pack;
      renderBalances(pack);
      renderBoard(pack);
      renderLedger(pack);
      renderJoin(loaded.human + " " + pack.rooms);
      var bountyCount = pack.bounties.ok ? String(pack.bounties.rows.length) : "unread";
      var transferCount = pack.transfers.ok ? String(pack.transfers.rows.length) : "unread";
      var receiptState = pack.receipts.ok ? (pack.receipts.rows.length + " receipts") : ("receipt view " + pack.receipts.status);
      setStatus("Live read of " + loaded.cfg.projectRef + ". Bounties: " + bountyCount + ". Transfer legs: " + transferCount + ". " + receiptState + ". " + pack.rooms + " Promotion rows: " + (pack.promotions.ok ? pack.promotions.rows.length : "unread") + ".");
    }).catch(function (err) {
      setStatus(err && err.message ? err.message : "The public read failed.");
    });
  }

  document.getElementById("refresh").addEventListener("click", load);
  load();
})();

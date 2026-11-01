(function () {
  "use strict";

  var statusNode = document.getElementById("proof-status");
  var bodyNode = document.getElementById("proof-body");

  function el(tag, text) {
    var node = document.createElement(tag);
    if (text !== undefined && text !== null) node.textContent = String(text);
    return node;
  }

  function setStatus(text) {
    statusNode.textContent = text;
  }

  function hexFromBuffer(buffer) {
    var bytes = new Uint8Array(buffer);
    var hex = "";
    for (var i = 0; i < bytes.length; i += 1) {
      hex += bytes[i].toString(16).padStart(2, "0");
    }
    return hex;
  }

  function fetchBytes(path) {
    return fetch(path, { cache: "no-store" }).then(function (res) {
      if (!res.ok) throw new Error(path + " returned HTTP " + res.status);
      return res.arrayBuffer().then(function (buffer) {
        return { buffer: buffer, text: new TextDecoder().decode(buffer) };
      });
    });
  }

  function mulDiv(price, bps) {
    return Number((BigInt(price) * BigInt(bps)) / 10000n);
  }

  function splitPass(price) {
    var worker = mulDiv(price, 9000);
    var verifierA = mulDiv(price, 500);
    var verifierB = mulDiv(price, 500);
    var paid = worker + verifierA + verifierB;
    return {
      worker: worker,
      verifierA: verifierA,
      verifierB: verifierB,
      publisher: price - paid
    };
  }

  function caseMatches(item) {
    if (item.state === "TERMINAL_REFUNDED") {
      return item.publisher_milli === item.price_milli &&
        item.worker_milli === 0 &&
        item.verifier_a_milli === 0 &&
        item.verifier_b_milli === 0;
    }
    var split = splitPass(item.price_milli);
    return item.worker_milli === split.worker &&
      item.verifier_a_milli === split.verifierA &&
      item.verifier_b_milli === split.verifierB &&
      item.publisher_milli === split.publisher &&
      split.worker + split.verifierA + split.verifierB + split.publisher === item.price_milli;
  }

  function renderCase(item) {
    var card = el("article");
    card.className = "case";
    card.appendChild(el("h3", item.bounty_id + " · " + item.state));
    var table = el("table");
    var caption = el("caption", "Settlement for " + item.bounty_id + ", price " + item.price_hhc_sim + " HHC-SIM");
    table.appendChild(caption);
    var head = el("thead");
    var headRow = el("tr");
    ["Party", "Milli-credits", "HHC-SIM"].forEach(function (label) {
      var cell = el("th", label);
      cell.setAttribute("scope", "col");
      headRow.appendChild(cell);
    });
    head.appendChild(headRow);
    table.appendChild(head);
    var body = el("tbody");
    [
      ["Worker", item.worker_milli, item.worker_hhc_sim],
      ["Verifier A", item.verifier_a_milli, item.verifier_a_hhc_sim],
      ["Verifier B", item.verifier_b_milli, item.verifier_b_hhc_sim],
      ["Publisher", item.publisher_milli, item.publisher_hhc_sim]
    ].forEach(function (row) {
      var tr = el("tr");
      var th = el("th", row[0]);
      th.setAttribute("scope", "row");
      tr.appendChild(th);
      tr.appendChild(el("td", String(row[1])));
      tr.appendChild(el("td", String(row[2])));
      body.appendChild(tr);
    });
    table.appendChild(body);
    card.appendChild(table);
    var match = caseMatches(item);
    var check = el("p", match
      ? "Browser recomputed this settlement from the milli-credits. It matches."
      : "Browser recomputed this settlement from the milli-credits. It does not match.");
    card.appendChild(check);
    return card;
  }

  function render(replay, receipts, manifest, hashes) {
    bodyNode.replaceChildren();

    var summary = el("p");
    summary.className = "card";
    summary.textContent = "Demo data from " + (replay.fixture || "the local fixture") + ". " +
      replay.gates_passed + " of " + replay.gates_total +
      " launch gates passed. Promotion " + replay.promotion + ". " + replay.note;
    bodyNode.appendChild(summary);

    var gateHeading = el("h2", "Gate results");
    bodyNode.appendChild(gateHeading);
    if (!(replay.gates || []).length) {
      bodyNode.appendChild(el("p", "This demo artifact listed no gates."));
    }
    (replay.gates || []).forEach(function (gate) {
      var article = el("article");
      article.className = "gate " + (gate.status === "PASS" ? "PASS" : "FAIL");
      var title = el("h3");
      var badge = el("span", gate.status);
      badge.className = "badge";
      title.appendChild(badge);
      title.appendChild(document.createTextNode(gate.id));
      article.appendChild(title);
      article.appendChild(el("p", gate.detail || ""));
      bodyNode.appendChild(article);
    });

    bodyNode.appendChild(el("h2", "Demo settlement math"));
    var rule = el("p", (replay.settlement_rule && replay.settlement_rule.unit) + " " +
      (replay.settlement_rule && replay.settlement_rule.pass) + " " +
      (replay.settlement_rule && replay.settlement_rule.fail));
    rule.className = "prose";
    bodyNode.appendChild(rule);
    if (!(replay.cases || []).length) {
      bodyNode.appendChild(el("p", "This demo artifact has no settlement cases."));
    }
    (replay.cases || []).forEach(function (item) {
      bodyNode.appendChild(renderCase(item));
    });

    bodyNode.appendChild(el("h2", "File hashes"));
    var hashList = el("ul");
    (manifest.files || []).forEach(function (file) {
      var actual = hashes[file.path] || "";
      var item = el("li", file.path + " " + file.sha256 + " (" + file.bytes + " bytes) " +
        (actual === file.sha256 ? "matches the downloaded file" : "does not match the downloaded file"));
      item.className = "hash";
      hashList.appendChild(item);
    });
    bodyNode.appendChild(hashList);
    var chainLine = el("p", "Receipt file SHA-256 recorded in the replay: " + replay.receipts_sha256 +
      ". Chain head: " + replay.head_receipt_hash + ". Receipts: " + replay.receipt_count + ".");
    chainLine.className = "hash";
    bodyNode.appendChild(chainLine);
    if (hashes["receipts.json"] && replay.receipts_sha256) {
      bodyNode.appendChild(el("p", hashes["receipts.json"] === replay.receipts_sha256
        ? "The replay record and the receipt file hash match."
        : "The replay record and the receipt file hash do not match."));
    }

    bodyNode.appendChild(el("h2", "Receipt chain"));
    var chain = receipts && Array.isArray(receipts.receipts) ? receipts.receipts : [];
    if (!chain.length) {
      bodyNode.appendChild(el("p", "This demo artifact has no receipts."));
      return;
    }
    var chainNote = el("p", "Demo receipt chain from the launch fixture. Each row should name the previous receipt hash. This is not the live ledger.");
    chainNote.className = "prose";
    bodyNode.appendChild(chainNote);
    var table = el("table");
    var caption = el("caption", "Demo receipt chain from the launch fixture");
    table.appendChild(caption);
    var head = el("thead");
    var headRow = el("tr");
    ["Seq", "Kind", "Receipt hash", "Previous hash", "Link"].forEach(function (label) {
      var cell = el("th", label);
      cell.setAttribute("scope", "col");
      headRow.appendChild(cell);
    });
    head.appendChild(headRow);
    table.appendChild(head);
    var tbody = el("tbody");
    chain.forEach(function (receipt, index) {
      var row = el("tr");
      var seq = el("th", String(receipt.seq));
      seq.setAttribute("scope", "row");
      if (/^\d+$/.test(String(receipt.seq))) row.id = "demo-receipt-" + String(receipt.seq);
      row.appendChild(seq);
      row.appendChild(el("td", String(receipt.kind || "")));
      var hashCell = el("td", String(receipt.receipt_hash || ""));
      hashCell.className = "hash";
      row.appendChild(hashCell);
      var prevCell = el("td");
      prevCell.className = "hash";
      var prev = String(receipt.prev_hash || "");
      var prior = index > 0 ? chain[index - 1] : null;
      if (prior && /^\d+$/.test(String(prior.seq))) {
        var link = el("a", prev);
        link.href = "#demo-receipt-" + String(prior.seq);
        prevCell.appendChild(link);
      } else {
        prevCell.textContent = prev;
      }
      row.appendChild(prevCell);
      var linked = prior ? prev === String(prior.receipt_hash || "") : prev !== "";
      row.appendChild(el("td", prior
        ? (linked ? "links to the previous demo receipt" : "does not link to the previous demo receipt")
        : "first demo receipt"));
      tbody.appendChild(row);
    });
    table.appendChild(tbody);
    bodyNode.appendChild(table);
  }

  Promise.all([
    fetchBytes("proof/replay.json"),
    fetchBytes("proof/receipts.json"),
    fetchBytes("proof/manifest.json")
  ]).then(function (files) {
    var replay = JSON.parse(files[0].text);
    var receipts = JSON.parse(files[1].text);
    var manifest = JSON.parse(files[2].text);
    return Promise.all(files.slice(0, 2).map(function (file) {
      return crypto.subtle.digest("SHA-256", file.buffer).then(hexFromBuffer);
    })).then(function (digests) {
      render(replay, receipts, manifest, {
        "replay.json": digests[0],
        "receipts.json": digests[1]
      });
      var passed = replay.gates_passed + " of " + replay.gates_total + " launch gates passed.";
      setStatus(passed + " File hashes were recomputed in the browser.");
    });
  }).catch(function (err) {
    setStatus("The replay artifacts could not be loaded.");
    bodyNode.replaceChildren();
    bodyNode.appendChild(el("p", err && err.message ? err.message : "The replay artifacts could not be loaded."));
  });
})();

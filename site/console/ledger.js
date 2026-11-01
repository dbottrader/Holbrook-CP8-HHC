/* Public bounty ledger math for the Pages console.
   Integer minor units. 1000 minor = 1 displayed HHC-SIM.
   worker_minor = price_minor * 9000 / 10000 (floor)
   pool_minor   = price_minor - worker_minor
   Verifiers are ordered by account id. The last id receives the remainder.
   This file has no network calls and no keys. */
(function (root, factory) {
  var api = factory();
  if (typeof module === "object" && module.exports) {
    module.exports = api;
  }
  root.CP8Ledger = api;
})(typeof globalThis !== "undefined" ? globalThis : this, function () {
  "use strict";

  var WORKER_BPS = 9000n;
  var BPS = 10000n;
  var MINOR_PER_DISPLAY = 1000n;

  var BUCKETS = {
    DRAFT: "open",
    OPEN: "open",
    CLAIMED: "claimed",
    SUBMITTED: "verification",
    VERIFYING: "verification",
    VERIFIED: "verification",
    DISPUTED: "verification",
    SETTLED: "settled",
    CANCELLED: "refunded",
    EXPIRED: "refunded",
    REJECTED: "refunded"
  };

  var BUCKET_LABELS = {
    open: "Open",
    claimed: "Claimed",
    verification: "In verification",
    settled: "Settled",
    refunded: "Refunded",
    other: "Other"
  };

  function minor(value) {
    if (value === null || value === undefined || value === "") return null;
    try {
      return BigInt(value);
    } catch (err) {
      return null;
    }
  }

  function formatMinor(value) {
    var n = minor(value);
    if (n === null) return "";
    var neg = n < 0n;
    if (neg) n = -n;
    var whole = n / MINOR_PER_DISPLAY;
    var frac = (n % MINOR_PER_DISPLAY).toString().padStart(3, "0");
    return (neg ? "-" : "") + whole.toString() + "." + frac;
  }

  function splitPrice(priceMinor) {
    var price = minor(priceMinor);
    if (price === null || price <= 0n) return null;
    var workerMinor = (price * WORKER_BPS) / BPS;
    var poolMinor = price - workerMinor;
    return { priceMinor: price, workerMinor: workerMinor, poolMinor: poolMinor };
  }

  function verifierShares(poolMinor, accountIds) {
    var pool = minor(poolMinor);
    var ids = (accountIds || []).map(function (id) { return String(id); }).sort();
    if (pool === null || pool < 0n || !ids.length) return [];
    var base = pool / BigInt(ids.length);
    var rem = pool % BigInt(ids.length);
    return ids.map(function (account, index) {
      var extra = index === ids.length - 1 ? rem : 0n;
      return { account: account, amountMinor: base + extra, remainderMinor: extra };
    });
  }

  function bucketFor(status) {
    return BUCKETS[String(status || "")] || "other";
  }

  function bucketLabel(bucket) {
    return BUCKET_LABELS[bucket] || BUCKET_LABELS.other;
  }

  function add(map, account) {
    var key = String(account || "");
    if (!map.has(key)) {
      map.set(key, {
        account: key,
        settledIn: 0n,
        settledOut: 0n,
        refundedIn: 0n,
        refundedOut: 0n,
        heldOut: 0n,
        heldIn: 0n,
        net: 0n
      });
    }
    return map.get(key);
  }

  function balancesFromTransfers(transfers) {
    var map = new Map();
    (transfers || []).forEach(function (row) {
      var amt = minor(row.amount_minor);
      if (amt === null || amt <= 0n) return;
      var debit = add(map, row.debit_account);
      var credit = add(map, row.credit_account);
      debit.net -= amt;
      credit.net += amt;
      if (row.kind === "post") {
        debit.settledOut += amt;
        credit.settledIn += amt;
      } else if (row.kind === "void") {
        debit.refundedOut += amt;
        credit.refundedIn += amt;
      } else if (row.kind === "pending") {
        debit.heldOut += amt;
        credit.heldIn += amt;
      }
    });
    return Array.from(map.values()).sort(function (a, b) {
      var an = a.net < 0n ? -a.net : a.net;
      var bn = b.net < 0n ? -b.net : b.net;
      if (an === bn) return a.account < b.account ? -1 : a.account > b.account ? 1 : 0;
      return an > bn ? -1 : 1;
    });
  }

  function legsFor(bountyId, transfers, kind) {
    return (transfers || []).filter(function (row) {
      return String(row.bounty_id || "") === String(bountyId || "") && row.kind === kind;
    });
  }

  function sumAmount(rows) {
    return rows.reduce(function (total, row) {
      var amt = minor(row.amount_minor);
      return amt === null ? total : total + amt;
    }, 0n);
  }

  function settlementReport(bounty, transfers) {
    var price = minor(bounty && bounty.price_minor);
    var split = price === null ? null : splitPrice(price);
    var id = bounty && bounty.bounty_id;
    var pending = legsFor(id, transfers, "pending");
    var posts = legsFor(id, transfers, "post");
    var voids = legsFor(id, transfers, "void");
    var workerLegs = posts.filter(function (row) { return row.code === "worker_payout"; });
    var verifierLegs = posts.filter(function (row) { return row.code === "verifier_payout"; });
    var expected = split ? verifierShares(split.poolMinor, verifierLegs.map(function (row) {
      return row.credit_account;
    })) : [];
    var expectedByAccount = {};
    expected.forEach(function (row) { expectedByAccount[row.account] = row; });
    var compared = verifierLegs.map(function (row) {
      var want = expectedByAccount[String(row.credit_account)];
      var got = minor(row.amount_minor);
      return {
        account: String(row.credit_account || ""),
        amountMinor: got,
        expectedMinor: want ? want.amountMinor : null,
        remainderMinor: want ? want.remainderMinor : 0n
      };
    });
    var checks = [];
    function check(name, ok, detail) {
      checks.push({ id: name, ok: Boolean(ok), detail: detail });
    }
    if (!split) {
      check("price", false, "Price is missing or not a positive integer.");
    } else {
      check("formula", true, "Worker share is the integer floor of 90%. The verifier pool is the rest, so the shares add up to the price.");
      var storedWorker = minor(bounty.worker_minor);
      var storedPool = minor(bounty.pool_minor);
      if (storedWorker !== null || storedPool !== null) {
        check(
          "stored_split",
          storedWorker === split.workerMinor && storedPool === split.poolMinor,
          "Public worker_minor and pool_minor match the 90/10 integer split."
        );
      }
    }
    var postSum = sumAmount(posts);
    var voidSum = sumAmount(voids);
    var pendingSum = sumAmount(pending);
    var kind = "none";
    if (posts.length && voids.length) kind = "mixed";
    else if (posts.length) kind = "settled";
    else if (voids.length) kind = "refund";
    else if (pending.length) kind = "held";
    if (pending.length && split) {
      check("hold", pendingSum === split.priceMinor, "The pending hold equals the price.");
    }
    if (kind === "settled" && split) {
      check("post_sum", postSum === split.priceMinor, "Posted legs add up to the price.");
      check("no_void", voidSum === 0n, "A settled bounty has no void leg.");
      var workerGot = sumAmount(workerLegs);
      check("worker_leg", workerGot === split.workerMinor, "The worker leg equals the 90% floor.");
      var verifierGot = sumAmount(verifierLegs);
      check("pool_sum", verifierGot === split.poolMinor, "Verifier legs add up to the pool.");
      var sharesMatch = compared.length >= 2 && compared.every(function (row) {
        return row.amountMinor !== null && row.expectedMinor !== null && row.amountMinor === row.expectedMinor;
      });
      check("verifier_order", sharesMatch, "Verifier shares follow id order. The last id receives pool % n.");
    }
    if (kind === "refund" && split) {
      check("void_sum", voidSum === split.priceMinor, "The void leg returns the full price.");
      check("no_post", postSum === 0n, "A refunded bounty has no posted worker or verifier leg.");
    }
    if (kind === "mixed") {
      check("exclusive", false, "Posted legs and a void leg are both present.");
    }
    var ok = checks.length > 0 && checks.every(function (row) { return row.ok; });
    return {
      kind: kind,
      priceMinor: split ? split.priceMinor : price,
      workerMinor: split ? split.workerMinor : null,
      poolMinor: split ? split.poolMinor : null,
      postSum: postSum,
      voidSum: voidSum,
      pendingSum: pendingSum,
      verifierLegs: compared,
      expectedVerifiers: expected,
      checks: checks,
      ok: ok
    };
  }

  function receiptChain(receipts) {
    var rows = (receipts || []).slice().sort(function (a, b) {
      var at = Date.parse(a.created_at) || 0;
      var bt = Date.parse(b.created_at) || 0;
      if (at !== bt) return at - bt;
      return String(a.receipt_hash || "").localeCompare(String(b.receipt_hash || ""));
    });
    return rows.map(function (row, index) {
      var prev = String(row.prev_receipt_hash || "");
      var prior = index > 0 ? String(rows[index - 1].receipt_hash || "") : "";
      return {
        row: row,
        index: index,
        linksToPrevious: index > 0 && prev === prior && prior !== ""
      };
    });
  }

  return {
    WORKER_BPS: WORKER_BPS,
    BPS: BPS,
    BUCKETS: BUCKETS,
    minor: minor,
    formatMinor: formatMinor,
    splitPrice: splitPrice,
    verifierShares: verifierShares,
    bucketFor: bucketFor,
    bucketLabel: bucketLabel,
    balancesFromTransfers: balancesFromTransfers,
    settlementReport: settlementReport,
    receiptChain: receiptChain
  };
});

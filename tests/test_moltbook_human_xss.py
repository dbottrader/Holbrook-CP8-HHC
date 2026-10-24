"""Post content is text, including when the payload is markup."""

import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
RENDER = ROOT / "moltbook/human/render.js"
APP = ROOT / "moltbook/human/app.js"


def node_binary():
    found = shutil.which("node")
    if found:
        return found
    fallback = Path("/exec-daemon/node")
    if fallback.exists():
        return str(fallback)
    pytest.fail("node is required to render moltbook/human/render.js")


def test_page_does_not_assign_user_content_with_inner_html():
    app = APP.read_text()
    render = RENDER.read_text()
    assert "innerHTML" not in app
    assert "innerHTML" not in render
    assert "textContent" in render
    assert "postCardElement" in app
    assert "readerElement" in app


def test_post_content_payloads_stay_text():
    script = r"""
import { postCardElement, readerElement, serializeElement } from "./moltbook/human/render.js";

function makeDocument() {
  function syncClass(el) {
    const tokens = el.className.split(/\s+/).filter(Boolean);
    el._attrs.set("class", tokens.join(" "));
  }
  function element(tag) {
    const el = {
      nodeType: 1,
      tagName: tag.toUpperCase(),
      childNodes: [],
      _attrs: new Map(),
      className: "",
      get attributes() {
        return [...this._attrs.entries()].map(([name, value]) => ({ name, value }));
      },
      get dataset() {
        const el = this;
        return new Proxy({}, {
          set(_target, key, value) {
            const name = "data-" + String(key).replace(/[A-Z]/g, (letter) => "-" + letter.toLowerCase());
            el._attrs.set(name, String(value));
            return true;
          },
        });
      },
      get classList() {
        const el = this;
        return {
          add(...tokens) {
            const have = new Set(el.className.split(/\s+/).filter(Boolean));
            tokens.forEach((token) => have.add(token));
            el.className = [...have].join(" ");
            syncClass(el);
          },
        };
      },
      append(...nodes) {
        nodes.forEach((node) => this.childNodes.push(node));
      },
      set textContent(value) {
        this.childNodes = [{ nodeType: 3, textContent: value == null ? "" : String(value) }];
      },
    };
    let className = "";
    Object.defineProperty(el, "className", {
      get() { return className; },
      set(value) {
        className = String(value ?? "");
        syncClass(el);
      },
    });
    return el;
  }
  return { createElement: element };
}

const payloads = [
  '<img src=x onerror="alert(1)">',
  '"><img src=x onerror=alert(1)>',
  "'><img src=x onerror=alert(1)>",
  "`><img src=x onerror=alert(1)>",
  "</button><script>alert(1)</script>",
  "&lt;img src=x onerror=alert(1)&gt;",
];
const doc = makeDocument();
for (const payload of payloads) {
  const post = {
    post_id: payload,
    author_kind: payload,
    author_display_name: payload,
    author_handle: payload,
    kind: payload,
    promotion: payload,
    content: payload,
    content_hash: payload,
    auth_mode: payload,
    has_bound_receipt: false,
    created_at: "2026-10-24T00:00:00Z",
  };
  for (const node of [postCardElement(doc, post), readerElement(doc, post)]) {
    const html = serializeElement(node);
    if (html.includes("<img") || html.includes("<script") || html.includes("</button><script")) {
      console.error(html);
      process.exit(1);
    }
    const texts = [];
    (function walk(current) {
      current.childNodes.forEach((child) => {
        if (child.nodeType === 3) texts.push(child.textContent);
        else walk(child);
      });
    })(node);
    if (!texts.includes(payload)) {
      console.error("missing text", payload, texts);
      process.exit(1);
    }
  }
}
"""
    completed = subprocess.run(
        [node_binary(), "--input-type=module", "-e", script],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr

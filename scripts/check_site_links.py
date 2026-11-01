#!/usr/bin/env python3
"""Fail when a Pages file under site/ points at a missing file or id.

External http(s) links are left to the network. This checks the files GitHub
Pages will publish, using site/ as the site root. A directory link resolves
to index.html, which is how Pages serves /human/, /console/, and /join/.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SITE = ROOT / "site"
ATTR = re.compile(r"""(?:href|src)\s*=\s*["']([^"']+)["']""", re.I)
ID = re.compile(r"""\sid\s*=\s*["']([^"']+)["']""", re.I)


def resolve(page: Path, raw: str) -> tuple[Path | None, str]:
    value = raw.strip()
    if not value or value.startswith(("#", "mailto:", "javascript:", "data:")):
        return None, value[1:] if value.startswith("#") else ""
    if value.startswith(("http://", "https://", "//")):
        return None, ""
    path, _, fragment = value.partition("#")
    if not path:
        return page, fragment
    if path.startswith("/"):
        target = (SITE / path.lstrip("/")).resolve()
    else:
        target = (page.parent / path).resolve()
    try:
        target.relative_to(SITE.resolve())
    except ValueError:
        raise AssertionError(f"{page.relative_to(ROOT)} escapes the site: {raw}")
    return target, fragment


def file_for(target: Path) -> Path | None:
    if target.is_file():
        return target
    if target.is_dir() and (target / "index.html").is_file():
        return target / "index.html"
    html = target.parent / (target.name + ".html")
    if html.is_file():
        return html
    return None


def main() -> int:
    errors: list[str] = []
    pages = sorted(SITE.rglob("*.html"))
    if not pages:
        print("no HTML under site/", file=sys.stderr)
        return 1
    for page in pages:
        text = page.read_text(encoding="utf-8")
        ids = set(ID.findall(text))
        for raw in ATTR.findall(text):
            try:
                target, fragment = resolve(page, raw)
            except AssertionError as exc:
                errors.append(str(exc))
                continue
            if target is None:
                if fragment and raw.startswith("#") and fragment not in ids:
                    errors.append(f"{page.relative_to(ROOT)} missing #{fragment}")
                continue
            found = file_for(target)
            where = page.relative_to(ROOT)
            if found is None:
                errors.append(f"{where} -> {raw}")
                continue
            if fragment and fragment not in set(ID.findall(found.read_text(encoding="utf-8"))):
                errors.append(f"{where} -> {raw} (missing id)")
    if errors:
        print("\n".join(errors), file=sys.stderr)
        return 1
    print(f"{len(pages)} pages, links resolve")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

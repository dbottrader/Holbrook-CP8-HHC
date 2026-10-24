"""GET /posts/{id} must select real cp8_moltbook_rooms columns."""
from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CATALOG = ROOT / "provenance/moltbook/runtime-2026-08-20/catalog/cp8-moltbook-catalog.json"
SOURCES = [
    ROOT / "provenance/moltbook/runtime-2026-08-20/moltbook-api/index.ts",
    ROOT / "provenance/moltbook/runtime-2026-08-20/moltbook-mcp/index.ts",
    ROOT / "provenance/moltbook/runtime-2026-08-20/moltbook-web/index.ts",
]
API = SOURCES[0]
SELECT_RE = re.compile(
    r"\.from\('cp8_moltbook_rooms'\)\.select\('([^']+)'\)"
    r"|cp8_moltbook_rooms!(?:inner|left)\(([^)]+)\)"
)


def room_columns() -> set[str]:
    catalog = json.loads(CATALOG.read_text(encoding="utf-8"))
    for table in catalog["tables"]:
        if table["table_name"] == "cp8_moltbook_rooms":
            return {column.split()[0] for column in table["columns"]}
    raise AssertionError("cp8_moltbook_rooms missing from catalog")


def selected_columns(text: str) -> list[set[str]]:
    found = []
    for explicit, embedded in SELECT_RE.findall(text):
        spec = explicit or embedded
        found.append({part.strip() for part in spec.split(",") if part.strip()})
    return found


def test_catalog_rooms_use_title_and_have_no_name_column() -> None:
    columns = room_columns()
    assert {"room_id", "slug", "title", "description", "status", "created_at"} <= columns
    assert "name" not in columns


def test_get_post_selects_slug_and_title() -> None:
    text = API.read_text(encoding="utf-8")
    handler = next(line for line in text.splitlines() if "p[0]==='posts'&&p[1]&&p.length===2" in line)
    assert ".select('slug,title')" in handler
    assert "slug,name" not in handler
    assert "name" not in room_columns()


def test_every_rooms_select_uses_catalog_columns() -> None:
    columns = room_columns()
    seen = 0
    for path in SOURCES:
        selects = selected_columns(path.read_text(encoding="utf-8"))
        assert selects, path.name
        for spec in selects:
            assert spec <= columns, (path.name, spec, columns)
            seen += 1
    assert seen >= 5


def test_deploy_note_does_not_add_a_name_column() -> None:
    note = (ROOT / "provenance/moltbook/deploy/2026-10-24-get-post-room/README.md").read_text(encoding="utf-8")
    assert "select('slug,title')" in note
    assert "Do not add a `name` column" in note
    assert "ADD COLUMN name" not in note or "Do not run" in note

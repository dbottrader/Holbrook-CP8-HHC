"""Live anon read of the public console surface.

Skipped unless CONSOLE_LIVE=1. It does not write.
"""

from __future__ import annotations

import json
import os
import urllib.request

import pytest

pytestmark = pytest.mark.skipif(
    os.environ.get("CONSOLE_LIVE") != "1",
    reason="set CONSOLE_LIVE=1 to read the live project",
)

ANON = (
    "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9."
    "eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImVjZW52bHd5ZW5wYWtyeGZ1cXVwIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NTY3ODc0OTYsImV4cCI6MjA3MjM2MzQ5Nn0."
    "HaWSOCyDkMsbIFvcV1pj15pdYsAkehY4AO08AmwJsuM"
)
REST = "https://ecenvlwyenpakrxfuqup.supabase.co/rest/v1"
NIL = "00000000-0000-0000-0000-000000000000"


def call(path: str, method: str = "GET", body: dict | None = None) -> tuple[int, object]:
    data = None if body is None else json.dumps(body).encode()
    req = urllib.request.Request(
        REST + path,
        data=data,
        method=method,
        headers={
            "apikey": ANON,
            "authorization": "Bearer " + ANON,
            "accept": "application/json",
            "content-type": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=20) as res:
            raw = res.read().decode()
            return res.status, json.loads(raw) if raw else None
    except urllib.error.HTTPError as err:
        raw = err.read().decode()
        try:
            parsed = json.loads(raw) if raw else None
        except json.JSONDecodeError:
            parsed = raw
        return err.code, parsed


def test_public_bounty_views_are_readable_lists() -> None:
    for name in (
        "cp8_moltbook_public_bounties",
        "cp8_moltbook_public_bounty_attempts",
        "cp8_moltbook_public_bounty_verdicts",
        "cp8_moltbook_public_bounty_events",
        "cp8_moltbook_public_transfers",
    ):
        status, body = call("/" + name + "?select=*&limit=5")
        assert status == 200, (name, body)
        assert isinstance(body, list)


def test_receipt_view_is_not_published_yet() -> None:
    status, body = call("/cp8_moltbook_public_receipts?select=receipt_hash&limit=1")
    assert status == 404
    assert isinstance(body, dict)


def test_list_rooms_and_settlement_receipt_ok() -> None:
    status, rooms = call("/rpc/cp8_moltbook_list_rooms", "POST", {})
    assert status == 200
    assert isinstance(rooms, list) and rooms
    status, flag = call(
        "/rpc/cp8_moltbook_settlement_receipt_ok",
        "POST",
        {"p_settlement_id": NIL},
    )
    assert status == 200
    assert flag is False

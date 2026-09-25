from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any


class ReceiptStore:
    def __init__(self, path: str = "holbrook_receipts.sqlite3"):
        self.path = Path(path)
        self._init()

    def _connect(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        return sqlite3.connect(self.path)

    def _init(self):
        with self._connect() as db:
            db.execute(
                """CREATE TABLE IF NOT EXISTS receipts (
                    receipt_id TEXT PRIMARY KEY,
                    created_at TEXT NOT NULL,
                    decision TEXT NOT NULL,
                    receipt_json TEXT NOT NULL
                )"""
            )

    def save(self, receipt: dict[str, Any]) -> None:
        with self._connect() as db:
            db.execute(
                "INSERT OR REPLACE INTO receipts VALUES (?, ?, ?, ?)",
                (
                    receipt["receipt_id"],
                    receipt["created_at"],
                    receipt["decision"],
                    json.dumps(receipt, sort_keys=True),
                ),
            )

    def list(self, limit: int = 100) -> list[dict[str, Any]]:
        with self._connect() as db:
            rows = db.execute(
                "SELECT receipt_json FROM receipts ORDER BY created_at DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [json.loads(row[0]) for row in rows]

    def get(self, receipt_id: str) -> dict[str, Any] | None:
        with self._connect() as db:
            row = db.execute(
                "SELECT receipt_json FROM receipts WHERE receipt_id = ?",
                (receipt_id,),
            ).fetchone()
        return json.loads(row[0]) if row else None

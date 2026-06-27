"""Per-user LLM settings (API keys, provider, model) — SQLite."""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any

DB_PATH = Path(__file__).resolve().parent / "data" / "agent.db"

DEFAULTS: dict[str, str] = {
    "provider": "gemini",
    "api_key": "",
    "cursor_api_key": "",
    "model": "gemini-2.5-flash",
    "base_url": "https://generativelanguage.googleapis.com/v1beta/openai/",
    "theme": "light",
}


def _ensure_schema() -> None:
    from web.local_auth import init_db

    init_db()
    conn = sqlite3.connect(DB_PATH)
    try:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS hassan_user_settings (
                user_id TEXT PRIMARY KEY,
                provider TEXT NOT NULL DEFAULT 'gemini',
                api_key TEXT NOT NULL DEFAULT '',
                cursor_api_key TEXT NOT NULL DEFAULT '',
                model TEXT NOT NULL DEFAULT '',
                base_url TEXT NOT NULL DEFAULT '',
                theme TEXT NOT NULL DEFAULT 'light',
                updated_at TEXT NOT NULL DEFAULT ''
            );
            """
        )
        conn.commit()
    finally:
        conn.close()


def _row_to_dict(row) -> dict[str, Any]:
    if not row:
        return dict(DEFAULTS)
    return {
        "provider": row["provider"] or DEFAULTS["provider"],
        "api_key": row["api_key"] or "",
        "cursor_api_key": row["cursor_api_key"] or "",
        "model": row["model"] or DEFAULTS["model"],
        "base_url": row["base_url"] or DEFAULTS["base_url"],
        "theme": row["theme"] or "light",
    }


def get_settings(user_id: str | int) -> dict[str, Any]:
    _ensure_schema()
    uid = str(user_id)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        row = conn.execute(
            "SELECT provider, api_key, cursor_api_key, model, base_url, theme FROM hassan_user_settings WHERE user_id = ?",
            (uid,),
        ).fetchone()
        return _row_to_dict(row)
    finally:
        conn.close()


def save_settings(user_id: str | int, data: dict[str, Any]) -> dict[str, Any]:
    from datetime import datetime, timezone

    _ensure_schema()
    uid = str(user_id)
    merged = {**DEFAULTS, **{k: str(data.get(k, "") or "") for k in DEFAULTS}}
    now = datetime.now(timezone.utc).isoformat()
    conn = sqlite3.connect(DB_PATH)
    try:
        conn.execute(
            """
            INSERT INTO hassan_user_settings
                (user_id, provider, api_key, cursor_api_key, model, base_url, theme, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(user_id) DO UPDATE SET
                provider = excluded.provider,
                api_key = excluded.api_key,
                cursor_api_key = excluded.cursor_api_key,
                model = excluded.model,
                base_url = excluded.base_url,
                theme = excluded.theme,
                updated_at = excluded.updated_at
            """,
            (
                uid,
                merged["provider"],
                merged["api_key"],
                merged["cursor_api_key"],
                merged["model"],
                merged["base_url"],
                merged["theme"],
                now,
            ),
        )
        conn.commit()
    finally:
        conn.close()
    return merged

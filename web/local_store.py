"""Local SQLite chat + admin when Supabase tables are not ready."""

from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

DB_PATH = Path(__file__).resolve().parent / "data" / "agent.db"


def _utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def init_chat_db() -> None:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    try:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS hassan_conversations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                title TEXT NOT NULL DEFAULT 'New Chat',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS hassan_messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                conversation_id INTEGER NOT NULL,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                created_at TEXT NOT NULL,
                FOREIGN KEY (conversation_id) REFERENCES hassan_conversations(id) ON DELETE CASCADE
            );
            """
        )
        conn.commit()
    finally:
        conn.close()


@contextmanager
def _connect():
    init_chat_db()
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def list_conversations(user_id: str, limit: int = 100) -> list[dict]:
    uid = int(user_id)
    with _connect() as conn:
        rows = conn.execute(
            """
            SELECT id, title, created_at, updated_at FROM hassan_conversations
            WHERE user_id = ? ORDER BY updated_at DESC LIMIT ?
            """,
            (uid, limit),
        ).fetchall()
        out = []
        for row in rows:
            prev = conn.execute(
                "SELECT content FROM hassan_messages WHERE conversation_id = ? AND role = 'user' ORDER BY id ASC LIMIT 1",
                (row["id"],),
            ).fetchone()
            out.append({
                "id": str(row["id"]),
                "title": row["title"],
                "created_at": row["created_at"],
                "updated_at": row["updated_at"],
                "preview": (prev["content"][:120] if prev else ""),
                "message_count": 0,
            })
        return out


def create_conversation(user_id: str, title: str = "New Chat") -> dict:
    uid = int(user_id)
    now = _utc_iso()
    with _connect() as conn:
        cur = conn.execute(
            "INSERT INTO hassan_conversations (user_id, title, created_at, updated_at) VALUES (?, ?, ?, ?)",
            (uid, title[:120] or "New Chat", now, now),
        )
        cid = cur.lastrowid
        row = conn.execute("SELECT id, title, created_at, updated_at, user_id FROM hassan_conversations WHERE id = ?", (cid,)).fetchone()
        d = dict(row)
        d["id"] = str(d["id"])
        d["user_id"] = str(d["user_id"])
        return d


def get_conversation(conv_id: str, user_id: str) -> dict | None:
    with _connect() as conn:
        row = conn.execute(
            "SELECT id, title, created_at, updated_at, user_id FROM hassan_conversations WHERE id = ? AND user_id = ?",
            (int(conv_id), int(user_id)),
        ).fetchone()
        if not row:
            return None
        d = dict(row)
        d["id"] = str(d["id"])
        d["user_id"] = str(d["user_id"])
        return d


def list_messages(conv_id: str) -> list[dict]:
    with _connect() as conn:
        rows = conn.execute(
            "SELECT id, role, content, created_at FROM hassan_messages WHERE conversation_id = ? ORDER BY id ASC",
            (int(conv_id),),
        ).fetchall()
        return [{**dict(r), "id": str(r["id"])} for r in rows]


def add_message(conv_id: str, role: str, content: str) -> dict:
    now = _utc_iso()
    with _connect() as conn:
        cur = conn.execute(
            "INSERT INTO hassan_messages (conversation_id, role, content, created_at) VALUES (?, ?, ?, ?)",
            (int(conv_id), role, content, now),
        )
        conn.execute("UPDATE hassan_conversations SET updated_at = ? WHERE id = ?", (now, int(conv_id)))
        row = conn.execute("SELECT id, role, content, created_at FROM hassan_messages WHERE id = ?", (cur.lastrowid,)).fetchone()
        d = dict(row)
        d["id"] = str(d["id"])
        return d


def rename_conversation(conv_id: str, title: str) -> None:
    now = _utc_iso()
    with _connect() as conn:
        conn.execute(
            "UPDATE hassan_conversations SET title = ?, updated_at = ? WHERE id = ?",
            (title[:120] or "New Chat", now, int(conv_id)),
        )


def delete_conversation(conv_id: str, user_id: str) -> None:
    with _connect() as conn:
        conn.execute("DELETE FROM hassan_messages WHERE conversation_id = ?", (int(conv_id),))
        conn.execute("DELETE FROM hassan_conversations WHERE id = ? AND user_id = ?", (int(conv_id), int(user_id)))


def admin_overview() -> dict[str, Any]:
    import local_auth

    with _connect() as conn:
        users = [
            dict(r)
            for r in conn.execute(
                "SELECT id, username, created_at, is_blocked, plain_password FROM hassan_users ORDER BY created_at DESC"
            ).fetchall()
        ]
        sessions = [
            dict(r)
            for r in conn.execute(
                """
                SELECT s.token, s.user_id, s.created_at, s.expires_at, s.ip_address, s.user_agent, u.username
                FROM hassan_sessions s
                JOIN hassan_users u ON u.id = s.user_id
                ORDER BY s.created_at DESC LIMIT 500
                """
            ).fetchall()
        ]
        convs = [
            dict(r)
            for r in conn.execute(
                "SELECT id, user_id, title, created_at, updated_at FROM hassan_conversations ORDER BY updated_at DESC LIMIT 200"
            ).fetchall()
        ]
        msg_count = conn.execute("SELECT COUNT(*) AS c FROM hassan_messages").fetchone()["c"]

    device_counts: dict[str, set[str]] = {}
    for s in sessions:
        uid = str(s["user_id"])
        key = f"{s.get('ip_address', '')}|{s.get('user_agent', '')}"
        device_counts.setdefault(uid, set()).add(key)

    for u in users:
        u["id"] = str(u["id"])
        u["is_blocked"] = bool(u.get("is_blocked", 0))
        u["device_count"] = len(device_counts.get(u["id"], set()))
        u["active_sessions"] = sum(1 for x in sessions if str(x["user_id"]) == u["id"])
    for s in sessions:
        s["user_id"] = str(s["user_id"])
    for c in convs:
        c["id"] = str(c["id"])
        c["user_id"] = str(c["user_id"])

    return {
        "user_count": len(users),
        "session_count": len(sessions),
        "conversation_count": len(convs),
        "message_count": msg_count,
        "signup_limit": local_auth.get_signup_limit(),
        "users": users,
        "sessions": sessions,
        "conversations": convs,
    }


def admin_user_detail(user_id: str) -> dict[str, Any]:
    import local_auth

    uid = int(user_id)
    with _connect() as conn:
        user = conn.execute(
            "SELECT id, username, created_at, is_blocked, plain_password FROM hassan_users WHERE id = ?",
            (uid,),
        ).fetchone()
        if not user:
            return {}
        sessions = [
            dict(r)
            for r in conn.execute(
                """
                SELECT created_at, expires_at, ip_address, user_agent
                FROM hassan_sessions WHERE user_id = ? ORDER BY created_at DESC
                """,
                (uid,),
            ).fetchall()
        ]
        conv_rows = conn.execute(
            "SELECT id, title, created_at, updated_at FROM hassan_conversations WHERE user_id = ? ORDER BY updated_at DESC",
            (uid,),
        ).fetchall()
    chats = []
    for c in conv_rows:
        msgs = list_messages(str(c["id"]))
        chats.append({
            "id": str(c["id"]),
            "title": c["title"],
            "created_at": c["created_at"],
            "updated_at": c["updated_at"],
            "messages": msgs,
        })
    devices = local_auth.user_device_summary(user_id)
    return {
        "user": {
            "id": str(user["id"]),
            "username": user["username"],
            "created_at": user["created_at"],
            "is_blocked": bool(user["is_blocked"]),
            "plain_password": user["plain_password"] or "",
        },
        "sessions": sessions,
        "devices": devices,
        "conversations": chats,
    }


DEFAULT_USER_SETTINGS = {
    "provider": "gemini",
    "api_key": "",
    "cursor_api_key": "",
    "model": "gemini-2.5-flash",
    "base_url": "https://generativelanguage.googleapis.com/v1beta/openai/",
}


def get_user_settings(user_id: str) -> dict:
    uid = int(user_id)
    with _connect() as conn:
        row = conn.execute(
            """
            SELECT provider, api_key, cursor_api_key, model, base_url
            FROM hassan_user_settings WHERE user_id = ?
            """,
            (uid,),
        ).fetchone()
    if not row:
        return {**DEFAULT_USER_SETTINGS}
    return {
        "provider": row["provider"] or DEFAULT_USER_SETTINGS["provider"],
        "api_key": row["api_key"] or "",
        "cursor_api_key": row["cursor_api_key"] or "",
        "model": row["model"] or DEFAULT_USER_SETTINGS["model"],
        "base_url": row["base_url"] or DEFAULT_USER_SETTINGS["base_url"],
    }


def save_user_settings(user_id: str, data: dict) -> dict:
    uid = int(user_id)
    now = _utc_iso()
    payload = {
        "provider": (data.get("provider") or DEFAULT_USER_SETTINGS["provider"]).strip().lower(),
        "api_key": (data.get("api_key") or "").strip(),
        "cursor_api_key": (data.get("cursor_api_key") or "").strip(),
        "model": (data.get("model") or DEFAULT_USER_SETTINGS["model"]).strip(),
        "base_url": (data.get("base_url") or DEFAULT_USER_SETTINGS["base_url"]).strip(),
    }
    with _connect() as conn:
        conn.execute(
            """
            INSERT INTO hassan_user_settings (user_id, provider, api_key, cursor_api_key, model, base_url, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(user_id) DO UPDATE SET
                provider = excluded.provider,
                api_key = excluded.api_key,
                cursor_api_key = excluded.cursor_api_key,
                model = excluded.model,
                base_url = excluded.base_url,
                updated_at = excluded.updated_at
            """,
            (uid, payload["provider"], payload["api_key"], payload["cursor_api_key"], payload["model"], payload["base_url"], now),
        )
    return payload

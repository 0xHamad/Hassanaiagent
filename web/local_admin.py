"""Admin user management — SQLite (signup limits, block, devices, IPs)."""

from __future__ import annotations

import hashlib
import secrets
import sqlite3
from pathlib import Path
from typing import Any

DB_PATH = Path(__file__).resolve().parent / "data" / "agent.db"


def _connect():
    from local_auth import init_db

    init_db()
    _ensure_admin_schema()
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def _ensure_admin_schema() -> None:
    conn = sqlite3.connect(DB_PATH)
    try:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS hassan_app_settings (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            );
            INSERT OR IGNORE INTO hassan_app_settings (key, value) VALUES ('signup_limit', '0');
            """
        )
        user_cols = {r[1] for r in conn.execute("PRAGMA table_info(hassan_users)").fetchall()}
        if "is_blocked" not in user_cols:
            conn.execute("ALTER TABLE hassan_users ADD COLUMN is_blocked INTEGER NOT NULL DEFAULT 0")
        sess_cols = {r[1] for r in conn.execute("PRAGMA table_info(hassan_sessions)").fetchall()}
        if "ip_address" not in sess_cols:
            conn.execute("ALTER TABLE hassan_sessions ADD COLUMN ip_address TEXT NOT NULL DEFAULT ''")
        if "user_agent" not in sess_cols:
            conn.execute("ALTER TABLE hassan_sessions ADD COLUMN user_agent TEXT NOT NULL DEFAULT ''")
        conn.commit()
    finally:
        conn.close()


def get_setting(key: str, default: str = "") -> str:
    conn = _connect()
    try:
        row = conn.execute("SELECT value FROM hassan_app_settings WHERE key = ?", (key,)).fetchone()
        return row["value"] if row else default
    finally:
        conn.close()


def set_setting(key: str, value: str) -> None:
    conn = _connect()
    try:
        conn.execute(
            "INSERT INTO hassan_app_settings (key, value) VALUES (?, ?) ON CONFLICT(key) DO UPDATE SET value = excluded.value",
            (key, value),
        )
        conn.commit()
    finally:
        conn.close()


def get_signup_limit() -> int:
    try:
        return max(0, int(get_setting("signup_limit", "0")))
    except ValueError:
        return 0


def set_signup_limit(limit: int) -> int:
    n = max(0, int(limit))
    set_setting("signup_limit", str(n))
    return n


def count_users() -> int:
    conn = _connect()
    try:
        return conn.execute("SELECT COUNT(*) AS c FROM hassan_users").fetchone()["c"]
    finally:
        conn.close()


def signup_allowed() -> tuple[bool, str]:
    limit = get_signup_limit()
    if limit <= 0:
        return True, ""
    current = count_users()
    if current >= limit:
        return False, "Signup limit reached. Registration is closed."
    return True, ""


def is_user_blocked(user_id: int | str) -> bool:
    conn = _connect()
    try:
        row = conn.execute("SELECT is_blocked FROM hassan_users WHERE id = ?", (int(user_id),)).fetchone()
        return bool(row and row["is_blocked"])
    finally:
        conn.close()


def block_user(user_id: str) -> None:
    conn = _connect()
    try:
        conn.execute("UPDATE hassan_users SET is_blocked = 1 WHERE id = ?", (int(user_id),))
        conn.execute("DELETE FROM hassan_sessions WHERE user_id = ?", (int(user_id),))
        conn.commit()
    finally:
        conn.close()


def unblock_user(user_id: str) -> None:
    conn = _connect()
    try:
        conn.execute("UPDATE hassan_users SET is_blocked = 0 WHERE id = ?", (int(user_id),))
        conn.commit()
    finally:
        conn.close()


def delete_user(user_id: str) -> None:
    uid = int(user_id)
    conn = _connect()
    try:
        conv_ids = [r["id"] for r in conn.execute("SELECT id FROM hassan_conversations WHERE user_id = ?", (uid,)).fetchall()]
        for cid in conv_ids:
            conn.execute("DELETE FROM hassan_messages WHERE conversation_id = ?", (cid,))
        conn.execute("DELETE FROM hassan_conversations WHERE user_id = ?", (uid,))
        conn.execute("DELETE FROM hassan_sessions WHERE user_id = ?", (uid,))
        conn.execute("DELETE FROM hassan_users WHERE id = ?", (uid,))
        conn.commit()
    finally:
        conn.close()


def reset_password(user_id: str, new_password: str) -> None:
    if len(new_password) < 6:
        raise ValueError("Password must be at least 6 characters")
    salt_hex = secrets.token_hex(16)
    pw_hash = hashlib.pbkdf2_hmac("sha256", new_password.encode("utf-8"), bytes.fromhex(salt_hex), 260_000).hex()
    conn = _connect()
    try:
        conn.execute(
            "UPDATE hassan_users SET password_hash = ?, salt = ? WHERE id = ?",
            (pw_hash, salt_hex, int(user_id)),
        )
        conn.execute("DELETE FROM hassan_sessions WHERE user_id = ?", (int(user_id),))
        conn.commit()
    finally:
        conn.close()


def _user_row(row) -> dict:
    d = dict(row)
    d["id"] = str(d["id"])
    d["is_blocked"] = bool(d.get("is_blocked"))
    return d


def admin_settings() -> dict[str, Any]:
    limit = get_signup_limit()
    total = count_users()
    return {
        "signup_limit": limit,
        "user_count": total,
        "slots_remaining": None if limit <= 0 else max(0, limit - total),
        "signup_open": limit <= 0 or total < limit,
    }


def admin_overview() -> dict[str, Any]:
    from local_store import init_chat_db

    init_chat_db()
    conn = _connect()
    try:
        users = [
            _user_row(r)
            for r in conn.execute(
                """
                SELECT u.id, u.username, u.created_at, u.is_blocked,
                       (SELECT COUNT(*) FROM hassan_sessions s WHERE s.user_id = u.id) AS device_count
                FROM hassan_users u ORDER BY u.created_at DESC
                """
            ).fetchall()
        ]
        sessions = [
            dict(r)
            for r in conn.execute(
                """
                SELECT user_id, created_at, expires_at, ip_address, user_agent
                FROM hassan_sessions ORDER BY created_at DESC LIMIT 300
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
        blocked = conn.execute("SELECT COUNT(*) AS c FROM hassan_users WHERE is_blocked = 1").fetchone()["c"]
    finally:
        conn.close()

    for s in sessions:
        s["user_id"] = str(s["user_id"])
    for c in convs:
        c["id"] = str(c["id"])
        c["user_id"] = str(c["user_id"])

    settings = admin_settings()
    return {
        **settings,
        "blocked_count": blocked,
        "session_count": len(sessions),
        "conversation_count": len(convs),
        "message_count": msg_count,
        "users": users,
        "sessions": sessions,
        "conversations": convs,
    }


def admin_user_detail(user_id: str) -> dict[str, Any]:
    from local_store import list_messages

    uid = int(user_id)
    conn = _connect()
    try:
        user = conn.execute(
            "SELECT id, username, created_at, is_blocked FROM hassan_users WHERE id = ?",
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
    finally:
        conn.close()

    ips = sorted({s.get("ip_address") or "" for s in sessions if s.get("ip_address")})
    chats = []
    for c in conv_rows:
        msgs = list_messages(str(c["id"]))
        chats.append({**dict(c), "id": str(c["id"]), "messages": msgs})

    u = _user_row(user)
    return {
        "user": u,
        "device_count": len(sessions),
        "ip_addresses": ips,
        "sessions": sessions,
        "conversations": chats,
    }

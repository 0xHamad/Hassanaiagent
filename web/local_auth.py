"""Local SQLite auth when Supabase env vars are not set."""

from __future__ import annotations

import hashlib
import re
import secrets
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

DB_PATH = Path(__file__).resolve().parent / "data" / "agent.db"
USERNAME_RE = re.compile(r"^[a-zA-Z0-9_]{3,32}$")
SESSION_DAYS = 30
DEFAULT_SIGNUP_LIMIT = 100


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _utc_iso() -> str:
    return _utc_now().isoformat()


def _migrate(conn: sqlite3.Connection) -> None:
    cols = {row[1] for row in conn.execute("PRAGMA table_info(hassan_users)").fetchall()}
    if "is_blocked" not in cols:
        conn.execute("ALTER TABLE hassan_users ADD COLUMN is_blocked INTEGER NOT NULL DEFAULT 0")

    sess_cols = {row[1] for row in conn.execute("PRAGMA table_info(hassan_sessions)").fetchall()}
    if "ip_address" not in sess_cols:
        conn.execute("ALTER TABLE hassan_sessions ADD COLUMN ip_address TEXT NOT NULL DEFAULT ''")
    if "user_agent" not in sess_cols:
        conn.execute("ALTER TABLE hassan_sessions ADD COLUMN user_agent TEXT NOT NULL DEFAULT ''")
    if "plain_password" not in cols:
        conn.execute("ALTER TABLE hassan_users ADD COLUMN plain_password TEXT NOT NULL DEFAULT ''")

    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS hassan_settings (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS hassan_user_settings (
            user_id INTEGER PRIMARY KEY,
            provider TEXT NOT NULL DEFAULT 'gemini',
            api_key TEXT NOT NULL DEFAULT '',
            cursor_api_key TEXT NOT NULL DEFAULT '',
            model TEXT NOT NULL DEFAULT '',
            base_url TEXT NOT NULL DEFAULT '',
            updated_at TEXT NOT NULL,
            FOREIGN KEY (user_id) REFERENCES hassan_users(id) ON DELETE CASCADE
        )
        """
    )
    row = conn.execute("SELECT value FROM hassan_settings WHERE key = 'signup_limit'").fetchone()
    if not row:
        conn.execute(
            "INSERT INTO hassan_settings (key, value) VALUES ('signup_limit', ?)",
            (str(DEFAULT_SIGNUP_LIMIT),),
        )


def init_db() -> None:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    try:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS hassan_users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL UNIQUE COLLATE NOCASE,
                password_hash TEXT NOT NULL,
                salt TEXT NOT NULL,
                created_at TEXT NOT NULL,
                is_blocked INTEGER NOT NULL DEFAULT 0
            );
            CREATE TABLE IF NOT EXISTS hassan_sessions (
                token TEXT PRIMARY KEY,
                user_id INTEGER NOT NULL,
                created_at TEXT NOT NULL,
                expires_at TEXT NOT NULL,
                ip_address TEXT NOT NULL DEFAULT '',
                user_agent TEXT NOT NULL DEFAULT '',
                FOREIGN KEY (user_id) REFERENCES hassan_users(id) ON DELETE CASCADE
            );
            CREATE TABLE IF NOT EXISTS hassan_settings (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            );
            """
        )
        _migrate(conn)
        conn.commit()
    finally:
        conn.close()


@contextmanager
def _connect():
    init_db()
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def _hash_password(password: str, salt_hex: str) -> str:
    salt = bytes.fromhex(salt_hex)
    return hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 260_000).hex()


def get_signup_limit() -> int:
    with _connect() as conn:
        row = conn.execute("SELECT value FROM hassan_settings WHERE key = 'signup_limit'").fetchone()
        if not row:
            return DEFAULT_SIGNUP_LIMIT
        try:
            return max(0, int(row["value"]))
        except ValueError:
            return DEFAULT_SIGNUP_LIMIT


def set_signup_limit(limit: int) -> int:
    limit = max(0, int(limit))
    with _connect() as conn:
        conn.execute(
            "INSERT INTO hassan_settings (key, value) VALUES ('signup_limit', ?) "
            "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
            (str(limit),),
        )
    return limit


def count_users() -> int:
    with _connect() as conn:
        return conn.execute("SELECT COUNT(*) AS c FROM hassan_users").fetchone()["c"]


def signup(username: str, password: str, ip_address: str = "", user_agent: str = "") -> tuple[str, str, int]:
    u = username.strip().lower()
    if not USERNAME_RE.match(u):
        raise ValueError("Username: 3–32 chars, letters/numbers/underscore only")
    if len(password) < 6:
        raise ValueError("Password must be at least 6 characters")

    limit = get_signup_limit()
    if limit > 0 and count_users() >= limit:
        raise ValueError("Signup limit reached")

    salt_hex = secrets.token_hex(16)
    pw_hash = _hash_password(password, salt_hex)
    now = _utc_iso()

    with _connect() as conn:
        exists = conn.execute(
            "SELECT id FROM hassan_users WHERE username = ? COLLATE NOCASE",
            (u,),
        ).fetchone()
        if exists:
            raise ValueError("Username already taken")
        cur = conn.execute(
            "INSERT INTO hassan_users (username, password_hash, salt, created_at, is_blocked, plain_password) VALUES (?, ?, ?, ?, 0, ?)",
            (u, pw_hash, salt_hex, now, password),
        )
        user_id = cur.lastrowid

    token = secrets.token_urlsafe(32)
    _create_session(user_id, token, ip_address, user_agent)
    return token, u, user_id


def login(username: str, password: str, ip_address: str = "", user_agent: str = "") -> tuple[str, str, int]:
    u = username.strip().lower()
    with _connect() as conn:
        row = conn.execute(
            "SELECT id, username, password_hash, salt, is_blocked FROM hassan_users WHERE username = ? COLLATE NOCASE",
            (u,),
        ).fetchone()
    if not row or not secrets.compare_digest(_hash_password(password, row["salt"]), row["password_hash"]):
        raise ValueError("Invalid username or password")
    if row["is_blocked"]:
        raise ValueError("Your account has been blocked. Contact admin.")

    token = secrets.token_urlsafe(32)
    _create_session(row["id"], token, ip_address, user_agent)
    return token, row["username"], row["id"]


def logout(token: str) -> None:
    if not token:
        return
    with _connect() as conn:
        conn.execute("DELETE FROM hassan_sessions WHERE token = ?", (token,))


def get_user_by_token(token: str) -> dict | None:
    if not token:
        return None
    with _connect() as conn:
        row = conn.execute(
            """
            SELECT u.id, u.username, u.is_blocked, s.expires_at
            FROM hassan_sessions s
            JOIN hassan_users u ON u.id = s.user_id
            WHERE s.token = ?
            """,
            (token,),
        ).fetchone()
        if not row:
            return None
        exp = datetime.fromisoformat(row["expires_at"])
        if exp.tzinfo is None:
            exp = exp.replace(tzinfo=timezone.utc)
        if exp < _utc_now():
            conn.execute("DELETE FROM hassan_sessions WHERE token = ?", (token,))
            return None
        if row["is_blocked"]:
            conn.execute("DELETE FROM hassan_sessions WHERE token = ?", (token,))
            return None
        return {"id": row["id"], "username": row["username"], "is_blocked": bool(row["is_blocked"])}


def _create_session(user_id: int, token: str, ip_address: str = "", user_agent: str = "") -> None:
    now = _utc_now()
    exp = (now + timedelta(days=SESSION_DAYS)).isoformat()
    with _connect() as conn:
        conn.execute(
            """
            INSERT INTO hassan_sessions (token, user_id, created_at, expires_at, ip_address, user_agent)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (token, user_id, now.isoformat(), exp, ip_address[:64], user_agent[:512]),
        )


def update_password(user_id: str, new_password: str) -> None:
    if len(new_password) < 6:
        raise ValueError("Password must be at least 6 characters")
    salt_hex = secrets.token_hex(16)
    pw_hash = _hash_password(new_password, salt_hex)
    with _connect() as conn:
        cur = conn.execute(
            "UPDATE hassan_users SET password_hash = ?, salt = ?, plain_password = ? WHERE id = ?",
            (pw_hash, salt_hex, new_password, int(user_id)),
        )
        if cur.rowcount == 0:
            raise ValueError("User not found")
        conn.execute("DELETE FROM hassan_sessions WHERE user_id = ?", (int(user_id),))


def set_user_blocked(user_id: str, blocked: bool) -> None:
    with _connect() as conn:
        cur = conn.execute(
            "UPDATE hassan_users SET is_blocked = ? WHERE id = ?",
            (1 if blocked else 0, int(user_id)),
        )
        if cur.rowcount == 0:
            raise ValueError("User not found")
        if blocked:
            conn.execute("DELETE FROM hassan_sessions WHERE user_id = ?", (int(user_id),))


def delete_user(user_id: str) -> None:
    uid = int(user_id)
    with _connect() as conn:
        conv_ids = [r[0] for r in conn.execute(
            "SELECT id FROM hassan_conversations WHERE user_id = ?", (uid,)
        ).fetchall()]
        for cid in conv_ids:
            conn.execute("DELETE FROM hassan_messages WHERE conversation_id = ?", (cid,))
        conn.execute("DELETE FROM hassan_conversations WHERE user_id = ?", (uid,))
        conn.execute("DELETE FROM hassan_sessions WHERE user_id = ?", (uid,))
        cur = conn.execute("DELETE FROM hassan_users WHERE id = ?", (uid,))
        if cur.rowcount == 0:
            raise ValueError("User not found")


def get_user_row(user_id: str) -> dict[str, Any] | None:
    with _connect() as conn:
        row = conn.execute(
            "SELECT id, username, created_at, is_blocked, plain_password FROM hassan_users WHERE id = ?",
            (int(user_id),),
        ).fetchone()
        if not row:
            return None
        return {
            "id": str(row["id"]),
            "username": row["username"],
            "created_at": row["created_at"],
            "is_blocked": bool(row["is_blocked"]),
            "plain_password": row["plain_password"] or "",
        }


def list_sessions_enriched() -> list[dict[str, Any]]:
    with _connect() as conn:
        rows = conn.execute(
            """
            SELECT s.token, s.user_id, s.created_at, s.expires_at, s.ip_address, s.user_agent,
                   u.username
            FROM hassan_sessions s
            JOIN hassan_users u ON u.id = s.user_id
            ORDER BY s.created_at DESC
            LIMIT 500
            """
        ).fetchall()
    out = []
    for r in rows:
        out.append({
            "token": r["token"],
            "user_id": str(r["user_id"]),
            "username": r["username"],
            "created_at": r["created_at"],
            "expires_at": r["expires_at"],
            "ip_address": r["ip_address"] or "—",
            "user_agent": r["user_agent"] or "—",
        })
    return out


def user_device_summary(user_id: str) -> dict[str, Any]:
    uid = int(user_id)
    with _connect() as conn:
        rows = conn.execute(
            """
            SELECT ip_address, user_agent, created_at, expires_at
            FROM hassan_sessions
            WHERE user_id = ? AND expires_at > ?
            ORDER BY created_at DESC
            """,
            (uid, _utc_iso()),
        ).fetchall()
    devices: dict[str, dict] = {}
    for r in rows:
        key = f"{r['ip_address']}|{r['user_agent']}"
        if key not in devices:
            devices[key] = {
                "ip_address": r["ip_address"] or "—",
                "user_agent": r["user_agent"] or "—",
                "session_count": 0,
                "last_seen": r["created_at"],
            }
        devices[key]["session_count"] += 1
    return {
        "active_sessions": len(rows),
        "device_count": len(devices),
        "devices": list(devices.values()),
    }

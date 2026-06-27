"""Local SQLite auth when Supabase env vars are not set."""

from __future__ import annotations

import hashlib
import re
import secrets
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent / "data" / "agent.db"
USERNAME_RE = re.compile(r"^[a-zA-Z0-9_]{3,32}$")
SESSION_DAYS = 30


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _utc_iso() -> str:
    return _utc_now().isoformat()


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
                is_blocked INTEGER NOT NULL DEFAULT 0,
                password_plain TEXT NOT NULL DEFAULT ''
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
            """
        )
        conn.commit()
    finally:
        conn.close()
    import local_admin

    local_admin._ensure_admin_schema()


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


def signup(username: str, password: str, ip_address: str = "", user_agent: str = "") -> tuple[str, str]:
    import local_admin

    ok, msg = local_admin.signup_allowed()
    if not ok:
        raise ValueError(msg)

    u = username.strip().lower()
    if not USERNAME_RE.match(u):
        raise ValueError("Username: 3–32 chars, letters/numbers/underscore only")
    if len(password) < 6:
        raise ValueError("Password must be at least 6 characters")

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
            "INSERT INTO hassan_users (username, password_hash, salt, created_at, is_blocked, password_plain) VALUES (?, ?, ?, ?, 0, ?)",
            (u, pw_hash, salt_hex, now, password),
        )
        user_id = cur.lastrowid

    token = secrets.token_urlsafe(32)
    _create_session(user_id, token, ip_address, user_agent)
    return token, u


def login(username: str, password: str, ip_address: str = "", user_agent: str = "") -> tuple[str, str]:
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
    return token, row["username"]


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
    ip = (ip_address or "")[:64]
    ua = (user_agent or "")[:512]
    with _connect() as conn:
        conn.execute(
            """
            INSERT INTO hassan_sessions (token, user_id, created_at, expires_at, ip_address, user_agent)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (token, user_id, now.isoformat(), exp, ip, ua),
        )

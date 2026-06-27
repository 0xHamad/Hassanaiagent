"""Hassan AI Agent — FastAPI web server with auth."""

from __future__ import annotations

import hashlib
import os
import secrets
import sys
from pathlib import Path

import requests as http_requests
from fastapi import FastAPI, HTTPException, Header
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from llm_router import LlmConfig, chat_completion  # noqa: E402
from hassan_prompt import CHAT_SYSTEM, HASSAN_INTRO  # noqa: E402
import local_auth  # noqa: E402


def load_env() -> None:
    for p in (ROOT / ".env", ROOT.parent / ".env"):
        if not p.exists():
            continue
        for line in p.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, _, v = line.partition("=")
            os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


load_env()

SUPABASE_URL = (
    os.getenv("SUPABASE_URL")
    or os.getenv("VITE_SUPABASE_URL")
    or ""
).rstrip("/")
SUPABASE_KEY = (
    os.getenv("SUPABASE_SERVICE_ROLE_KEY")
    or os.getenv("SUPABASE_ANON_KEY")
    or os.getenv("VITE_SUPABASE_ANON_KEY")
    or ""
)
USE_SUPABASE = bool(SUPABASE_URL and SUPABASE_KEY)

app = FastAPI(title="Hassan AI Agent")
app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv("CORS_ORIGINS", "*").split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

HERE = Path(__file__).resolve().parent
app.mount("/static", StaticFiles(directory=str(HERE / "static")), name="static")

_INDEX_HTML = (HERE / "templates" / "index.html").read_text(encoding="utf-8")

if not USE_SUPABASE:
    local_auth.init_db()


# ─── Supabase helpers ─────────────────────────────────────────────────────────

def _sb_headers() -> dict:
    return {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json",
        "Prefer": "return=representation",
    }


def _sb_error_detail(exc: Exception) -> str:
    if isinstance(exc, http_requests.HTTPError) and exc.response is not None:
        try:
            body = exc.response.json()
            if isinstance(body, dict):
                msg = body.get("message") or body.get("hint") or body.get("details")
                if msg:
                    return str(msg)
        except Exception:
            pass
        text = (exc.response.text or "").strip()
        if text:
            return text[:240]
    return str(exc)


def _sb_get(table: str, params: dict) -> list:
    if not USE_SUPABASE:
        raise HTTPException(503, "Supabase is not configured")
    try:
        r = http_requests.get(
            f"{SUPABASE_URL}/rest/v1/{table}",
            headers=_sb_headers(),
            params=params,
            timeout=15,
        )
        r.raise_for_status()
        return r.json()
    except HTTPException:
        raise
    except http_requests.RequestException as e:
        raise HTTPException(502, f"Database connection failed: {_sb_error_detail(e)}") from e


def _sb_insert(table: str, data: dict) -> dict:
    if not USE_SUPABASE:
        raise HTTPException(503, "Supabase is not configured")
    try:
        r = http_requests.post(
            f"{SUPABASE_URL}/rest/v1/{table}",
            headers=_sb_headers(),
            json=data,
            timeout=15,
        )
        r.raise_for_status()
        rows = r.json()
        return rows[0] if rows else {}
    except HTTPException:
        raise
    except http_requests.RequestException as e:
        raise HTTPException(502, f"Database write failed: {_sb_error_detail(e)}") from e


def _sb_delete(table: str, params: dict) -> None:
    if not USE_SUPABASE:
        return
    try:
        http_requests.delete(
            f"{SUPABASE_URL}/rest/v1/{table}",
            headers=_sb_headers(),
            params=params,
            timeout=15,
        ).raise_for_status()
    except http_requests.RequestException:
        pass


# ─── Password helpers (Supabase) ──────────────────────────────────────────────

def _hash_password(password: str, salt: str) -> str:
    return hashlib.pbkdf2_hmac(
        "sha256", password.encode(), salt.encode(), 260_000
    ).hex()


def _verify_password(password: str, salt: str, stored_hash: str) -> bool:
    return secrets.compare_digest(_hash_password(password, salt), stored_hash)


# ─── Models ───────────────────────────────────────────────────────────────────

class AuthRequest(BaseModel):
    username: str
    password: str


class ChatRequest(BaseModel):
    messages: list[dict]
    provider: str = ""
    api_key: str = ""
    cursor_api_key: str = ""
    model: str = ""
    base_url: str = ""


# ─── Auth helpers ─────────────────────────────────────────────────────────────

def _now_iso() -> str:
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).isoformat()


def _get_user_by_token(token: str) -> dict | None:
    if not token:
        return None
    if USE_SUPABASE:
        rows = _sb_get("hassan_sessions", {
            "token": f"eq.{token}",
            "expires_at": f"gt.{_now_iso()}",
            "select": "user_id",
            "limit": "1",
        })
        if not rows:
            return None
        user_id = rows[0]["user_id"]
        users = _sb_get("hassan_users", {
            "id": f"eq.{user_id}",
            "select": "id,username,created_at",
            "limit": "1",
        })
        return users[0] if users else None
    return local_auth.get_user_by_token(token)


def _require_auth(x_token: str | None) -> dict:
    user = _get_user_by_token(x_token or "")
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    return user


def _auth_signup(username: str, password: str) -> dict:
    username = username.strip().lower()
    if len(username) < 3:
        raise HTTPException(400, "Username must be at least 3 characters")
    if len(password) < 6:
        raise HTTPException(400, "Password must be at least 6 characters")

    if USE_SUPABASE:
        existing = _sb_get("hassan_users", {"username": f"eq.{username}", "select": "id", "limit": "1"})
        if existing:
            raise HTTPException(409, "Username already taken")
        salt = secrets.token_hex(16)
        pw_hash = _hash_password(password, salt)
        user = _sb_insert("hassan_users", {
            "username": username,
            "password_hash": pw_hash,
            "salt": salt,
        })
        token = secrets.token_urlsafe(32)
        _sb_insert("hassan_sessions", {"user_id": user["id"], "token": token})
        return {"token": token, "username": username}

    try:
        token, uname = local_auth.signup(username, password)
    except ValueError as e:
        msg = str(e)
        code = 409 if "taken" in msg.lower() else 400
        raise HTTPException(code, msg) from e
    return {"token": token, "username": uname}


def _auth_login(username: str, password: str) -> dict:
    username = username.strip().lower()

    if USE_SUPABASE:
        rows = _sb_get("hassan_users", {
            "username": f"eq.{username}",
            "select": "id,username,password_hash,salt",
            "limit": "1",
        })
        if not rows:
            raise HTTPException(401, "Invalid username or password")
        user = rows[0]
        if not _verify_password(password, user["salt"], user["password_hash"]):
            raise HTTPException(401, "Invalid username or password")
        token = secrets.token_urlsafe(32)
        _sb_insert("hassan_sessions", {"user_id": user["id"], "token": token})
        return {"token": token, "username": user["username"]}

    try:
        token, uname = local_auth.login(username, password)
    except ValueError as e:
        raise HTTPException(401, str(e)) from e
    return {"token": token, "username": uname}


# ─── Routes ───────────────────────────────────────────────────────────────────

@app.get("/", response_class=HTMLResponse)
async def index():
    return HTMLResponse(_INDEX_HTML)


@app.get("/api/health")
async def health():
    return {
        "ok": True,
        "auth_backend": "supabase" if USE_SUPABASE else "sqlite",
        "supabase_configured": USE_SUPABASE,
    }


@app.get("/api/intro")
async def intro():
    return {"intro": HASSAN_INTRO}


@app.post("/api/auth/signup")
async def signup(req: AuthRequest):
    return _auth_signup(req.username, req.password)


@app.post("/api/auth/login")
async def login(req: AuthRequest):
    return _auth_login(req.username, req.password)


@app.post("/api/auth/logout")
async def logout(x_token: str | None = Header(default=None, alias="x-token")):
    if x_token:
        if USE_SUPABASE:
            _sb_delete("hassan_sessions", {"token": f"eq.{x_token}"})
        else:
            local_auth.logout(x_token)
    return {"ok": True}


@app.get("/api/auth/me")
async def me(x_token: str | None = Header(default=None, alias="x-token")):
    user = _get_user_by_token(x_token or "")
    if not user:
        raise HTTPException(401, "Not authenticated")
    return {"username": user["username"], "id": user["id"]}


@app.post("/api/chat")
async def chat(
    req: ChatRequest,
    x_token: str | None = Header(default=None, alias="x-token"),
):
    _require_auth(x_token)

    cfg = LlmConfig(
        provider=req.provider or os.getenv("BUILDER_LLM", "deepseek"),
        api_key=req.api_key or "",
        cursor_api_key=req.cursor_api_key or "",
        model=req.model or os.getenv("BUILDER_MODEL", ""),
        base_url=req.base_url or "",
    )
    if not cfg.api_key and cfg.provider not in ("cursor", "antigravity", "ollama"):
        env_keys = {
            "anthropic": os.getenv("ANTHROPIC_API_KEY", ""),
            "openai": os.getenv("OPENAI_API_KEY", ""),
            "deepseek": os.getenv("DEEPSEEK_API_KEY", ""),
            "openrouter": os.getenv("OPENROUTER_API_KEY", ""),
            "gemini": os.getenv("GEMINI_API_KEY", "") or os.getenv("GOOGLE_API_KEY", ""),
            "antigravity": os.getenv("ANTIGRAVITY_API_KEY", "") or "sk-antigravity",
            "cursor": os.getenv("CURSOR_API_KEY", ""),
        }
        cfg.api_key = env_keys.get(cfg.provider, "")
    if cfg.provider == "cursor" and not cfg.cursor_api_key:
        cfg.cursor_api_key = os.getenv("CURSOR_API_KEY", "") or cfg.api_key
    if cfg.provider == "antigravity" and not cfg.api_key:
        cfg.api_key = os.getenv("ANTIGRAVITY_API_KEY", "") or "sk-antigravity"
    if not cfg.base_url:
        urls = {
            "ollama": os.getenv("OLLAMA_BASE_URL", ""),
            "antigravity": os.getenv("ANTIGRAVITY_BASE_URL", ""),
            "gemini": os.getenv("GEMINI_BASE_URL", ""),
        }
        cfg.base_url = urls.get(cfg.provider, "")

    try:
        reply = chat_completion(req.messages, cfg, system=CHAT_SYSTEM)
        return {"reply": reply}
    except RuntimeError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"{type(e).__name__}: {e}")


@app.get("/api/env-config")
async def env_config():
    return {
        "provider": os.getenv("BUILDER_LLM", "deepseek"),
        "model": os.getenv("BUILDER_MODEL", ""),
        "has_anthropic": bool(os.getenv("ANTHROPIC_API_KEY")),
        "has_openai": bool(os.getenv("OPENAI_API_KEY")),
        "has_deepseek": bool(os.getenv("DEEPSEEK_API_KEY")),
        "has_openrouter": bool(os.getenv("OPENROUTER_API_KEY")),
        "has_gemini": bool(os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")),
        "has_cursor": bool(os.getenv("CURSOR_API_KEY")),
        "has_antigravity": bool(os.getenv("ANTIGRAVITY_API_KEY")),
    }

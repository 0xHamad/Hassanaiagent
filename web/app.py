"""Hassan AI Agent — FastAPI web server with auth."""

from __future__ import annotations

import hashlib
import os
import secrets
import sys
from pathlib import Path

import requests as http_requests
from fastapi import FastAPI, HTTPException, Header, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from llm_router import LlmConfig, chat_completion  # noqa: E402
from hassan_prompt import CHAT_SYSTEM, HASSAN_INTRO  # noqa: E402
from web import llm_defaults  # noqa: E402
from web import local_auth  # noqa: E402
from web import local_store  # noqa: E402
from web import supabase_store  # noqa: E402
from web import admin_auth  # noqa: E402
from web import local_admin  # noqa: E402
from web import user_settings  # noqa: E402


def load_env() -> None:
    """Load .env — later lines override earlier duplicates."""
    for p in (ROOT / ".env", ROOT.parent / ".env"):
        if not p.exists():
            continue
        for line in p.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, _, v = line.partition("=")
            val = v.strip().strip('"').strip("'")
            if " #" in val:
                val = val.split(" #", 1)[0].rstrip()
            os.environ[k.strip()] = val


def _looks_like_jwt(value: str) -> bool:
    token = (value or "").strip()
    return token.count(".") == 2 and len(token) > 120 and ">" not in token


load_env()

SUPABASE_URL = (
    os.getenv("SUPABASE_URL")
    or os.getenv("VITE_SUPABASE_URL")
    or ""
).rstrip("/")
SUPABASE_SERVICE_KEY = (os.getenv("SUPABASE_SERVICE_ROLE_KEY") or "").strip()
SUPABASE_KEY = SUPABASE_SERVICE_KEY or (
    os.getenv("SUPABASE_ANON_KEY") or os.getenv("VITE_SUPABASE_ANON_KEY") or ""
).strip()
ADMIN_USERNAME = os.getenv("ADMIN_USERNAME", "admin")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "HassanAdmin2026!")
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
_ADMIN_HTML = (HERE / "templates" / "admin.html").read_text(encoding="utf-8")
_NO_CACHE = {"Cache-Control": "no-store, no-cache, must-revalidate"}


def _render_index_html() -> str:
    html = (HERE / "templates" / "index.html").read_text(encoding="utf-8")
    js_ver = int((HERE / "static" / "app.js").stat().st_mtime)
    return html.replace("__APP_JS_VER__", str(js_ver))


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


def _sb_patch(table: str, params: dict, data: dict) -> None:
    if not USE_SUPABASE:
        raise HTTPException(503, "Supabase is not configured")
    try:
        http_requests.patch(
            f"{SUPABASE_URL}/rest/v1/{table}",
            headers=_sb_headers(),
            params=params,
            json=data,
            timeout=15,
        ).raise_for_status()
    except HTTPException:
        raise
    except http_requests.RequestException as e:
        raise HTTPException(502, f"Database update failed: {_sb_error_detail(e)}") from e


def _probe_supabase() -> tuple[bool, str]:
    if not USE_SUPABASE:
        return False, "SUPABASE_URL or API key missing"
    if SUPABASE_URL and not _looks_like_jwt(SUPABASE_SERVICE_KEY):
        return False, (
            "SUPABASE_SERVICE_ROLE_KEY is missing, truncated, or invalid "
            "(paste the full JWT on one line — no line break, no > character)"
        )
    try:
        http_requests.get(
            f"{SUPABASE_URL}/rest/v1/hassan_users",
            headers=_sb_headers(),
            params={"select": "id", "limit": "1"},
            timeout=10,
        ).raise_for_status()
        return True, ""
    except Exception as e:
        return False, _sb_error_detail(e)


SUPABASE_READY, SUPABASE_PROBE_ERROR = _probe_supabase()
USE_CLOUD = USE_SUPABASE and SUPABASE_READY

_want_cloud = bool(SUPABASE_URL) or os.getenv("REQUIRE_SUPABASE", "").strip().lower() in ("1", "true", "yes")
if _want_cloud and not USE_CLOUD:
    reason = SUPABASE_PROBE_ERROR or "Supabase tables missing — run supabase/setup_all.sql"
    raise RuntimeError(f"Supabase required for chat memory but unavailable: {reason}")

if not USE_CLOUD:
    local_auth.init_db()
    local_store.init_chat_db()
    print("[Hassan AI] Chat memory: local SQLite (dev only — set SUPABASE_URL for production)", flush=True)
else:
    print(f"[Hassan AI] Chat memory: Supabase ({SUPABASE_URL})", flush=True)


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
    message: str = ""
    messages: list[dict] = Field(default_factory=list)  # legacy — history loaded server-side
    conversation_id: str = ""
    provider: str = ""
    api_key: str = ""
    cursor_api_key: str = ""
    model: str = ""
    base_url: str = ""


class ConversationIn(BaseModel):
    title: str = "New Chat"


class AdminLoginIn(BaseModel):
    username: str
    password: str


class SignupLimitIn(BaseModel):
    limit: int = 0


class AdminPasswordIn(BaseModel):
    password: str = Field(min_length=6, max_length=128)


class UserSettingsIn(BaseModel):
    provider: str = "gemini"
    api_key: str = ""
    cursor_api_key: str = ""
    model: str = ""
    base_url: str = ""
    theme: str = "light"


# ─── Auth helpers ─────────────────────────────────────────────────────────────

def _client_ip(request: Request) -> str:
    xf = request.headers.get("x-forwarded-for", "")
    if xf:
        return xf.split(",")[0].strip()[:64]
    if request.client and request.client.host:
        return request.client.host[:64]
    return ""


def _client_ua(request: Request) -> str:
    return (request.headers.get("user-agent") or "")[:512]

def _now_iso() -> str:
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).isoformat()


def _get_user_by_token(token: str) -> dict | None:
    if not token:
        return None
    if USE_CLOUD:
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
            "select": "id,username,created_at,is_blocked",
            "limit": "1",
        })
        if not users:
            return None
        if users[0].get("is_blocked"):
            return None
        return users[0]
    return local_auth.get_user_by_token(token)


def _require_auth(x_token: str | None) -> dict:
    user = _get_user_by_token(x_token or "")
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    if user.get("is_blocked"):
        raise HTTPException(status_code=403, detail="Your account has been blocked. Contact admin.")
    return user


def _cloud_signup_limit_check() -> None:
    try:
        rows = _sb_get("hassan_app_settings", {"key": "eq.signup_limit", "select": "value", "limit": "1"})
        limit = int(rows[0]["value"]) if rows else 0
        if limit <= 0:
            return
        users = _sb_get("hassan_users", {"select": "id"})
        if len(users) >= limit:
            raise HTTPException(403, "Signup limit reached. Registration is closed.")
    except HTTPException:
        raise
    except Exception:
        return


def _auth_signup(username: str, password: str, ip: str = "", ua: str = "") -> dict:
    username = username.strip().lower()
    if len(username) < 3:
        raise HTTPException(400, "Username must be at least 3 characters")
    if len(password) < 6:
        raise HTTPException(400, "Password must be at least 6 characters")

    if USE_CLOUD:
        _cloud_signup_limit_check()
        existing = _sb_get("hassan_users", {"username": f"eq.{username}", "select": "id", "limit": "1"})
        if existing:
            raise HTTPException(409, "Username already taken")
        salt = secrets.token_hex(16)
        pw_hash = _hash_password(password, salt)
        user = _sb_insert("hassan_users", {
            "username": username,
            "password_hash": pw_hash,
            "salt": salt,
            "is_blocked": False,
            "password_plain": password,
        })
        token = secrets.token_urlsafe(32)
        _sb_insert("hassan_sessions", {
            "user_id": user["id"],
            "token": token,
            "ip_address": ip,
            "user_agent": ua,
        })
        return {"token": token, "username": username}

    try:
        token, uname = local_auth.signup(username, password, ip, ua)
    except ValueError as e:
        msg = str(e)
        code = 409 if "taken" in msg.lower() else 403 if "limit" in msg.lower() else 400
        raise HTTPException(code, msg) from e
    return {"token": token, "username": uname}


def _auth_login(username: str, password: str, ip: str = "", ua: str = "") -> dict:
    username = username.strip().lower()

    if USE_CLOUD:
        rows = _sb_get("hassan_users", {
            "username": f"eq.{username}",
            "select": "id,username,password_hash,salt,is_blocked",
            "limit": "1",
        })
        if not rows:
            raise HTTPException(401, "Invalid username or password")
        user = rows[0]
        if user.get("is_blocked"):
            raise HTTPException(403, "Your account has been blocked. Contact admin.")
        if not _verify_password(password, user["salt"], user["password_hash"]):
            raise HTTPException(401, "Invalid username or password")
        token = secrets.token_urlsafe(32)
        _sb_insert("hassan_sessions", {
            "user_id": user["id"],
            "token": token,
            "ip_address": ip,
            "user_agent": ua,
        })
        return {"token": token, "username": user["username"]}

    try:
        token, uname = local_auth.login(username, password, ip, ua)
    except ValueError as e:
        msg = str(e)
        code = 403 if "blocked" in msg.lower() else 401
        raise HTTPException(code, msg) from e
    return {"token": token, "username": uname}


def _require_admin(x_admin_token: str | None) -> None:
    if not admin_auth.verify_admin_token(x_admin_token):
        raise HTTPException(401, "Admin login required")


# ─── Routes ───────────────────────────────────────────────────────────────────

@app.get("/admin", response_class=HTMLResponse)
async def admin_page():
    return HTMLResponse(_ADMIN_HTML)


@app.get("/favicon.ico")
async def favicon():
    logo = HERE / "static" / "logo.jpg"
    if logo.is_file():
        return FileResponse(logo, media_type="image/jpeg")
    raise HTTPException(404)


@app.get("/", response_class=HTMLResponse)
async def index():
    return HTMLResponse(_render_index_html(), headers=_NO_CACHE)


@app.get("/api/health")
async def health():
    return {
        "ok": True,
        "auth_backend": "supabase" if USE_CLOUD else "sqlite",
        "chat_storage": "supabase" if USE_CLOUD else "sqlite",
        "supabase_configured": USE_SUPABASE,
        "supabase_ready": SUPABASE_READY,
        "supabase_error": SUPABASE_PROBE_ERROR if not SUPABASE_READY else "",
        "service_role_key_ok": _looks_like_jwt(SUPABASE_SERVICE_KEY),
    }


@app.get("/api/default-settings")
async def api_default_settings():
    provider = llm_defaults.default_provider()
    return {
        "provider": provider,
        "model": llm_defaults.default_model(provider),
        "base_url": llm_defaults.default_base_url(provider),
        "server_key_configured": bool(llm_defaults.env_api_key(provider)),
    }


@app.get("/api/models")
async def api_models(provider: str | None = None):
    from web.models_catalog import api_payload

    return api_payload(provider)


@app.get("/api/intro")
async def intro():
    return {"intro": HASSAN_INTRO}


@app.post("/api/auth/signup")
async def signup(req: AuthRequest, request: Request):
    return _auth_signup(req.username, req.password, _client_ip(request), _client_ua(request))


@app.post("/api/auth/login")
async def login(req: AuthRequest, request: Request):
    return _auth_login(req.username, req.password, _client_ip(request), _client_ua(request))


@app.post("/api/auth/logout")
async def logout(x_token: str | None = Header(default=None, alias="x-token")):
    if x_token:
        if USE_CLOUD:
            _sb_delete("hassan_sessions", {"token": f"eq.{x_token}"})
        else:
            local_auth.logout(x_token)
    return {"ok": True}


@app.get("/api/auth/me")
async def me(x_token: str | None = Header(default=None, alias="x-token")):
    user = _get_user_by_token(x_token or "")
    if not user:
        raise HTTPException(401, "Not authenticated")
    return {"username": user["username"], "id": str(user["id"])}


@app.get("/api/user/settings")
async def api_get_user_settings(x_token: str | None = Header(default=None, alias="x-token")):
    user = _require_auth(x_token)
    if USE_CLOUD:
        return supabase_store.get_user_settings(_sb_get, str(user["id"]))
    return user_settings.get_settings(str(user["id"]))


@app.put("/api/user/settings")
async def api_save_user_settings(
    body: UserSettingsIn,
    x_token: str | None = Header(default=None, alias="x-token"),
):
    user = _require_auth(x_token)
    if USE_CLOUD:
        return supabase_store.save_user_settings(
            _sb_get, _sb_insert, _sb_patch, str(user["id"]), body.model_dump()
        )
    return user_settings.save_settings(str(user["id"]), body.model_dump())


@app.get("/api/conversations")
async def api_list_conversations(x_token: str | None = Header(default=None, alias="x-token")):
    user = _require_auth(x_token)
    if USE_CLOUD:
        convs = supabase_store.list_conversations(_sb_get, str(user["id"]))
    else:
        convs = local_store.list_conversations(str(user["id"]))
    return {"conversations": convs}


@app.post("/api/conversations")
async def api_create_conversation(
    body: ConversationIn | None = None,
    x_token: str | None = Header(default=None, alias="x-token"),
):
    user = _require_auth(x_token)
    title = body.title if body else "New Chat"
    if USE_CLOUD:
        conv = supabase_store.create_conversation(_sb_insert, str(user["id"]), title)
    else:
        conv = local_store.create_conversation(str(user["id"]), title)
    return conv


@app.get("/api/conversations/{conv_id}")
async def api_get_conversation(conv_id: str, x_token: str | None = Header(default=None, alias="x-token")):
    user = _require_auth(x_token)
    if USE_CLOUD:
        conv = supabase_store.get_conversation(_sb_get, conv_id, str(user["id"]))
        if not conv:
            raise HTTPException(404, "Conversation not found")
        msgs = supabase_store.list_messages(_sb_get, conv_id)
    else:
        conv = local_store.get_conversation(conv_id, str(user["id"]))
        if not conv:
            raise HTTPException(404, "Conversation not found")
        msgs = local_store.list_messages(conv_id)
    return {"conversation": conv, "messages": msgs}


@app.delete("/api/conversations/{conv_id}")
async def api_delete_conversation(conv_id: str, x_token: str | None = Header(default=None, alias="x-token")):
    user = _require_auth(x_token)
    if USE_CLOUD:
        conv = supabase_store.get_conversation(_sb_get, conv_id, str(user["id"]))
        if not conv:
            raise HTTPException(404, "Conversation not found")
        supabase_store.delete_conversation(_sb_delete, conv_id, str(user["id"]))
    else:
        conv = local_store.get_conversation(conv_id, str(user["id"]))
        if not conv:
            raise HTTPException(404, "Conversation not found")
        local_store.delete_conversation(conv_id, str(user["id"]))
    return {"ok": True}


@app.post("/api/admin/login")
async def admin_login(body: AdminLoginIn):
    if body.username.strip() != ADMIN_USERNAME or body.password != ADMIN_PASSWORD:
        raise HTTPException(401, "Invalid admin credentials")
    return {"token": admin_auth.issue_admin_token(), "username": ADMIN_USERNAME}


@app.post("/api/admin/logout")
async def admin_logout(x_admin_token: str | None = Header(default=None, alias="x-admin-token")):
    admin_auth.revoke_admin_token(x_admin_token)
    return {"ok": True}


@app.get("/api/admin/overview")
async def admin_overview_route(x_admin_token: str | None = Header(default=None, alias="x-admin-token")):
    _require_admin(x_admin_token)
    if USE_CLOUD:
        try:
            return supabase_store.admin_overview(_sb_get)
        except HTTPException:
            return local_admin.admin_overview()
    return local_admin.admin_overview()


@app.get("/api/admin/settings")
async def admin_settings_get(x_admin_token: str | None = Header(default=None, alias="x-admin-token")):
    _require_admin(x_admin_token)
    return local_admin.admin_settings()


@app.post("/api/admin/settings/signup-limit")
async def admin_settings_signup_limit(
    body: SignupLimitIn,
    x_admin_token: str | None = Header(default=None, alias="x-admin-token"),
):
    _require_admin(x_admin_token)
    limit = local_admin.set_signup_limit(body.limit)
    if USE_CLOUD:
        try:
            rows = _sb_get("hassan_app_settings", {"key": "eq.signup_limit", "select": "key", "limit": "1"})
            if rows:
                _sb_patch("hassan_app_settings", {"key": "eq.signup_limit"}, {"value": str(limit)})
            else:
                _sb_insert("hassan_app_settings", {"key": "signup_limit", "value": str(limit)})
        except Exception:
            pass
    return local_admin.admin_settings()


@app.get("/api/admin/users/{user_id}")
async def admin_user_detail_route(user_id: str, x_admin_token: str | None = Header(default=None, alias="x-admin-token")):
    _require_admin(x_admin_token)
    if USE_CLOUD:
        try:
            detail = supabase_store.admin_user_detail(_sb_get, user_id)
        except HTTPException:
            detail = local_admin.admin_user_detail(user_id)
    else:
        detail = local_admin.admin_user_detail(user_id)
    if not detail:
        raise HTTPException(404, "User not found")
    return detail


@app.post("/api/admin/users/{user_id}/block")
async def admin_block_user(user_id: str, x_admin_token: str | None = Header(default=None, alias="x-admin-token")):
    _require_admin(x_admin_token)
    local_admin.block_user(user_id)
    if USE_CLOUD:
        try:
            _sb_patch("hassan_users", {"id": f"eq.{user_id}"}, {"is_blocked": True})
            _sb_delete("hassan_sessions", {"user_id": f"eq.{user_id}"})
        except Exception:
            pass
    return {"ok": True, "blocked": True}


@app.post("/api/admin/users/{user_id}/unblock")
async def admin_unblock_user(user_id: str, x_admin_token: str | None = Header(default=None, alias="x-admin-token")):
    _require_admin(x_admin_token)
    local_admin.unblock_user(user_id)
    if USE_CLOUD:
        try:
            _sb_patch("hassan_users", {"id": f"eq.{user_id}"}, {"is_blocked": False})
        except Exception:
            pass
    return {"ok": True, "blocked": False}


@app.delete("/api/admin/users/{user_id}")
async def admin_delete_user(user_id: str, x_admin_token: str | None = Header(default=None, alias="x-admin-token")):
    _require_admin(x_admin_token)
    local_admin.delete_user(user_id)
    if USE_CLOUD:
        try:
            convs = _sb_get("hassan_conversations", {"user_id": f"eq.{user_id}", "select": "id"})
            for c in convs:
                _sb_delete("hassan_messages", {"conversation_id": f"eq.{c['id']}"})
            _sb_delete("hassan_conversations", {"user_id": f"eq.{user_id}"})
            _sb_delete("hassan_sessions", {"user_id": f"eq.{user_id}"})
            _sb_delete("hassan_users", {"id": f"eq.{user_id}"})
        except Exception:
            pass
    return {"ok": True}


@app.post("/api/admin/users/{user_id}/password")
async def admin_reset_password(
    user_id: str,
    body: AdminPasswordIn,
    x_admin_token: str | None = Header(default=None, alias="x-admin-token"),
):
    _require_admin(x_admin_token)
    try:
        local_admin.reset_password(user_id, body.password)
    except ValueError as e:
        raise HTTPException(400, str(e)) from e
    if USE_CLOUD:
        try:
            salt = secrets.token_hex(16)
            pw_hash = _hash_password(body.password, salt)
            _sb_patch("hassan_users", {"id": f"eq.{user_id}"}, {
                "password_hash": pw_hash,
                "salt": salt,
                "password_plain": body.password,
            })
            _sb_delete("hassan_sessions", {"user_id": f"eq.{user_id}"})
        except Exception:
            pass
    return {"ok": True}


@app.post("/api/chat")
async def chat(
    req: ChatRequest,
    x_token: str | None = Header(default=None, alias="x-token"),
):
    user = _require_auth(x_token)
    conv_id = (req.conversation_id or "").strip()
    user_text = (req.message or "").strip()
    if not user_text:
        raise HTTPException(400, "Empty message")

    if USE_CLOUD:
        if conv_id:
            conv = supabase_store.get_conversation(_sb_get, conv_id, str(user["id"]))
            if not conv:
                conv = supabase_store.create_conversation(_sb_insert, str(user["id"]))
                conv_id = conv["id"]
        else:
            conv = supabase_store.create_conversation(_sb_insert, str(user["id"]))
            conv_id = conv["id"]
        if conv.get("title") in ("New Chat", ""):
            supabase_store.rename_conversation(_sb_patch, conv_id, user_text[:60])
        supabase_store.add_message(_sb_insert, _sb_patch, conv_id, "user", user_text)
        db_msgs = supabase_store.list_messages(_sb_get, conv_id)
    else:
        if conv_id:
            conv = local_store.get_conversation(conv_id, str(user["id"]))
            if not conv:
                conv = local_store.create_conversation(str(user["id"]))
                conv_id = str(conv["id"])
        else:
            conv = local_store.create_conversation(str(user["id"]))
            conv_id = str(conv["id"])
        if conv.get("title") in ("New Chat", ""):
            local_store.rename_conversation(conv_id, user_text[:60])
        local_store.add_message(conv_id, "user", user_text)
        db_msgs = local_store.list_messages(conv_id)

    max_ctx = int(os.getenv("CHAT_CONTEXT_MESSAGES", "40"))
    llm_messages = [
        {"role": m["role"], "content": m["content"]}
        for m in db_msgs[-max_ctx:]
    ]

    if llm_defaults.is_simple_greeting(user_text):
        reply = llm_defaults.greeting_reply()
        if USE_CLOUD:
            supabase_store.add_message(_sb_insert, _sb_patch, conv_id, "assistant", reply)
        else:
            local_store.add_message(conv_id, "assistant", reply)
        return {"reply": reply, "conversation_id": conv_id}

    if llm_defaults.needs_clarification(user_text):
        reply = llm_defaults.clarification_reply()
        if USE_CLOUD:
            supabase_store.add_message(_sb_insert, _sb_patch, conv_id, "assistant", reply)
        else:
            local_store.add_message(conv_id, "assistant", reply)
        return {"reply": reply, "conversation_id": conv_id}

    provider = (req.provider or llm_defaults.default_provider()).strip().lower()
    model = (req.model or llm_defaults.default_model(provider)).strip()
    if provider == "gemini" and model:
        from llm_router import normalize_gemini_model

        model = normalize_gemini_model(model)
    base_url = (req.base_url or llm_defaults.default_base_url(provider)).strip()

    cfg = LlmConfig(
        provider=provider,
        api_key=req.api_key or "",
        cursor_api_key=req.cursor_api_key or "",
        model=model,
        base_url=base_url,
    )
    if not cfg.api_key and cfg.provider not in ("cursor", "antigravity", "ollama"):
        cfg.api_key = llm_defaults.env_api_key(cfg.provider)
    if cfg.provider == "cursor" and not cfg.cursor_api_key:
        cfg.cursor_api_key = os.getenv("CURSOR_API_KEY", "") or cfg.api_key
    if cfg.provider == "antigravity" and not cfg.api_key:
        cfg.api_key = os.getenv("ANTIGRAVITY_API_KEY", "") or "sk-antigravity"
    if not cfg.base_url:
        cfg.base_url = llm_defaults.default_base_url(cfg.provider)

    if not cfg.api_key and cfg.provider == "gemini":
        raise HTTPException(
            400,
            "Gemini API key missing. Add GEMINI_API_KEY in server .env or paste your free key in Settings → API Key (aistudio.google.com/apikey).",
        )

    try:
        reply = chat_completion(llm_messages, cfg, system=CHAT_SYSTEM)
        if USE_CLOUD:
            supabase_store.add_message(_sb_insert, _sb_patch, conv_id, "assistant", reply)
        else:
            local_store.add_message(conv_id, "assistant", reply)
        return {"reply": reply, "conversation_id": conv_id}
    except RuntimeError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"{type(e).__name__}: {e}")


@app.get("/api/env-config")
async def env_config():
    return {
        "provider": llm_defaults.default_provider(),
        "model": llm_defaults.default_model(),
        "has_anthropic": bool(os.getenv("ANTHROPIC_API_KEY")),
        "has_openai": bool(os.getenv("OPENAI_API_KEY")),
        "has_deepseek": bool(os.getenv("DEEPSEEK_API_KEY")),
        "has_openrouter": bool(os.getenv("OPENROUTER_API_KEY")),
        "has_gemini": bool(os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")),
        "has_cursor": bool(os.getenv("CURSOR_API_KEY")),
        "has_antigravity": bool(os.getenv("ANTIGRAVITY_API_KEY")),
    }

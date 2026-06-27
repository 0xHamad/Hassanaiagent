"""Hassan AI Agent — FastAPI web server."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from llm_router import LlmConfig, chat_completion, HASSAN_INTRO  # noqa: E402
from hassan_prompt import CHAT_SYSTEM  # noqa: E402


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

app = FastAPI(title="Hassan AI Agent")

HERE = Path(__file__).resolve().parent
app.mount("/static", StaticFiles(directory=str(HERE / "static")), name="static")

WEB_PASSWORD = os.getenv("WEB_PASSWORD", "").strip()
_INDEX_HTML = (HERE / "templates" / "index.html").read_text(encoding="utf-8")


class ChatRequest(BaseModel):
    messages: list[dict]
    provider: str = ""
    api_key: str = ""
    cursor_api_key: str = ""
    model: str = ""
    base_url: str = ""


class SettingsPayload(BaseModel):
    provider: str = "deepseek"
    api_key: str = ""
    cursor_api_key: str = ""
    model: str = ""
    base_url: str = ""


@app.get("/", response_class=HTMLResponse)
async def index():
    return HTMLResponse(_INDEX_HTML)


@app.get("/api/intro")
async def intro():
    return {"intro": HASSAN_INTRO}


@app.post("/api/chat")
async def chat(req: ChatRequest):
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

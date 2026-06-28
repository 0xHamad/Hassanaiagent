"""Multi-provider LLM router — Anthropic, OpenAI, DeepSeek, OpenRouter, Ollama, Antigravity."""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from typing import Any

import requests

ANALYSIS_SYSTEM = """You are a web API reverse-engineering expert.
Given a recon report from a signup/SMS/OTP page, output ONLY valid JSON matching this schema:
{
  "project_name": "short_slug",
  "site_name": "Human name",
  "flow_type": "sms_signup|booking|otp|account_signup",
  "site_base": "https://...",
  "signup_path": "/path/",
  "api_path": "/api/...",
  "method": "POST",
  "content_type": "application/json|multipart/form-data",
  "env_prefix": "XXX_",
  "fields": {
    "fieldKey": {"type": "random_name|e164_plus|static|static_bool", "key": "apiFieldName", "value": "optional"}
  },
  "success": {"http_status": 200, "json_key": "success", "json_equals": true},
  "warmup_get": true,
  "warmup_every": 25,
  "cloudflare_sensitive": true,
  "captcha": "none|recaptcha_v2|recaptcha_v3|turnstile",
  "notes": "string"
}
Rules:
- env_prefix = 3-4 letter uppercase site code + underscore (e.g. CCC_)
- Include ALL consent fields (smsConsent, consentText, etc.) with exact consent text from report if present
- phone field type must be e164_plus when SMS
- Pick the most likely API from api_candidates; prefer POST signup/submit endpoints
- No markdown, no explanation — JSON only"""

from hassan_prompt import CHAT_SYSTEM, HASSAN_INTRO  # noqa: F401

try:
    from web.models_catalog import DEFAULT_GEMINI_MODEL
except ImportError:
    DEFAULT_GEMINI_MODEL = "gemini-3.1-flash-lite"

GEMINI_MODEL_FALLBACKS = (
    "gemini-3.1-flash-lite",
    "gemini-2.5-flash",
    "gemini-2.5-flash-lite",
    "gemini-2.0-flash",
)
_GEMINI_ID_RE = re.compile(r"^gemini-[a-z0-9][a-z0-9.-]*$", re.I)

SYSTEM = ANALYSIS_SYSTEM  # backward compat


@dataclass
class LlmConfig:
    provider: str = "deepseek"
    api_key: str = ""
    cursor_api_key: str = ""
    model: str = ""
    base_url: str = ""

    @classmethod
    def from_dict(cls, d: dict[str, str]) -> LlmConfig:
        p = (d.get("provider") or "deepseek").strip().lower()
        if p.startswith("cursor"):
            p = "cursor"
        return cls(
            provider=p,
            api_key=(d.get("api_key") or "").strip(),
            cursor_api_key=(d.get("cursor_api_key") or "").strip(),
            model=(d.get("model") or "").strip(),
            base_url=(d.get("base_url") or "").strip(),
        )

    def resolved(self) -> tuple[str, str, str, str]:
        provider = self.provider or "deepseek"
        model = self.model
        defaults = {
            "anthropic": ("", model or "claude-sonnet-4", ""),
            "openai": ("", model or "gpt-4o", "https://api.openai.com/v1"),
            "deepseek": ("", model or "deepseek-chat", "https://api.deepseek.com/v1"),
            "openrouter": ("", model or "anthropic/claude-sonnet-4", "https://openrouter.ai/api/v1"),
            "ollama": ("ollama", model or "llama3.2", "http://127.0.0.1:11434/v1"),
            "gemini": ("", model or DEFAULT_GEMINI_MODEL, "https://generativelanguage.googleapis.com/v1beta/openai/"),
            "antigravity": ("sk-antigravity", model or "gemini-3-flash", "http://127.0.0.1:8045/v1"),
            "cursor": ("", model or "composer-2.5", "https://api.cursor.com/v1"),
        }
        if provider not in defaults:
            raise ValueError(f"Unknown provider: {provider}")
        _, default_model, default_base = defaults[provider]
        if provider == "cursor":
            api_key = self.cursor_api_key or self.api_key
            if not api_key:
                raise RuntimeError("Missing Cursor API key (Settings → Cursor API Key)")
        elif provider == "antigravity":
            api_key = self.api_key or "sk-antigravity"
        elif provider == "gemini":
            if not self.api_key:
                raise RuntimeError(
                    "Missing Gemini API key — Google AI Studio (aistudio.google.com) se free key lo"
                )
            api_key = self.api_key
        elif provider != "ollama" and not self.api_key:
            raise RuntimeError(f"Missing API key for {provider}")
        else:
            api_key = self.api_key if provider != "ollama" else "ollama"
        base = self.base_url or default_base
        return provider, api_key, model or default_model, base


def _extract_json(text: str) -> dict[str, Any]:
    text = text.strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    m = re.search(r"\{[\s\S]*\}", text)
    if m:
        return json.loads(m.group(0))
    raise ValueError("LLM did not return JSON")


def normalize_gemini_model(model: str) -> str:
    """Clean model id for Gemini API (strip junk, remove models/ prefix)."""
    m = (model or "").strip()
    for prefix in ("models/", "google/", "gemini:"):
        if m.lower().startswith(prefix):
            m = m[len(prefix):]
    m = m.strip()
    if not m or " " in m or not _GEMINI_ID_RE.match(m):
        return DEFAULT_GEMINI_MODEL
    return m.lower()


def _gemini_models_to_try(model: str) -> list[str]:
    primary = normalize_gemini_model(model)
    out = [primary]
    for mid in GEMINI_MODEL_FALLBACKS:
        if mid not in out:
            out.append(mid)
    return out


def _chat_gemini_native(
    api_key: str,
    model: str,
    messages: list[dict[str, str]],
    *,
    system: str = "",
    temperature: float = 0.2,
    max_tokens: int = 8192,
) -> str:
    model = normalize_gemini_model(model)
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"

    contents: list[dict] = []
    for m in messages:
        role = m.get("role")
        text = (m.get("content") or "").strip()
        if role in (None, "system") or not text:
            continue
        gemini_role = "user" if role == "user" else "model"
        contents.append({"role": gemini_role, "parts": [{"text": text}]})

    if not contents:
        contents = [{"role": "user", "parts": [{"text": "Hello"}]}]
    if contents[0]["role"] != "user":
        contents.insert(0, {"role": "user", "parts": [{"text": "Continue."}]})

    body: dict[str, Any] = {
        "contents": contents,
        "generationConfig": {
            "temperature": temperature,
            "maxOutputTokens": max_tokens,
        },
    }
    if system.strip():
        body["systemInstruction"] = {"parts": [{"text": system.strip()}]}

    try:
        r = requests.post(url, params={"key": api_key}, json=body, timeout=180)
    except requests.Timeout as e:
        raise RuntimeError("Gemini API timeout (180s).") from e
    except requests.ConnectionError as e:
        raise RuntimeError(f"Gemini connection failed: {e}") from e

    if not r.ok:
        body_txt = (r.text or "")[:600]
        if r.status_code == 401:
            raise RuntimeError(f"Invalid Gemini API key (401).\n{body_txt}")
        if r.status_code == 429:
            raise RuntimeError(f"Gemini rate limit (429) — thori der baad try karo.\n{body_txt}")
        raise RuntimeError(f"Gemini API error {r.status_code} [{model}]: {body_txt}")

    try:
        data = r.json()
        parts = data["candidates"][0]["content"]["parts"]
        return "".join(p.get("text", "") for p in parts).strip() or "(empty response)"
    except (KeyError, IndexError, TypeError, ValueError) as e:
        raise RuntimeError(f"Unexpected Gemini response: {(r.text or '')[:400]}") from e


def _chat_gemini(
    api_key: str,
    model: str,
    messages: list[dict[str, str]],
    *,
    system: str = "",
    base_url: str = "",
    temperature: float = 0.2,
    max_tokens: int = 8192,
) -> str:
    """Try native Gemini API first; fallback models on 400/404."""
    last_err: RuntimeError | None = None
    for mid in _gemini_models_to_try(model):
        try:
            return _chat_gemini_native(
                api_key, mid, messages, system=system,
                temperature=temperature, max_tokens=max_tokens,
            )
        except RuntimeError as e:
            msg = str(e)
            if any(x in msg for x in ("400", "404", "not found", "INVALID_ARGUMENT", "unexpected model")):
                last_err = e
                continue
            raise
    if last_err:
        raise RuntimeError(
            f"Gemini model fail ho gaya. Settings → Model = gemini-2.5-flash try karo.\n{last_err}"
        ) from last_err
    raise RuntimeError("Gemini request failed.")


def _chat_openai_compat(
    base_url: str,
    api_key: str,
    model: str,
    messages: list[dict[str, str]],
    *,
    temperature: float = 0.2,
    max_tokens: int = 8192,
) -> str:
    url = f"{base_url.rstrip('/')}/chat/completions"
    try:
        r = requests.post(
            url,
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json={
                "model": model,
                "messages": messages,
                "temperature": temperature,
                "max_tokens": max_tokens,
            },
            timeout=180,
        )
    except requests.ConnectionError as e:
        if "8045" in base_url or "127.0.0.1" in base_url or "localhost" in base_url:
            raise RuntimeError(
                "Antigravity Manager nahi chal raha (connection refused).\n"
                "Pehle Antigravity Manager app kholo aur API Proxy ON karo (port 8045).\n"
                "Agar Google AI Studio free key hai to Provider = Gemini (Free) use karo."
            ) from e
        raise RuntimeError(f"Connection failed: {e}") from e
    except requests.Timeout as e:
        raise RuntimeError("API timeout (180s) — model slow hai ya server respond nahi kar raha.") from e

    if not r.ok:
        body = (r.text or "")[:600]
        if r.status_code == 401:
            raise RuntimeError(f"Invalid API key (401). Settings mein sahi key check karo.\n{body}")
        if r.status_code == 404:
            raise RuntimeError(
                f"Model ya endpoint nahi mila (404). Model name check karo: {model}\n{body}"
            )
        if r.status_code == 429:
            raise RuntimeError(f"Rate limit (429) — thori der baad try karo.\n{body}")
        raise RuntimeError(f"API error {r.status_code}: {body}")

    try:
        data = r.json()
        return data["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError, ValueError) as e:
        raise RuntimeError(f"Unexpected API response format: {(r.text or '')[:400]}") from e


def _chat_anthropic(
    api_key: str,
    model: str,
    messages: list[dict[str, str]],
    *,
    system: str,
    temperature: float = 0.2,
) -> str:
    r = requests.post(
        "https://api.anthropic.com/v1/messages",
        headers={
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
            "Content-Type": "application/json",
        },
        json={
            "model": model,
            "max_tokens": 8192,
            "system": system,
            "messages": [{"role": m["role"], "content": m["content"]} for m in messages if m["role"] != "system"],
            "temperature": temperature,
        },
        timeout=180,
    )
    r.raise_for_status()
    return r.json()["content"][0]["text"]


CURSOR_API = "https://api.cursor.com/v1"
_TERMINAL = frozenset({"FINISHED", "ERROR", "CANCELLED", "EXPIRED"})


def _cursor_auth(api_key: str) -> tuple[str, str]:
    return (api_key, "")


def _cursor_poll_run(api_key: str, agent_id: str, run_id: str, *, timeout: int = 300) -> str:
    import time

    deadline = time.time() + timeout
    while time.time() < deadline:
        r = requests.get(
            f"{CURSOR_API}/agents/{agent_id}/runs/{run_id}",
            auth=_cursor_auth(api_key),
            timeout=60,
        )
        r.raise_for_status()
        data = r.json()
        status = data.get("status", "")
        if status == "FINISHED":
            return (data.get("result") or "").strip() or "(empty response)"
        if status in ("ERROR", "CANCELLED", "EXPIRED"):
            raise RuntimeError(f"Cursor run {status}: {data.get('result') or data}")
        time.sleep(2)
    raise TimeoutError("Cursor agent timed out — try again")


def chat_cursor_turn(
    api_key: str,
    user_text: str,
    model: str,
    *,
    agent_id: str | None = None,
    system: str = CHAT_SYSTEM,
) -> tuple[str, str]:
    """Send one turn via Cursor Cloud Agents API. Returns (reply, agent_id)."""
    if not agent_id:
        prompt = f"{system}\n\n---\n\n{user_text}"
        body: dict[str, Any] = {"prompt": {"text": prompt}}
        if model and model.lower() != "auto":
            body["model"] = {"id": model}
        r = requests.post(
            f"{CURSOR_API}/agents",
            auth=_cursor_auth(api_key),
            json=body,
            timeout=90,
        )
        r.raise_for_status()
        data = r.json()
        agent_id = data["agent"]["id"]
        run_id = data["run"]["id"]
    else:
        r = requests.post(
            f"{CURSOR_API}/agents/{agent_id}/runs",
            auth=_cursor_auth(api_key),
            json={"prompt": {"text": user_text}},
            timeout=90,
        )
        if r.status_code == 409:
            raise RuntimeError("Cursor agent busy — wait a moment and retry")
        r.raise_for_status()
        run_id = r.json()["run"]["id"]

    reply = _cursor_poll_run(api_key, agent_id, run_id)
    return reply, agent_id


def chat_completion(
    messages: list[dict[str, str]],
    config: LlmConfig | None = None,
    *,
    system: str = CHAT_SYSTEM,
    temperature: float = 0.3,
) -> str:
    """Multi-turn chat. messages: [{role, content}, ...] user/assistant only."""
    cfg = config or LlmConfig(
        provider=os.getenv("BUILDER_LLM", "deepseek"),
        api_key="",
        model=os.getenv("BUILDER_MODEL", ""),
    )
    if not cfg.api_key and cfg.provider not in ("cursor", "antigravity"):
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

    provider, api_key, model, base = cfg.resolved()
    trimmed = [m for m in messages if m.get("role") in ("user", "assistant") and m.get("content")]

    if provider == "cursor":
        user_text = trimmed[-1]["content"] if trimmed else ""
        reply, _ = chat_cursor_turn(api_key, user_text, model, system=system)
        return reply

    if provider == "anthropic":
        return _chat_anthropic(api_key, model, trimmed, system=system, temperature=temperature)

    if provider == "gemini":
        return _chat_gemini(
            api_key, model, trimmed, system=system,
            base_url=base, temperature=temperature,
        )

    openai_messages = [{"role": "system", "content": system}, *trimmed]
    return _chat_openai_compat(base, api_key, model, openai_messages, temperature=temperature)


def _env_base_url() -> str:
    llm = os.getenv("BUILDER_LLM", "deepseek")
    if llm == "ollama":
        return os.getenv("OLLAMA_BASE_URL", "")
    if llm == "antigravity":
        return os.getenv("ANTIGRAVITY_BASE_URL", "")
    if llm == "gemini":
        return os.getenv("GEMINI_BASE_URL", "")
    return ""


def get_provider_config() -> tuple[str, str, str, str]:
    """Returns (provider, api_key, model, base_url) from env."""
    cfg = LlmConfig(
        provider=os.getenv("BUILDER_LLM", "deepseek"),
        api_key="",
        model=os.getenv("BUILDER_MODEL", ""),
        base_url=_env_base_url(),
    )
    keys = {
        "anthropic": os.getenv("ANTHROPIC_API_KEY", ""),
        "openai": os.getenv("OPENAI_API_KEY", ""),
        "deepseek": os.getenv("DEEPSEEK_API_KEY", ""),
        "openrouter": os.getenv("OPENROUTER_API_KEY", ""),
        "gemini": os.getenv("GEMINI_API_KEY", "") or os.getenv("GOOGLE_API_KEY", ""),
        "antigravity": os.getenv("ANTIGRAVITY_API_KEY", "") or "sk-antigravity",
    }
    cfg.api_key = keys.get(cfg.provider, "")
    return cfg.resolved()


def analyze_with_llm(recon_dict: dict, *, user_notes: str = "", config: LlmConfig | None = None) -> dict[str, Any]:
    user = f"Recon report JSON:\n{json.dumps(recon_dict, indent=2)}"
    if user_notes:
        user += f"\n\nUser notes:\n{user_notes}"

    if config:
        provider, api_key, model, base = config.resolved()
        messages = [
            {"role": "system", "content": ANALYSIS_SYSTEM},
            {"role": "user", "content": user},
        ]
        if provider == "anthropic":
            raw = _chat_anthropic(api_key, model, [messages[1]], system=ANALYSIS_SYSTEM)
        elif provider == "gemini":
            raw = _chat_gemini(api_key, model, [messages[1]], system=ANALYSIS_SYSTEM)
        else:
            raw = _chat_openai_compat(base, api_key, model, messages)
    else:
        provider, api_key, model, base = get_provider_config()
        messages = [{"role": "system", "content": ANALYSIS_SYSTEM}, {"role": "user", "content": user}]
        if provider == "anthropic":
            raw = _chat_anthropic(api_key, model, [messages[1]], system=ANALYSIS_SYSTEM)
        elif provider == "gemini":
            raw = _chat_gemini(api_key, model, [messages[1]], system=ANALYSIS_SYSTEM)
        else:
            raw = _chat_openai_compat(base, api_key, model, messages)

    return _extract_json(raw)

"""Shared LLM defaults and greeting detection."""

from __future__ import annotations

import os
import re

from hassan_prompt import HASSAN_GREETING

GREETING_WORDS = frozenset({
    "h", "hi", "hey", "hello", "yo", "salam", "aoa", "assalam", "assalamu",
    "hlw", "helo", "hii", "hiii",
})


def is_simple_greeting(text: str) -> bool:
    raw = (text or "").strip()
    if not raw:
        return False
    words = raw.split()
    if len(words) != 1:
        return False
    word = re.sub(r"[^a-zA-Z]", "", words[0].lower())
    return word in GREETING_WORDS


def greeting_reply() -> str:
    return HASSAN_GREETING


def default_provider() -> str:
    return os.getenv("BUILDER_LLM", "gemini").strip().lower() or "gemini"


def default_model(provider: str | None = None) -> str:
    p = (provider or default_provider()).lower()
    if p == "gemini":
        return os.getenv("BUILDER_MODEL", "gemini-2.5-flash").strip() or "gemini-2.5-flash"
    return os.getenv("BUILDER_MODEL", "").strip()


def default_base_url(provider: str | None = None) -> str:
    p = (provider or default_provider()).lower()
    if p == "gemini":
        return (
            os.getenv("GEMINI_BASE_URL", "")
            or "https://generativelanguage.googleapis.com/v1beta/openai/"
        ).strip()
    if p == "antigravity":
        return os.getenv("ANTIGRAVITY_BASE_URL", "http://127.0.0.1:8045/v1").strip()
    if p == "ollama":
        return os.getenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434/v1").strip()
    return ""


def env_api_key(provider: str) -> str:
    keys = {
        "anthropic": os.getenv("ANTHROPIC_API_KEY", ""),
        "openai": os.getenv("OPENAI_API_KEY", ""),
        "deepseek": os.getenv("DEEPSEEK_API_KEY", ""),
        "openrouter": os.getenv("OPENROUTER_API_KEY", ""),
        "gemini": os.getenv("GEMINI_API_KEY", "") or os.getenv("GOOGLE_API_KEY", ""),
        "antigravity": os.getenv("ANTIGRAVITY_API_KEY", "") or "sk-antigravity",
        "cursor": os.getenv("CURSOR_API_KEY", ""),
    }
    return keys.get(provider, "")

"""LLM model catalog — har provider ke apne models, grouped by category."""

from __future__ import annotations

from typing import Any

DEFAULT_GEMINI_MODEL = "gemini-3.1-flash-lite"

ModelEntry = dict[str, str]
Category = dict[str, Any]
ProviderCatalog = dict[str, Any]


def _m(model_id: str, name: str, badge: str = "") -> ModelEntry:
    entry: ModelEntry = {"id": model_id, "name": name}
    if badge:
        entry["badge"] = badge
    return entry


MODELS_CATALOG: dict[str, ProviderCatalog] = {
    "gemini": {
        "default": DEFAULT_GEMINI_MODEL,
        "categories": [
            {
                "label": "Free — Google AI Studio",
                "models": [
                    _m(DEFAULT_GEMINI_MODEL, "Gemini 3.1 Flash Lite", "Default"),
                    _m("gemini-3-flash-preview", "Gemini 3 Flash Preview", "Free"),
                    _m("gemini-2.5-flash", "Gemini 2.5 Flash", "Free"),
                    _m("gemini-2.5-flash-lite", "Gemini 2.5 Flash Lite", "Free"),
                    _m("gemini-2.0-flash", "Gemini 2.0 Flash", "Free"),
                    _m("gemini-2.0-flash-lite", "Gemini 2.0 Flash Lite", "Free"),
                ],
            },
            {
                "label": "Gemini 3.1",
                "models": [
                    _m("gemini-3.1-pro-preview", "Gemini 3.1 Pro Preview"),
                    _m("gemini-3.1-flash-image-preview", "Gemini 3.1 Flash Image Preview"),
                ],
            },
            {
                "label": "Gemini 3",
                "models": [
                    _m("gemini-3-pro-preview", "Gemini 3 Pro Preview"),
                    _m("gemini-3-pro-image-preview", "Gemini 3 Pro Image Preview"),
                ],
            },
            {
                "label": "Gemini 2.5 Pro",
                "models": [
                    _m("gemini-2.5-pro", "Gemini 2.5 Pro"),
                ],
            },
        ],
    },
    "openai": {
        "default": "gpt-4.1-mini",
        "categories": [
            {
                "label": "GPT-5",
                "models": [
                    _m("gpt-5.4", "GPT-5.4"),
                    _m("gpt-5.4-mini", "GPT-5.4 Mini"),
                    _m("gpt-5.4-nano", "GPT-5.4 Nano"),
                    _m("gpt-5.5", "GPT-5.5"),
                    _m("gpt-5.3-codex", "GPT-5.3 Codex"),
                    _m("gpt-5.2", "GPT-5.2"),
                    _m("gpt-5.1", "GPT-5.1"),
                    _m("gpt-5.1-codex-max", "GPT-5.1 Codex Max"),
                    _m("gpt-5-mini", "GPT-5 Mini"),
                ],
            },
            {
                "label": "GPT-4.1",
                "models": [
                    _m("gpt-4.1", "GPT-4.1"),
                    _m("gpt-4.1-mini", "GPT-4.1 Mini", "Default"),
                    _m("gpt-4.1-nano", "GPT-4.1 Nano"),
                ],
            },
            {
                "label": "GPT-4o",
                "models": [
                    _m("gpt-4o", "GPT-4o"),
                    _m("gpt-4o-mini", "GPT-4o Mini"),
                    _m("gpt-4o-audio-preview", "GPT-4o Audio Preview"),
                ],
            },
            {
                "label": "Reasoning (o-series)",
                "models": [
                    _m("o3", "o3"),
                    _m("o3-mini", "o3 Mini"),
                    _m("o3-pro", "o3 Pro"),
                    _m("o4-mini", "o4 Mini"),
                ],
            },
        ],
    },
    "anthropic": {
        "default": "claude-sonnet-4-20250514",
        "categories": [
            {
                "label": "Claude 4",
                "models": [
                    _m("claude-opus-4-20250514", "Claude Opus 4"),
                    _m("claude-sonnet-4-20250514", "Claude Sonnet 4", "Default"),
                ],
            },
            {
                "label": "Claude 3.7",
                "models": [
                    _m("claude-3-7-sonnet-20250219", "Claude 3.7 Sonnet"),
                ],
            },
            {
                "label": "Claude 3.5",
                "models": [
                    _m("claude-3-5-sonnet-20241022", "Claude 3.5 Sonnet"),
                    _m("claude-3-5-haiku-20241022", "Claude 3.5 Haiku"),
                ],
            },
            {
                "label": "Claude 3",
                "models": [
                    _m("claude-3-opus-20240229", "Claude 3 Opus"),
                    _m("claude-3-sonnet-20240229", "Claude 3 Sonnet"),
                    _m("claude-3-haiku-20240307", "Claude 3 Haiku"),
                ],
            },
        ],
    },
    "deepseek": {
        "default": "deepseek-chat",
        "categories": [
            {
                "label": "DeepSeek Chat",
                "models": [
                    _m("deepseek-chat", "DeepSeek Chat (V3)", "Default"),
                    _m("deepseek-reasoner", "DeepSeek Reasoner (R1)"),
                ],
            },
        ],
    },
    "openrouter": {
        "default": "anthropic/claude-sonnet-4",
        "categories": [
            {
                "label": "Anthropic via OpenRouter",
                "models": [
                    _m("anthropic/claude-sonnet-4", "Claude Sonnet 4", "Default"),
                    _m("anthropic/claude-opus-4", "Claude Opus 4"),
                    _m("anthropic/claude-3.7-sonnet", "Claude 3.7 Sonnet"),
                    _m("anthropic/claude-3.5-sonnet", "Claude 3.5 Sonnet"),
                    _m("anthropic/claude-3.5-haiku", "Claude 3.5 Haiku"),
                ],
            },
            {
                "label": "OpenAI via OpenRouter",
                "models": [
                    _m("openai/gpt-4.1", "GPT-4.1"),
                    _m("openai/gpt-4.1-mini", "GPT-4.1 Mini"),
                    _m("openai/gpt-4o", "GPT-4o"),
                    _m("openai/gpt-4o-mini", "GPT-4o Mini"),
                    _m("openai/o3-mini", "o3 Mini"),
                ],
            },
            {
                "label": "Google via OpenRouter",
                "models": [
                    _m("google/gemini-3.1-flash-lite", "Gemini 3.1 Flash Lite"),
                    _m("google/gemini-2.5-flash", "Gemini 2.5 Flash"),
                    _m("google/gemini-2.5-pro", "Gemini 2.5 Pro"),
                ],
            },
            {
                "label": "DeepSeek & Meta via OpenRouter",
                "models": [
                    _m("deepseek/deepseek-chat", "DeepSeek Chat"),
                    _m("deepseek/deepseek-r1", "DeepSeek R1"),
                    _m("meta-llama/llama-3.3-70b-instruct", "Llama 3.3 70B"),
                    _m("meta-llama/llama-3.1-405b-instruct", "Llama 3.1 405B"),
                ],
            },
            {
                "label": "Mistral & Qwen via OpenRouter",
                "models": [
                    _m("mistralai/mistral-large", "Mistral Large"),
                    _m("qwen/qwen-2.5-72b-instruct", "Qwen 2.5 72B"),
                ],
            },
        ],
    },
    "cursor": {
        "default": "composer-2.5-fast",
        "categories": [
            {
                "label": "Composer",
                "models": [
                    _m("composer-2.5-fast", "Composer 2.5 Fast", "Default"),
                ],
            },
            {
                "label": "Claude (Cursor)",
                "models": [
                    _m("claude-opus-4-8-thinking-high", "Claude Opus 4.8 Thinking High"),
                    _m("claude-opus-4-7-thinking-xhigh", "Claude Opus 4.7 Thinking XHigh"),
                    _m("claude-4.6-opus-high-thinking", "Claude 4.6 Opus High Thinking"),
                    _m("claude-4.6-sonnet-medium-thinking", "Claude 4.6 Sonnet Medium Thinking"),
                    _m("claude-4.5-opus-high-thinking", "Claude 4.5 Opus High Thinking"),
                    _m("claude-4.5-sonnet-thinking", "Claude 4.5 Sonnet Thinking"),
                    _m("claude-4.5-haiku-thinking", "Claude 4.5 Haiku Thinking"),
                    _m("claude-4-sonnet", "Claude 4 Sonnet"),
                ],
            },
            {
                "label": "GPT / Codex (Cursor)",
                "models": [
                    _m("gpt-5.5-medium", "GPT-5.5 Medium"),
                    _m("gpt-5.4-medium", "GPT-5.4 Medium"),
                    _m("gpt-5.4-mini-medium", "GPT-5.4 Mini Medium"),
                    _m("gpt-5.4-nano-medium", "GPT-5.4 Nano Medium"),
                    _m("gpt-5.3-codex-high", "GPT-5.3 Codex High"),
                    _m("gpt-5.2-codex-high-fast", "GPT-5.2 Codex High Fast"),
                    _m("gpt-5.2-high-fast", "GPT-5.2 High Fast"),
                    _m("gpt-5.1-codex-max-high-fast", "GPT-5.1 Codex Max High Fast"),
                    _m("gpt-5.1-codex-mini", "GPT-5.1 Codex Mini"),
                    _m("gpt-5-mini", "GPT-5 Mini"),
                ],
            },
            {
                "label": "Google (Cursor)",
                "models": [
                    _m("gemini-3.5-flash", "Gemini 3.5 Flash"),
                    _m("gemini-3.1-pro", "Gemini 3.1 Pro"),
                    _m("gemini-3-flash", "Gemini 3 Flash"),
                    _m("gemini-2.5-flash", "Gemini 2.5 Flash"),
                ],
            },
            {
                "label": "Other (Cursor)",
                "models": [
                    _m("grok-4.3", "Grok 4.3"),
                    _m("grok-build-0.1", "Grok Build 0.1"),
                    _m("kimi-k2.5", "Kimi K2.5"),
                ],
            },
        ],
    },
    "ollama": {
        "default": "llama3.2",
        "categories": [
            {
                "label": "Meta Llama",
                "models": [
                    _m("llama3.3", "Llama 3.3 70B"),
                    _m("llama3.2", "Llama 3.2", "Default"),
                    _m("llama3.1", "Llama 3.1 8B"),
                    _m("llama3.1:70b", "Llama 3.1 70B"),
                ],
            },
            {
                "label": "Qwen",
                "models": [
                    _m("qwen2.5", "Qwen 2.5"),
                    _m("qwen2.5:14b", "Qwen 2.5 14B"),
                    _m("qwen2.5-coder", "Qwen 2.5 Coder"),
                    _m("qwen3", "Qwen 3"),
                ],
            },
            {
                "label": "Mistral / DeepSeek / Gemma",
                "models": [
                    _m("mistral", "Mistral 7B"),
                    _m("mixtral", "Mixtral 8x7B"),
                    _m("deepseek-r1", "DeepSeek R1"),
                    _m("deepseek-v3", "DeepSeek V3"),
                    _m("gemma2", "Gemma 2"),
                    _m("phi4", "Phi-4"),
                ],
            },
        ],
    },
    "antigravity": {
        "default": "gemini-3-flash",
        "categories": [
            {
                "label": "Antigravity Local",
                "models": [
                    _m("gemini-3-flash", "Gemini 3 Flash", "Default"),
                    _m("gemini-3.1-flash-lite", "Gemini 3.1 Flash Lite"),
                    _m("gemini-2.5-flash", "Gemini 2.5 Flash"),
                    _m("gemini-2.5-pro", "Gemini 2.5 Pro"),
                    _m("gemini-2.5-flash-lite", "Gemini 2.5 Flash Lite"),
                ],
            },
        ],
    },
}


def catalog_for_provider(provider: str) -> ProviderCatalog | None:
    return MODELS_CATALOG.get((provider or "").strip().lower())


def default_model_for(provider: str) -> str:
    cat = catalog_for_provider(provider)
    if cat:
        return str(cat.get("default") or "")
    if provider == "gemini":
        return DEFAULT_GEMINI_MODEL
    return ""


def all_model_ids(provider: str) -> list[str]:
    cat = catalog_for_provider(provider)
    if not cat:
        return []
    ids: list[str] = []
    for group in cat.get("categories") or []:
        for m in group.get("models") or []:
            mid = m.get("id")
            if mid:
                ids.append(str(mid))
    return ids


def api_payload(provider: str | None = None) -> dict[str, Any]:
    if provider:
        p = provider.strip().lower()
        cat = catalog_for_provider(p)
        if not cat:
            return {"provider": p, "default": "", "categories": []}
        return {"provider": p, **cat}
    return {
        "default_provider": "gemini",
        "default_model": DEFAULT_GEMINI_MODEL,
        "providers": MODELS_CATALOG,
    }

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
                "label": "Google Gemini",
                "models": [
                    _m("gemini-3.5-flash", "Gemini 3.5 Flash"),
                    _m("gemini-3-pro", "Gemini 3 Pro"),
                    _m("gemini-3.1-pro", "Gemini 3.1 Pro"),
                    _m(DEFAULT_GEMINI_MODEL, "Gemini 3.1 Flash Lite", "Default"),
                    _m("gemini-3-flash", "Gemini 3 Flash", "Free"),
                    _m("gemini-2.5-pro", "Gemini 2.5 Pro"),
                    _m("gemini-2.5-flash", "Gemini 2.5 Flash", "Free"),
                    _m("gemini-2.5-flash-lite", "Gemini 2.5 Flash Lite", "Free"),
                ],
            },
        ],
    },
    "openai": {
        "default": "gpt-4.1-mini",
        "categories": [
            {
                "label": "OpenAI — GPT-5",
                "models": [
                    _m("gpt-5.5", "GPT-5.5"),
                    _m("gpt-5.4", "GPT-5.4"),
                    _m("gpt-5.3-codex", "GPT-5.3 Codex"),
                    _m("gpt-5", "GPT-5"),
                    _m("gpt-5-mini", "GPT-5 Mini"),
                    _m("gpt-5-nano", "GPT-5 Nano"),
                ],
            },
            {
                "label": "OpenAI — GPT-4.1",
                "models": [
                    _m("gpt-4.1", "GPT-4.1"),
                    _m("gpt-4.1-mini", "GPT-4.1 Mini", "Default"),
                    _m("gpt-4.1-nano", "GPT-4.1 Nano"),
                ],
            },
            {
                "label": "OpenAI — GPT-4o",
                "models": [
                    _m("gpt-4o", "GPT-4o"),
                    _m("gpt-4o-mini", "GPT-4o Mini"),
                ],
            },
            {
                "label": "OpenAI — Reasoning",
                "models": [
                    _m("o3", "o3"),
                    _m("o4-mini", "o4 Mini"),
                ],
            },
        ],
    },
    "anthropic": {
        "default": "claude-sonnet-4",
        "categories": [
            {
                "label": "Anthropic — Opus",
                "models": [
                    _m("claude-opus-4.7", "Claude Opus 4.7"),
                    _m("claude-opus-4.6", "Claude Opus 4.6"),
                    _m("claude-opus-4.5", "Claude Opus 4.5"),
                    _m("claude-opus-4", "Claude Opus 4"),
                ],
            },
            {
                "label": "Anthropic — Sonnet",
                "models": [
                    _m("claude-sonnet-4.6", "Claude Sonnet 4.6"),
                    _m("claude-sonnet-4.5", "Claude Sonnet 4.5"),
                    _m("claude-sonnet-4", "Claude Sonnet 4", "Default"),
                    _m("claude-3.7-sonnet", "Claude 3.7 Sonnet"),
                ],
            },
            {
                "label": "Anthropic — Haiku",
                "models": [
                    _m("claude-haiku-4.5", "Claude Haiku 4.5"),
                    _m("claude-3.5-haiku", "Claude 3.5 Haiku"),
                ],
            },
        ],
    },
    "deepseek": {
        "default": "deepseek-chat",
        "categories": [
            {
                "label": "DeepSeek",
                "models": [
                    _m("deepseek-v4-pro", "DeepSeek V4 Pro"),
                    _m("deepseek-v4-flash", "DeepSeek V4 Flash"),
                    _m("deepseek-v3.2", "DeepSeek V3.2"),
                    _m("deepseek-v3", "DeepSeek V3"),
                    _m("deepseek-r1", "DeepSeek R1"),
                    _m("deepseek-reasoner", "DeepSeek Reasoner"),
                    _m("deepseek-chat", "DeepSeek Chat", "Default"),
                ],
            },
        ],
    },
    "openrouter": {
        "default": "google/gemini-3.1-flash-lite",
        "categories": [
            {
                "label": "Google Gemini",
                "models": [
                    _m("google/gemini-3.5-flash", "Gemini 3.5 Flash"),
                    _m("google/gemini-3-pro", "Gemini 3 Pro"),
                    _m("google/gemini-3.1-pro", "Gemini 3.1 Pro"),
                    _m("google/gemini-3.1-flash-lite", "Gemini 3.1 Flash Lite", "Default"),
                    _m("google/gemini-3-flash", "Gemini 3 Flash"),
                    _m("google/gemini-2.5-pro", "Gemini 2.5 Pro"),
                    _m("google/gemini-2.5-flash", "Gemini 2.5 Flash"),
                    _m("google/gemini-2.5-flash-lite", "Gemini 2.5 Flash Lite"),
                ],
            },
            {
                "label": "OpenAI",
                "models": [
                    _m("openai/gpt-5.5", "GPT-5.5"),
                    _m("openai/gpt-5.4", "GPT-5.4"),
                    _m("openai/gpt-5.3-codex", "GPT-5.3 Codex"),
                    _m("openai/gpt-5", "GPT-5"),
                    _m("openai/gpt-5-mini", "GPT-5 Mini"),
                    _m("openai/gpt-5-nano", "GPT-5 Nano"),
                    _m("openai/gpt-4.1", "GPT-4.1"),
                    _m("openai/gpt-4.1-mini", "GPT-4.1 Mini"),
                    _m("openai/gpt-4.1-nano", "GPT-4.1 Nano"),
                    _m("openai/gpt-4o", "GPT-4o"),
                    _m("openai/gpt-4o-mini", "GPT-4o Mini"),
                    _m("openai/o3", "o3"),
                    _m("openai/o4-mini", "o4 Mini"),
                ],
            },
            {
                "label": "Anthropic",
                "models": [
                    _m("anthropic/claude-opus-4.7", "Claude Opus 4.7"),
                    _m("anthropic/claude-opus-4.6", "Claude Opus 4.6"),
                    _m("anthropic/claude-opus-4.5", "Claude Opus 4.5"),
                    _m("anthropic/claude-opus-4", "Claude Opus 4"),
                    _m("anthropic/claude-sonnet-4.6", "Claude Sonnet 4.6"),
                    _m("anthropic/claude-sonnet-4.5", "Claude Sonnet 4.5"),
                    _m("anthropic/claude-sonnet-4", "Claude Sonnet 4"),
                    _m("anthropic/claude-3.7-sonnet", "Claude 3.7 Sonnet"),
                    _m("anthropic/claude-haiku-4.5", "Claude Haiku 4.5"),
                    _m("anthropic/claude-3.5-haiku", "Claude 3.5 Haiku"),
                ],
            },
            {
                "label": "xAI",
                "models": [
                    _m("x-ai/grok-4", "Grok 4"),
                    _m("x-ai/grok-4-fast", "Grok 4 Fast"),
                    _m("x-ai/grok-code", "Grok Code"),
                ],
            },
            {
                "label": "DeepSeek",
                "models": [
                    _m("deepseek/deepseek-v4-pro", "DeepSeek V4 Pro"),
                    _m("deepseek/deepseek-v4-flash", "DeepSeek V4 Flash"),
                    _m("deepseek/deepseek-v3.2", "DeepSeek V3.2"),
                    _m("deepseek/deepseek-v3", "DeepSeek V3"),
                    _m("deepseek/deepseek-r1", "DeepSeek R1"),
                    _m("deepseek/deepseek-reasoner", "DeepSeek Reasoner"),
                    _m("deepseek/deepseek-chat", "DeepSeek Chat"),
                ],
            },
            {
                "label": "Alibaba Qwen",
                "models": [
                    _m("qwen/qwen3.6", "Qwen 3.6"),
                    _m("qwen/qwen3-max-thinking", "Qwen 3 Max Thinking"),
                    _m("qwen/qwen3-max", "Qwen 3 Max"),
                    _m("qwen/qwen3-coder", "Qwen 3 Coder"),
                    _m("qwen/qwen3", "Qwen 3"),
                    _m("qwen/qwen2.5-coder", "Qwen 2.5 Coder"),
                ],
            },
            {
                "label": "Meta",
                "models": [
                    _m("meta-llama/llama-4-behemoth", "Llama 4 Behemoth"),
                    _m("meta-llama/llama-4-maverick", "Llama 4 Maverick"),
                    _m("meta-llama/llama-4-scout", "Llama 4 Scout"),
                ],
            },
            {
                "label": "Mistral AI",
                "models": [
                    _m("mistralai/mistral-large", "Mistral Large"),
                    _m("mistralai/mistral-medium", "Mistral Medium"),
                    _m("mistralai/mistral-small-4", "Mistral Small 4"),
                    _m("mistralai/codestral", "Codestral"),
                    _m("mistralai/pixtral", "Pixtral"),
                    _m("mistralai/magistral-medium", "Magistral Medium"),
                    _m("mistralai/magistral-small", "Magistral Small"),
                ],
            },
            {
                "label": "Cohere",
                "models": [
                    _m("cohere/command-a", "Command A"),
                    _m("cohere/command-r-plus", "Command R+"),
                    _m("cohere/command-r", "Command R"),
                ],
            },
            {
                "label": "Moonshot AI",
                "models": [
                    _m("moonshotai/kimi-k2.5", "Kimi K2.5"),
                    _m("moonshotai/kimi-k2", "Kimi K2"),
                ],
            },
            {
                "label": "Z.ai (GLM)",
                "models": [
                    _m("z-ai/glm-5.2", "GLM 5.2"),
                    _m("z-ai/glm-5.1", "GLM 5.1"),
                    _m("z-ai/glm-5", "GLM 5"),
                    _m("z-ai/glm-4.7", "GLM 4.7"),
                    _m("z-ai/glm-4.6", "GLM 4.6"),
                ],
            },
            {
                "label": "Microsoft",
                "models": [
                    _m("microsoft/phi-4", "Phi-4"),
                    _m("microsoft/phi-4-mini", "Phi-4 Mini"),
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
                    _m("claude-opus-4-7-thinking-xhigh", "Claude Opus 4.7 Thinking"),
                    _m("claude-4.6-opus-high-thinking", "Claude Opus 4.6 Thinking"),
                    _m("claude-4.5-opus-high-thinking", "Claude Opus 4.5 Thinking"),
                    _m("claude-opus-4-8-thinking-high", "Claude Opus 4.8 Thinking"),
                    _m("claude-4.6-sonnet-medium-thinking", "Claude Sonnet 4.6 Thinking"),
                    _m("claude-4.5-sonnet-thinking", "Claude Sonnet 4.5 Thinking"),
                    _m("claude-4.5-haiku-thinking", "Claude Haiku 4.5 Thinking"),
                    _m("claude-4-sonnet", "Claude Sonnet 4"),
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
                    _m("gpt-5.1-codex-max-high-fast", "GPT-5.1 Codex Max High Fast"),
                    _m("gpt-5-mini", "GPT-5 Mini"),
                ],
            },
            {
                "label": "Google (Cursor)",
                "models": [
                    _m("gemini-3.5-flash", "Gemini 3.5 Flash"),
                    _m("gemini-3.1-pro", "Gemini 3.1 Pro"),
                    _m("gemini-3.1-flash-lite", "Gemini 3.1 Flash Lite"),
                    _m("gemini-3-flash", "Gemini 3 Flash"),
                    _m("gemini-2.5-pro", "Gemini 2.5 Pro"),
                    _m("gemini-2.5-flash", "Gemini 2.5 Flash"),
                    _m("gemini-2.5-flash-lite", "Gemini 2.5 Flash Lite"),
                ],
            },
            {
                "label": "xAI / Moonshot (Cursor)",
                "models": [
                    _m("grok-4.3", "Grok 4.3"),
                    _m("grok-build-0.1", "Grok Build 0.1"),
                    _m("kimi-k2.5", "Kimi K2.5"),
                ],
            },
        ],
    },
    "ollama": {
        "default": "llama4",
        "categories": [
            {
                "label": "Ollama — Popular Local",
                "models": [
                    _m("llama4", "Llama 4", "Default"),
                    _m("qwen3", "Qwen 3"),
                    _m("qwen3-coder", "Qwen 3 Coder"),
                    _m("deepseek-v4", "DeepSeek V4"),
                    _m("deepseek-r1", "DeepSeek R1"),
                    _m("mistral-small-4", "Mistral Small 4"),
                    _m("codestral", "Codestral"),
                    _m("gemma4", "Gemma 4"),
                    _m("phi4", "Phi-4"),
                    _m("glm-5", "GLM-5"),
                ],
            },
            {
                "label": "Meta Llama 4",
                "models": [
                    _m("llama-4-behemoth", "Llama 4 Behemoth"),
                    _m("llama-4-maverick", "Llama 4 Maverick"),
                    _m("llama-4-scout", "Llama 4 Scout"),
                ],
            },
            {
                "label": "Alibaba Qwen",
                "models": [
                    _m("qwen3.6", "Qwen 3.6"),
                    _m("qwen3-max", "Qwen 3 Max"),
                    _m("qwen2.5-coder", "Qwen 2.5 Coder"),
                ],
            },
            {
                "label": "Microsoft Phi",
                "models": [
                    _m("phi-4", "Phi-4"),
                    _m("phi-4-mini", "Phi-4 Mini"),
                ],
            },
        ],
    },
    "antigravity": {
        "default": "gemini-3.1-flash-lite",
        "categories": [
            {
                "label": "Antigravity — Google Gemini",
                "models": [
                    _m("gemini-3.5-flash", "Gemini 3.5 Flash"),
                    _m("gemini-3-pro", "Gemini 3 Pro"),
                    _m("gemini-3.1-pro", "Gemini 3.1 Pro"),
                    _m("gemini-3.1-flash-lite", "Gemini 3.1 Flash Lite", "Default"),
                    _m("gemini-3-flash", "Gemini 3 Flash"),
                    _m("gemini-2.5-pro", "Gemini 2.5 Pro"),
                    _m("gemini-2.5-flash", "Gemini 2.5 Flash"),
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

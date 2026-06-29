"""Translate non-English SMS bodies to English for the live feed."""

from __future__ import annotations

import hashlib
import os
import re
from concurrent.futures import ThreadPoolExecutor, as_completed

_CJK = re.compile(r"[\u4e00-\u9fff\u3040-\u30ff\u3400-\u4dbf\uac00-\ud7af]")
_CACHE: dict[str, str] = {}
_MAX = int(os.getenv("PLATFORMS_TRANSLATE_CACHE", "3000") or "3000")
_ENABLED = os.getenv("PLATFORMS_TRANSLATE", "1").strip().lower() in ("1", "true", "yes", "on")
_WORKERS = int(os.getenv("PLATFORMS_TRANSLATE_WORKERS", "6") or "6")


def enabled() -> bool:
    return _ENABLED


def needs_translation(text: str) -> bool:
    text = (text or "").strip()
    if not text:
        return False
    if _CJK.search(text):
        return True
    non_latin = sum(1 for ch in text if ord(ch) > 127)
    return non_latin >= max(3, len(text) // 8)


def _cache_key(text: str) -> str:
    return hashlib.md5(text.encode("utf-8", errors="ignore")).hexdigest()


def translate_one(text: str) -> str:
    text = (text or "").strip()
    if not text or not enabled() or not needs_translation(text):
        return text

    key = _cache_key(text)
    if key in _CACHE:
        return _CACHE[key]

    try:
        from deep_translator import GoogleTranslator

        out = GoogleTranslator(source="auto", target="en").translate(text[:4800])
        out = (out or text).strip()
    except Exception:
        out = text

    if len(_CACHE) >= _MAX:
        _CACHE.clear()
    _CACHE[key] = out
    return out


def translate_many(texts: list[str]) -> list[str]:
    if not enabled():
        return texts

    out = list(texts)
    todo: list[tuple[int, str]] = []
    for i, text in enumerate(texts):
        if needs_translation(text):
            key = _cache_key(text)
            if key in _CACHE:
                out[i] = _CACHE[key]
            else:
                todo.append((i, text))

    if not todo:
        return out

    workers = min(_WORKERS, len(todo))
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {pool.submit(translate_one, text): idx for idx, text in todo}
        for fut in as_completed(futures):
            idx = futures[fut]
            try:
                out[idx] = fut.result()
            except Exception:
                out[idx] = texts[idx]
    return out

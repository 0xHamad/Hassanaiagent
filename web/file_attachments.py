"""Chat file attachments — validation and LLM context building."""

from __future__ import annotations

import base64
import binascii
import re
from typing import Any

MAX_FILES = 8
MAX_FILE_BYTES = 5 * 1024 * 1024
MAX_TEXT_CHARS = 80_000

SUPPORTED: dict[str, list[str]] = {
    "images": [".jpg", ".jpeg", ".png", ".webp", ".heic", ".heif", ".bmp", ".gif"],
    "documents": [".pdf", ".txt", ".md", ".csv", ".tsv", ".json", ".xml", ".yaml", ".yml", ".log", ".rtf"],
    "code": [
        ".py", ".js", ".ts", ".jsx", ".tsx", ".java", ".cpp", ".c", ".cs", ".go", ".rs",
        ".php", ".rb", ".swift", ".kt", ".scala", ".sql", ".sh", ".bat", ".ps1",
        ".html", ".css", ".scss", ".vue",
    ],
    "config": [
        ".env", ".env.example", "docker-compose.yml", "dockerfile", "package.json",
        "package-lock.json", "requirements.txt", "pyproject.toml", "cargo.toml", "go.mod", "composer.json",
    ],
    "spreadsheet": [".csv", ".xlsx", ".xls"],
}

MIME_BY_EXT: dict[str, str] = {
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
    ".webp": "image/webp",
    ".heic": "image/heic",
    ".heif": "image/heif",
    ".bmp": "image/bmp",
    ".gif": "image/gif",
    ".pdf": "application/pdf",
    ".json": "application/json",
    ".xml": "application/xml",
    ".csv": "text/csv",
    ".txt": "text/plain",
    ".md": "text/markdown",
    ".html": "text/html",
    ".css": "text/css",
    ".py": "text/x-python",
}

TEXT_EXTENSIONS = set(
    SUPPORTED["documents"] + SUPPORTED["code"] + [".csv", ".tsv", ".yaml", ".yml", ".log", ".rtf", ".env", ".env.example"]
)
IMAGE_EXTENSIONS = set(SUPPORTED["images"])
ALL_EXTENSIONS = set()
for exts in SUPPORTED.values():
    ALL_EXTENSIONS.update(exts)
SPECIAL_FILENAMES = {
    "docker-compose.yml", "dockerfile", "package.json", "package-lock.json",
    "requirements.txt", "pyproject.toml", "cargo.toml", "go.mod", "composer.json",
    ".env", ".env.example",
}


def _fmt_size(n: int) -> str:
    if n < 1024:
        return f"{n} B"
    if n < 1024 * 1024:
        return f"{n / 1024:.1f} KB"
    return f"{n / (1024 * 1024):.1f} MB"


def supported_payload() -> dict[str, Any]:
    flat = sorted(ALL_EXTENSIONS | {f.lower() for f in SPECIAL_FILENAMES})
    return {
        "max_files": MAX_FILES,
        "max_file_mb": MAX_FILE_BYTES // (1024 * 1024),
        "categories": SUPPORTED,
        "accept": ",".join(sorted(set(flat))),
    }


def _ext(name: str) -> str:
    low = (name or "").strip().lower()
    if low in SPECIAL_FILENAMES or low.split("/")[-1] in SPECIAL_FILENAMES:
        base = low.split("/")[-1]
        if base == "dockerfile":
            return ".dockerfile"
        if base.endswith(".example"):
            return ".env.example"
        return f".{base}" if not base.startswith(".") else base
    dot = low.rfind(".")
    return low[dot:] if dot >= 0 else ""


def _category(name: str) -> str:
    low = name.lower()
    if low in SPECIAL_FILENAMES or low.split("/")[-1] in SPECIAL_FILENAMES:
        if low in (".env", ".env.example") or "docker" in low or low.endswith(".toml") or low.endswith(".mod"):
            return "config"
        if low.endswith(".json") or low == "package-lock.json":
            return "config"
        if low == "requirements.txt":
            return "config"
    ext = _ext(name)
    for cat, exts in SUPPORTED.items():
        if ext in exts:
            return cat
    return "other"


def is_allowed_filename(name: str) -> bool:
    low = (name or "").strip().lower()
    base = low.split("/")[-1].split("\\")[-1]
    if base in SPECIAL_FILENAMES:
        return True
    ext = _ext(name)
    return ext in ALL_EXTENSIONS


def decode_payload(data_b64: str) -> bytes:
    raw = (data_b64 or "").strip()
    if raw.startswith("data:") and "," in raw:
        raw = raw.split(",", 1)[1]
    try:
        return base64.b64decode(raw, validate=True)
    except (binascii.Error, ValueError) as e:
        raise ValueError("Invalid file encoding") from e


def _decode_text(data: bytes) -> str:
    for enc in ("utf-8", "utf-8-sig", "latin-1"):
        try:
            return data.decode(enc)
        except UnicodeDecodeError:
            continue
    return data.decode("utf-8", errors="replace")


def process_upload(name: str, data_b64: str, declared_size: int = 0) -> dict[str, Any]:
    name = (name or "file").strip()[:200]
    if not is_allowed_filename(name):
        raise ValueError(f"Unsupported file type: {name}")
    data = decode_payload(data_b64)
    size = len(data)
    if declared_size and abs(declared_size - size) > 1024:
        pass
    if size > MAX_FILE_BYTES:
        raise ValueError(f"{name} exceeds {MAX_FILE_BYTES // (1024 * 1024)}MB limit")
    if size == 0:
        raise ValueError(f"{name} is empty")

    ext = _ext(name)
    category = _category(name)
    mime = MIME_BY_EXT.get(ext, "application/octet-stream")

    if ext in IMAGE_EXTENSIONS or category == "images":
        return {
            "name": name,
            "category": "images",
            "kind": "image",
            "mime": mime,
            "size": size,
            "base64": base64.b64encode(data).decode("ascii"),
        }

    if ext in (".xlsx", ".xls") or category == "spreadsheet" and ext != ".csv":
        return {
            "name": name,
            "category": category,
            "kind": "binary",
            "mime": mime,
            "size": size,
            "note": "Spreadsheet attached — open in Excel/LibreOffice. Describe what you need from it.",
        }

    if ext == ".pdf":
        return {
            "name": name,
            "category": "documents",
            "kind": "binary",
            "mime": "application/pdf",
            "size": size,
            "note": "PDF attached — paste relevant text or ask about filename/context.",
        }

    if ext in TEXT_EXTENSIONS or category in ("documents", "code", "config") or ext == ".csv":
        text = _decode_text(data)
        if len(text) > MAX_TEXT_CHARS:
            text = text[:MAX_TEXT_CHARS] + f"\n\n… [truncated — {MAX_TEXT_CHARS} char limit]"
        lang = ext.lstrip(".") or "text"
        return {
            "name": name,
            "category": category,
            "kind": "text",
            "mime": mime,
            "size": size,
            "text": text,
            "lang": lang,
        }

    return {
        "name": name,
        "category": category,
        "kind": "binary",
        "mime": mime,
        "size": size,
        "note": f"Binary file ({ext or 'unknown'}) attached.",
    }


def process_many(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if len(items) > MAX_FILES:
        raise ValueError(f"Maximum {MAX_FILES} files per message")
    out = []
    for item in items:
        out.append(process_upload(
            str(item.get("name") or "file"),
            str(item.get("data") or ""),
            int(item.get("size") or 0),
        ))
    return out


def summary_for_display(items: list[dict[str, Any]]) -> str:
    if not items:
        return ""
    parts = [f"📎 {i['name']} ({_fmt_size(i.get('size', 0))})" for i in items]
    return "\n".join(parts)


def build_llm_context(user_text: str, items: list[dict[str, Any]]) -> tuple[str, list[dict[str, str]]]:
    """Return (text_for_llm, gemini_image_parts)."""
    images: list[dict[str, str]] = []
    blocks: list[str] = []

    for item in items:
        if item.get("kind") == "image":
            images.append({"mime": item.get("mime") or "image/jpeg", "data": item["base64"]})
            blocks.append(f"[Image attached: {item['name']}]")
        elif item.get("kind") == "text" and item.get("text"):
            lang = item.get("lang") or "text"
            blocks.append(
                f"--- File: {item['name']} ({item.get('category', 'file')}) ---\n"
                f"```{lang}\n{item['text']}\n```"
            )
        elif item.get("note"):
            blocks.append(f"[{item['name']}: {item['note']}]")

    attach_block = "\n\n".join(blocks)
    if user_text and attach_block:
        combined = f"{user_text.strip()}\n\n{attach_block}"
    elif attach_block:
        combined = attach_block
    else:
        combined = user_text.strip()
    return combined, images

"""Supabase persistence for conversations and messages."""

from __future__ import annotations

from typing import Any, Callable


def list_conversations(sb_get: Callable, user_id: str, limit: int = 100) -> list[dict]:
    rows = sb_get(
        "hassan_conversations",
        {
            "user_id": f"eq.{user_id}",
            "select": "id,title,created_at,updated_at",
            "order": "updated_at.desc",
            "limit": str(limit),
        },
    )
    out = []
    for row in rows:
        preview_rows = sb_get(
            "hassan_messages",
            {
                "conversation_id": f"eq.{row['id']}",
                "role": "eq.user",
                "select": "content",
                "order": "created_at.asc",
                "limit": "1",
            },
        )
        preview = preview_rows[0]["content"][:120] if preview_rows else ""
        out.append({**row, "message_count": 0, "preview": preview})
    return out


def create_conversation(sb_insert: Callable, user_id: str, title: str = "New Chat") -> dict:
    return sb_insert(
        "hassan_conversations",
        {"user_id": user_id, "title": title[:120] or "New Chat"},
    )


def get_conversation(sb_get: Callable, conv_id: str, user_id: str) -> dict | None:
    rows = sb_get(
        "hassan_conversations",
        {
            "id": f"eq.{conv_id}",
            "user_id": f"eq.{user_id}",
            "select": "id,title,created_at,updated_at,user_id",
            "limit": "1",
        },
    )
    return rows[0] if rows else None


def list_messages(sb_get: Callable, conv_id: str) -> list[dict]:
    return sb_get(
        "hassan_messages",
        {
            "conversation_id": f"eq.{conv_id}",
            "select": "id,role,content,created_at",
            "order": "created_at.asc",
        },
    )


def add_message(sb_insert: Callable, sb_patch: Callable, conv_id: str, role: str, content: str) -> dict:
    msg = sb_insert(
        "hassan_messages",
        {"conversation_id": conv_id, "role": role, "content": content},
    )
    from datetime import datetime, timezone

    sb_patch(
        "hassan_conversations",
        {"id": f"eq.{conv_id}"},
        {"updated_at": datetime.now(timezone.utc).isoformat()},
    )
    return msg


def rename_conversation(sb_patch: Callable, conv_id: str, title: str) -> None:
    from datetime import datetime, timezone

    sb_patch(
        "hassan_conversations",
        {"id": f"eq.{conv_id}"},
        {"title": title[:120] or "New Chat", "updated_at": datetime.now(timezone.utc).isoformat()},
    )


def delete_conversation(sb_delete: Callable, conv_id: str, user_id: str) -> None:
    sb_delete(
        "hassan_messages",
        {"conversation_id": f"eq.{conv_id}"},
    )
    sb_delete(
        "hassan_conversations",
        {"id": f"eq.{conv_id}", "user_id": f"eq.{user_id}"},
    )


def admin_overview(sb_get: Callable) -> dict[str, Any]:
    users = sb_get("hassan_users", {"select": "id,username,created_at", "order": "created_at.desc"})
    sessions = sb_get("hassan_sessions", {"select": "id,user_id,token,created_at,expires_at", "order": "created_at.desc", "limit": "200"})
    conversations = sb_get("hassan_conversations", {"select": "id,user_id,title,created_at,updated_at", "order": "updated_at.desc", "limit": "200"})
    messages = sb_get("hassan_messages", {"select": "id", "limit": "1000"})
    return {
        "user_count": len(users),
        "session_count": len(sessions),
        "conversation_count": len(conversations),
        "message_count": len(messages),
        "users": users,
        "sessions": sessions,
        "conversations": conversations,
    }


def get_user_settings(sb_get: Callable, user_id: str) -> dict[str, Any]:
    from web.user_settings import DEFAULTS, _row_to_dict

    rows = sb_get(
        "hassan_user_settings",
        {
            "user_id": f"eq.{user_id}",
            "select": "provider,api_key,cursor_api_key,model,base_url,theme",
            "limit": "1",
        },
    )
    if not rows:
        return dict(DEFAULTS)
    return _row_to_dict(rows[0])


def save_user_settings(
    sb_get: Callable,
    sb_insert: Callable,
    sb_patch: Callable,
    user_id: str,
    data: dict[str, Any],
) -> dict[str, Any]:
    from datetime import datetime, timezone

    from llm_router import normalize_gemini_model
    from web.user_settings import DEFAULTS

    merged = {**DEFAULTS, **{k: str(data.get(k, "") or "") for k in DEFAULTS}}
    if merged.get("provider") == "gemini" and merged.get("model"):
        merged["model"] = normalize_gemini_model(merged["model"])
    now = datetime.now(timezone.utc).isoformat()
    payload = {
        "user_id": user_id,
        "provider": merged["provider"],
        "api_key": merged["api_key"],
        "cursor_api_key": merged["cursor_api_key"],
        "model": merged["model"],
        "base_url": merged["base_url"],
        "theme": merged["theme"],
        "updated_at": now,
    }
    existing = sb_get(
        "hassan_user_settings",
        {"user_id": f"eq.{user_id}", "select": "user_id", "limit": "1"},
    )
    if existing:
        sb_patch(
            "hassan_user_settings",
            {"user_id": f"eq.{user_id}"},
            {k: v for k, v in payload.items() if k != "user_id"},
        )
    else:
        sb_insert("hassan_user_settings", payload)
    return merged


def admin_user_detail(sb_get: Callable, user_id: str) -> dict[str, Any]:
    users = sb_get(
        "hassan_users",
        {"id": f"eq.{user_id}", "select": "id,username,created_at", "limit": "1"},
    )
    if not users:
        return {}
    user = users[0]
    sessions = sb_get(
        "hassan_sessions",
        {"user_id": f"eq.{user_id}", "select": "id,created_at,expires_at", "order": "created_at.desc"},
    )
    convs = sb_get(
        "hassan_conversations",
        {"user_id": f"eq.{user_id}", "select": "id,title,created_at,updated_at", "order": "updated_at.desc"},
    )
    chats = []
    for c in convs:
        msgs = list_messages(sb_get, c["id"])
        chats.append({**c, "messages": msgs})
    return {"user": user, "sessions": sessions, "conversations": chats}

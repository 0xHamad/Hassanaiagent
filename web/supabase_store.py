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
    users = sb_get("hassan_users", {"select": "id,username,created_at,is_blocked", "order": "created_at.desc"})
    sessions = sb_get(
        "hassan_sessions",
        {"select": "id,user_id,token,created_at,expires_at,ip_address,user_agent", "order": "created_at.desc", "limit": "500"},
    )
    conversations = sb_get("hassan_conversations", {"select": "id,user_id,title,created_at,updated_at", "order": "updated_at.desc", "limit": "200"})
    messages = sb_get("hassan_messages", {"select": "id", "limit": "1000"})

    user_map = {u["id"]: u["username"] for u in users}
    device_counts: dict[str, set[str]] = {}
    for s in sessions:
        uid = s["user_id"]
        key = f"{s.get('ip_address', '')}|{s.get('user_agent', '')}"
        device_counts.setdefault(uid, set()).add(key)
        s["username"] = user_map.get(uid, "—")

    for u in users:
        u["device_count"] = len(device_counts.get(u["id"], set()))
        u["active_sessions"] = sum(1 for x in sessions if x["user_id"] == u["id"])
        u["is_blocked"] = bool(u.get("is_blocked", False))

    signup_limit = 100
    try:
        rows = sb_get("hassan_settings", {"key": "eq.signup_limit", "select": "value", "limit": "1"})
        if rows:
            signup_limit = int(rows[0]["value"])
    except Exception:
        pass

    return {
        "user_count": len(users),
        "session_count": len(sessions),
        "conversation_count": len(conversations),
        "message_count": len(messages),
        "signup_limit": signup_limit,
        "users": users,
        "sessions": sessions,
        "conversations": conversations,
    }


def admin_user_detail(sb_get: Callable, user_id: str) -> dict[str, Any]:
    users = sb_get(
        "hassan_users",
        {"id": f"eq.{user_id}", "select": "id,username,created_at,is_blocked", "limit": "1"},
    )
    if not users:
        return {}
    user = users[0]
    user["is_blocked"] = bool(user.get("is_blocked", False))
    sessions = sb_get(
        "hassan_sessions",
        {"user_id": f"eq.{user_id}", "select": "id,created_at,expires_at,ip_address,user_agent", "order": "created_at.desc"},
    )
    convs = sb_get(
        "hassan_conversations",
        {"user_id": f"eq.{user_id}", "select": "id,title,created_at,updated_at", "order": "updated_at.desc"},
    )
    chats = []
    for c in convs:
        msgs = list_messages(sb_get, c["id"])
        chats.append({**c, "messages": msgs})

    devices_map: dict[str, dict] = {}
    for s in sessions:
        key = f"{s.get('ip_address', '')}|{s.get('user_agent', '')}"
        if key not in devices_map:
            devices_map[key] = {
                "ip_address": s.get("ip_address") or "—",
                "user_agent": s.get("user_agent") or "—",
                "session_count": 0,
                "last_seen": s.get("created_at"),
            }
        devices_map[key]["session_count"] += 1

    return {
        "user": user,
        "sessions": sessions,
        "devices": {
            "active_sessions": len(sessions),
            "device_count": len(devices_map),
            "devices": list(devices_map.values()),
        },
        "conversations": chats,
    }

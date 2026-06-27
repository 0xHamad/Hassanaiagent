"""Admin panel API helpers."""

from __future__ import annotations

import secrets
from datetime import datetime, timedelta, timezone

_admin_tokens: dict[str, datetime] = {}


def issue_admin_token() -> str:
    token = secrets.token_urlsafe(32)
    _admin_tokens[token] = datetime.now(timezone.utc) + timedelta(hours=12)
    return token


def verify_admin_token(token: str | None) -> bool:
    if not token:
        return False
    exp = _admin_tokens.get(token)
    if not exp:
        return False
    if exp < datetime.now(timezone.utc):
        _admin_tokens.pop(token, None)
        return False
    return True


def revoke_admin_token(token: str | None) -> None:
    if token:
        _admin_tokens.pop(token, None)

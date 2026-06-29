"""Unified live SMS row (no platform name exposed to UI)."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timezone

_UI_JUNK = re.compile(
    r"查看|号码列表|号码$|View number|number list|click here",
    re.I,
)
_DIGITS_ONLY = re.compile(r"^\d{6,20}$")
_SENDER_DIGITS = re.compile(r"^\d+$")
_BRAND_CN = re.compile(r"【([^】]{2,32})】")
_BRAND_EN = re.compile(r"\[([A-Za-z0-9][^\]\[]]{1,30})\]")
_MASKED = re.compile(r"^\*+[0-9Xx]{2,8}$")


def format_recv_number(raw: str, *, dial: str = "") -> str:
    digits = re.sub(r"\D", "", str(raw or ""))
    if not digits:
        return ""
    dial_digits = re.sub(r"\D", "", dial or "")
    if dial_digits and not digits.startswith(dial_digits):
        return f"+{dial_digits}{digits}"
    return f"+{digits}"


def resolve_cli_display(
    *,
    sender: str,
    text: str,
    recv_number: str = "",
    dial: str = "",
) -> str:
    """Best CLI/Sender label: service name, masked sender, or short code."""
    sender = (sender or "").strip()
    text = (text or "").strip()

    brand = ""
    m = _BRAND_CN.search(text) or _BRAND_EN.search(text)
    if m:
        brand = m.group(1).strip()

    named_sender = bool(
        sender
        and not _SENDER_DIGITS.fullmatch(sender)
        and sender.lower() not in {"unknown", "—"}
    )

    if named_sender:
        if brand and (_MASKED.match(sender) or len(sender) <= 8):
            return f"{brand} · {sender}"
        return sender

    if brand:
        if sender and _SENDER_DIGITS.fullmatch(sender):
            return f"{brand} · {sender}"
        return brand

    if sender:
        return sender

    recv = format_recv_number(recv_number, dial=dial)
    return recv or "Unknown"


def format_display_time(raw: str) -> str:
    raw = (raw or "").strip()
    if not raw:
        return "—"

    if raw.isdigit():
        ts = int(raw)
        if ts > 1_000_000_000_000:
            ts //= 1000
        if ts > 1_000_000_000:
            dt = datetime.fromtimestamp(ts, tz=timezone.utc)
            now = datetime.now(timezone.utc)
            diff = max(0, int((now - dt).total_seconds()))
            if diff < 45:
                return "just now"
            if diff < 3600:
                mins = diff // 60
                return f"{mins} min ago" if mins > 1 else "1 min ago"
            if diff < 86400:
                hrs = diff // 3600
                return f"{hrs} hr ago" if hrs > 1 else "1 hr ago"
            if diff < 604800:
                days = diff // 86400
                return f"{days} day ago" if days > 1 else "1 day ago"
            return dt.strftime("%d %b %Y, %H:%M UTC")

    if "T" in raw and len(raw) >= 19:
        try:
            dt = datetime.fromisoformat(raw.replace("Z", "+00:00"))
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt.strftime("%d %b %Y, %H:%M UTC")
        except ValueError:
            pass

    return raw


def is_valid_sms_row(*, cli: str, text: str) -> bool:
    text = (text or "").strip()
    cli = (cli or "").strip()
    if not text or len(text) < 6:
        return False
    if _DIGITS_ONLY.fullmatch(text):
        return False
    if _UI_JUNK.search(cli) or _UI_JUNK.search(text):
        return False
    return True


@dataclass(frozen=True)
class LiveSms:
    id: str
    country: str
    cli: str
    text: str
    code: str
    time: str
    sort_key: str

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "cli": self.cli,
            "text": self.text,
            "code": self.code,
            "time": format_display_time(self.time),
        }

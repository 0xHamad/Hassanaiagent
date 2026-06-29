"""7sim.net widget messages API."""

from __future__ import annotations

import os

import requests

from web.sms_platforms.base import LiveSms, is_valid_sms_row, resolve_cli_display

UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/149.0.0.0 Safari/537.36"
)
WIDGET_ID = os.getenv("SEVEN_SIM_WIDGET_ID", "y4b16")
PAGES = int(os.getenv("SEVEN_SIM_PAGES", "2") or "2")

_PREFIX_COUNTRY = [
    ("971", "UAE"), ("966", "Saudi Arabia"), ("880", "Bangladesh"), ("234", "Nigeria"),
    ("91", "India"), ("86", "China"), ("84", "Vietnam"), ("66", "Thailand"),
    ("62", "Indonesia"), ("60", "Malaysia"), ("49", "Germany"), ("44", "UK"),
    ("39", "Italy"), ("34", "Spain"), ("33", "France"), ("1", "USA"),
]


def _country_from_sender(sender: str) -> str:
    digits = "".join(c for c in sender if c.isdigit())
    for prefix, name in sorted(_PREFIX_COUNTRY, key=lambda x: -len(x[0])):
        if digits.startswith(prefix):
            return name
    if "XXX" in sender.upper():
        return "International"
    return "Unknown"


def fetch() -> list[LiveSms]:
    out: list[LiveSms] = []
    session = requests.Session()
    session.headers.update({"User-Agent": UA, "Accept": "application/json", "Referer": "https://7sim.net/"})
    for page in range(1, PAGES + 1):
        try:
            r = session.get(
                f"https://7sim.net/api/v2/widget/messages?id={WIDGET_ID}&page={page}&lang=en",
                timeout=25,
            )
            r.raise_for_status()
            for row in r.json().get("messages") or []:
                sender = str(row.get("sender") or "Unknown")
                text = str(row.get("text") or "")
                cli = resolve_cli_display(sender=sender, text=text)
                out.append(
                    LiveSms(
                        id=f"7s-{row.get('_id', '')}-{row.get('code', '')}",
                        country=_country_from_sender(sender),
                        cli=cli,
                        text=text,
                        code=str(row.get("code") or ""),
                        time=str(row.get("date_human") or ""),
                        sort_key=str(row.get("date_human") or ""),
                    )
                )
        except Exception:
            continue
    return out

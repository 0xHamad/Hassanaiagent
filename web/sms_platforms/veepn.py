"""VeePN online-sms JSON endpoints."""

from __future__ import annotations

import os

import requests

from web.sms_platforms.base import LiveSms

UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/149.0.0.0 Safari/537.36"
)
BASE = "https://veepn.com"
MAX_COUNTRIES = int(os.getenv("VEEPN_FEED_COUNTRIES", "10") or "10")
NUMBERS_EACH = int(os.getenv("VEEPN_FEED_NUMBERS", "2") or "2")


def fetch() -> list[LiveSms]:
    session = requests.Session()
    session.headers.update({"User-Agent": UA, "Referer": f"{BASE}/online-sms/"})
    out: list[LiveSms] = []
    try:
        countries = session.get(f"{BASE}/online-sms/countries/", timeout=25).json()
    except Exception:
        return out

    for c in countries[:MAX_COUNTRIES]:
        if not c.get("online", True):
            continue
        slug = str(c.get("name") or "")
        locale = str(c.get("locale") or slug.title())
        try:
            nums = session.get(f"{BASE}/online-sms/countries/{slug}/", timeout=25).json()
        except Exception:
            continue
        active = [n for n in nums if not n.get("is_archive")][:NUMBERS_EACH]
        for n in active:
            code = str(n.get("code") or "")
            if not code:
                continue
            try:
                data = session.get(
                    f"{BASE}/online-sms/countries/{slug}/{code}/",
                    params={"page": 1, "count": 8},
                    headers={"Referer": f"{BASE}/online-sms/{slug}/{code}/"},
                    timeout=25,
                ).json()
                for row in (data.get("data") or [])[:8]:
                    out.append(
                        LiveSms(
                            id=f"vp-{row.get('id', '')}",
                            country=locale,
                            cli=str(row.get("in_number") or "Unknown"),
                            text=str(row.get("text") or ""),
                            code=str(row.get("code") or ""),
                            time=str(row.get("data_humans") or row.get("created_at") or ""),
                            sort_key=str(row.get("created_at") or ""),
                        )
                    )
            except Exception:
                continue
    return out

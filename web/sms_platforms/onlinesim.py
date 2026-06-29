"""OnlineSim.io free numbers API."""

from __future__ import annotations

import os

import requests

from web.sms_platforms.base import LiveSms

UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/149.0.0.0 Safari/537.36"
)
MAX_COUNTRIES = int(os.getenv("ONLINESIM_COUNTRIES", "14") or "14")


def fetch() -> list[LiveSms]:
    session = requests.Session()
    session.headers.update(
        {
            "User-Agent": UA,
            "Accept": "application/json",
            "api": "true",
            "Referer": "https://onlinesim.io/",
        }
    )
    out: list[LiveSms] = []
    try:
        seed = session.get(
            "https://onlinesim.io/api/v1/free_numbers_content/countries/united_kingdom",
            params={"ui": "true", "lang": "en"},
            timeout=30,
        )
        seed.raise_for_status()
        counties = seed.json().get("counties") or []
    except Exception:
        return out

    for c in counties[:MAX_COUNTRIES]:
        if not c.get("online", True):
            continue
        name = str(c.get("name") or "")
        locale = str(c.get("locale") or name.title())
        try:
            r = session.get(
                f"https://onlinesim.io/api/v1/free_numbers_content/countries/{name}",
                params={"ui": "true", "lang": "en"},
                timeout=25,
            )
            r.raise_for_status()
            msgs = (r.json().get("messages") or {}).get("data") or []
            for row in msgs[:15]:
                out.append(
                    LiveSms(
                        id=f"os-{row.get('id', '')}",
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

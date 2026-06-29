"""Ajiema.com HTML SMS pages."""

from __future__ import annotations

import hashlib
import os
import re

import requests

from web.sms_platforms.base import LiveSms, format_recv_number, is_valid_sms_row, resolve_cli_display

UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/149.0.0.0 Safari/537.36"
)
BASE = "https://ajiema.com"
MAX_COUNTRIES = int(os.getenv("AJIEMA_FEED_COUNTRIES", "8") or "8")
NUMBERS_EACH = int(os.getenv("AJIEMA_FEED_NUMBERS", "2") or "2")

COUNTRY_LINK = re.compile(r'href="/num/(\d+)"[^>]*>([^<]+)</a>')
NUMBER_LINK = re.compile(r'href="(/num/(\d+)/(\d+))"')
MSG_BLOCK = re.compile(
    r'<div class="row message_details">\s*'
    r'<div class="col-md-3 sender">\s*<label>Sender</label><br>\s*(.*?)\s*</div>\s*'
    r'<div class="col-md-6 msg">\s*<label>Message</label><br>\s*(.*?)\s*</div>\s*'
    r'<div class="col-md-3 time">\s*<label>Time</label><br>\s*'
    r'<p class="timestamp">(\d+)</p>',
    re.S,
)


def _clean(text: str) -> str:
    text = re.sub(r"<[^>]+>", " ", text or "")
    return re.sub(r"\s+", " ", text).strip()


def fetch() -> list[LiveSms]:
    session = requests.Session()
    session.headers.update({"User-Agent": UA, "Referer": f"{BASE}/"})
    out: list[LiveSms] = []
    try:
        home = session.get(f"{BASE}/", timeout=25).text
    except Exception:
        return out

    countries: list[tuple[str, str]] = []
    seen: set[str] = set()
    for code, label in COUNTRY_LINK.findall(home):
        if code in seen:
            continue
        seen.add(code)
        countries.append((code, _clean(label) or f"+{code}"))
    countries = countries[:MAX_COUNTRIES]

    for cc, label in countries:
        try:
            html = session.get(f"{BASE}/num/{cc}", timeout=25).text
        except Exception:
            continue
        nums = []
        for _path, ccode, num in NUMBER_LINK.findall(html):
            if ccode == cc and num not in nums:
                nums.append(num)
            if len(nums) >= NUMBERS_EACH:
                break
        for num in nums:
            try:
                page = session.get(
                    f"{BASE}/num/{cc}/{num}",
                    headers={"Referer": f"{BASE}/num/{cc}"},
                    timeout=25,
                ).text
            except Exception:
                continue
            for sender, text, ts in MSG_BLOCK.findall(page):
                text = _clean(text)
                sender = _clean(sender)
                if not is_valid_sms_row(cli=sender or "Unknown", text=text):
                    continue
                recv = f"+{cc}{num}"
                cli = resolve_cli_display(sender=sender, text=text, recv_number=recv, dial=cc)
                if re.fullmatch(r"\d{13,}", cli.replace(" ", "")):
                    cli = format_recv_number(recv, dial=cc) or cli
                h = hashlib.md5(f"{sender}|{text}".encode()).hexdigest()[:8]
                out.append(
                    LiveSms(
                        id=f"aj-{cc}-{num}-{ts}-{h}",
                        country=label,
                        cli=cli,
                        text=text,
                        code="",
                        time=ts,
                        sort_key=ts,
                    )
                )
    return out

"""Merge all temp-SMS sources into one live feed."""

from __future__ import annotations

import os
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone

from web.sms_platforms import ajiema, onlinesim, seven_sim, veepn
from web.sms_platforms.base import LiveSms, extract_brand, is_valid_sms_row
from web.sms_platforms import translate

_CACHE: dict | None = None
_CACHE_AT = 0.0
TTL = float(os.getenv("PLATFORMS_CACHE_SECONDS", "12") or "12")
MAX_ROWS = int(os.getenv("PLATFORMS_MAX_ROWS", "150") or "150")
MAX_PER_SOURCE = int(os.getenv("PLATFORMS_MAX_PER_SOURCE", "40") or "40")

_FETCHERS = (
    ("seven_sim", seven_sim.fetch),
    ("onlinesim", onlinesim.fetch),
    ("veepn", veepn.fetch),
    ("ajiema", ajiema.fetch),
)


def _dedupe(rows: list[LiveSms]) -> list[LiveSms]:
    seen: set[str] = set()
    out: list[LiveSms] = []
    for row in rows:
        if row.id in seen:
            continue
        seen.add(row.id)
        out.append(row)
    return out


def _source_key(row: LiveSms) -> str:
    return row.id.split("-", 1)[0] if "-" in row.id else row.id


def _cap_per_source(rows: list[LiveSms]) -> list[LiveSms]:
    counts: dict[str, int] = {}
    out: list[LiveSms] = []
    for row in rows:
        key = _source_key(row)
        counts[key] = counts.get(key, 0) + 1
        if counts[key] <= MAX_PER_SOURCE:
            out.append(row)
    return out


def _normalize_rows(rows: list[LiveSms]) -> list[LiveSms]:
    out: list[LiveSms] = []
    for row in rows:
        cli = (row.cli or "").strip()
        if cli.lower() in {"unknown", "—"} or not cli:
            cli = extract_brand(row.text)
        if not cli or cli.lower() in {"unknown", "—"}:
            continue
        if cli == row.cli:
            out.append(row)
        else:
            out.append(
                LiveSms(
                    id=row.id,
                    country=row.country,
                    cli=cli,
                    text=row.text,
                    code=row.code,
                    time=row.time,
                    sort_key=row.sort_key,
                )
            )
    return out


def _translate_rows(rows: list[LiveSms]) -> list[LiveSms]:
    if not translate.enabled() or not rows:
        return rows
    texts = translate.translate_many([r.text for r in rows])
    out: list[LiveSms] = []
    for i, row in enumerate(rows):
        cli = row.cli
        if translate.needs_translation(cli):
            cli = translate.translate_one(cli)
        out.append(
            LiveSms(
                id=row.id,
                country=row.country,
                cli=cli,
                text=texts[i],
                code=row.code,
                time=row.time,
                sort_key=row.sort_key,
            )
        )
    return out


def _sort_rows(rows: list[LiveSms]) -> list[LiveSms]:
    def key(r: LiveSms):
        if r.sort_key.isdigit():
            return (0, -int(r.sort_key))
        return (1, r.time)

    return sorted(rows, key=key)


def fetch_live(*, force: bool = False) -> dict:
    global _CACHE, _CACHE_AT
    now = time.time()
    if not force and _CACHE is not None and (now - _CACHE_AT) < TTL:
        return _CACHE

    rows: list[LiveSms] = []
    source_stats: dict[str, int | str] = {}

    with ThreadPoolExecutor(max_workers=len(_FETCHERS)) as pool:
        futures = {pool.submit(fn): name for name, fn in _FETCHERS}
        for fut in as_completed(futures):
            name = futures[fut]
            try:
                got = fut.result()
                source_stats[name] = len(got)
                rows.extend(got)
            except Exception as e:
                source_stats[name] = f"err:{type(e).__name__}"

    rows = _normalize_rows(_sort_rows(_dedupe(rows)))
    rows = [r for r in rows if is_valid_sms_row(cli=r.cli, text=r.text)]
    rows = _cap_per_source(rows)[:MAX_ROWS]
    rows = _translate_rows(rows)
    payload = {
        "updated_at": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC"),
        "count": len(rows),
        "messages": [r.to_dict() for r in rows],
        "active_sources": len(_FETCHERS),
        "source_stats": source_stats,
        "translate": translate.enabled(),
    }
    _CACHE = payload
    _CACHE_AT = now
    return payload

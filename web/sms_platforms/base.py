"""Unified live SMS row (no platform name exposed to UI)."""

from __future__ import annotations

from dataclasses import asdict, dataclass


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
        return asdict(self)

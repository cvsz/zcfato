"""Pure subscription effective-tier rules; no Camfrog purchase or entitlement writes."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Protocol


class _Baseline(Protocol):
    base_tier: str
    base_term: str


class _Overlay(Protocol):
    tier: str
    starts_at: datetime
    expires_at: datetime


def utc_aware(value: datetime) -> datetime:
    """Normalize database timestamps to UTC for comparisons (SQLite can drop tzinfo)."""
    if value.tzinfo is None or value.utcoffset() is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def effective_subscription(
    baseline: _Baseline | None,
    overlays: list[_Overlay],
    *,
    now: datetime | None = None,
) -> tuple[str, str, _Overlay | None]:
    """Return the one active overlay, otherwise the durable baseline without inference."""
    now_utc = utc_aware(now or datetime.now(UTC))
    active = [
        overlay
        for overlay in overlays
        if utc_aware(overlay.starts_at) <= now_utc < utc_aware(overlay.expires_at)
    ]
    if len(active) > 1:
        return "unknown", "overlapping_overlays", None
    if active:
        return active[0].tier, "temporary_overlay", active[0]
    if baseline is None:
        return "unknown", "baseline_not_recorded", None
    if baseline.base_term == "unknown" or baseline.base_tier == "unknown":
        return "unknown", "baseline_unverified", None
    return baseline.base_tier, "durable_baseline", None

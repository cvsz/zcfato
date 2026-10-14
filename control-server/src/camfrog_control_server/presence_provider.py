"""Evidence-ranked, cache-aware presence normalization."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from .profile_provider import normalize_presence

PRESENCE_SOURCE_PRIORITY = (
    "profile",
    "friend_list",
    "public_profile",
    "status_image",
)


@dataclass(frozen=True, slots=True)
class PresenceObservation:
    state: str
    source: str
    observed_at: datetime


def resolve_presence(
    observations: list[PresenceObservation],
    *,
    now: datetime | None = None,
    max_age: timedelta = timedelta(minutes=10),
) -> PresenceObservation:
    """Choose the highest-priority fresh observation.

    Uncalibrated status images stay unknown.
    """
    current = now or datetime.now(UTC)
    priority = {source: index for index, source in enumerate(PRESENCE_SOURCE_PRIORITY)}
    candidates: list[PresenceObservation] = []
    for item in observations:
        state = normalize_presence(item.state)
        observed_at = item.observed_at
        if observed_at.tzinfo is None or observed_at.utcoffset() is None:
            observed_at = observed_at.replace(tzinfo=UTC)
        if item.source not in priority or state == "unknown":
            continue
        if current - observed_at > max_age or observed_at > current + timedelta(minutes=1):
            continue
        if item.source == "status_image":
            continue
        candidates.append(PresenceObservation(state, item.source, observed_at))
    if candidates:
        return min(candidates, key=lambda item: priority[item.source])
    latest = max(observations, key=lambda item: item.observed_at, default=None)
    return PresenceObservation(
        state="unknown",
        source="stale" if latest else "unknown",
        observed_at=latest.observed_at if latest else current,
    )

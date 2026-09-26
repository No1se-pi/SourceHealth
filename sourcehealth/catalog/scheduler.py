"""Pure adaptive refresh policy shared by workers and profile presentation."""

from datetime import UTC, datetime, timedelta

PREFERENCE_SECONDS = {"1h": 3600, "6h": 21600, "24h": 86400, "7d": 604800}
MINIMUM_INTERVAL_SECONDS = 3600


def adaptive_interval(last_activity_at: datetime | None, *, now: datetime | None = None) -> timedelta:
    now = now or datetime.now(UTC)
    if last_activity_at is None:
        return timedelta(hours=24)
    age = max(timedelta(0), now - last_activity_at)
    if age <= timedelta(days=1):
        return timedelta(hours=1)
    if age <= timedelta(days=7):
        return timedelta(hours=6)
    if age <= timedelta(days=30):
        return timedelta(hours=24)
    if age <= timedelta(days=180):
        return timedelta(hours=72)
    return timedelta(days=7)


def effective_interval(last_activity_at: datetime | None, preferences: list[str], *, now=None) -> timedelta:
    seconds = [int(adaptive_interval(last_activity_at, now=now).total_seconds())]
    seconds.extend(PREFERENCE_SECONDS[p] for p in preferences if p in PREFERENCE_SECONDS)
    return timedelta(seconds=max(MINIMUM_INTERVAL_SECONDS, min(seconds)))

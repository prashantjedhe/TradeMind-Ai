"""Pure helpers for evaluating price movement after a news signal."""

from dataclasses import dataclass
from datetime import datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

BAR_CLOSE_OFFSETS = {
    "15m": timedelta(minutes=15),
}
INDIA_TZ = ZoneInfo("Asia/Kolkata")


@dataclass(frozen=True)
class BarPoint:
    timestamp: datetime
    close: float


def _utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _bar_close_time(timestamp: datetime, interval: str) -> datetime:
    timestamp = _utc(timestamp)
    if interval == "1d":
        session_date = timestamp.astimezone(INDIA_TZ).date()
        session_close = datetime.combine(
            session_date,
            time(hour=15, minute=30),
            tzinfo=INDIA_TZ,
        )
        return session_close.astimezone(timezone.utc)
    return timestamp + BAR_CLOSE_OFFSETS[interval]


def find_forward_outcome(
    signal_timestamp: datetime,
    horizon_minutes: int,
    interval: str,
    bars: list[BarPoint],
    now: datetime,
) -> dict | None:
    """Use only bars fully closed at signal time and after the horizon."""
    signal_time = _utc(signal_timestamp)
    evaluation_time = _utc(now)
    source: tuple[datetime, float] | None = None
    target: tuple[datetime, float] | None = None
    target_after = signal_time + timedelta(minutes=horizon_minutes)

    for bar in bars:
        close_time = _bar_close_time(bar.timestamp, interval)
        if close_time <= signal_time and (source is None or close_time > source[0]):
            source = (close_time, bar.close)
        if close_time >= target_after and close_time <= evaluation_time:
            if target is None or close_time < target[0]:
                target = (close_time, bar.close)

    if source is None or target is None or source[1] <= 0:
        return None

    realized_return = target[1] / source[1] - 1.0
    return {
        "source_timestamp": source[0],
        "target_timestamp": target[0],
        "source_price": source[1],
        "target_price": target[1],
        "return_fraction": realized_return,
        "actual_horizon_minutes": round(
            (target[0] - signal_time).total_seconds() / 60
        ),
    }

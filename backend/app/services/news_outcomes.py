"""Forward-return evaluation for qualified, signed news-impact signals."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.news import NewsSignal, NewsSignalOutcome
from app.models.ohlcv import BarInterval, OHLCVBar
from app.services.news_outcome_math import BarPoint, find_forward_outcome

SIGNAL_WINDOW_MINUTES = 15
SIGNAL_LOOKBACK = timedelta(days=60)
BAR_LOOKBACK = timedelta(days=61)
HORIZONS = (
    (15, BarInterval.FIFTEEN_MIN),
    (60, BarInterval.FIFTEEN_MIN),
    (1440, BarInterval.ONE_DAY),
)


def _utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


async def record_due_outcomes(
    db: AsyncSession, now: datetime | None = None
) -> dict[str, int]:
    """Persist one first-qualified signal per ticker/hour and its closed-bar outcomes."""
    now = _utc(now or datetime.now(timezone.utc))
    cutoff = now - SIGNAL_LOOKBACK
    qualified = _qualified_signals(cutoff, now)
    signals = list((await db.execute(
        select(NewsSignal)
        .join(qualified, qualified.c.signal_id == NewsSignal.id)
        .where(qualified.c.hourly_rank == 1)
    )).scalars().all())
    if not signals:
        return {"signals_checked": 0, "outcomes_recorded": 0}

    existing = set((await db.execute(
        select(
            NewsSignalOutcome.signal_id,
            NewsSignalOutcome.horizon_minutes,
        )
        .join(NewsSignal, NewsSignal.id == NewsSignalOutcome.signal_id)
        .join(qualified, qualified.c.signal_id == NewsSignal.id)
        .where(qualified.c.hourly_rank == 1)
    )).all())

    ticker_bars: dict[tuple[str, BarInterval], list[BarPoint]] = {}
    for ticker in {signal.ticker for signal in signals}:
        for interval in (BarInterval.FIFTEEN_MIN, BarInterval.ONE_DAY):
            rows = (await db.execute(
                select(OHLCVBar.timestamp, OHLCVBar.close)
                .where(
                    OHLCVBar.ticker == ticker,
                    OHLCVBar.interval == interval,
                    OHLCVBar.timestamp >= now - BAR_LOOKBACK,
                    OHLCVBar.timestamp <= now,
                )
                .order_by(OHLCVBar.timestamp.asc())
            )).all()
            ticker_bars[(ticker, interval)] = [
                BarPoint(_utc(timestamp), float(close))
                for timestamp, close in rows
            ]

    outcomes: list[NewsSignalOutcome] = []
    for signal in signals:
        impact = float(signal.impact)
        direction = "UP" if impact > 0 else "DOWN"
        for horizon_minutes, interval in HORIZONS:
            if (signal.id, horizon_minutes) in existing:
                continue
            measured = find_forward_outcome(
                signal.timestamp,
                horizon_minutes,
                interval.value,
                ticker_bars[(signal.ticker, interval)],
                now,
            )
            if measured is None:
                continue
            realized_return = measured["return_fraction"]
            actual_direction = (
                "UP" if realized_return > 0
                else "DOWN" if realized_return < 0
                else None
            )
            outcomes.append(NewsSignalOutcome(
                signal_id=signal.id,
                horizon_minutes=horizon_minutes,
                forecast_direction=direction,
                signal_impact=Decimal(str(impact)),
                signal_band=signal.band,
                source_timestamp=measured["source_timestamp"],
                target_timestamp=measured["target_timestamp"],
                source_price=Decimal(str(measured["source_price"])),
                target_price=Decimal(str(measured["target_price"])),
                return_fraction=Decimal(str(realized_return)),
                directional_hit=(
                    direction == actual_direction
                    if actual_direction is not None else None
                ),
                actual_horizon_minutes=measured["actual_horizon_minutes"],
            ))

    if outcomes:
        db.add_all(outcomes)
        await db.commit()

    return {
        "signals_checked": len(signals),
        "outcomes_recorded": len(outcomes),
    }


def _qualified_signals(cutoff: datetime, now: datetime):
    hourly_rank = func.row_number().over(
        partition_by=(
            NewsSignal.ticker,
            func.date_trunc(
                "hour", func.timezone("UTC", NewsSignal.timestamp)
            ),
        ),
        order_by=NewsSignal.timestamp.asc(),
    ).label("hourly_rank")
    qualified = (
        select(NewsSignal.id.label("signal_id"), hourly_rank)
        .where(
            NewsSignal.window_minutes == SIGNAL_WINDOW_MINUTES,
            NewsSignal.article_count >= settings.NEWS_MIN_ARTICLES,
            func.abs(NewsSignal.impact) >= settings.NEWS_MED_THRESHOLD,
            NewsSignal.timestamp >= cutoff,
            NewsSignal.timestamp <= now,
        )
        .subquery()
    )
    return qualified


async def get_outcome_summary(
    db: AsyncSession,
    ticker: str | None,
    days: int,
    now: datetime | None = None,
) -> dict:
    """Summarize the medium/high impact cohort; returns are gross of costs."""
    now = _utc(now or datetime.now(timezone.utc))
    cutoff = now - timedelta(days=days)
    qualified = _qualified_signals(cutoff, now)
    stmt = (
        select(
            NewsSignal.ticker,
            NewsSignalOutcome.horizon_minutes,
            NewsSignalOutcome.forecast_direction,
            NewsSignalOutcome.return_fraction,
            NewsSignalOutcome.directional_hit,
            NewsSignalOutcome.actual_horizon_minutes,
        )
        .join(NewsSignal, NewsSignal.id == NewsSignalOutcome.signal_id)
        .where(
            NewsSignal.timestamp >= cutoff,
            NewsSignal.timestamp <= now,
            NewsSignalOutcome.signal_band.in_(("MEDIUM", "HIGH")),
        )
    )
    if ticker:
        stmt = stmt.where(NewsSignal.ticker == ticker.strip().upper())

    grouped: dict[int, list[tuple[str, float, bool | None, int]]] = {
        15: [], 60: [], 1440: [],
    }
    for _, horizon, direction, returned, hit, actual_minutes in (
        await db.execute(stmt)
    ).all():
        grouped[horizon].append(
            (direction, float(returned), hit, actual_minutes)
        )

    labels = {15: "15m", 60: "1h", 1440: "1d"}
    horizons = []
    for minutes, values in grouped.items():
        eligible_stmt = (
            select(func.count())
            .select_from(
                qualified.join(
                    NewsSignal, NewsSignal.id == qualified.c.signal_id
                )
            )
            .where(
                qualified.c.hourly_rank == 1,
                NewsSignal.timestamp <= now - timedelta(minutes=minutes),
            )
        )
        if ticker:
            eligible_stmt = eligible_stmt.where(
                NewsSignal.ticker == ticker.strip().upper()
            )
        eligible = int((await db.execute(eligible_stmt)).scalar_one())
        hit_values = [hit for _, _, hit, _ in values if hit is not None]
        aligned_returns = [
            returned * (1 if direction == "UP" else -1)
            for direction, returned, _, _ in values
        ]
        horizons.append({
            "horizon": labels[minutes],
            "horizon_minutes": minutes,
            "samples": len(values),
            "eligible_signals": eligible,
            "coverage_pct": (
                round(100 * len(values) / eligible, 2) if eligible else None
            ),
            "directional_samples": len(hit_values),
            "directional_accuracy_pct": (
                round(100 * sum(hit_values) / len(hit_values), 2)
                if hit_values else None
            ),
            "mean_aligned_return_pct": (
                round(100 * sum(aligned_returns) / len(aligned_returns), 4)
                if aligned_returns else None
            ),
            "mean_actual_horizon_minutes": (
                round(sum(item[3] for item in values) / len(values), 1)
                if values else None
            ),
        })
    return {
        "ticker": ticker.strip().upper() if ticker else None,
        "days": days,
        "signal_window": "15m",
        "qualification": (
            f"At least {settings.NEWS_MIN_ARTICLES} articles and MEDIUM/HIGH impact; "
            "first qualified signal per ticker per UTC hour."
        ),
        "method": (
            "Impact sign is the uncalibrated UP/DOWN baseline. Source uses the latest "
            "fully closed bar at signal time; target uses the first fully closed bar "
            "at or after the requested horizon."
        ),
        "costs_included": False,
        "horizons": horizons,
    }

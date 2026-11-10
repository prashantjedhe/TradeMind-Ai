"""
Celery application instance and beat schedule.

Design notes:
- Broker and result backend both use Redis (same instance as the
  price cache and JWT blacklist, different logical "databases" via
  the REDIS_URL - Celery manages its own key namespacing internally).
- Beat schedule entries defined here are picked up by the separate
  `celery_beat` process (see docker-compose.yml), NOT by the worker
  process itself. Worker executes tasks; beat only schedules them.
- Pending order checks run alongside each price refresh (15s), so
  triggers fire against fresh prices.
- OHLCV recent-bar sync runs every 15 minutes, deliberately much
  less frequent than the live price refresh - it fetches from
  yfinance across the full watchlist for two intervals each run
  (36 calls), and Yahoo Finance rate-limits aggressive request
  patterns (a real constraint solved earlier in this project for
  live price fetching too).
- League auto-finalization runs daily at midnight IST to close any
  leagues whose end_date has passed and compute final rankings/badges.
"""

from celery import Celery
from celery.schedules import schedule, crontab

from app.config import settings

celery_app = Celery(
    "trademind",
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL,
    include=[
        "app.workers.market_data",
        "app.workers.pending_orders",
        "app.workers.ohlcv_sync",
        "app.workers.strategy_evaluator",
        "app.workers.news_ingest",
        "app.workers.news_outcomes",
        "app.workers.league_reset",
    ],
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="Asia/Kolkata",
    enable_utc=True,
)

celery_app.conf.beat_schedule = {
    "refresh-market-prices": {
        "task": "app.workers.market_data.refresh_watchlist_prices",
        "schedule": schedule(run_every=15.0),  # every 15 seconds
    },
    "check-pending-orders": {
        "task": "app.workers.pending_orders.check_pending_orders",
        "schedule": schedule(run_every=15.0),  # every 15 seconds
    },
    "sync-ohlcv-bars": {
        "task": "app.workers.ohlcv_sync.sync_recent_bars",
        "schedule": schedule(run_every=900.0),  # every 15 minutes
    },
    "evaluate-active-strategies": {
        "task": "app.workers.strategy_evaluator.evaluate_active_strategies",
        "schedule": schedule(run_every=60.0),  # every 1 minute
    },
    "ingest-news": {
        "task": "app.workers.news_ingest.ingest_news",
        "schedule": schedule(run_every=300.0),  # every 5 minutes (free RSS)
    },
    "evaluate-news-outcomes": {
        "task": "app.workers.news_outcomes.evaluate_news_outcomes",
        "schedule": schedule(run_every=900.0),  # after recent OHLCV syncs
    },
    "auto-finalize-leagues": {
        "task": "app.workers.league_reset.auto_finalize_leagues",
        "schedule": crontab(hour=0, minute=0),  # daily at midnight IST
    },
}

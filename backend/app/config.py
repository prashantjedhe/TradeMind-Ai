from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    DATABASE_URL: str
    REDIS_URL: str
    SECRET_KEY: str
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    DEFAULT_VIRTUAL_BALANCE: float = 1000000.0

    # Fixed watchlist of liquid NSE stocks, kept warm in the Redis
    # price cache regardless of whether any user holds a position.
    # Chosen to cover every sector used in the Phase 6 News
    # Intelligence sector-weight table (BANK, IT, OIL, AUTO, FMCG,
    # METAL, PHARMA, REALTY).
    # Indices (Nifty 50 + Bank Nifty) are also included here;
    # their spot prices are fetched without the .NS suffix.
    WATCHLIST_TICKERS: list[str] = [
        "NIFTY", "BANKNIFTY",  # indices - special-handled by market_data
        "HDFCBANK", "ICICIBANK", "SBIN", "KOTAKBANK",   # BANK
        "TCS", "INFY", "WIPRO", "HCLTECH",              # IT
        "RELIANCE", "ONGC",                              # OIL
        "MARUTI", "TMPV",                                 # AUTO
        "HINDUNILVR", "ITC",                              # FMCG
        "TATASTEEL", "JSWSTEEL",                          # METAL
        "SUNPHARMA",                                      # PHARMA
        "DLF",                                            # REALTY
    ]

    # How long a cached price is considered fresh before order
    # execution should treat it as stale (safety net; Celery beat
    # refreshes prices well before this expires under normal operation).
    PRICE_CACHE_TTL_SECONDS: int = 30

    # ── News Intelligence (free RSS only, EN + HI) ──────────────
    # Google News RSS needs no API key. Ingest runs on its own beat
    # schedule; signals are cached in Redis with a TTL safety net,
    # same pattern as the price cache above.
    NEWS_ENABLED: bool = True
    NEWS_FETCH_INTERVAL_SECONDS: int = 300  # Celery beat: every 5 min
    NEWS_WINDOWS_MINUTES: list[int] = [15, 60, 1440]
    NEWS_MIN_ARTICLES: int = 3  # fire gate: ignore single-rumor spikes
    NEWS_HALF_LIFE_HOURS: float = 6.0  # recency decay half-life
    NEWS_SIGNAL_TTL_SECONDS: int = 600
    NEWS_MAX_ITEMS_PER_FEED: int = 20
    NEWS_LOOKBACK_DAYS: int = 7  # z-score baseline window
    NEWS_USER_AGENT: str = "Mozilla/5.0 (TradeMindAI paper-trading research bot)"

    # ── News Impact Engine (corrections baked in) ────────────────
    # impact = polarity × (W_SECTOR·sector + W_SOURCE·source + W_REC·recency)
    # polarity is SIGNED (+conf POS / -conf NEG / P(pos)-P(neg) NEU).
    # Thresholds are env-tunable defaults; recalibrate by percentile
    # from the news_signals log (HIGH ≈ 95th pct of |impact|).
    NEWS_HIGH_THRESHOLD: float = 0.70
    NEWS_MED_THRESHOLD: float = 0.40
    NEWS_W_SECTOR: float = 0.4
    NEWS_W_SOURCE: float = 0.3
    NEWS_W_RECENCY: float = 0.3
    NEWS_RECENCY_HALF_LIFE_MIN: float = 120.0  # recency = max(0.1, 1 - age/half_life)
    NEWS_RECENCY_FLOOR: float = 0.1
    NEWS_IMPACT_MAX_AGE_MIN: int = 360  # articles older than this never score
    # Sector priors v1 (tunable; refit quarterly from spike→move correlation).
    NEWS_SECTOR_WEIGHTS: dict = {
        "BANK": 0.95, "IT": 0.90, "OIL": 0.88, "AUTO": 0.82,
        "FMCG": 0.80, "METAL": 0.78, "PHARMA": 0.75, "REALTY": 0.65,
        "INDEX": 1.00, "UNKNOWN": 0.60, "ALL": 1.00,
    }
    # Source credibility priors v1 (matched case-insensitively, substring).
    NEWS_SOURCE_WEIGHTS: dict = {
        "reuters": 0.95, "bloomberg": 0.95, "economictimes": 0.90,
        "moneycontrol": 0.88, "livemint": 0.85, "business-standard": 0.85,
        "ndtv": 0.82, "cnbc": 0.85, "zerodha": 0.80, "screener": 0.75,
    }
    NEWS_SOURCE_DEFAULT_WEIGHT: float = 0.50
    # Action engine: cooldown per (strategy, action) + auto-restore.
    NEWS_ACTION_COOLDOWN_MIN: int = 60
    NEWS_MULTIPLIER_RESTORE_MIN: int = 120
    NEWS_RESUME_CALM_CYCLES: int = 2  # resume after N calm cycles OR timeout
    NEWS_MED_REDUCTION: float = 0.3  # MEDIUM lot reduction factor scale
    NEWS_DEFAULT_SL_PCT: float = 0.02  # base SL distance when none exists
    # FinBERT (EN only). Lazy singleton per worker process; lexicon
    # covers HI + fallback when the model is unavailable.
    NEWS_FINBERT_ID: str = "ProsusAI/finbert"
    NEWS_FINBERT_MAX_TOKENS: int = 512
    NEWS_FINBERT_TIMEOUT_S: float = 30.0
    NEWS_FINBERT_MAX_PER_CYCLE: int = 120  # rest of cycle falls back to lexicon
    # Claude advisor (advisory-only, on-demand, fail-soft when unset).
    ANTHROPIC_API_KEY: str = ""
    ANTHROPIC_MODEL: str = "claude-sonnet-4-20250514"  # confirm ID in console
    ANTHROPIC_MAX_TOKENS: int = 1000
    ANTHROPIC_TIMEOUT_S: float = 45.0

    # Free-tier fallback: OpenRouter-compatible API for model access without
    # requiring a paid Anthropic subscription. Often available with a free key.
    OPENROUTER_API_KEY: str = ""
    OPENROUTER_MODEL: str = "meta-llama/llama-3.1-8b-instruct:free"
    OPENROUTER_TIMEOUT_S: float = 45.0
    OPENROUTER_BASE_URL: str = "https://openrouter.ai/api/v1/chat/completions"

    class Config:
        env_file = ".env"


settings = Settings()
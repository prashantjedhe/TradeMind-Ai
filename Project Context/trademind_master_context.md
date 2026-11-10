═══════════════════════════════════════════════════════════════
TRADEMIND AI — MASTER PROJECT CONTEXT DOCUMENT
B.Tech Capstone Project | Data Science Engineering
G H Raisoni College of Engineering and Management
Session: 2025–2026 | Team: 4 members
═══════════════════════════════════════════════════════════════

PROJECT CONTEXT FILES (Project Context/):
  trademind_master_context.md  — This file. Full project reference.
  trademind_roadmap.md         — 16-week build plan (Markdown).
  trademind_16week_roadmap.html — 16-week build plan (visual HTML).
  trademind_app_flow.md        — Navigation, features, user journeys.

You are my dedicated AI assistant for building TradeMind AI —
my B.Tech final year capstone project. You know the complete
architecture, all decisions, all code, and all phases from the
very beginning. Never ask me to re-explain the project. Always
continue from where we left off.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
1. PROJECT IDENTITY
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Project Name      : TradeMind AI
Full Title        : AI-Powered Event-Driven Paper Trading Platform
Department        : Data Science Engineering
Student           : Prashant (username: prashant5214)
OS / Machine      : Windows 11 + WSL2 Ubuntu (Lenovo laptop)
Current Status    : Phase 7 COMPLETE — Phase 8 (Testing, Polish & Deployment) IN PROGRESS

Core Innovation   : A News Intelligence Engine that detects
                    financial news in near real-time, runs FinBERT
                    sentiment analysis, scores market impact, and
                    actively interacts with live paper trading
                    portfolios — pausing, modifying, or triggering
                    trades automatically.

Inspired by       : Mirror Pip, Algorooms
Target users      : B.Tech students, beginner algo traders,
                    quant researchers
No real money     : Paper trading only. Virtual balance only.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
2. COMPLETE TECH STACK
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Backend           : Python 3.11 + FastAPI + Pydantic v2
Async ORM         : SQLAlchemy 2.0 async + asyncpg
Migrations        : Alembic
Task Queue        : Celery + Redis (broker + backend)
Frontend          : React 19 + Vite + Tailwind CSS v4 (via @tailwindcss/vite plugin)
State Management  : Zustand
HTTP Client       : Axios with interceptors (auto-refresh, request queuing)
Database          : PostgreSQL 16
Cache             : Redis 7
Containerization  : Docker + Docker Compose (6 services)
Reverse Proxy     : Nginx (production, not yet wired)
CI/CD             : GitHub Actions (not yet wired)
Deployment        : Render (backend) + Vercel (frontend) (not yet wired)

AI / NLP Stack:
  Sentiment       : ProsusAI/finbert (HuggingFace, EN only, 110M params)
  Sentiment (HI)  : Bilingual lexicon (Devanagari + transliterated Hindi)
  Keywords        : rake-nltk (RAKE algorithm, EN only)
  Sector mapping  : Custom Python expert-system (63 tickers, 180+ keywords)
  LLM Advisor     : Claude API (claude-sonnet-4-20250514, advisory-only, fail-soft)
  AI Journal      : Claude API (claude-sonnet-4-20250514, on-demand)

Market Data       : yFinance 1.5.1 (NSE suffix .NS, 20-ticker watchlist)
News Sources      : Google News RSS (free, no API key, EN + HI feeds)
Auth              : JWT (access 30min + refresh 7 days)
                    Redis blacklist for token rotation
                    HTTPBearer (not OAuth2PasswordBearer)

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
3. ALL 10 FEATURES
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

CORE FEATURES:
F1. Paper Trading Engine ✅ COMPLETE
    - Simulated NSE order execution (MARKET, LIMIT, SL, TP)
    - Slippage model: 0.05% per trade
    - Real NSE fee model: STT, stamp duty, exchange charges, SEBI, GST, DP
    - Position tracker: signed qty (long/short), FIFO close, avg price
    - Virtual balance: ₹10,00,000 per user
    - Transaction history and order book
    - Celery auto-trigger: PENDING orders fill against live cached prices

F2. News Intelligence Engine ✅ COMPLETE
    - Google News RSS fetch (EN+HI, 40 feeds, every 5 min)
    - RAKE keyword extraction (EN only, <5ms/article)
    - FinBERT sentiment (EN) + bilingual lexicon (HI/transliterated)
    - FinBERT signed expected polarity: P(pos)-P(neg); winning-class confidence kept separate
    - Lexicon score uses smoothing to avoid saturating from a few positive/negative terms
    - Expert-system sector mapper: 63 tickers → 9 sectors
    - Attenuating impact formula: signed polarity × sector relevance × source credibility × recency
    - Recent legacy headlines are re-scored once after scorer version changes
    - Impact bands: HIGH (≥0.70), MEDIUM (≥0.40), LOW (<0.40)
    - Action engine: pause/resume, tighten SL, reduce lot size, exit-on-news
    - Decay-weighted aggregation + z-score vs 7-day baseline

F3. Visual Strategy Builder ✅ COMPLETE
    - Condition tree: AND/OR nested JSON + 21 templates (18 classic + 3 news)
    - Indicators: RSI, EMA, SMA, MACD, Volume, Price, Sentiment
    - Visual builder UI (builder on top, templates below)
    - Celery evaluator (60s, edge-triggered, auto-fires trades)
    - Strategy prompt feature: key→tree+action library
    - quantity_multiplier scales fired order qty
    - Multi-leg options foundation: time/indicator strategy types,
      Spot/Future reference, MIS/CNC/BTST, schedules, weekday masks,
      repeatable CE/PE legs, expiry/strike criteria, lot sizing,
      risk controls, and advanced execution flags

F4. F&O (Futures & Options) Module ✅ COMPLETE
    - Black-Scholes pricing + Greeks (Δ/Γ/Θ/Vega)
    - Synthetic IV smile, futures carry basis
    - NSE last-Thursday expiry calendar
    - 6 equity underlyings + NIFTY/BANKNIFTY indices
    - 384+ F&O contracts priced/15s, option chain API
    - Strategy evaluation resolves F&O→underlying for OHLCV bars
    - F&O STT rates in fee calculator

F5.  Copy Trading Module — REMOVED (design decision: replaced by League system)
F6. User Auth and Profiles ✅ COMPLETE
    - Signup, login, JWT refresh rotation
    - Redis blacklist for logout (jti-based)
    - bcrypt password hashing (pinned 4.0.1)
    - Profile page with virtual balance display

NEW FEATURES:
F7. Walk-Forward Backtesting ✅ COMPLETE (Phase 5)
    - Per-strategy and unsaved-draft backtest modal
    - Historical replay with equity curve, P/L, fees, slippage, and metrics
    - Walk-forward analysis with IS/OOS Sharpe, ER, and window results
F8. LLM-Powered Strategy Advisor ✅ COMPLETE
    - Claude API on-demand strategy review
    - Advisory-only, never touches execution
    - Fail-soft when API key unset
    - Persists to trade_journal table

F9. AI-Generated Trade Journal ✅ COMPLETE
    - On-demand journal generation from recent trades
    - Pattern detection: win rate by day/ticker/time
    - Joins with news events table
    - Claude API generates structured analysis

F10. Paper Trading League / Competition ✅ COMPLETE (Phase 7)

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
4. COMPLETE FOLDER STRUCTURE
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

trademind-ai/
├── backend/
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py               # FastAPI app factory, CORS, lifespan
│   │   ├── config.py             # pydantic-settings, all env vars
│   │   ├── database.py           # async SQLAlchemy engine + get_db
│   │   ├── api/
│   │   │   ├── __init__.py
│   │   │   ├── deps.py           # get_current_user, get_redis, DbSession
│   │   │   └── v1/
│   │   │       ├── __init__.py
│   │   │       ├── auth.py       # signup, login, refresh, logout, /me
│   │   │       ├── users.py      # GET /users/me
│   │   │       ├── orders.py     # POST/GET /orders/, POST /orders/exit-on-news, /manual-exit
│   │   │       ├── portfolio.py  # /portfolio/summary, /history
│   │   │       ├── market.py     # /watchlist, /prices, /fno/chain, /fno/quote
│   │   │       ├── strategies.py # CRUD strategies, templates
│   │   │       └── news.py       # News signals, explainability, outcomes, alerts, advisor
│   │   ├── models/
│   │   │   ├── __init__.py       # imports all models for Alembic
│   │   │   ├── user.py           # UUID PK, email, username, balance
│   │   │   ├── order.py          # TriggeredBy enum, triggered_by FK
│   │   │   ├── portfolio.py      # Position with signed qty
│   │   │   ├── strategy.py       # single-action + multi-leg option configuration
│   │   │   ├── news.py           # NewsArticle, NewsSentiment, NewsSignal + outcomes
│   │   │   ├── ohlcv.py          # OHLCVBar (ticker+interval+ts unique)
│   │   │   └── trade_journal.py  # TradeJournal for advisor output
│   │   ├── schemas/
│   │   │   ├── auth.py
│   │   │   ├── order.py
│   │   │   └── strategy.py       # conditions, ActionSchema, OptionLeg, RiskControls
│   │   ├── services/
│   │   │   ├── auth_service.py
│   │   │   ├── order_service.py  # get_price_or_derive() F&O fallback
│   │   │   ├── portfolio_service.py
│   │   │   ├── position_service.py
│   │   │   ├── strategy_service.py # CRUD, evaluator, fire_action, multiplier
│   │   │   ├── strategy_templates.py # 21 templates
│   │   │   ├── fee_calculator.py  # NSE + F&O fee model
│   │   │   ├── rate_limiter.py
│   │   │   ├── price_cache_service.py
│   │   │   ├── ohlcv_service.py
│   │   │   ├── fn_o_service.py   # Black-Scholes, Greeks, futures, expiry, symbols
│   │   │   ├── advisor.py        # Claude advisor + journal (stdlib HTTP)
│   │   │   ├── news_universe.py  # 20-ticker EN+HI alias map
│   │   │   ├── news_sentiment.py # FinBERT singleton + lexicon hybrid
│   │   │   ├── news_keywords.py  # RAKE extraction + finance tags
│   │   │   ├── news_sector.py    # Sector mapper (63 tickers, 180+ keywords)
│   │   │   ├── news_impact.py    # Multiplicative attenuation + bands
│   │   │   ├── news_ingest.py    # RSS fetch + dedupe + scoring
│   │   │   ├── news_signal_service.py # Aggregation + z-score + impact
│   │   │   ├── news_outcomes.py  # Closed-bar forward-return baseline evaluation
│   │   │   └── news_actions.py   # Pause/resume, SL tighten, exit-on-news
│   │   ├── workers/
│   │   │   ├── celery_app.py     # Beat: prices 15s, pending 15s, strategy 60s, news 5min, OHLCV 15min, league daily
│   │   │   ├── market_data.py    # Price cache + F&O derivation + Redis aclose
│   │   │   ├── pending_orders.py # Auto-trigger PENDING orders
│   │   │   ├── ohlcv_sync.py     # OHLCV bar sync
│   │   │   ├── strategy_evaluator.py # Edge-triggered eval
│   │   │   ├── news_ingest.py    # Celery news ingest+score+action
│   │   │   ├── news_outcomes.py  # Periodic outcome persistence
│   │   │   └── league_reset.py   # Daily auto-finalize expired leagues
│   │   └── utils/
│   │       ├── indicators.py     # RSI, EMA, SMA, MACD, VOLUME, PRICE, SENTIMENT
│   │       └── market_data.py    # yFinance client, NIFTY→^NSEI mapping
│   ├── migrations/
│   │   └── versions/             # strategy, news, multi-leg, and backtest migrations
│   ├── alembic.ini
│   ├── requirements.txt          # torch 2.4.1 CPU, transformers 4.44.2, rake-nltk
│   ├── Dockerfile                # Python 3.11-slim, FinBERT baked at /opt/hf_cache
│   ├── .dockerignore             # Excludes __pycache__, .hf_cache, celerybeat-schedule
│   └── .env
│
├── frontend/
│   ├── src/
│   │   ├── main.jsx
│   │   ├── App.jsx               # Routes: /login, /register, /dashboard, /trading, /fno, /strategies, /news, /profile
│   │   ├── index.css             # Tailwind directives, dark theme
│   │   ├── api/
│   │   │   ├── axiosClient.js    # base Axios + auto-refresh interceptor
│   │   │   ├── authApi.js
│   │   │   ├── orderApi.js
│   │   │   ├── strategyApi.js    # + templates API
│   │   │   ├── newsApi.js        # News signals, alerts, advisor, journal, exitOnNews
│   │   │   └── marketApi.js      # F&O chain, universe, expiries, quote
│   │   ├── components/
│   │   │   ├── common/           # Button, Modal, Navbar, ProtectedRoute
│   │   │   └── strategy/         # ConditionRow.jsx (SENTIMENT indicator support)
│   │   ├── pages/
│   │   │   ├── LoginPage.jsx
│   │   │   ├── RegisterPage.jsx
│   │   │   ├── DashboardPage.jsx
│   │   │   ├── TradingPage.jsx   # Manual and news exit actions per position
│   │   │   ├── FOPage.jsx        # Option chain + futures + trade ticket
│   │   │   ├── StrategyBuilderPage.jsx # Builder, templates, backtest, multi-leg options
│   │   │   ├── NewsPage.jsx      # Impact bands, alerts, headlines, advisor, journal
│   │   │   └── ProfilePage.jsx
│   │   └── store/
│   │       └── authStore.js      # Zustand + persist to localStorage
│   ├── index.html
│   ├── vite.config.js
│   ├── tailwind.config.js
│   ├── postcss.config.js
│   ├── package.json
│   └── Dockerfile
│
├── docker-compose.yml            # 6 services: db, redis, backend, celery_worker, celery_beat, frontend
├── .gitignore
├── docs/
└── nginx/
    └── nginx.conf

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
5. DOCKER COMPOSE SERVICES
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Service           : db (postgres:16-alpine)
                    User: trademind | Pass: trademind_secret
                    DB: trademind_db | Port: 5432

Service           : redis (redis:7-alpine)
                    Port: 6379

Service           : backend (FastAPI)
                    Port: 8000
                    Command: uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
                    depends_on: db (healthy) + redis (healthy)

Service           : celery_worker
                    Same image as backend
                    Command: celery -A app.workers.celery_app worker --loglevel=info --concurrency=2
                    depends_on: backend + redis
                    NOTE: --concurrency=2 required (FinBERT ~1.5GB/process)

Service           : celery_beat
                    Same image as backend
                    Command: celery -A app.workers.celery_app beat --loglevel=info
                    depends_on: backend + redis

Service           : frontend (React/Vite)
                    Port: 5173
                    Command: npm run build && npm run preview -- --host 0.0.0.0 --port 5173
                    (Static production build, NOT dev server)

Volume            : postgres_data (persistent DB storage)

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
6. ENVIRONMENT VARIABLES (.env)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

DATABASE_URL=postgresql+asyncpg://trademind:trademind_secret@db:5432/trademind_db
REDIS_URL=redis://redis:6379/0
SECRET_KEY=replace-with-a-random-secret-at-least-32-characters-long
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30
REFRESH_TOKEN_EXPIRE_DAYS=7
DEFAULT_VIRTUAL_BALANCE=1000000.0

# News Intelligence
NEWS_ENABLED=true
NEWS_FETCH_INTERVAL_SECONDS=300
NEWS_WINDOWS_MINUTES=[15,60,1440]
NEWS_MIN_ARTICLES=3
NEWS_HALF_LIFE_HOURS=6.0
NEWS_HIGH_THRESHOLD=0.70
NEWS_MED_THRESHOLD=0.40
NEWS_RECENCY_HALF_LIFE_MIN=120.0
NEWS_FINBERT_ID=ProsusAI/finbert

# Claude Advisor (optional, fail-soft)
ANTHROPIC_API_KEY=
ANTHROPIC_MODEL=claude-sonnet-4-20250514

Note: 'db' and 'redis' are Docker service hostnames, not localhost.
Frontend must use http://127.0.0.1:5173 (NOT localhost — IPv6 issue).

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
7. NEWS INTELLIGENCE — MODELS AND PARAMETERS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

MODEL 1 — FinBERT (EN only):
  HuggingFace ID  : ProsusAI/finbert
  Architecture    : BERT-base (Google) fine-tuned on financial text
  Parameters      : 110 million
  Layers          : 12 transformer encoder layers
  Hidden size     : 768 dimensions
  Max tokens      : 512
  Output          : positive / negative / neutral + confidence 0-1
  Accuracy        : 86.1% on Financial PhraseBank
  RAM             : ~1.5GB float32
  Load strategy   : Lazy singleton per worker process (NOT inside task)
  Budget guard    : Max 120 inferences/cycle, rest fall back to lexicon
  Docker bake     : /opt/hf_cache (NOT /app/.hf_cache — hidden by bind mount)
  Concurrency     : --concurrency=2 on celery worker (default OOMs Docker VM)

MODEL 2 — Bilingual Lexicon (HI + fallback):
  Type            : Dictionary-based sentiment scorer
  Coverage        : Devanagari Hindi + transliterated Hindi + English finance terms
  Signed polarity : P(positive) − P(negative); confidence is separate
  Speed           : <1ms per article
  Used for        : All non-English text + FinBERT budget overflow

MODEL 3 — RAKE (EN only):
  Library         : rake-nltk
  Type            : Statistical algorithm (NOT machine learning)
  Parameters      : min_length=1, max_length=4, top_n=15
  Speed           : <5ms per article
  NLTK data       : punkt, punkt_tab, stopwords (baked in Docker image)

MODEL 4 — Sector Mapper:
  Type            : Python expert system (NOT ML)
  Coverage        : 180+ financial keywords → 9 NIFTY sectors
  Tickers         : 63 NSE stocks mapped
  Sectors         : BANK, IT, OIL, AUTO, FMCG, METAL, PHARMA, REALTY, INDEX

MODEL 5 — Claude API:
  Model           : claude-sonnet-4-20250514
  Used for        : Strategy Advisor + AI Trade Journal
  max_tokens      : 1000 per response
  Input           : Structured trade/backtest data as JSON context
  Implementation  : stdlib HTTP (no SDK dependency)
  Fail mode       : Advisory-only, returns error message when key unset

IMPACT SCORE FORMULA (attenuating factors):
  impact = signed_polarity × sector_weight × source_weight × recency

  FinBERT polarity: P(positive) − P(negative); winning-class probability
                    is retained separately as confidence (not sentiment).
  Lexicon polarity: signed lexicon score in [-1, +1].
  sector_weight   : BANK=0.95, IT=0.90, OIL=0.88, AUTO=0.82,
                    FMCG=0.80, METAL=0.78, PHARMA=0.75, REALTY=0.65,
                    INDEX=1.00, UNKNOWN=0.60
  source_weight   : reuters=0.95, bloomberg=0.95, economictimes=0.90,
                    moneycontrol=0.88, livemint=0.85, ndtv=0.82,
                    cnbc=0.85, default=0.50
  recency         : max(0.1, 1.0 − (age_minutes / 120))

  Sector, source credibility, and recency attenuate sentiment and never
  inflate it. Publisher matching normalizes spaces/punctuation.
  Thresholds remain configurable; evaluate them against time-ordered
  labeled outcomes before treating impact bands as predictive.

NEWS OUTCOME EVALUATION (research-only):
  GET /api/v1/news/evaluation?ticker=...&days=30 reports 15m, 1h, and
  1d realized outcomes for qualified MEDIUM/HIGH 15m signal snapshots.
  The first qualified observation per ticker per UTC hour is recorded.
  Only fully closed bars at or after the requested forward horizon are
  used; accuracy is not a probability forecast and gross aligned returns
  exclude fees/slippage. This evaluator never places or changes orders.
  Per-headline responses include impact factors, event tags, keywords,
  and a plain-language rationale.

THRESHOLDS (env-tunable):
  HIGH   : score ≥ 0.70
  MEDIUM : score ≥ 0.40
  LOW    : score < 0.40

  Recalibrate by percentile from news_signals log
  (HIGH ≈ 95th percentile of |impact|).

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
8. TRADE ACTION ENGINE — ALL PARAMETERS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

HIGH IMPACT (score ≥ 0.70):
  Action 1 — Pause Strategy
    DB: strategy.status = "PAUSED"
    DB: strategy.paused_reason = news headline (truncated)
    DB: strategy.news_event_id = FK to news_signals table
    Effect: Celery evaluator skips — no new orders fire
    Position: stays open, unchanged
    Resume: after 2 calm cycles OR 120min timeout
    Resume clears: paused_reason, news_event_id, restores multiplier

  Action 2 — Cut Position (USER triggered only, never auto)
    Fetch LTP from Redis cache (F&O: get_price_or_derive fallback)
    Apply slippage: execution_price = ltp × (1 - 0.0005)
    Create paper SELL order with triggered_by = 'NEWS_EVENT'
    Update position.status = 'CLOSED'
    Calculate pnl = (exit - entry) × qty
    Restore user.virtual_balance
    Endpoint: POST /api/v1/orders/exit-on-news

  Action 3 — Tighten Stop Loss (auto on HIGH)
    Only tightens PENDING SL orders (stop_loss_price column is a no-op)
    new_distance = current_distance × (1 - (impact_score × 0.5))
    new_trigger = min(current_price, current_trigger + new_distance)
    Only moves trigger closer, never loosens
    Short positions: trigger moved higher
    DB: UPDATE orders SET trigger_price = new_trigger,
        updated_reason = 'AUTO_TIGHTEN_NEWS'
    Cooldown: 60 min per (strategy, action) pair

  Action 4 — Reduce Lot Size (for next order)
    reduction = impact_score × 0.6
    new_multiplier = 1.0 - reduction
    DB: strategy.quantity_multiplier = new_multiplier
    actual_qty = base_quantity × new_multiplier
    Auto-restore: after 120 min → multiplier = 1.0
    Also restored on resume + manual re-activation

MEDIUM IMPACT (0.40 ≤ score < 0.70):
  - In-app alert only
  - Lot size reduction (NEWS_MED_REDUCTION = 0.3)
  - Strategy keeps running
  - SL unchanged

LOW IMPACT (score < 0.40):
  - Log to news feed only
  - No trade action whatsoever

SINGLE-RUMOR GATE:
  - If fewer than NEWS_MIN_ARTICLES (3) articles match the ticker,
    skip all actions (ignores single-rumor spikes)

COOLDOWNS:
  - Redis NX key: news_action:{strategy_id}:{action} TTL 60 min
  - Prevents flapping (re-pause on same signal)
  - Timer can be backdated for testing

SLIPPAGE MODEL:
  slippage_rate : 0.0005 (0.05%)
  brokerage     : 0.001  (0.10%) — per fee_calculator.py
  stt           : 0.001  (0.10%)
  effective_cost = price × (1 + slippage + brokerage + stt)

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
9. F&O MODULE — PRICING AND CONTRACTS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Purpose           : Derive realistic F&O instruments from equity spot
Pricing Model     : Black-Scholes for options, spot × (1 + carry) for futures
Greeks            : Delta, Gamma, Theta, Vega (computed per contract)
IV Surface        : Synthetic (base IV + moneyness smile + time decay)
Futures Carry     : 8% annualised (funding + dividends), decays toward expiry

Contract Encoding : {UNDERLYING}{DDMMM}{STRIKE}{CE|PE}
                    e.g. RELIANCE24AUG2800CE, ICICIBANK24AUGFUT
                    Fits Order.ticker String(20) column

Underlyings       : RELIANCE, INFY, HDFCBANK, ICICIBANK, TCS, SBIN
                    + NIFTY (index), BANKNIFTY (index)

Contract Specs    : RELIANCE(250 lot), INFY(400 lot), HDFCBANK(550 lot),
                    ICICIBANK(700 lot), TCS(175 lot), SBIN(3000 lot),
                    NIFTY(50 lot), BANKNIFTY(15 lot)

Pricing Cache     : 384+ contracts priced every 15s via market_data worker
API Endpoints     : /fno/universe, /fno/expiries, /fno/chain, /fno/quote

Strategy Eval     : F&O ticker → underlying_of() → load OHLCV bars
                    → evaluate conditions → fire order on F&O ticker

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
10. CELERY BEAT SCHEDULE
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

refresh-market-prices      : every 15 seconds (NSE + F&O derivation)
check-pending-orders       : every 15 seconds (auto-trigger fills)
sync-ohlcv-bars            : every 15 minutes (recent bar sync)
evaluate-active-strategies : every 1 minute (edge-triggered)
ingest-news                : every 5 minutes (RSS + score + action)

All workers use asyncio.run() per invocation.
Each must dispose engine + redis_client.aclose() in finally block
(prevents InterfaceError: another operation is in progress).

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
11. BACKTESTING + WALK-FORWARD (COMPLETE — Phase 5)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Purpose           : Prevent strategy overfitting to historical data
Train window      : 3 years rolling
Test window       : 1 year out-of-sample
Efficiency Ratio  : OOS Sharpe ÷ IS Sharpe
Good ratio        : ER > 0.7 (strategy generalizes well)
Standard metrics  : CAGR, Sharpe Ratio, Max Drawdown, Win Rate
Library           : Pandas + NumPy (custom implementation)
UI                 : Per-strategy and draft backtest modal with equity curve,
                     P/L, historical range, and walk-forward results
API endpoint      : POST /api/v1/backtest/walk-forward

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
12. PHASE STATUS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

PHASE 1 — ✅ COMPLETE (Weeks 1–2)
  Auth + Dashboard
  Docker Compose, JWT auth, Redis blacklist, React login/register,
  protected routes, Zustand state, Tailwind dark theme, auto-refresh interceptor

PHASE 2 — ✅ COMPLETE (Weeks 3–4)
  Paper Trading Engine
  yFinance live prices, 20-ticker watchlist, MARKET/LIMIT/SL/TP orders,
  NSE fee model, signed positions, FIFO close, 48,286 OHLCV bars backfilled,
  Celery auto-trigger for PENDING orders, rate limiting

PHASE 3 — ✅ COMPLETE (Week 5)
  Strategy Builder + F&O Module
  AND/OR condition tree, 6 indicators + SENTIMENT, 21 templates,
  visual builder UI, Celery evaluator (60s), auto-fires trades.
  F&O: Black-Scholes + Greeks, 384+ contracts, option chain API,
  strategy evaluation resolves F&O→underlying for OHLCV.

PHASE 4 — ✅ COMPLETE (Weeks 6–7)
  News Intelligence (FinBERT + Action Engine + Advisor)
  FinBERT singleton (EN) + bilingual lexicon (HI), RAKE keywords,
  sector mapper (63 tickers), attenuating impact formula,
  action engine (pause/resume, SL tighten, lot multiplier, exit-on-news),
  Claude advisor + trade journal, z-score aggregation,
  Docker image with FinBERT baked at /opt/hf_cache.
  Verified end-to-end: scoring, impact, actions, resume, exit.

PHASE 5 — ✅ COMPLETE (Weeks 8–9)
  Backtesting + Walk-Forward
  Standard backtest engine, walk-forward with Efficiency Ratio,
  per-strategy/draft backtest UI with equity curve + WFO results.
  Backtest result schema synchronized with the current ORM model.

PHASE 6 — REMOVED
  Copy Trading was removed from scope and replaced by the League milestone.

PHASE 7 — ✅ COMPLETE (Weeks 10–12)
  League & Competition Mode  [Copy Trading REMOVED — replaced by League system]
  League model: Competition, LeagueEntry, Badge (6 badge types)
  Real metrics from orders (Sharpe, return, drawdown, win rate, P&L)
  Celery beat daily league auto-finalization (midnight IST)
  Sharpe-ranked leaderboard with usernames
  Badge awards: Top Trader, Drawdown Master, Consistent Performer, News Ninja, First Win
  LeaguePage.jsx: full UI with tabs (All Leagues, My Entries, Create), badge showcase

PHASE 8 — 🔄 IN PROGRESS (Weeks 13–16)
  Testing, Polish & Deployment
  ORM registry and migration parity checks pass; FinBERT inference is verified.
  Backend suite is passing, but measured coverage is currently below the 70% target.
  Remaining: broaden service/API coverage, authenticated dashboard/mobile review,
  Locust load test, security hardening, CI/CD, Render + Vercel deploy,
  README, API docs, academic report, presentation, demo video.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
13. KEY ARCHITECTURAL DECISIONS (with reasons)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

WHY FastAPI not Django:
  Async support for WebSockets + Celery integration.
  Auto Swagger docs. Pydantic v2 validation built-in.

WHY UUID not integer PKs:
  Never expose sequential IDs to frontend. Security best practice.

WHY Redis blacklist for JWT:
  True stateless logout. jti-based so individual tokens revocable.
  TTL auto-cleans expired entries. No DB query per request.

WHY FinBERT not GPT for news:
  Runs locally → no API cost, no rate limits.
  Trained specifically on financial text → 86% vs 67% accuracy.
  Load once as singleton → 50ms inference per article.

WHY bilingual lexicon for HI:
  FinBERT only handles English. Hindi financial news needs coverage.
  Dictionary-based scorer is fast (<1ms) and free.

WHY attenuating impact factors:
  A weighted average of sector/source/recency was close to 1 for most
  fresh headlines, so weak sourcing or relevance did not reduce a score.
  Impact now multiplies signed polarity by sector, source, and recency
  factors. These are priors, not empirically calibrated probabilities;
  accuracy still requires labeled, chronological evaluation.

WHY Claude API for Advisor + Journal:
  Strategy advisor needs reasoning, not just classification.
  Journal needs narrative generation. Claude excels at both.
  No GPU needed. Advisory-only, fail-soft when key unset.

WHY Celery not FastAPI BackgroundTasks:
  BackgroundTasks die if server restarts.
  Celery persists tasks in Redis, retries on failure.
  Celery beat handles cron scheduling.

WHY yFinance not only Alpha Vantage:
  yFinance is free, unlimited, works for NSE (.NS suffix).
  Alpha Vantage free tier: 25 requests/day.

WHY Google News RSS not NewsAPI/GNews:
  Free, no API key required, supports EN + HI languages.
  NewsAPI/GNews free tiers too restrictive for 5min cycles.

WHY static production build for frontend:
  Dev server (npm run dev) has memory leaks in Docker.
  Production build (npm run build + preview) is stable.
  Requires docker compose up -d --force-recreate after changes.

WHY --concurrency=2 for celery worker:
  Default prefork spawns Ncpu workers, each loading FinBERT (~1.5GB).
  Docker Desktop VM (4-8GB) OOMs with default concurrency.
  2 workers × 1.5GB = 3GB, fits within Docker memory.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
14. IMPORTANT IMPLEMENTATION NOTES
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

1. FinBERT MUST be loaded as a module-level singleton in the
   Celery worker — NOT inside the task function. Loading inside
   the task causes 10+ second delays per article.

2. WebSocket manager must be at FastAPI application level.
   Celery cannot directly access FastAPI's WebSocket connections.
   Use Redis pub/sub: Celery publishes → FastAPI background task
   subscribes → fans out to connected WebSocket clients.

3. Vite proxy: add usePolling:true for file watching in WSL2.
   Without this, hot reload does not work on Windows.

4. Docker service hostnames: use 'db' not 'localhost' for
   PostgreSQL URL, 'redis' not 'localhost' for Redis URL.
   Docker's internal DNS resolves service names automatically.

5. For Indian stocks use NSE suffix: RELIANCE.NS, TCS.NS etc.
   yFinance: yf.download("RELIANCE.NS", period="1y", interval="1d")

6. Alembic env.py must be async-compatible.
   Use create_async_engine + asyncio.run() for migrations.

7. JWT type field: access tokens have type="access",
   refresh tokens have type="refresh". Always validate type
   in the deps.py get_current_user function.

8. Never auto-cut positions without user confirmation.
   The system only OFFERS the option — user must click the button.
   Exit-on-news is USER-triggered only, never automatic.

9. F&O tickers encode everything in the ticker string:
   RELIANCE24AUG2800CE, ICICIBANK24AUGFUT.
   The order/position engine is agnostic — just reads cached price.

10. Strategy evaluation resolves F&O tickers to underlying:
    evaluator loads OHLCV bars for underlying equity, evaluates
    conditions, then fires order on the F&O ticker string.

11. Frontend must use http://127.0.0.1:5173 not localhost.
    Docker port binding is on 127.0.0.1, IPv6 localhost → ::1 fails.

12. Docker compose restart does NOT reload .env changes.
    Must use: docker compose up -d --force-recreate <service>

13. All monetary values use Decimal, never Float.
    Quantized to 2 decimal places at point of ingestion.

14. Celery tasks using asyncio.run() create a new event loop
    per invocation. Must .dispose() engine + redis_client.aclose()
    in finally block or next run hits InterfaceError.

15. Docker bind mount shows /app in container. HF cache at
    /app/.hf_cache gets hidden. Use /opt/hf_cache instead.

16. NLTK data (punkt, punkt_tab, stopwords) must be downloaded
    in Dockerfile AND in requirements.txt (rake-nltk depends on it).

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
15. HOW TO HELP ME
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

- I am a final-year B.Tech Data Science Engineering student.
- Explain things clearly with both code AND plain-English reasoning.
- Always give complete, copy-paste ready code — no placeholders.
- When writing files, give the exact file path first.
- When I share a screenshot of an error, diagnose it precisely.
- When I ask about a concept, explain it simply with examples.
- Always continue from current phase status (see Section 12).
- Production-quality code: typed, documented, modular.
- Never suggest starting over — always build incrementally.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
16. NEXT STEPS (Phase 8 — Testing, Polish & Deployment)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Continue Phase 8 by:
1. Expanding backend/API tests toward the 70% coverage target.
2. Running the 50-user Locust test and reviewing its measured results.
3. Completing authenticated dashboard/mobile checks.
4. Configuring production API/frontend URLs, CORS origins, and provider secrets.
5. Deploying only after production settings and user authorization are confirmed.

═══════════════════════════════════════════════════════════════
END OF MASTER CONTEXT DOCUMENT
═══════════════════════════════════════════════════════════════

# TradeMind AI — App Flow Document

Navigation logic, features, and user journey maps.

> Full project details: [trademind_master_context.md](trademind_master_context.md)
> Build plan: [trademind_roadmap.md](trademind_roadmap.md)

---

## 1. Route Map

All routes are protected by `ProtectedRoute` (JWT guard) except `/login` and `/register`.

```
/login          → LoginPage           (public)
/register       → RegisterPage        (public)
/dashboard      → DashboardPage       (protected)
/trading        → TradingPage         (protected)
/fno            → FOPage              (protected)
/strategies     → StrategyBuilderPage  (protected)
/news           → NewsPage            (protected)
/profile        → ProfilePage         (protected)
*               → Redirect to /login
```

---

## 2. Navigation Bar

Visible on all protected pages. Top bar, sticky, dark theme.

```
┌──────────────────────────────────────────────────────────────────┐
│  [T] TradeMind AI    Dashboard  Trading  F&O  News  Strategies  │
│      Paper Trading     ◈        ⇄      ◆   📰      ⚡         │
│                                                      Profile ◉  │
│                                                    [Logout]     │
└──────────────────────────────────────────────────────────────────┘
```

- **Desktop**: horizontal nav links + user avatar + logout button
- **Mobile**: hamburger menu → vertical nav links + logout

---

## 3. Page Map & Features

### /dashboard — Command Centre
```
┌─────────────────────────────────────────────────────┐
│  Welcome back, {username}                           │
│  Market Open • NSE Live                             │
│                                                     │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌────────┐ │
│  │ Net Worth│ │ Cash Bal │ │ Unreal.  │ │Realised│ │
│  │ ₹10,00,000│ │ ₹9,50,000│ │ +₹12,450 │ │+₹8,200│ │
│  └──────────┘ └──────────┘ └──────────┘ └────────┘ │
│                                                     │
│  [Trade Now]  [Build Strategy]                      │
│                                                     │
│  ┌─────────────────────────┐ ┌─────────────────┐   │
│  │   Equity Curve (Recharts│ │ Open Positions  │   │
│  │   AreaChart, cyan fill) │ │ (live P&L)      │   │
│  │   64px height           │ │ View all →      │   │
│  └─────────────────────────┘ └─────────────────┘   │
│                                                     │
│  Stat Cards:                                        │
│  Open Positions (count) | Total Trades | Strategies │
│  Market Status: LIVE                                │
│                                                     │
│  Your Strategies (top 3, with status badges)        │
│  Open builder →                                     │
└─────────────────────────────────────────────────────┘
```

**API calls on load:**
- `GET /users/me` → username, balance
- `GET /portfolio/summary` → positions, P&L, net worth
- `GET /orders/` → transaction history (for equity curve)
- `GET /strategies/` → strategy list

**Actions:**
- "Trade Now" → navigates to `/trading`
- "Build Strategy" → navigates to `/strategies`
- "View all →" → navigates to `/trading`
- "Open builder →" → navigates to `/strategies`

---

### /trading — Paper Trading Terminal
```
┌─────────────────────────────────────────────────────┐
│  Paper Trading Terminal                             │
│                                                     │
│  ┌───────────────────────────┐ ┌─────────────────┐  │
│  │  Order Form               │ │  Balance Card   │  │
│  │  Ticker: [RELIANCE    ▼]  │ │  Cash: ₹9,50,000│  │
│  │  Side:   [BUY] [SELL]     │ │  Positions: 3   │  │
│  │  Type:   [MARKET▼]        │ │                 │  │
│  │  Qty:    [100      ]      │ │                 │  │
│  │  Settle: [DELIVERY▼]      │ │                 │  │
│  │  (if LIMIT/SL: trigger)   │ │                 │  │
│  │                           │ │                 │  │
│  │  [Place Order]            │ │                 │  │
│  └───────────────────────────┘ └─────────────────┘  │
│                                                     │
│  Open Positions                                     │
│  ┌────────┬─────┬───────┬────────┬───────┬────────┐ │
│  │ Ticker │ Qty │ Entry │ Current│ P&L   │ Action │ │
│  │ RELIANCE│ 100│ ₹2,450│ ₹2,470 │+₹2,000│[Exit] │ │
│  │ INFY   │  50 │ ₹1,420│ ₹1,415 │  -₹250│[Exit] │ │
│  │        │     │       │        │       │[📰Exit]│ │
│  └────────┴─────┴───────┴────────┴───────┴────────┘ │
│                    Exit on news = user-click only    │
│                                                     │
│  Pending Orders                                     │
│  ┌────────┬─────┬────────┬────────┬────────────────┐│
│  │ Ticker │ Side│ Type   │ Trigger│ Status         ││
│  │ TCS    │ BUY │ LIMIT  │ ₹3,800 │ PENDING        ││
│  └────────┴─────┴────────┴────────┴────────────────┘│
│                                                     │
│  Transaction History (most recent first)            │
└─────────────────────────────────────────────────────┘
```

**API calls on load:**
- `GET /market/watchlist` → ticker dropdown options
- `GET /portfolio/summary` → open positions, balance
- `GET /orders/` → history + pending orders

**Order flow:**
```
User fills form → POST /orders/
  → Redis rate limit check (10/user/60s)
  → Price fetched from Redis cache
  → If MARKET: immediate fill (slippage + fees)
  → If LIMIT/SL/TP: save as PENDING
     → Celery checks every 15s against live prices
     → Auto-fills when trigger hit
  → Position created/updated (FIFO close)
  → Balance deducted/credited
  → Response: OrderResponse
```

**Exit on news flow:**
```
User clicks "📰 Exit" on position row
  → POST /orders/exit-on-news { ticker }
  → Finds OPEN position for ticker
  → MARKET SELL at current price (slippage + fees)
  → triggered_by = NEWS_EVENT
  → Position CLOSED, balance restored
  → Order returned
```

---

### /fno — Futures & Options Terminal
```
┌─────────────────────────────────────────────────────┐
│  F&O Terminal                                       │
│                                                     │
│  Underlying: [RELIANCE▼]  Expiry: [24AUG▼]         │
│                                                     │
│  Spot: ₹2,450.00                                   │
│                                                     │
│  Option Chain (CE ← Spot → PE)                      │
│  ┌──────────┬──────────┬──────────┬──────────┐      │
│  │  CE LTP  │  CE Δ   │  Strike  │  PE Δ   │ PE LTP│
│  │  ₹45.20  │  0.42   │  ₹2,400  │ -0.58   │ ₹32.10│
│  │  ₹28.50  │  0.31   │  ₹2,450  │ -0.69   │ ₹28.50│
│  │  ₹15.80  │  0.19   │  ₹2,500  │ -0.81   │ ₹45.20│
│  └──────────┴──────────┴──────────┴──────────┘      │
│                                                     │
│  Futures                                            │
│  ┌──────────────┬───────────┬───────────┐           │
│  │ Contract      │ LTP       │ Basis     │           │
│  │ RELIANCE24AUGFUT│ ₹2,470  │ +0.82%   │           │
│  │ RELIANCE25SEPFUT│ ₹2,490  │ +1.63%   │           │
│  └──────────────┴───────────┴───────────┘           │
│                                                     │
│  Trade Ticket: [Buy CE] [Sell PE] [Buy FUT]         │
│  → Opens order form pre-filled with contract ticker  │
└─────────────────────────────────────────────────────┘
```

**API calls on load:**
- `GET /market/fno/universe` → available underlyings
- `GET /market/fno/expiries` → expiry dates
- `GET /market/fno/chain?underlying=RELIANCE` → full chain + futures
- `GET /market/prices` → live spot prices

**Trade flow:**
```
User selects contract from chain
  → Trade ticket opens (pre-filled ticker: RELIANCE24AUG2800CE)
  → User enters quantity, side
  → POST /orders/ (same as equity, engine agnostic to ticker format)
  → Price read from Redis cache (derived by market_data worker)
  → Black-Scholes Greeks recomputed each 15s cycle
```

---

### /strategies — Strategy Builder + Templates
```
┌─────────────────────────────────────────────────────┐
│  Strategy Builder                                   │
│                                                     │
│  ┌───────────────────────────────────────────────┐  │
│  │  Builder (top section)                        │  │
│  │  Name: [My RSI Strategy    ]                  │  │
│  │  Ticker: [RELIANCE▼]  Timeframe: [1h▼]       │  │
│  │  Type: [Classic▼]  Reference: [SPOT▼]         │  │
│  │  Options: [MIS▼] [MARKET▼]  Entry [09:20]     │  │
│  │  Square-off [15:15]  Days [MON-FRI]           │  │
│  │                                               │  │
│  │  Condition: [AND▼]                            │  │
│  │  ┌─ RSI(14) [crosses_below] [30]             │  │
│  │  ├─ EMA(50) [crosses_above] EMA(200)         │  │
│  │  └─ Volume [above_avg] [20]                   │  │
│  │                                               │  │
│  │  Action: [BUY] [MARKET] qty [100] [DELIVERY]  │  │
│  │  Legs: BUY CE weekly ATM 1 lot  [+ Add leg]   │  │
│  │  Risk: SL / Target / trailing / advanced flags│  │
│  │  Prompt: [optional description    ]            │  │
│  │                                               │  │
│  │  [Backtest Strategy] [Save Draft] [Activate]  │  │
│  └───────────────────────────────────────────────┘  │
│                                                     │
│  Templates (below builder)                          │
│  ┌─────────┬──────────────┬──────────────┐         │
│  │ 📈       │ 📉            │ 📰           │         │
│  │ RSI      │ MACD         │ News Bullish │         │
│  │ Oversold │ Crossover    │ Breakout     │         │
│  │ [Use]    │ [Use]        │ [Use]        │         │
│  └─────────┴──────────────┴──────────────┘         │
│  (21 templates: 18 classic + 3 news-triggered)      │
│                                                     │
│  Your Strategies                                    │
│  ┌────────┬────────┬────────┬──────────┬──────────┐ │
│  │ Name   │ Ticker │ Status │ Multiplier│ Reason  │ │
│  │ RSI    │ RELIANCE│ACTIVE │ 1.0       │ —       │ │
│  │ News   │ KOTAK  │PAUSED ⚠│ 0.57      │ RBI hike│ │
│  └────────┴────────┴────────┴──────────┴──────────┘ │
│  Paused strategies show reason + lot multiplier     │
│  Each strategy supports Backtest before activation  │
└─────────────────────────────────────────────────────┘
```

**Backtest behavior:**
- Saved strategies and unsaved drafts run from the strategy builder modal.
- The modal shows historical P/L, CAGR, Sharpe, drawdown, win rate,
  trade count, final equity, and an equity curve.
- Walk-forward analysis shows in-sample/out-of-sample Sharpe,
  Efficiency Ratio, and per-window results.
- Activation is gated until the current strategy configuration has passed
  a successful backtest.
- Time-based option strategies may omit indicator conditions; indicator-based
  option strategies require a condition tree and at least one option leg.

**Indicators available:**
| Indicator | Parameters | Condition Types |
|-----------|-----------|-----------------|
| RSI | period (int) | crosses_above, crosses_below, above, below |
| EMA | period (int) | crosses_above, crosses_below, above, below |
| SMA | period (int) | crosses_above, crosses_below, above, below |
| MACD | — | crosses_above, crosses_below, above, below |
| Volume | window (int) | above_avg, below_avg |
| Price | — | above, below |
| Sentiment | window (15m/1h/1d), metric (score/magnitude) | above, below |

**Strategy evaluation flow (every 60s):**
```
Celery task: evaluate_active_strategies
  → Load all ACTIVE strategies
  → For each strategy:
    → Resolve ticker (if F&O → underlying for OHLCV)
    → Load OHLCV bars from cache/DB
    → Preload sentiment series if SENTIMENT indicator used
    → Evaluate root_condition tree (AND/OR recursive)
    → If condition MET and edge-triggered (not already fired):
      → fire_action():
        → Calculate effective_qty = base × quantity_multiplier
        → Execute order (same path as manual trade)
        → Set triggered_by = STRATEGY or NEWS_EVENT
        → Attach evidence headlines if news-driven
      → Update strategy.last_triggered_at
  → Dispose engine, close Redis (finally block)
```

**News-paused strategy visibility:**
```
Strategy list shows:
  - paused_reason: headline text (truncated)
  - quantity_multiplier: 0.57 (if reduced)
  - multiplier_set_at: timestamp
  - news_event_id: FK to news_signals
```

---

### /news — News Intelligence Hub
```
┌─────────────────────────────────────────────────────┐
│  News Intelligence                                  │
│                                                     │
│  Ticker: [RELIANCE▼]  Window: [1h▼]                │
│                                                     │
│  Impact Bands                                       │
│  ┌───────────────────────────────────────────────┐  │
│  │ 15m: 0.62 ████████████░░░░ MEDIUM             │  │
│  │  1h: 0.45 █████████░░░░░░░ MEDIUM             │  │
│  │ 24h: 0.71 ██████████████░░ HIGH               │  │
│  │                                               │  │
│  │ Regime: spike-bearish | z-score: -2.3         │  │
│  │ Articles: 12 (24h) | POS: 3 | NEG: 8 | NEU: 1│  │
│  └───────────────────────────────────────────────┘  │
│                                                     │
│  Latest Headlines                                   │
│  ┌───────────────────────────────────────────────┐  │
│  │ 🔴 RELIANCE Q2 profit drops 15% - Reuters     │  │
│  │    Score: -0.88 NEG | 2h ago                  │  │
│  │ 🔴 RBI hikes rates, banks under pressure      │  │
│  │    Score: -0.65 NEG | 4h ago                  │  │
│  │ 🟢 Reliance Jio adds 5M subscribers           │  │
│  │    Score: +0.73 POS | 6h ago                  │  │
│  └───────────────────────────────────────────────┘  │
│                                                     │
│  Impact Alerts (24h)                                │
│  ┌───────────────────────────────────────────────┐  │
│  │ ⚠ HIGH: KOTAKBANK — RBI policy hike           │  │
│  │   Strategy "Bank RSI" auto-paused              │  │
│  │   Lot multiplier: 0.57                         │  │
│  │                                               │  │
│  │ ⚠ MEDIUM: HDFCBANK — Q2 results mixed         │  │
│  │   In-app alert only                            │  │
│  └───────────────────────────────────────────────┘  │
│                                                     │
│  Strategy Advisor                                   │
│  ┌───────────────────────────────────────────────┐  │
│  │ Select strategy: [RSI RELIANCE▼]              │  │
│  │ Note: [What should I improve?]                 │  │
│  │ [Get Advice]                                   │  │
│  │                                               │  │
│  │ ┌─ AI Response ─────────────────────────────┐ │  │
│  │ │ Consider adding EMA(50) as trend filter... │ │  │
│  │ │ Your RSI entry is too aggressive at 30.    │ │  │
│  │ │ Try 35 for better risk-adjusted returns.   │ │  │
│  │ └───────────────────────────────────────────┘ │  │
│  └───────────────────────────────────────────────┘  │
│                                                     │
│  AI Trade Journal                                   │
│  ┌───────────────────────────────────────────────┐  │
│  │ Strategy: [All▼]  Period: [7 days▼]           │  │
│  │ [Generate Journal]                             │  │
│  │                                               │  │
│  │ ┌─ Weekly Summary ──────────────────────────┐ │  │
│  │ │ Week of Sep 8-14: 12 trades, 8 wins       │ │  │
│  │ │ Best: INFY +₹4,200 | Worst: SBIN -₹1,800 │ │  │
│  │ │ Win rate: 67% | Avg hold: 2.3 days        │ │  │
│  │ │ News events triggered 2 position exits.    │ │  │
│  │ └───────────────────────────────────────────┘ │  │
│  └───────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────┘
```

**API calls on load:**
- `GET /news/signal?ticker=RELIANCE` → all-window snapshot + headlines
- `GET /news/alerts` → user's impact alerts (24h TTL)

**Advisor flow:**
```
User selects strategy + optional note
  → POST /news/advisor { strategy_id, note }
  → Backend builds context:
    → Strategy details (conditions, action, status, multiplier)
    → Last 20 orders (ticker, side, price, fees, triggered_by)
    → Open positions (qty, entry, P&L)
  → Claude API call (stdlib HTTP, fail-soft)
  → Response saved to trade_journal table
  → Returned to UI
```

**Journal flow:**
```
User selects strategy + days
  → POST /news/journal { strategy_id, days }
  → Backend builds context + window_days
  → Claude API generates narrative analysis
  → Saved to trade_journal table
  → Journal card displayed
```

---

### /profile — User Profile
```
┌─────────────────────────────────────────────────────┐
│  Profile                                            │
│                                                     │
│  Username: prashant5214                             │
│  Email: prashant@example.com                        │
│  Member since: Jan 2026                             │
│                                                     │
│  Virtual Balance: ₹10,00,000                        │
│  Account Status: Active                             │
│                                                     │
│  [Logout]                                           │
└─────────────────────────────────────────────────────┘
```

---

## 4. User Journey Flows

### Journey 1: First-Time User (Onboarding)
```
1. Visit /register
   → Enter username, email, password
   → POST /api/v1/auth/register
   → Auto-login (POST /api/v1/auth/login)
   → Redirect to /dashboard

2. See dashboard: ₹10,00,000 balance, no positions, no strategies
   → "Place your first trade to get started"

3. Click "Trade Now" → /trading
   → Select ticker (RELIANCE), BUY, MARKET, 10 shares
   → POST /orders/ → position created
   → Balance deducted, position appears in table

4. Return to /dashboard
   → Net worth updated, equity curve shows first trade
   → Open Positions card shows 1
```

### Journey 2: Strategy Builder → Auto-Trade
```
1. Navigate to /strategies
   → Click template "RSI Oversold" → condition pre-filled
   → Adjust: Ticker RELIANCE, Qty 50
   → [Save Strategy] → POST /strategies/
   → [Activate] → status = ACTIVE

2. Celery evaluates every 60s
   → Loads OHLCV bars for RELIANCE
   → Checks RSI(14) crosses below 30
   → When triggered: fires BUY 50 RELIANCE MARKET
   → Order appears in /trading transaction history
   → Position created

3. Strategy shows last_triggered_at timestamp
   → Next evaluation skips (edge-triggered, already fired)
```

### Journey 3: News Impact → Strategy Auto-Pause
```
1. Google News RSS detects "KOTAKBANK: RBI raises interest rates"
   → Ingested every 5 min by Celery

2. FinBERT scores: NEGATIVE, confidence 0.88
   → polarity = -0.88
   → Sector: BANK (weight 0.95)
   → Source: reuters (weight 0.95)
   → Recency: 0.95 (2 min old)
   → impact = -0.88 × (0.4×0.95 + 0.3×0.95 + 0.3×0.95) = -0.84
   → |impact| = 0.84 ≥ 0.70 → HIGH

3. Action engine fires:
   → Pause strategy "Bank RSI" (status=PAUSED, paused_reason="RBI hike")
   → Tighten SL on pending KOTAKBANK orders (move trigger closer)
   → Reduce lot multiplier to 0.57
   → Create in-app alert for user

4. User sees on /strategies:
   → "Bank RSI" shows ⚠ PAUSED, reason "RBI hike", multiplier 0.57

5. User sees on /news:
   → HIGH impact alert with headline + action taken

6. After 2 calm cycles OR 120min:
   → Strategy resumes (status=ACTIVE, multiplier=1.0)
   → Or user manually resumes (clears paused_reason)
```

### Journey 4: F&O Trading
```
1. Navigate to /fno
   → Select RELIANCE from dropdown
   → Option chain loads (Black-Scholes priced)
   → Spot: ₹2,450, CE/PE at various strikes

2. Click on RELIANCE24AUG2800CE (LTP ₹28.50)
   → Trade ticket opens with pre-filled ticker
   → Enter qty: 2 lots (500 shares for RELIANCE lot=250)
   → [Buy CE]

3. POST /orders/ with ticker=RELIANCE24AUG2800CE
   → Price read from Redis (derived from underlying spot)
   → Order fills at ₹28.50 + slippage
   → Position created

4. Strategy can also trade F&O:
   → Strategy ticker = RELIANCE24AUG2800CE
   → Evaluator resolves to RELIANCE for OHLCV bars
   → Fires order on F&O ticker
```

### Journey 5: Exit on News (Manual)
```
1. User holds position in KOTAKBANK
   → News HIGH impact detected, strategy paused

2. User decides to exit manually
   → Clicks "📰 Exit" button on position row in /trading

3. POST /orders/exit-on-news { ticker: "KOTAKBANK" }
   → Backend finds OPEN position
   → Creates MARKET SELL order
   → triggered_by = NEWS_EVENT, triggered_by_user = USER_EXIT_NEWS
   → Fills at current market price + slippage
   → Position CLOSED, balance restored

4. Position disappears from open positions
   → Appears in transaction history with NEWS_EVENT tag
```

### Journey 6: Strategy Advisor + Journal
```
1. Navigate to /news → Strategy Advisor section
   → Select strategy "RSI RELIANCE"
   → Type note: "How can I reduce drawdown?"
   → [Get Advice]

2. POST /news/advisor { strategy_id, note }
   → Backend builds context (strategy + last 20 orders + positions)
   → Claude API generates suggestions
   → Saved to trade_journal (kind="advisor")
   → Response displayed

3. Later, user generates weekly journal
   → Select "All strategies", 7 days
   → [Generate Journal]
   → POST /news/journal
   → Claude generates narrative from trade data
   → Saved to trade_journal (kind="journal")
   → Journal card appears in history
```

---

## 5. Data Flow Diagrams

### Price Update Cycle (every 15s)
```
Celery Beat → market_data.refresh_watchlist_prices
  → yfinance: 20 equity tickers (.NS) → Redis price:{TICKER}
  → For each F&O underlying:
    → Read spot from Redis
    → Compute futures (spot × (1 + carry))
    → Compute options (Black-Scholes × strikes × expiries)
    → Write 384+ F&O prices to Redis
  → Dispose engine, close Redis
```

### News Ingest Cycle (every 5min)
```
Celery Beat → news_ingest.ingest_news
  → Google News RSS (EN + HI, 40 feeds)
  → Filter: last 6h, unique url_hash
  → For each article:
    → FinBERT (EN) or lexicon (HI) → signed polarity
    → RAKE → keywords (EN only)
    → Sector mapper → sector + tickers
    → Impact scorer → weighted-blend score + band
  → Bulk upsert: news_articles, news_sentiment, news_signals
  → Aggregate: decay-weighted score per ticker per window
  → Action engine: pause/resume, SL tighten, lot multiplier
  → Dispose engine, close Redis
```

### Strategy Evaluation Cycle (every 60s)
```
Celery Beat → strategy_evaluator.evaluate_active_strategies
  → Load all ACTIVE strategies
  → For each:
    → If ticker is F&O → resolve to underlying
    → Load OHLCV bars (from Redis/DB)
    → If has SENTIMENT condition → load sentiment series
    → Evaluate root_condition tree (AND/OR recursive)
    → If MET and edge-triggered:
      → fire_action() → create_order()
      → Update last_triggered_at
  → Dispose engine, close Redis
```

### Order Execution Path
```
POST /orders/
  → Rate limit check (Redis, 10/user/60s)
  → Price: Redis cache (price:{TICKER})
    → If F&O not cached: get_price_or_derive() fallback
  → Fees: calculate_fees(price, qty, settlement, order_type)
    → Brokerage, STT, stamp, exchange, SEBI, GST, DP
  → Execute:
    → BEGIN TRANSACTION
    → Lock user row (SELECT ... FOR UPDATE)
    → Check balance ≥ cost + fees
    → Create Order row (PENDING or FILLED)
    → If FILLED:
      → Create/update Position (signed qty, FIFO close)
      → Update user.virtual_balance
    → COMMIT
  → Return OrderResponse
```

---

## 6. Celery Worker Memory Model

```
┌─────────────────────────────────────────┐
│ Docker Desktop VM (4-8GB RAM)           │
│                                         │
│  ┌──────────┐  ┌──────────┐            │
│  │ Worker 1 │  │ Worker 2 │  --concurrency=2
│  │ FinBERT  │  │ FinBERT  │  (lazy singleton per fork)
│  │ ~1.5GB   │  │ ~1.5GB   │            │
│  └──────────┘  └──────────┘            │
│                                         │
│  ┌──────────┐                           │
│  │ Beat     │  (scheduler only, no model)
│  └──────────┘                           │
│                                         │
│  Total worker memory: ~3GB             │
│  Must fit within Docker memory limit    │
└─────────────────────────────────────────┘
```

---

## 7. Error Handling & Fail-Soft

| Component | Failure Mode | Behaviour |
|-----------|-------------|-----------|
| FinBERT | Model load fails | Falls back to lexicon for all text |
| FinBERT | Inference timeout (30s) | Skip article, lexicon fallback |
| FinBERT | Budget exceeded (>120/cycle) | Remaining articles use lexicon |
| Claude Advisor | API key unset | Returns advisory message, no crash |
| Claude Advisor | API timeout/error | Returns error message, saves to journal |
| Price cache | Ticker not in Redis | get_price_or_derive() attempts F&O derivation |
| News ingest | RSS feed unreachable | Skips that feed, continues with others |
| News ingest | Google rate-limited | 0 candidates → skips actions, logs |
| Celery worker | asyncio InterfaceError | engine.dispose() + redis.aclose() in finally |
| Strategy eval | F&O ticker, no underlying price | Skips that strategy, logs |
| Rate limiter | Order spam | 429 Too Many Requests |

---

## 8. Authentication Flow

```
1. Register: POST /auth/register
   → bcrypt hash password (pinned 4.0.1)
   → Create user with ₹10,00,000 virtual balance
   → Return 201

2. Login: POST /auth/login
   → Verify bcrypt hash
   → Issue access token (30min) + refresh token (7d)
   → Set HTTP-only cookies
   → Return 200 + tokens

3. Auto-refresh (Axios interceptor):
   → Request → 401 (token expired)
   → Queue request
   → POST /auth/refresh with refresh token
   → New access + refresh tokens
   → Retry queued request
   → User never sees interruption

4. Logout: POST /auth/logout
   → Add jti to Redis blacklist (TTL = token expiry)
   → Clear cookies
   → Return 204

5. Protected route guard:
   → ProtectedRoute component checks authStore
   → If no token → redirect to /login
   → If token → render page
```

---

## 9. State Management (Zustand)

```
authStore (persisted to localStorage):
  user: { id, username, email, virtual_balance }
  setUser(user)
  logout()

Usage in pages:
  DashboardPage: setUser(meRes.data) on load
  Navbar: user.username for avatar, logout() on logout
  ProtectedRoute: checks if user exists
```

---

## 10. Docker Build & Deploy Flow

```
docker compose up -d --build

  db (postgres:16-alpine)
    → Health check: pg_isready
    → Volume: postgres_data (persistent)

  redis (redis:7-alpine)
    → Health check: redis-cli ping

  backend (Python 3.11-slim)
    → Build: requirements.txt + torch CPU + transformers + rake-nltk
    → FinBERT baked at /opt/hf_cache
    → NLTK data: punkt, punkt_tab, stopwords
    → Command: uvicorn --reload

  celery_worker (same image)
    → Command: celery worker --concurrency=2
    → Loads FinBERT lazily per fork

  celery_beat (same image)
    → Command: celery beat
    → Schedules: prices 15s, pending 15s, strategy 60s, news 5min, OHLCV 15min

  frontend (Node + Vite)
    → Build: npm run build (static)
    → Serve: npm run preview --host 0.0.0.0
    → Port: 5173

After any frontend change:
  docker compose up -d --force-recreate frontend

After backend code change:
  uvicorn auto-reloads (bind mount)

After worker code change:
  docker compose restart celery_worker celery_beat
```

# TradeMind AI — 16-Week Build Plan

**10 features · 8 phases · 5/8 complete**

> Full project details: [trademind_master_context.md](trademind_master_context.md)
> App flow & user journeys: [trademind_app_flow.md](trademind_app_flow.md)

---

## Phase 1 — Foundation & Auth ✅ DONE
**Weeks 1–2**

| Tasks | Deliverables |
|-------|-------------|
| Docker Compose: FastAPI + PostgreSQL + Redis + React | Working auth with Swagger docs |
| User model, JWT auth (access+refresh), Redis blacklist | Protected dashboard (JWT guard) |
| React: login, register, protected routes, dashboard | Auto-refresh interceptor (no token flicker) |
| Tailwind dark theme, Zustand state management | |

**🏁 Auth working end-to-end**

---

## Phase 2 — Paper Trading Engine ✅ DONE
**Weeks 3–4**

| Tasks | Deliverables |
|-------|-------------|
| yFinance live prices (20-ticker NSE watchlist) | POST /orders/ executes paper trades to the paisa |
| Orders: MARKET, LIMIT, SL, TP with NSE fee model | GET /portfolio/summary with live unrealised P&L |
| Position tracker: signed qty, FIFO close, P&L | Trading page with order form + position table |
| Celery beat: prices 15s, pending 15s, OHLCV 15min | Realistic broker fees (STT, stamp, exchange, SEBI, GST) |
| 48,286 OHLCV bars backfilled (5yr daily + 60d 15min) | |

**🏁 First paper trade placed**

---

## Phase 3 — Strategy Builder + F&O Module ✅ DONE
**Week 5**

| Tasks — Strategy Builder | Tasks — F&O Module |
|--------------------------|-------------------|
| Indicator engine: RSI, EMA, SMA, MACD, Volume, Price | Black-Scholes pricing + Greeks (Δ/Γ/Θ/Vega) |
| AND/OR condition tree (nested JSON) + 21 templates | Synthetic IV smile, futures carry basis |
| Visual builder UI (builder on top, templates below) | NSE last-Thursday expiry calendar |
| Celery evaluator (60s, edge-triggered, auto-fires trades) | 6 equity underlyings + NIFTY/BANKNIFTY indices |
| Strategy prompt feature: key→tree+action library | 384+ F&O contracts priced/15s, option chain API |
| Multi-leg options foundation: schedules, CE/PE legs, expiry/strike selection, risk controls | |

**🏁 Strategy auto-executes + F&O chain live**

---

## Phase 4 — News Intelligence (FinBERT) ✅ DONE
**Weeks 6–7**

| Tasks — NLP Pipeline | Tasks — Impact + Actions |
|----------------------|--------------------------|
| FinBERT singleton (EN only) + bilingual lexicon (HI) | Weighted-blend formula: polarity × (sector + source + recency) |
| Hybrid scorer: signed polarity, budget guard | HIGH/MEDIUM/LOW bands, env-tunable thresholds |
| RAKE keyword extraction (EN only, <5ms/article) | Auto-pause strategy, tighten SL, reduce lot size |
| Expert-system sector mapper: 63 tickers, 180+ keywords | User-triggered exit-on-news (MARKET SELL) |
| Google News RSS (EN+HI), 40 feeds/5min cycle | Claude strategy advisor + AI trade journal (fail-soft) |
| | Decay-weighted aggregation + z-score vs 7-day baseline |

**🏁 FinBERT scores news, trades react automatically**

---

## Phase 5 — Backtesting + Walk-Forward ✅ DONE
**Weeks 8–9**

| Tasks | Deliverables |
|-------|-------------|
| Standard backtest: CAGR, Sharpe, drawdown, win rate | POST /backtest/run returns metrics + equity data |
| Slippage + brokerage fee model in backtest | POST /backtest/walk-forward returns ER + windows |
| Walk-forward engine: rolling 3yr train / 1yr test | Per-strategy backtest modal with equity curve + WFO results |
| Efficiency Ratio = OOS Sharpe ÷ IS Sharpe | Efficiency Ratio badge (green > 0.7) |
| WFO report: per-window results table | |
| Backtest result schema synchronized with the current ORM model | |

**🏁 WFO Efficiency Ratio computed**

---

## Phase 6 — Copy Trading ⬜ NEXT
**Week 10**

| Tasks | Deliverables |
|-------|-------------|
| Strategy publish/unpublish toggle | Follower gets mirrored trade on publisher fire |
| Follower model: user → strategy subscription | Public strategy marketplace page |
| Trade replication at follow ratio | Risk settings per follower respected |
| Risk controls: max allocation cap, SL override | |
| Marketplace + leaderboard (return-ranked) | |

**🏁 Copy trade replicated**

---

## Phase 7 — League + Competition Mode ⬜ PENDING
**Weeks 11–12**

| Tasks | Deliverables |
|-------|-------------|
| League model: Competition, LeagueEntry, Badge | League page: live rank table + badge showcase |
| Monthly Celery beat: reset balances on 1st | Monthly competition auto-reset |
| Sharpe Ratio leaderboard ranking query | Sharpe-ranked leaderboard |
| Badge logic: Consistent Performer, Drawdown Master, News Ninja | |
| Trophy + marketplace highlight at month end | |

**🏁 League system live**

---

## Phase 8 — Testing, Polish & Deployment ⬜ PENDING
**Weeks 13–16**

| Tasks | Deliverables |
|-------|-------------|
| Full dashboard assembly: all charts + cards | Live demo URL |
| Responsive mobile layout pass | Complete README + API docs |
| pytest suite (target 70%+ coverage) | Academic report (all 15 sections) |
| Locust load test: 50 concurrent users | 30-slide presentation deck |
| Security: rate limiting, input validation, CORS | 50 viva Q&A answers |
| GitHub Actions CI/CD: lint → test → deploy | 5-min demo video |
| Deploy: Render (backend) + Vercel (frontend) | |

**🏁 Submitted and deployed**

---

## Summary

| | |
|---|---|
| **16** weeks total | **10** features |
| **3** AI engines | **6/8** milestones done |

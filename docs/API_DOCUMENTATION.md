# TradeMind AI API Documentation

This document describes the HTTP API currently mounted by the FastAPI backend. It is based on the implementation, not a promise of live exchange connectivity or investment performance.

## Base URL and conventions

- Local API: `http://localhost:8000`
- Versioned routes use the `/api/v1` prefix.
- Send and receive JSON unless an endpoint indicates otherwise.
- Protected endpoints require `Authorization: Bearer <access_token>`.
- IDs are generally UUIDs. Timestamps are ISO 8601.
- Use `/docs` on a running backend for the generated OpenAPI interface.
- `/health` is an unversioned service health endpoint.

Most examples below omit response fields that are generated IDs, timestamps, or user-specific metadata.

## Authentication

### Register

`POST /api/v1/auth/register`

```json
{
  "email": "trader@example.com",
  "username": "trader",
  "password": "example-password"
}
```

The password must contain at least eight characters. A successful response includes the user's ID, email, username, virtual balance, and active status. Registration does not accept a username in place of an email.

### Log in

`POST /api/v1/auth/login`

Submit JSON containing the registered email and password. The response provides access and refresh tokens. The configured defaults are a 30-minute access token and a 7-day refresh token.

### Refresh, log out, and current user

- `POST /api/v1/auth/refresh` — send `{"refresh_token": "<refresh_token>"}` to exchange a valid refresh token for refreshed credentials.
- `POST /api/v1/auth/logout` — log out using the authenticated session/token.
- `GET /api/v1/auth/me` — return the authenticated user's profile.
- `GET /api/v1/users/me` — return the current user's profile through the users API.

These routes require the authentication format specified by their request model; use `/docs` for the exact token body and response schema.

## Health

`GET /health`

Returns backend service health/status. This checks service availability; it is not a guarantee that every third-party or market-data source is available.

## Market data

### Watchlist and prices

- `GET /api/v1/market/watchlist`
- `GET /api/v1/market/prices`

Prices are based on the application's cached quote feed. Returned movement fields represent daily/last-session changes when available. A missing or stale upstream quote can limit the data shown; the API does not guarantee exchange-real-time coverage.

### Portfolio summary

`GET /api/v1/portfolio/summary`

Returns the authenticated user's virtual balance, net worth, realized/unrealized P&L, and position summary.

### Futures and options

- `GET /api/v1/market/fno/universe`
- `GET /api/v1/market/fno/expiries`
- `GET /api/v1/market/fno/chain`
- `GET /api/v1/market/fno/quote`

Consult `/docs` for the current query parameters and response model. The option-chain response includes call (CE) and put (PE) contracts and calculated Greeks. These derivatives are **synthetically derived** from cached underlying prices using a carry model for futures and Black–Scholes with a synthetic volatility surface for options. They are not live NSE/BSE option-chain quotes, exchange order-book prices, or exchange-provided Greeks.

## Orders and trade proposals

### Orders

- `POST /api/v1/orders` — submit an order.
- `GET /api/v1/orders` — list the authenticated user's orders.
- `POST /api/v1/orders/manual-exit` — request a manual exit (body: `{"ticker": "RELIANCE"}`).
- `POST /api/v1/orders/exit-on-news` — request an exit based on a news event.

Orders are part of the application's virtual trading workflow; they do not place orders with a broker or exchange. A market order uses the cached price and applies 0.05% adverse slippage. LIMIT, SL, and TP orders remain pending for the order worker to evaluate against available prices. Fill, balance, and fee behavior is implemented in `backend/app/services/order_service.py`; do not assume every request fills immediately.

For order creation, use the request schema in `/docs` for the exact supported order types, side, quantity, settlement, and optional price fields. Both exit endpoints take a ticker and are user-triggered full-position market exits; exit-on-news is not an automatic liquidation.

### Trade proposals

- `GET /api/v1/orders/proposals` — list pending/available trade proposals for the authenticated user.
- `POST /api/v1/orders/proposals/{proposal_id}/confirm` — explicitly confirm a strategy/news trade proposal.

News- and strategy-generated proposals are not orders until confirmed. Confirmation rechecks strategy validity where applicable; a proposal may be invalidated if its setup has changed. A successful confirmation submits a LIMIT order through the order service, which may then remain pending rather than fill immediately.

## Strategies

- `GET /api/v1/strategies/templates` — list available templates.
- `POST /api/v1/strategies/` — create a strategy.
- `GET /api/v1/strategies/` — list the user's strategies.
- `GET /api/v1/strategies/{strategy_id}` — retrieve a strategy.
- `PATCH /api/v1/strategies/{strategy_id}` — update a strategy.
- `POST /api/v1/strategies/{strategy_id}/activate` — activate a strategy.
- `POST /api/v1/strategies/{strategy_id}/pause` — pause a strategy.
- `DELETE /api/v1/strategies/{strategy_id}` — delete a strategy.

A basic strategy request uses a recursive condition tree and an action, for example:

```json
{
  "name": "RSI example",
  "ticker": "RELIANCE.NS",
  "timeframe": "1d",
  "root_condition": {
    "type": "condition",
    "left": {"indicator": "RSI", "params": {"period": 14}},
    "operator": "<",
    "right": 30
  },
  "action": {
    "side": "BUY",
    "order_type": "MARKET",
    "quantity": 1,
    "settlement_type": "DELIVERY"
  }
}
```

Condition groups use `type: "group"`, `logic` such as `AND` or `OR`, and a `conditions` array. Strategy actions and optional options/multi-leg fields are defined by the live schema; check `/docs` for enums and required fields.

Activating a strategy enables periodic evaluation. When a condition triggers, the engine creates a trade proposal; the user must confirm it before an order is submitted. A strategy trigger is not an automatic trade. The news-risk process can pause opposing active strategies and adjust proposed size under configured rules. News controls do not create or modify orders by themselves. A news-paused strategy can resume after qualifying calm cycles or timeout; a manually paused strategy is not resumed by that process.

## News intelligence

News routes are mounted under `/api/v1/news`:

- `GET /api/v1/news/market-brief` — retrieve the current news-led brief and any conditional paper proposal.
- `POST /api/v1/news/market-brief/confirm` — revalidate and submit a specific brief proposal (requires `proposal_id` and `signal_id`).
- `GET /api/v1/news/latest?ticker=ALL&limit=10` — retrieve recent scored headlines; `ticker` may be a specific ticker and `limit` is 1–50.
- `GET /api/v1/news/sentiment?ticker=RELIANCE&window=1h` — retrieve the cached aggregate sentiment for `15m`, `1h`, or `1d`.
- `GET /api/v1/news/signal?ticker=ALL` — retrieve available signal windows/evidence for a ticker or broad market.
- `GET /api/v1/news/evaluation?days=30` — retrieve historical outcome evaluation; optional `ticker`, with `days` from 1 to 60.
- `GET /api/v1/news/alerts` — retrieve the authenticated user's in-app alerts (24-hour TTL).
- `POST /api/v1/news/advisor` — request advisory output; it does not execute trades.
- `POST /api/v1/news/journal` and `GET /api/v1/news/journal` — create/retrieve journal entries.

See `/docs` for exact payload fields and response schemas.

The impact score is a heuristic combining signed polarity, sector relevance, source credibility, and recency. The current high/medium bands use configured thresholds of 0.70 and 0.40. Scores are neither calibrated probabilities nor price predictions. English scoring uses FinBERT when available; Hindi and fallback scoring use the bilingual lexicon. News ingestion is scheduled every five minutes, so coverage and freshness depend on upstream availability and processing.

News-generated opportunities are proposals that require explicit confirmation. High-impact opposing news can pause affected strategies, and configured rules can reduce proposed size, produce alerts, and later resume news-paused strategies. It does not silently close an open position or submit an order. Exiting a position remains an explicit user request.

Historical outcome evaluation measures realized forward returns for eligible historical signals at 15-minute, 1-hour, and 1-day horizons when the required bars are available. The outcome summary is retrospective, may have incomplete samples, and reports gross returns rather than a guaranteed forecast or net trading result.

## Backtesting

Backtesting routes are mounted under `/api/v1/backtest`:

- `POST /api/v1/backtest/run` — standard historical replay; accepts query parameters and/or a JSON `BacktestRequest`.
- `POST /api/v1/backtest/walk-forward` — walk-forward evaluation (strategy ID, ticker, timeframe are query parameters).
- `GET /api/v1/backtest/` — list the user's backtests.
- `GET /api/v1/backtest/{backtest_id}` — retrieve one of the user's backtests.

The standard backtest request can identify a strategy or provide ticker, timeframe, years, conditions, and action. Results include available performance statistics such as CAGR, Sharpe, drawdown, win rate, trade count, P&L, equity, and—where applicable—in-sample/out-of-sample and walk-forward window results.

Walk-forward evaluation uses rolling three-year training and one-year test windows with a monthly step in the current implementation. Results depend on available historical bars and the simulated execution assumptions. Statistics are descriptive, not a guarantee of future performance. An efficiency ratio is a diagnostic metric, not proof that a strategy is robust.

See `/docs` for exact endpoint paths and response fields.

## Leagues

League routes are mounted under `/api/v1/league`:

- `GET /api/v1/league/` — list active and upcoming leagues; `GET /api/v1/league/all` includes completed leagues.
- `POST /api/v1/league/` — create a league.
- `POST /api/v1/league/{league_id}/join` and `GET /api/v1/league/{league_id}/leaderboard`.
- `GET /api/v1/league/my`, `GET /api/v1/league/badges/me`, and `GET /api/v1/league/{league_id}/badges`.
- `POST /api/v1/league/{league_id}/finalize` — finalize an expired active league.

League trading and results belong to the virtual portfolio environment. Check `/docs` for request schemas and status enums.

## Scheduled processing

The current Celery schedule includes:

| Task | Interval |
|---|---:|
| Cached price refresh and pending-order checks | 15 seconds |
| OHLCV synchronization | 15 minutes |
| Strategy evaluation | 60 seconds |
| News ingestion and configured news actions | 5 minutes |
| News outcome evaluation | 15 minutes |
| League finalization | Daily at midnight, Asia/Kolkata |

Schedules are worker configuration, not response-time guarantees. Tasks require the relevant worker, broker, database, and upstream sources to be available.

## Error handling

The API uses standard HTTP status codes and FastAPI validation errors for invalid requests. Authentication/authorization failures, missing resources, conflicts (including invalidated proposals), and unavailable data are reported by the relevant endpoint. Consult `/docs` and the actual response detail for a specific failure.

## Important limitations

1. The trading system is a simulator; it does not route orders to a brokerage or exchange.
2. F&O premiums and Greeks are model-derived rather than live exchange-chain data.
3. Market/news freshness and historical coverage depend on configured upstream sources, workers, and available data.
4. Impact and sentiment are heuristic/model outputs, not guaranteed outcomes or investment advice.
5. Strategy/news automation evaluates conditions and can produce risk controls and proposals, but a user confirmation is required before proposal-to-order submission.

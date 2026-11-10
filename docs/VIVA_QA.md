# TradeMind AI — Viva Questions and Answers

These answers describe the current application. Where data coverage, external feeds, or configured services affect behavior, the answer says so rather than promising a fixed result.

## 1. Architecture and application

### Q1. What is TradeMind AI?
**Answer:** TradeMind AI is a web application for Indian-market exploration, news intelligence, strategy testing, and paper trading. Orders are simulated in the application and are not routed to a broker or exchange.

### Q2. What are the main parts of the application?
**Answer:** The frontend is a React application. The backend exposes REST endpoints through FastAPI, uses Pydantic schemas for request/response validation, and persists application data through an asynchronous database layer. Redis and Celery support caching and scheduled/background work.

### Q3. Why use FastAPI?
**Answer:** FastAPI supports asynchronous request handlers, typed request validation, and generated OpenAPI documentation. Those features fit the backend's API-oriented design and make the endpoint schemas discoverable.

### Q4. What does Celery do?
**Answer:** Celery runs scheduled/background work outside the request-response path. The current schedule includes cached price refreshes and pending-order checks, OHLCV synchronization, strategy evaluation, news ingestion, outcome evaluation, and league finalization. Those intervals are scheduling configuration, not latency guarantees.

### Q5. What roles do Redis and the database have?
**Answer:** The database stores durable application records such as users, orders, strategies, and news outcomes. Redis is used for short-lived/cache or coordination state, including cached data, scheduled work infrastructure, and token/risk-control state where configured.

### Q6. Does the platform trade on a live brokerage account?
**Answer:** No. Orders and positions are part of a virtual paper-trading workflow. The application does not submit orders to NSE, BSE, or a broker.

## 2. News intelligence

### Q7. What is the project's news-intelligence feature?
**Answer:** It ingests available headlines, associates them with relevant tickers/sectors, scores sentiment, computes a signed impact measure, and presents signals, rationale, and alerts. News can also inform strategy risk controls and trade proposals.

### Q8. How is the news impact score computed?
**Answer:** The current score is heuristic: signed polarity is combined with sector relevance, source credibility, and a recency factor. The current high/medium thresholds are configured at 0.70 and 0.40. The value is not a calibrated probability, price target, or guarantee of direction.

### Q9. Does the system analyze English and Hindi headlines?
**Answer:** English scoring uses FinBERT when that model is available. Hindi and fallback scoring use a bilingual lexicon. This should not be described as FinBERT directly understanding Hindi or as a guarantee of equal coverage across languages.

### Q10. How often is news ingested?
**Answer:** The scheduled ingestion task runs every five minutes. Actual freshness and coverage depend on the upstream feed, task workers, and successful processing.

### Q11. How many headlines does the broad-market view show?
**Answer:** The latest-news endpoint defaults to ten headlines and supports `ticker=ALL` for broad-market results. Its API allows a limit from 1 to 50. The available results depend on the data ingested.

### Q12. Is sentiment the same as market impact?
**Answer:** No. Sentiment reflects the scored polarity of available text. Impact additionally accounts for sector relevance, source credibility, and recency. Neither measure guarantees a price movement.

### Q13. What happens when significant opposing news appears?
**Answer:** Under configured rules and eligibility checks, high-impact news can pause opposing active strategies; news actions can also adjust a strategy's proposed size. Medium-impact events can produce alerts. The process does not independently submit an order or close a position.

### Q14. Does the platform automatically exit an open position because of news?
**Answer:** No. The Trading page offers a user-triggered exit-on-news action. The user must choose it and confirm the exit; the engine does not silently liquidate the position.

### Q15. What does the outcome study measure?
**Answer:** It summarizes realized forward price returns for eligible historical signals at 15-minute, 1-hour, and 1-day horizons when suitable bars are stored. It is retrospective, can have incomplete samples, and reports gross returns rather than a guaranteed forecast or net return.

## 3. Strategy engine and proposals

### Q16. How is a strategy represented?
**Answer:** A strategy includes a ticker, timeframe, a recursive `root_condition` tree, and an action. Condition leaves compare indicators or values; groups combine child conditions with logic such as AND or OR. Optional fields support options and multi-leg strategies.

### Q17. What happens when a strategy is activated?
**Answer:** Activation allows the periodic evaluator to inspect the strategy's conditions. A trigger creates a trade proposal for the user; activation alone does not automatically submit a trade.

### Q18. What happens when a strategy condition triggers?
**Answer:** The engine creates a proposal containing a suggested side and order details. The user can review and confirm it. The confirmation endpoint revalidates relevant strategy conditions and context, and can invalidate an outdated proposal.

### Q19. What kind of order follows proposal confirmation?
**Answer:** Proposal confirmation submits a paper LIMIT order through the standard order service. The order can remain pending until its price conditions are met; confirmation does not guarantee an immediate fill.

### Q20. How often are strategies evaluated?
**Answer:** The scheduled strategy evaluator runs every 60 seconds in the current Celery configuration. Actual operation depends on the scheduler, worker, data, and services being available.

### Q21. How can news affect an active strategy?
**Answer:** News risk rules can pause an active strategy that conflicts with a sufficiently significant signal and can adjust the quantity multiplier used for future proposals. News-paused strategies may resume after configured calm cycles or a timeout. A strategy that the user manually paused is not automatically resumed by that news-resume logic.

## 4. Paper orders and portfolio

### Q22. Which order types are available?
**Answer:** The current order workflow supports MARKET, LIMIT, SL, and TP types. LIMIT, SL, and TP use a trigger/limit price and can stay pending for worker evaluation. Consult the API schema and Trading page for the exact fields and validation rules.

### Q23. How is a market order priced?
**Answer:** A market order uses the latest available cached price and applies 0.05% adverse slippage in the simulated fill. If a usable price is unavailable, the order may not be created.

### Q24. Are pending orders filled immediately?
**Answer:** No. Pending orders are checked by a scheduled worker, configured to run every 15 seconds. A fill depends on the price condition being met and on current price data being available.

### Q25. What happens when a user confirms an exit?
**Answer:** The manual-exit and exit-on-news endpoints submit a full-position simulated market exit for the chosen ticker. The action is initiated by the user and uses the ordinary paper-order fill path.

### Q26. How does the dashboard equity chart work?
**Answer:** The frontend reconstructs a simple cash/equity series from filled orders and their fees. The dashboard also displays portfolio summary values supplied by the backend. It should not be presented as a third-party audited statement.

### Q27. Are all fees and exchange charges guaranteed to match current statutory rates?
**Answer:** No such guarantee should be made. The paper-order service applies the fee logic configured in the current code. Rates and applicability can change and must be verified against the implementation before quoting exact figures.

### Q28. Does the portfolio summary show actual brokerage holdings?
**Answer:** No. It reports the user's virtual paper balance, simulated positions, and simulated P&L stored by this application.

## 5. Futures and options

### Q29. Is the displayed option chain a live NSE/BSE exchange chain?
**Answer:** No. The available F&O contracts are synthetically derived from cached underlying spot prices. They are useful for demonstrating a modeled chain, not for representing exchange-quoted premiums.

### Q30. How are option premiums calculated?
**Answer:** The current service uses Black–Scholes with a synthetic volatility surface and the cached underlying price as model input. Premiums therefore depend on model assumptions and source-price availability.

### Q31. How are futures prices represented?
**Answer:** Futures use a carry model based on the underlying reference price and model inputs. They are not live exchange futures quotes.

### Q32. What do option Greeks mean in the interface?
**Answer:** Delta, Gamma, Theta, and Vega are model-derived sensitivities associated with the calculated option value. They are not exchange-provided values and inherit the assumptions and limitations of the synthetic pricing model.

### Q33. Does the F&O screen show both call and put sides?
**Answer:** Yes. The chain response contains CE and PE contracts, and the interface presents the call and put sides for available strikes. Missing contracts or values can reflect the generated universe or input-data availability.

## 6. Backtesting and evaluation

### Q34. What is a standard backtest?
**Answer:** A standard backtest replays a strategy configuration against available historical OHLCV bars and returns metrics such as CAGR, Sharpe, drawdown, win rate, trade count, P&L, and equity where those results can be calculated.

### Q35. What is walk-forward testing in this application?
**Answer:** The current service uses rolling three-year training and one-year test windows with a monthly step. It evaluates across successive time windows rather than relying on one in-sample period alone.

### Q36. Does a good backtest guarantee future performance?
**Answer:** No. Historical results depend on the available bars, strategy conditions, and simulated execution assumptions. They do not guarantee future returns or account for every real-world market condition.

### Q37. What is the Efficiency Ratio shown by walk-forward results?
**Answer:** It is a diagnostic statistic reported with the walk-forward results to compare in-sample and out-of-sample behavior. It should not be treated as a universal pass/fail threshold or proof of robustness.

### Q38. Why might a backtest have zero trades or fail?
**Answer:** The selected period may lack sufficient historical bars, the ticker/timeframe may not be supported by available data, or the strategy conditions may not have triggered. The result/error shown by the application should be checked rather than assuming the strategy executed.

## 7. Authentication, data, and operations

### Q39. How does a user authenticate?
**Answer:** Users register with an email, username, and password of at least eight characters, then log in using email and password. Protected API endpoints use bearer access tokens.

### Q40. What are the configured token lifetimes?
**Answer:** The current defaults are a 30-minute access token and a 7-day refresh token. Deployment configuration can affect runtime values; these defaults are not a claim that every deployment has identical settings.

### Q41. How does logout work?
**Answer:** The logout endpoint blacklists the authenticated access token's identifier in Redis until its remaining lifetime expires, allowing protected requests to reject that token after logout.

### Q42. Does every API require authentication?
**Answer:** Most application data and trading endpoints require an authenticated user. Registration, login, refresh, and health checks have their own access behavior; consult the route definitions or generated `/docs`.

### Q43. How often are prices and OHLCV data refreshed?
**Answer:** Price refresh and pending-order checks are configured every 15 seconds. OHLCV synchronization is configured every 15 minutes. These are scheduled attempts, not a guarantee of live or complete market data.

### Q44. Why might market, news, or backtest results be missing?
**Answer:** External data sources may be unavailable or delayed, a background worker may not be running, or there may not yet be suitable data for the selected ticker, period, or signal. The UI and API can therefore legitimately show empty results or an unavailable-data message.

## 8. User interface and limitations

### Q45. Which main views are available in the frontend?
**Answer:** The current routed application includes Dashboard, Trading, F&O, Strategies, News Intelligence, League, and Profile pages, plus login and registration.

### Q46. What does the Strategy Advisor do?
**Answer:** It provides advisory text based on supplied news or strategy context. It is not the order engine and does not execute a trade.

### Q47. What does the league leaderboard represent?
**Answer:** It displays virtual competition results and available metrics for users who joined. Entries, rankings, or badges can be empty until there is participation and the relevant league activity/finalization.

### Q48. What is the main safety boundary in automated trading?
**Answer:** Strategy and news processing can evaluate conditions, apply configured strategy-risk controls, and generate proposals. A user confirmation is required before a proposal submits a paper order; the application does not place a broker order.

### Q49. What should be disclosed when presenting the application?
**Answer:** Disclose that it is paper trading; market/news freshness and historical coverage vary; F&O prices/Greeks are synthetic; news scores are heuristic; and backtests/outcome studies do not guarantee future performance.

### Q50. What is the project's central contribution?
**Answer:** The project brings news context, sentiment/impact scoring, historical evaluation, strategy safeguards, and a confirmation-gated simulated trading workflow into one application. Its value is an integrated research and learning workflow, not a claim of guaranteed market prediction or autonomous live execution.

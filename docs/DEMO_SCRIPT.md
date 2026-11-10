# TradeMind AI — 5-Minute Demonstration Script

**Purpose:** Demonstrate the application's current paper-trading, news-intelligence, strategy, derivatives, and league workflows without implying live brokerage execution or guaranteed market predictions.

**Before recording:** Start the application and sign in with a prepared demo account. Confirm backend, database, cache, and scheduled workers are running. Market/news content and historical bars depend on the configured sources and may be missing or stale. Do not rely on a particular signal, alert, proposal, fill, or leaderboard entry appearing on demand.

## 0:00–0:30 — Introduction

**Show:** The login page, then sign in and open the dashboard.

**Say:**
> “TradeMind AI is a web-based paper-trading application for exploring Indian-market data, news signals, simulated orders, and rule-based strategies. It combines news context with trading tools, while keeping order submission in the user's hands. It does not connect to a brokerage or guarantee investment returns.”

## 0:30–1:05 — Dashboard and portfolio

**Show:** Dashboard overview, portfolio cards, equity chart, open positions, and quick links.

**Say:**
> “The dashboard summarizes this account's virtual cash, net worth, realised and unrealised P&L, and open positions. Its equity chart is reconstructed from filled paper orders, so the values depend on this account's activity. The ticker strip and market information are supplied from the application's market-data cache and can be delayed or unavailable.”

If the account has no trades, explain that the empty position list or starting chart is expected rather than inventing activity.

## 1:05–1:55 — News Intelligence

**Show:** Open **News Intelligence**. Keep the ticker selector on **ALL** to view recent broad-market headlines, then select a ticker if one is available. Point out article sentiment/impact, market signal, alerts, advisor, and the outcome study.

**Say:**
> “News Intelligence brings together available headlines, sentiment, and a signed impact score. The impact is a heuristic using polarity, sector relevance, source credibility, and recency; it is not a probability or price target. The advisor provides analysis, not execution. The outcome study looks backward at eligible historical signals and subsequent price returns; its results depend on stored bars and are not a forecast.”

If no current headlines or historical outcomes are available, state that the relevant feed or qualifying sample is currently empty; do not substitute a fabricated signal.

## 1:55–2:35 — User-confirmed proposals and simulated order entry

**Show:** Return to the dashboard's market-brief and strategy-proposal panel. If a valid proposal is already available, review its ticker, direction, rationale, and expiry. Demonstrate confirmation only if the prepared demo account is intended for a state-changing test. Otherwise, explain the flow without submitting an order. Then open the Trading page to show the order form and order/position history.

**Say:**
> “A strategy or news setup can create a trade proposal, but it is not an order. A user must confirm it. The backend revalidates the setup at confirmation; if the conditions have changed, it can invalidate the proposal. Confirmation submits a paper LIMIT order, which can remain pending. In the Trading page, a user can also submit a simulated order directly. A market order uses the cached price and configured adverse slippage; limit-style orders wait for their trigger.”

Mention that manual exit and exit-on-news are explicit user actions. Do not demonstrate a trade using an account unless the presenter has approved that state change.

## 2:35–3:05 — Futures and options

**Show:** Open **F&O**, select an available underlying, and display the CE and PE sides of the option chain and their available calculated values.

**Say:**
> “The F&O view shows both call and put contracts with model-derived premiums and available Greeks. These are synthetic calculations based on cached underlying prices, a carry model for futures, and Black–Scholes with a synthetic volatility surface. They are not live NSE/BSE option-chain quotes or exchange-provided Greeks.”

Do not claim a fixed number of contracts; available underlyings, expiries, and strikes depend on the current response.

## 3:05–4:20 — Strategy builder and testing

**Show:** Open **Strategies**. Select a template or prepare a simple indicator condition, show the AND/OR condition builder and action, and use **Backtest Strategy** or **Run Walk-Forward** if historical data is available. Briefly show the activate/pause controls.

**Say:**
> “Strategies are built from conditions and an action. The application can run a standard historical replay and a walk-forward test; these results depend on available bars and simulated execution assumptions. Walk-forward uses rolling three-year training and one-year test windows with a monthly step. These metrics are diagnostics, not proof of future performance.”
>
> “Activating a strategy enables periodic evaluation. A trigger creates a proposal for the user to review and confirm; it does not submit a trade automatically. News-risk controls can pause an opposing strategy or adjust proposed size under configured rules. They do not silently change or close orders.”

If the test reports insufficient history or no trades, explain that outcome as a data/condition result and do not present it as a successful backtest.

## 4:20–4:45 — League

**Show:** Open **League**, review available competitions, and show a leaderboard or the user's entries/badges if present.

**Say:**
> “The League page displays available virtual trading competitions, their participants, performance metrics, and any earned badges. A leaderboard or badge list may be empty until users join and the relevant activity or league finalization occurs.”

## 4:45–5:00 — Close

**Show:** Return to the dashboard.

**Say:**
> “TradeMind AI combines market context, historical analysis, strategy evaluation, and a confirmation-gated paper-trading workflow. Its outputs are research and simulation aids; market-data coverage and historical samples vary, and the application does not provide guaranteed predictions or execute trades with a broker. Thank you.”

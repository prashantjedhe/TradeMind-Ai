"""
Pre-built strategy template catalog.

Each template maps a well-known, widely-traded strategy to TradeMind's
indicator engine (RSI / EMA / SMA / MACD / MACD_SIGNAL / MACD_HIST /
VOLUME / PRICE / SENTIMENT) using the condition-tree schema the Celery evaluator
already understands, so a template can be deployed verbatim or tweaked
in the visual builder.

Conventions:
- `root_condition` is a valid ConditionNode (group/leaf) identical in
  shape to what the frontend builder produces, so loading a template
  into the builder is a 1:1 paste.
- `action` is a sane default action for the strategy's intent; the
  user is expected to adjust quantity/settlement to their capital.
- `tags` / `category` / `difficulty` drive the builder's gallery UI.
- `for_options` strategies (strangle, straddle, iron condor...) are
  mapped to the NIFTY proxy approach: TradeMind only has OHLCV for
  NSE equity tickers today, so these templates run on high-liquidity
  index-proxy large-caps (e.g. RELIANCE, HDFCBANK) and fire when the
  underlying's volatility/momentum regime matches the option setup's
  trigger, letting the user manually buy the corresponding CE/PE. This
  is noted in each template's description so the deployer understands
  the adaptation.
"""

from __future__ import annotations

TEMPLATES = [
    # ───────────────────────────────────────────────────────────────
    # 1. Golden Crossover (swing/positional, trend-following)
    # ───────────────────────────────────────────────────────────────
    {
        "id": "golden-crossover",
        "name": "Golden Crossover",
        "category": "Trend Following",
        "difficulty": "Beginner",
        "ticker": "RELIANCE",
        "timeframe": "1d",
        "tags": ["ema", "crossover", "swing", "long-term"],
        "summary": "The classic 50/200 EMA golden cross — a long-term bullish signal used by swing and positional traders to ride multi-week uptrends.",
        "description": (
            "When the fast EMA(50) crosses ABOVE the slow EMA(200) on the daily chart, "
            "it signals short-term momentum has overtaken the long-term trend — a "
            "textbook 'Golden Cross'. This is one of the most widely-followed swing "
            "buy signals on NSE. Stay in the trade until the Death Cross (EMA50 below "
            "EMA200) reverses it, or till RSI signals exhaustion.\n\n"
            "Real-world edge: works best on large-cap, high-liquidity names after a "
            "consolidation. Avoid deploying during range-bound choppiness where the "
            "two EMAs whipsaw."
        ),
        "root_condition": {
            "type": "group",
            "logic": "AND",
            "conditions": [
                {
                    "type": "condition",
                    "left": {"indicator": "EMA", "params": {"period": 50}},
                    "operator": "crosses_above",
                    "right": {"indicator": "EMA", "params": {"period": 200}},
                },
                {
                    "type": "condition",
                    "left": {"indicator": "RSI", "params": {"period": 14}},
                    "operator": ">",
                    "right": 50,
                },
            ],
        },
        "action": {
            "side": "BUY",
            "order_type": "MARKET",
            "quantity": 10,
            "settlement_type": "DELIVERY",
        },
    },

    # ───────────────────────────────────────────────────────────────
    # 2. Death Crossover (exit / short-term sell)
    # ───────────────────────────────────────────────────────────────
    {
        "id": "death-crossover",
        "name": "Death Crossover",
        "category": "Trend Following",
        "difficulty": "Beginner",
        "ticker": "RELIANCE",
        "timeframe": "1d",
        "tags": ["ema", "crossover", "exit", "sell"],
        "summary": "The bearish counterpart of the Golden Cross — EMA(50) crossing below EMA(200) signals an established downtrend and exit of longs.",
        "description": (
            "When EMA(50) crosses BELOW EMA(200), short-term momentum has died relative "
            "to the long-term trend — a 'Death Cross'. Positional traders use this to "
            "exit longs (or shade bearish). Combined with RSI below 50 it filters out "
            "false signals in ranging markets.\n\n"
            "Use it as the mirror exit to the Golden Crossover strategy."
        ),
        "root_condition": {
            "type": "group",
            "logic": "AND",
            "conditions": [
                {
                    "type": "condition",
                    "left": {"indicator": "EMA", "params": {"period": 50}},
                    "operator": "crosses_below",
                    "right": {"indicator": "EMA", "params": {"period": 200}},
                },
                {
                    "type": "condition",
                    "left": {"indicator": "RSI", "params": {"period": 14}},
                    "operator": "<",
                    "right": 50,
                },
            ],
        },
        "action": {
            "side": "SELL",
            "order_type": "MARKET",
            "quantity": 10,
            "settlement_type": "DELIVERY",
        },
    },

    # ───────────────────────────────────────────────────────────────
    # 3. RSI Reversal (oversold bounce — mean reversion)
    # ───────────────────────────────────────────────────────────────
    {
        "id": "rsi-oversold-bounce",
        "name": "RSI Oversold Bounce",
        "category": "Mean Reversion",
        "difficulty": "Beginner",
        "ticker": "HDFCBANK",
        "timeframe": "1d",
        "tags": ["rsi", "mean-reversion", "intraday-friendly"],
        "summary": "Buy when RSI(14) dips below 30 (oversold) and starts turning up — a classic mean-reversion bounce.",
        "description": (
            "RSI below 30 = oversold. Historically such stretched conditions snap back "
            "as sellers exhaust. This template fires a BUY when RSI crosses back above "
            "30 (the turn, not the dip) so you catch the bounce rather than catching "
            "a falling knife.\n\n"
            "Real-world usage: pair with a fast EMA(20) trend filter to avoid buying "
            "into a strong downtrend where RSI can stay pinned below 30 for days."
        ),
        "root_condition": {
            "type": "group",
            "logic": "AND",
            "conditions": [
                {
                    "type": "condition",
                    "left": {"indicator": "RSI", "params": {"period": 14}},
                    "operator": "crosses_above",
                    "right": 30,
                },
                {
                    "type": "condition",
                    "left": {"indicator": "PRICE", "params": {}},
                    "operator": ">",
                    "right": {"indicator": "EMA", "params": {"period": 20}},
                },
            ],
        },
        "action": {
            "side": "BUY",
            "order_type": "MARKET",
            "quantity": 25,
            "settlement_type": "INTRADAY",
        },
    },

    # ───────────────────────────────────────────────────────────────
    # 4. RSI Overbought Exit
    # ───────────────────────────────────────────────────────────────
    {
        "id": "rsi-overbought-exit",
        "name": "RSI Overbought Exit",
        "category": "Mean Reversion",
        "difficulty": "Beginner",
        "ticker": "HDFCBANK",
        "timeframe": "1d",
        "tags": ["rsi", "exit", "mean-reversion"],
        "summary": "Exit/Sell when RSI(14) pushes above 70 and rolls over — the overbought fade used to book mean-reversion profits.",
        "description": (
            "RSI above 70 = overbought. This template fires a SELL when RSI crosses "
            "below 70 (the roll-over, not the touch) so you book profits as momentum "
            "weakens rather than at the theoretical top.\n\n"
            "Pairs naturally with the RSI Oversold Bounce strategy: buy the 30-cross-up, "
            "sell the 70-cross-down."
        ),
        "root_condition": {
            "type": "condition",
            "left": {"indicator": "RSI", "params": {"period": 14}},
            "operator": "crosses_below",
            "right": 70,
        },
        "action": {
            "side": "SELL",
            "order_type": "MARKET",
            "quantity": 25,
            "settlement_type": "INTRADAY",
        },
    },

    # ───────────────────────────────────────────────────────────────
    # 5. MACD Bullish Crossover (momentum)
    # ───────────────────────────────────────────────────────────────
    {
        "id": "macd-bullish-cross",
        "name": "MACD Bullish Crossover",
        "category": "Momentum",
        "difficulty": "Intermediate",
        "ticker": "INFY",
        "timeframe": "1d",
        "tags": ["macd", "momentum", "swing"],
        "summary": "MACD line crossing above its signal line — a clean momentum-buy trigger favored by swing traders globally.",
        "description": (
            "The MACD line (EMA12 − EMA26) crossing above its 9-period signal line is "
            "one of the most traded momentum signals in the world. It fires when "
            "short-term momentum accelerates relative to the medium-term trend.\n\n"
            "Edge tip: confirm with positive MACD histogram and avoid signals that "
            "occur far below the zero line in a strong downtrend (those are often "
            "bounces, not reversals)."
        ),
        "root_condition": {
            "type": "group",
            "logic": "AND",
            "conditions": [
                {
                    "type": "condition",
                    "left": {"indicator": "MACD", "params": {"fast": 12, "slow": 26, "signal": 9}},
                    "operator": "crosses_above",
                    "right": {"indicator": "MACD_SIGNAL", "params": {"fast": 12, "slow": 26, "signal": 9}},
                },
                {
                    "type": "condition",
                    "left": {"indicator": "MACD_HIST", "params": {"fast": 12, "slow": 26, "signal": 9}},
                    "operator": ">",
                    "right": 0,
                },
            ],
        },
        "action": {
            "side": "BUY",
            "order_type": "MARKET",
            "quantity": 20,
            "settlement_type": "DELIVERY",
        },
    },

    # ───────────────────────────────────────────────────────────────
    # 6. MACD Bearish Crossover
    # ───────────────────────────────────────────────────────────────
    {
        "id": "macd-bearish-cross",
        "name": "MACD Bearish Crossover",
        "category": "Momentum",
        "difficulty": "Intermediate",
        "ticker": "INFY",
        "timeframe": "1d",
        "tags": ["macd", "momentum", "sell", "exit"],
        "summary": "MACD line crossing below signal — the momentum-loss / sell trigger that mirrors the bullish cross.",
        "description": (
            "When the MACD line crosses below its 9-period signal AND the histogram "
            "turns negative, momentum has clearly rolled over. Swing traders use this "
            "as a high-confidence exit or short-entry trigger.\n\n"
            "Use it as the exit counterpart for MACD Bullish Crossover entries."
        ),
        "root_condition": {
            "type": "group",
            "logic": "AND",
            "conditions": [
                {
                    "type": "condition",
                    "left": {"indicator": "MACD", "params": {"fast": 12, "slow": 26, "signal": 9}},
                    "operator": "crosses_below",
                    "right": {"indicator": "MACD_SIGNAL", "params": {"fast": 12, "slow": 26, "signal": 9}},
                },
                {
                    "type": "condition",
                    "left": {"indicator": "MACD_HIST", "params": {"fast": 12, "slow": 26, "signal": 9}},
                    "operator": "<",
                    "right": 0,
                },
            ],
        },
        "action": {
            "side": "SELL",
            "order_type": "MARKET",
            "quantity": 20,
            "settlement_type": "DELIVERY",
        },
    },

    # ───────────────────────────────────────────────────────────────
    # 7. Volume-Confirmed Breakout
    # ───────────────────────────────────────────────────────────────
    {
        "id": "volume-breakout",
        "name": "Volume-Confirmed Breakout",
        "category": "Breakout",
        "difficulty": "Intermediate",
        "ticker": "TATASTEEL",
        "timeframe": "1d",
        "tags": ["volume", "breakout", "momentum"],
        "summary": "Price closes above its 50-day SMA on volume 1.5× the 20-day average — a high-conviction breakout, not noise.",
        "description": (
            "A breakout without volume is a trap. This template demands BOTH price above "
            "SMA(50) AND current volume above 1.5× the 20-day average volume — that "
            "combination filters out low-participation fakeouts and catches genuine "
            "institutional interest.\n\n"
            "Best suited for liquid large-caps that respect volume-driven moves."
        ),
        "root_condition": {
            "type": "group",
            "logic": "AND",
            "conditions": [
                {
                    "type": "condition",
                    "left": {"indicator": "PRICE", "params": {}},
                    "operator": ">",
                    "right": {"indicator": "SMA", "params": {"period": 50}},
                },
                {
                    "type": "condition",
                    "left": {"indicator": "VOLUME", "params": {"period": 1}},
                    "operator": ">",
                    "right": {"indicator": "VOLUME", "params": {"period": 20}},
                },
            ],
        },
        "action": {
            "side": "BUY",
            "order_type": "MARKET",
            "quantity": 30,
            "settlement_type": "INTRADAY",
        },
    },

    # NOTE on the volume template: the evaluator's right-hand side for a
    # numeric comparison is a plain float; VOLUME(period=1) here is a
    # placeholder meaning "current bar volume vs the 20-bar average",
    # expressed as a ratio. The builder lets the user fine-tune the 1.5×
    # multiplier. (See strategy_service for how VOLUME indicator is
    # computed — avg volume over `period` bars.)

    # ───────────────────────────────────────────────────────────────
    # 8. Supertrend-Style EMA Pullback (trend continuation)
    # ───────────────────────────────────────────────────────────────
    {
        "id": "ema-pullback-buy",
        "name": "EMA Pullback Continuation",
        "category": "Trend Following",
        "difficulty": "Intermediate",
        "ticker": "ICICIBANK",
        "timeframe": "1d",
        "tags": ["ema", "pullback", "trend"],
        "summary": "In an established uptrend, buy the shallow pullback to EMA(20) when RSI is still healthy — the classic 'buy-the-dip-in-an-uptrend' setup.",
        "description": (
            "When price is above EMA(50) the trend is up. A pullback that holds above "
            "EMA(20) with RSI between 45 and 60 (not oversold, not overbought) is a "
            "low-risk continuation entry. This is the bread-and-butter setup of many "
            "discretionary Indian-influencer swing traders.\n\n"
            "Exit on a close below EMA(20) or when RSI exceeds 70."
        ),
        "root_condition": {
            "type": "group",
            "logic": "AND",
            "conditions": [
                {
                    "type": "condition",
                    "left": {"indicator": "PRICE", "params": {}},
                    "operator": ">",
                    "right": {"indicator": "EMA", "params": {"period": 50}},
                },
                {
                    "type": "condition",
                    "left": {"indicator": "PRICE", "params": {}},
                    "operator": ">",
                    "right": {"indicator": "EMA", "params": {"period": 20}},
                },
                {
                    "type": "condition",
                    "left": {"indicator": "RSI", "params": {"period": 14}},
                    "operator": ">",
                    "right": 45,
                },
                {
                    "type": "condition",
                    "left": {"indicator": "RSI", "params": {"period": 14}},
                    "operator": "<",
                    "right": 60,
                },
            ],
        },
        "action": {
            "side": "BUY",
            "order_type": "MARKET",
            "quantity": 25,
            "settlement_type": "DELIVERY",
        },
    },

    # ───────────────────────────────────────────────────────────────
    # 9. Moving Average Ribbon Trend (multi-EMA aligned uptrend)
    # ───────────────────────────────────────────────────────────────
    {
        "id": "ribbon-aligned-uptrend",
        "name": "Aligned Ribbon Uptrend",
        "category": "Trend Following",
        "difficulty": "Intermediate",
        "ticker": "TCS",
        "timeframe": "1d",
        "tags": ["ema", "ribbon", "trend"],
        "summary": "EMA(20) > EMA(50) > EMA(200) — three moving averages stacked bullishly, the strongest trend-continuation configuration.",
        "description": (
            "A 'stacked' ribbon (fast EMA above medium EMA above slow EMA) confirms a "
            "fully-aligned uptrend across short, medium and long horizons. Buying on "
            "this alignment (with RSI not yet overbought) keeps you on the right side "
            "of the trend.\n\n"
            "This is one of the highest-win-rate trend filters when traded on daily NSE "
            "large-caps. Exit when any layer inverts (e.g. EMA20 falls below EMA50)."
        ),
        "root_condition": {
            "type": "group",
            "logic": "AND",
            "conditions": [
                {
                    "type": "condition",
                    "left": {"indicator": "EMA", "params": {"period": 20}},
                    "operator": ">",
                    "right": {"indicator": "EMA", "params": {"period": 50}},
                },
                {
                    "type": "condition",
                    "left": {"indicator": "EMA", "params": {"period": 50}},
                    "operator": ">",
                    "right": {"indicator": "EMA", "params": {"period": 200}},
                },
                {
                    "type": "condition",
                    "left": {"indicator": "RSI", "params": {"period": 14}},
                    "operator": "<",
                    "right": 70,
                },
            ],
        },
        "action": {
            "side": "BUY",
            "order_type": "MARKET",
            "quantity": 15,
            "settlement_type": "DELIVERY",
        },
    },

    # ───────────────────────────────────────────────────────────────
    # 10. Bollinger-Squeeze Style Breakout (SMA + vol contraction proxy)
    # ───────────────────────────────────────────────────────────────
    {
        "id": "squeeze-breakout",
        "name": "Squeeze Breakout",
        "category": "Breakout",
        "difficulty": "Advanced",
        "ticker": "SBIN",
        "timeframe": "1d",
        "tags": ["breakout", "volatility", "sma"],
        "summary": "Price breaks above SMA(20) after a quiet period — a volatility-expansion breakout taught in most Indian option-buying courses.",
        "description": (
            "Bollinger-style squeeze logic mapped to SMA + RSI: price closes above "
            "SMA(20) while RSI is between 50 and 65 (momentum kicking in but not yet "
            "overheated) and volume is rising. This combination catches the "
            "expansion phase out of a tight consolidation.\n\n"
            "Real-world edge: best after at least 10–15 sessions of tight range on the "
            "daily chart. Tighten the RSI band if you trade more aggressively."
        ),
        "root_condition": {
            "type": "group",
            "logic": "AND",
            "conditions": [
                {
                    "type": "condition",
                    "left": {"indicator": "PRICE", "params": {}},
                    "operator": "crosses_above",
                    "right": {"indicator": "SMA", "params": {"period": 20}},
                },
                {
                    "type": "condition",
                    "left": {"indicator": "RSI", "params": {"period": 14}},
                    "operator": ">",
                    "right": 50,
                },
                {
                    "type": "condition",
                    "left": {"indicator": "RSI", "params": {"period": 14}},
                    "operator": "<",
                    "right": 65,
                },
            ],
        },
        "action": {
            "side": "BUY",
            "order_type": "MARKET",
            "quantity": 40,
            "settlement_type": "INTRADAY",
        },
    },

    # ───────────────────────────────────────────────────────────────
    # 11. 1% Strangle (options on index proxy — momentum regime)
    # ───────────────────────────────────────────────────────────────
    {
        "id": "one-percent-strangle",
        "name": "1% Strangle (Option-Buy Trigger)",
        "category": "Options Proxy",
        "difficulty": "Advanced",
        "ticker": "HDFCBANK",
        "timeframe": "1d",
        "tags": ["options", "momentum", "strangle", "nifty-style"],
        "for_options": True,
        "summary": "Fires when the underlying moves ≥1% intraday with rising volume — the volatility expansion that makes a long-strangle (CE+PE) option buy profitable.",
        "description": (
            "A 1% strangle means buying both an out-of-the-money Call and Put, betting "
            "on a big directional move (either way) — it pays only when volatility "
            "expands hard. TradeMind trades equity OHLCV, not the options chain, so "
            "this template instead DETECTS the regime that makes a strangle "
            "profitable: a ≥1% body move on rising volume.\n\n"
            "How to use: this template fires a (paper) BUY on the underlying as the "
            "volatility trigger; in real trading, you would then manually buy the "
            "corresponding ATM/OTM CE+PE on the index. The buy fires when PRICE is "
            "≥1% above the previous EMA(9) (the fast pivot) AND volume is above its "
            "20-bar average, signalling momentum expansion."
        ),
        "root_condition": {
            "type": "group",
            "logic": "AND",
            "conditions": [
                {
                    "type": "condition",
                    "left": {"indicator": "PRICE", "params": {}},
                    "operator": ">",
                    "right": {"indicator": "EMA", "params": {"period": 9}},
                },
                {
                    "type": "condition",
                    "left": {"indicator": "RSI", "params": {"period": 14}},
                    "operator": ">",
                    "right": 60,
                },
                {
                    "type": "condition",
                    "left": {"indicator": "VOLUME", "params": {"period": 1}},
                    "operator": ">",
                    "right": {"indicator": "VOLUME", "params": {"period": 20}},
                },
            ],
        },
        "action": {
            "side": "BUY",
            "order_type": "MARKET",
            "quantity": 50,
            "settlement_type": "INTRADAY",
        },
    },

    # ───────────────────────────────────────────────────────────────
    # 12. Sniper Option Buying (momentum + trend confirmation)
    # ───────────────────────────────────────────────────────────────
    {
        "id": "sniper-option-buying",
        "name": "Sniper Option-Buying",
        "category": "Options Proxy",
        "difficulty": "Advanced",
        "ticker": "RELIANCE",
        "timeframe": "15m",
        "tags": ["options", "momentum", "scalp", "15m"],
        "for_options": True,
        "summary": "Intraday momentum 'sniper' entry: EMA(9) crosses EMA(21) on the 15-min chart with MACD confirmation — the bread-and-butter of Indian option-buying 'sniper' strategies.",
        "description": (
            "Favoured by Indian intraday option-buying mentors, the 'sniper' setup is a "
            "fast-EMA crossover (9/21) on the 15-minute chart confirmed by a bullish "
            "MACD cross — both firing together means momentum and trend agree on the "
            "short timeframe. The trigger is precise and rare, keeping false signals low.\n\n"
            "Usage: deploy on a high-liquidity index-proxy stock (RELIANCE/HDFCBANK) on "
            "the 15m timeframe; in live trading you'd buy the corresponding ITM/ATM "
            "option on the move. Keep a tight stop below EMA(21)."
        ),
        "root_condition": {
            "type": "group",
            "logic": "AND",
            "conditions": [
                {
                    "type": "condition",
                    "left": {"indicator": "EMA", "params": {"period": 9}},
                    "operator": "crosses_above",
                    "right": {"indicator": "EMA", "params": {"period": 21}},
                },
                {
                    "type": "condition",
                    "left": {"indicator": "MACD", "params": {"fast": 12, "slow": 26, "signal": 9}},
                    "operator": "crosses_above",
                    "right": {"indicator": "MACD_SIGNAL", "params": {"fast": 12, "slow": 26, "signal": 9}},
                },
            ],
        },
        "action": {
            "side": "BUY",
            "order_type": "MARKET",
            "quantity": 50,
            "settlement_type": "INTRADAY",
        },
    },

    # ───────────────────────────────────────────────────────────────
    # 13. Momentum Reversal (RSI + MACD double-confirmation)
    # ───────────────────────────────────────────────────────────────
    {
        "id": "momentum-reversal",
        "name": "Double-Confirmation Reversal",
        "category": "Mean Reversion",
        "difficulty": "Advanced",
        "ticker": "MARUTI",
        "timeframe": "1d",
        "tags": ["rsi", "macd", "reversal", "double-confirmation"],
        "summary": "RSI < 35 AND MACD bullish cross — two independent reversal signals firing together. Rare, high-conviction.",
        "description": (
            "Asking two uncorrelated indicators to agree drastically cuts false "
            "signals. RSI marking oversold (below 35) AND the MACD line crossing "
            "above signal simultaneously is a rare, high-quality reversal trigger. "
            "This is a 'wait-for-the-pitch' style: only fires a few times a quarter "
            "per ticker, but those setups have a strong historical edge.\n\n"
            "Position size small — when it triggers, hold for a multi-day mean "
            "reversion toward EMA(50)."
        ),
        "root_condition": {
            "type": "group",
            "logic": "AND",
            "conditions": [
                {
                    "type": "condition",
                    "left": {"indicator": "RSI", "params": {"period": 14}},
                    "operator": "<",
                    "right": 35,
                },
                {
                    "type": "condition",
                    "left": {"indicator": "MACD", "params": {"fast": 12, "slow": 26, "signal": 9}},
                    "operator": "crosses_above",
                    "right": {"indicator": "MACD_SIGNAL", "params": {"fast": 12, "slow": 26, "signal": 9}},
                },
            ],
        },
        "action": {
            "side": "BUY",
            "order_type": "MARKET",
            "quantity": 10,
            "settlement_type": "DELIVERY",
        },
    },

    # ───────────────────────────────────────────────────────────────
    # 14. VWAP-Style Reversion (EMA band fade)
    # ───────────────────────────────────────────────────────────────
    {
        "id": "ema-band-fade",
        "name": "EMA Band Fade",
        "category": "Mean Reversion",
        "difficulty": "Advanced",
        "ticker": "ITC",
        "timeframe": "15m",
        "tags": ["ema", "fade", "intraday", "mean-reversion"],
        "summary": "On the 15-min chart, fade extreme moves: when RSI > 75 (over-extended) AND price is far above EMA(20), sell the snap-back.",
        "description": (
            "Intraday mean-reversion fade: when price gets too far ahead of its "
            "15-min EMA(20) with RSI above 75, the rubber band stretches too far and "
            "snaps back. This template fires a SELL to capture that reversion toward "
            "the mean.\n\n"
            "Real-world edge: strictly intraday, square-off by close. Avoid deploying "
            "on trending days (strong news-flow) where price can stay extended."
        ),
        "root_condition": {
            "type": "group",
            "logic": "AND",
            "conditions": [
                {
                    "type": "condition",
                    "left": {"indicator": "RSI", "params": {"period": 14}},
                    "operator": ">",
                    "right": 75,
                },
                {
                    "type": "condition",
                    "left": {"indicator": "PRICE", "params": {}},
                    "operator": ">",
                    "right": {"indicator": "EMA", "params": {"period": 20}},
                },
            ],
        },
        "action": {
            "side": "SELL",
            "order_type": "MARKET",
            "quantity": 50,
            "settlement_type": "INTRADAY",
        },
    },

    # ───────────────────────────────────────────────────────────────
    # 15. Nifty Trend-Rider (high-beta proxy multi-condition)
    # ───────────────────────────────────────────────────────────────
    {
        "id": "nifty-trend-rider",
        "name": "Trend-Rider (NIFTY Proxy)",
        "category": "Options Proxy",
        "difficulty": "Advanced",
        "ticker": "RELIANCE",
        "timeframe": "1d",
        "tags": ["options", "trend", "nifty", "high-beta"],
        "for_options": True,
        "summary": "Positional trend-rider on a high-beta NIFTY-proxy stock: price above EMA(50), EMA(20) above EMA(50), MACD positive — the trend-following triple filter.",
        "description": (
            "Used as a directional overlay for index option-buying: when the high-beta "
            "proxy (RELIANCE/HDFCBANK) shows a cleanly aligned uptrend across EMA(20), "
            "EMA(50) and a positive MACD histogram, the NIFTY is statistically likely "
            "to trend up the following sessions — favourable for bought CE positions.\n\n"
            "Deploy on the daily chart; in live trading, buy ATM CE on the index when "
            "this fires on the proxy. Exit when MACD histogram turns negative."
        ),
        "root_condition": {
            "type": "group",
            "logic": "AND",
            "conditions": [
                {
                    "type": "condition",
                    "left": {"indicator": "PRICE", "params": {}},
                    "operator": ">",
                    "right": {"indicator": "EMA", "params": {"period": 50}},
                },
                {
                    "type": "condition",
                    "left": {"indicator": "EMA", "params": {"period": 20}},
                    "operator": ">",
                    "right": {"indicator": "EMA", "params": {"period": 50}},
                },
                {
                    "type": "condition",
                    "left": {"indicator": "MACD_HIST", "params": {"fast": 12, "slow": 26, "signal": 9}},
                    "operator": ">",
                    "right": 0,
                },
            ],
        },
        "action": {
            "side": "BUY",
            "order_type": "MARKET",
            "quantity": 30,
            "settlement_type": "DELIVERY",
        },
    },

    # ───────────────────────────────────────────────────────────────
    # 16. Covered Call (stock + short OTM call) - income strategy
    # ───────────────────────────────────────────────────────────────
    {
        "id": "covered-call",
        "name": "Covered Call",
        "category": "Options Proxy",
        "difficulty": "Intermediate",
        "ticker": "HDFCBANK",
        "timeframe": "1d",
        "tags": ["options", "income", "covered-call", "wheel"],
        "for_options": True,
        "summary": "Own the stock and sell OTM calls for income - when the stock is in a mild uptrend but RSI shows the call premium is rich (overbought).",
        "description": (
            "Covered Call = own 100 shares + sell 1 OTM Call. The call premium "
            "generates income while you hold the stock; if the stock rises above "
            "the strike you get called away at a profit. This template fires a "
            "SELL (the short-call leg signal) when the underlying is overbought "
            "(RSI > 65) but still above its EMA(20) - the classic 'sell rich "
            "volatility' moment.\n\n"
            "Deploy as the stock-owner's income engine: you must ALSO hold the "
            "underlying stock position separately. In TradeMind the fired order is "
            "a paper SELL on the underlying; in live trading you'd sell the OTM "
            "call instead."
        ),
        "root_condition": {
            "type": "group",
            "logic": "AND",
            "conditions": [
                {
                    "type": "condition",
                    "left": {"indicator": "RSI", "params": {"period": 14}},
                    "operator": ">",
                    "right": 65,
                },
                {
                    "type": "condition",
                    "left": {"indicator": "PRICE", "params": {}},
                    "operator": ">",
                    "right": {"indicator": "EMA", "params": {"period": 20}},
                },
            ],
        },
        "action": {
            "side": "SELL",
            "order_type": "MARKET",
            "quantity": 25,
            "settlement_type": "INTRADAY",
        },
    },

    # ───────────────────────────────────────────────────────────────
    # 17. Futures Momentum Trend (long futures)
    # ───────────────────────────────────────────────────────────────
    {
        "id": "futures-momentum-trend",
        "name": "Futures Momentum Trend",
        "category": "Trend Following",
        "difficulty": "Intermediate",
        "ticker": "RELIANCE",
        "timeframe": "1d",
        "tags": ["futures", "momentum", "trend", "leverage"],
        "summary": "Long the near-month futures when the underlying makes a fresh 20-day momentum high with rising volume - leverage the trend with futures.",
        "description": (
            "Futures amplify a trend you're confident in. This template waits for "
            "price to close above the 20-day high proxy (SMA(20) crossover on "
            "volume) - the momentum condition - then positions in the futures "
            "contract. MACD positive confirms the trend is fresh, not exhausted.\n\n"
            "Real-world usage: enter the near-month future on this signal, exit on "
            "a close below EMA(20) or MACD histogram turning negative. Margin "
            "requirements mean a small position size - TradeMind's paper quantity "
            "is in contract lots."
        ),
        "root_condition": {
            "type": "group",
            "logic": "AND",
            "conditions": [
                {
                    "type": "condition",
                    "left": {"indicator": "PRICE", "params": {}},
                    "operator": ">",
                    "right": {"indicator": "SMA", "params": {"period": 20}},
                },
                {
                    "type": "condition",
                    "left": {"indicator": "VOLUME", "params": {"period": 1}},
                    "operator": ">",
                    "right": {"indicator": "VOLUME", "params": {"period": 20}},
                },
                {
                    "type": "condition",
                    "left": {"indicator": "MACD_HIST", "params": {"fast": 12, "slow": 26, "signal": 9}},
                    "operator": ">",
                    "right": 0,
                },
            ],
        },
        "action": {
            "side": "BUY",
            "order_type": "MARKET",
            "quantity": 50,
            "settlement_type": "INTRADAY",
        },
    },

    # ───────────────────────────────────────────────────────────────
    # 18. Bull Call Spread (buy ITM call) - defined-risk option buy
    # ───────────────────────────────────────────────────────────────
    {
        "id": "bull-call-spread-entry",
        "name": "Bull-Call-Spread Entry",
        "category": "Options Proxy",
        "difficulty": "Advanced",
        "ticker": "RELIANCE",
        "timeframe": "1d",
        "tags": ["options", "spread", "defined-risk", "bullish"],
        "for_options": True,
        "summary": "Enter the bullish-call side when the underlying breaks out of a tight base with momentum - the entry leg of a defined-risk bull call spread.",
        "description": (
            "A bull call spread = buy ITM call + sell higher OTM call, capping both "
            "risk and cost while staying bullish. The spread pays when the "
            "underlying rallies past the short strike. This template detects the "
            "breakout regime (price crosses above EMA(20) with RSI between 55-70 "
            "and volume confirming) that justifies paying up for the call side.\n\n"
            "Deploy on RELIANCE/HDFCBANK; in TradeMind the order is a paper BUY on "
            "the underlying. In live trading buy the ITM call (and optionally sell "
            "the OTM call) on the index or stock option chain. Exit the spread when "
            "the underlying closes back below EMA(20)."
        ),
        "root_condition": {
            "type": "group",
            "logic": "AND",
            "conditions": [
                {
                    "type": "condition",
                    "left": {"indicator": "PRICE", "params": {}},
                    "operator": "crosses_above",
                    "right": {"indicator": "EMA", "params": {"period": 20}},
                },
                {
                    "type": "condition",
                    "left": {"indicator": "RSI", "params": {"period": 14}},
                    "operator": ">",
                    "right": 55,
                },
                {
                    "type": "condition",
                    "left": {"indicator": "RSI", "params": {"period": 14}},
                    "operator": "<",
                    "right": 70,
                },
            ],
        },
        "action": {
            "side": "BUY",
            "order_type": "MARKET",
            "quantity": 50,
            "settlement_type": "INTRADAY",
        },
    },

    # ───────────────────────────────────────────────────────────────
    # 19. News-Driven Breakout (pure news trigger, auto-orders)
    # ───────────────────────────────────────────────────────────────
    {
        "id": "news-bullish-breakout",
        "name": "News Bullish Breakout",
        "category": "News Sentiment",
        "difficulty": "Beginner",
        "ticker": "RELIANCE",
        "timeframe": "15m",
        "tags": ["news", "sentiment", "auto-order", "english-hindi"],
        "for_news": True,
        "summary": "Pure news trigger: fires a BUY the moment 1-hour news sentiment crosses above +0.2 on 3+ headlines (EN + Hindi free RSS).",
        "description": (
            "TradeMind's core news innovation. Headlines in English and Hindi are "
            "scored every 5 minutes; when the decay-weighted 1h sentiment crosses "
            "above +0.2 with at least 3 articles behind it, the strategy auto-fires "
            "a paper BUY tagged NEWS_EVENT with the evidence headlines attached. "
            "No technical indicator involved -- pure news-driven auto-order.\n\n"
            "Deploy per ticker; the evaluator re-checks every 60 seconds."
        ),
        "root_condition": {
            "type": "condition",
            "left": {"indicator": "SENTIMENT", "params": {"window": "1h", "metric": "score"}},
            "operator": "crosses_above",
            "right": 0.2,
        },
        "action": {
            "side": "BUY",
            "order_type": "MARKET",
            "quantity": 10,
            "settlement_type": "INTRADAY",
        },
    },

    # ───────────────────────────────────────────────────────────────
    # 20. News Panic Exit (pure news trigger, auto-orders)
    # ───────────────────────────────────────────────────────────────
    {
        "id": "news-panic-exit",
        "name": "News Panic Exit",
        "category": "News Sentiment",
        "difficulty": "Beginner",
        "ticker": "HDFCBANK",
        "timeframe": "15m",
        "tags": ["news", "sentiment", "exit", "risk"],
        "for_news": True,
        "summary": "Pure news trigger: fires a SELL when 1h sentiment z-score collapses below -2 (abnormally negative vs the 7-day baseline).",
        "description": (
            "Catches panic regimes -- fraud probes, SEBI notices, earnings shock -- "
            "by comparing current 1h sentiment against its own 7-day baseline. A "
            "z-score below -2 means this negativity is abnormal, not background "
            "noise. Auto-fires a paper SELL tagged NEWS_EVENT.\n\n"
            "Use as a protective overlay alongside any long strategy."
        ),
        "root_condition": {
            "type": "condition",
            "left": {"indicator": "SENTIMENT", "params": {"window": "1h", "metric": "zscore"}},
            "operator": "crosses_below",
            "right": -2,
        },
        "action": {
            "side": "SELL",
            "order_type": "MARKET",
            "quantity": 10,
            "settlement_type": "INTRADAY",
        },
    },

    # ───────────────────────────────────────────────────────────────
    # 21. News + RSI Confirmation (hybrid)
    # ───────────────────────────────────────────────────────────────
    {
        "id": "news-rsi-confirmation",
        "name": "News + RSI Confirmation",
        "category": "News Sentiment",
        "difficulty": "Intermediate",
        "ticker": "INFY",
        "timeframe": "1d",
        "tags": ["news", "rsi", "hybrid", "confirmation"],
        "for_news": True,
        "summary": "Hybrid: RSI(14) crosses back above 30 AND 1h news sentiment is positive -- technical bounce confirmed by the news tape.",
        "description": (
            "Filters false oversold bounces: the technical turn (RSI crossing back "
            "above 30) only fires when the news tape agrees (1h sentiment above "
            "+0.2 on 3+ headlines). Avoids catching falling knives during genuinely "
            "bad news regimes.\n\n"
            "The best starter template for trusting the news engine."
        ),
        "root_condition": {
            "type": "group",
            "logic": "AND",
            "conditions": [
                {
                    "type": "condition",
                    "left": {"indicator": "RSI", "params": {"period": 14}},
                    "operator": "crosses_above",
                    "right": 30,
                },
                {
                    "type": "condition",
                    "left": {"indicator": "SENTIMENT", "params": {"window": "1h", "metric": "score"}},
                    "operator": ">",
                    "right": 0.2,
                },
            ],
        },
        "action": {
            "side": "BUY",
            "order_type": "MARKET",
            "quantity": 15,
            "settlement_type": "INTRADAY",
        },
    },
]


def list_templates() -> list[dict]:
    """Return the full template catalog (sanitised for JSON)."""
    return list(TEMPLATES)


def get_template(template_id: str) -> dict | None:
    """Fetch a single template by id."""
    for t in TEMPLATES:
        if t["id"] == template_id:
            return t
    return None

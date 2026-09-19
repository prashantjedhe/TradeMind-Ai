"""
Walk-forward windowing with strict IS / OOS separation.

Train: rolling 3 calendar years.
Test: the following 1 calendar year.
Step: 12 months by default (annual roll).

In-sample parameter selection never sees OOS bars. OOS replay may use
IS bars only as indicator warm-up (no OOS fills during IS).
Efficiency Ratio = OOS Sharpe / IS Sharpe per window, then averaged.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal

import pandas as pd

from app.services.backtest_engine import (
    BacktestConfig,
    BacktestSpec,
    compute_metrics,
    parameter_grid,
    simulate_strategy,
)


WFO_TRAIN_YEARS = 3
WFO_TEST_YEARS = 1
WFO_STEP_MONTHS = 12


@dataclass
class WfoWindow:
    train_start: pd.Timestamp
    train_end: pd.Timestamp  # exclusive
    test_start: pd.Timestamp  # == train_end
    test_end: pd.Timestamp  # exclusive


def _ts(value) -> pd.Timestamp:
    t = pd.Timestamp(value)
    if t.tzinfo is None:
        t = t.tz_localize("UTC")
    else:
        t = t.tz_convert("UTC")
    return t


def generate_wfo_windows(
    start: datetime,
    end: datetime,
    train_years: int = WFO_TRAIN_YEARS,
    test_years: int = WFO_TEST_YEARS,
    step_months: int = WFO_STEP_MONTHS,
) -> list[WfoWindow]:
    """
    Non-overlapping IS/OOS per window: [train_start, train_end) then
    [test_start, test_end) with test_start == train_end.
    Adjacent windows may share IS history (rolling), never mix IS with
    that window's OOS.
    """
    if train_years <= 0 or test_years <= 0 or step_months <= 0:
        return []
    start_t = _ts(start)
    end_t = _ts(end)
    if end_t <= start_t:
        return []

    windows: list[WfoWindow] = []
    current = start_t
    guard = 0
    while guard < 64:
        guard += 1
        train_start = current
        train_end = current + pd.DateOffset(years=train_years)
        test_start = train_end
        test_end = test_start + pd.DateOffset(years=test_years)
        if test_start >= end_t:
            break
        if test_end > end_t:
            test_end = end_t
        if test_end <= test_start or train_end <= train_start:
            break
        windows.append(WfoWindow(train_start, train_end, test_start, test_end))
        current = current + pd.DateOffset(months=step_months)
        if current >= end_t:
            break
    return windows


def windows_have_strict_split(windows: list[WfoWindow]) -> bool:
    for w in windows:
        if not (w.train_start < w.train_end == w.test_start < w.test_end):
            return False
    return True


def _efficiency_ratio(oos_sharpe: float, is_sharpe: float) -> float:
    if not math.isfinite(is_sharpe) or not math.isfinite(oos_sharpe):
        return 0.0
    if is_sharpe == 0:
        return 0.0
    er = oos_sharpe / is_sharpe
    if not math.isfinite(er):
        return 0.0
    # Cap pathological ratios from near-zero IS Sharpe
    return float(max(-10.0, min(10.0, er)))


def run_walk_forward_on_frame(
    df: pd.DataFrame,
    spec: BacktestSpec,
    config: BacktestConfig,
    start: datetime,
    end: datetime,
    train_years: int = WFO_TRAIN_YEARS,
    test_years: int = WFO_TEST_YEARS,
    step_months: int = WFO_STEP_MONTHS,
    optimize_is: bool = True,
) -> dict:
    windows = generate_wfo_windows(start, end, train_years, test_years, step_months)
    rows: list[dict] = []
    selected_params: list[dict] = []

    for w in windows:
        is_df = df[(df.index >= w.train_start) & (df.index < w.train_end)]
        oos_hist = df[df.index < w.test_end]  # IS + OOS for warm-up; fills gated
        oos_bars = df[(df.index >= w.test_start) & (df.index < w.test_end)]
        if len(is_df) < 40 or len(oos_bars) < 20:
            continue

        best_spec = spec
        best_is_metrics = None
        best_is_sim = None
        grid = parameter_grid(spec.root_condition) if optimize_is and spec.root_condition else [spec.root_condition]
        if not grid:
            grid = [spec.root_condition]

        for tree in grid:
            trial = BacktestSpec(
                root_condition=tree,
                action_side=spec.action_side,
                action_order_type=spec.action_order_type,
                action_quantity=spec.action_quantity,
                action_settlement_type=spec.action_settlement_type,
                action_limit_price=spec.action_limit_price,
                ticker=spec.ticker,
            )
            sim = simulate_strategy(
                is_df, trial, config,
                trade_start=w.train_start.to_pydatetime(),
                trade_end=w.train_end.to_pydatetime(),
            )
            if sim.error:
                continue
            metrics = compute_metrics(sim.equity, sim.trades, float(config.initial_capital))
            if best_is_metrics is None or (
                metrics["sharpe"], metrics["cagr"]
            ) > (best_is_metrics["sharpe"], best_is_metrics["cagr"]):
                best_is_metrics = metrics
                best_spec = trial
                best_is_sim = sim

        if best_is_metrics is None or best_is_sim is None:
            continue

        oos_sim = simulate_strategy(
            oos_hist, best_spec, config,
            trade_start=w.test_start.to_pydatetime(),
            trade_end=w.test_end.to_pydatetime(),
        )
        oos_metrics = compute_metrics(
            oos_sim.equity, oos_sim.trades, float(config.initial_capital)
        ) if not oos_sim.error else compute_metrics(
            pd.Series(dtype=float), [], float(config.initial_capital)
        )
        er = _efficiency_ratio(oos_metrics["sharpe"], best_is_metrics["sharpe"])
        selected_params.append({
            "train_start": w.train_start.strftime("%Y-%m-%d"),
            "tree": best_spec.root_condition,
        })
        rows.append({
            "train_start": w.train_start.strftime("%Y-%m-%d"),
            "train_end": w.train_end.strftime("%Y-%m-%d"),
            "test_start": w.test_start.strftime("%Y-%m-%d"),
            "test_end": w.test_end.strftime("%Y-%m-%d"),
            "is_sharpe": best_is_metrics["sharpe"],
            "oos_sharpe": oos_metrics["sharpe"],
            "is_cagr": best_is_metrics["cagr"],
            "oos_cagr": oos_metrics["cagr"],
            "is_drawdown": best_is_metrics["max_drawdown"],
            "oos_drawdown": oos_metrics["max_drawdown"],
            "is_win_rate": best_is_metrics["win_rate"],
            "oos_win_rate": oos_metrics["win_rate"],
            "is_profit_factor": best_is_metrics["profit_factor"],
            "oos_profit_factor": oos_metrics["profit_factor"],
            "is_trades": int(best_is_metrics["total_trades"]),
            "oos_trades": int(oos_metrics["total_trades"]),
            "efficiency_ratio": er,
            "is_final_equity": best_is_metrics["final_equity"],
            "oos_final_equity": oos_metrics["final_equity"],
            "oos_total_pnl": oos_metrics["total_pnl"],
        })

    if not rows:
        return {
            "windows": [],
            "num_windows": 0,
            "avg_is_sharpe": 0.0,
            "avg_oos_sharpe": 0.0,
            "efficiency_ratio": 0.0,
            "mean_window_er": 0.0,
            "selected_params": [],
            "error": "Not enough history for a 3-year train / 1-year test window",
        }

    avg_is = float(sum(r["is_sharpe"] for r in rows) / len(rows))
    avg_oos = float(sum(r["oos_sharpe"] for r in rows) / len(rows))
    mean_er = float(sum(r["efficiency_ratio"] for r in rows) / len(rows))
    overall_er = _efficiency_ratio(avg_oos, avg_is)
    return {
        "windows": rows,
        "num_windows": len(rows),
        "avg_is_sharpe": avg_is,
        "avg_oos_sharpe": avg_oos,
        "efficiency_ratio": overall_er,
        "mean_window_er": mean_er,
        "selected_params": selected_params,
        "error": None,
    }

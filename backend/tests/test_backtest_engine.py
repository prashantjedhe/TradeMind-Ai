import math
import uuid
from datetime import datetime, timezone
from types import SimpleNamespace
import pandas as pd
import pytest

from app.models.order import OrderSide, SettlementType
from app.models.strategy import StrategyActionOrderType
from app.models.backtest_copy_league import BacktestStatus
from app.services import backtest_service
from app.services.backtest_engine import (
    BacktestConfig,
    BacktestSpec,
    FillRecord,
    compute_metrics,
    simulate_strategy,
)


def test_compute_metrics_basic_calculation():
    dates = pd.date_range("2025-01-01", periods=252, freq="D", tz="UTC")
    # Equity doubles over 1 year (1M -> 2M)
    equity_values = [1000000.0 + (i * 1000000.0 / 251.0) for i in range(252)]
    equity = pd.Series(equity_values, index=dates)

    trades = [
        FillRecord(
            timestamp=datetime(2025, 2, 1, tzinfo=timezone.utc).isoformat(),
            side="BUY",
            order_type="MARKET",
            reason="ENTRY",
            price=100.0,
            qty=100,
            fees=25.0,
            cash_after=989975.0,
            pnl=None,
            position_after=100,
        ),
        FillRecord(
            timestamp=datetime(2025, 3, 1, tzinfo=timezone.utc).isoformat(),
            side="SELL",
            order_type="MARKET",
            reason="EXIT",
            price=150.0,
            qty=100,
            fees=25.0,
            cash_after=1004950.0,
            pnl=4950.0,  # Winning trade
            position_after=0,
        ),
    ]

    metrics = compute_metrics(equity, trades, initial_capital=1000000.0)

    assert metrics["total_trades"] == 1
    assert metrics["winning_trades"] == 1
    assert metrics["losing_trades"] == 0
    assert metrics["win_rate"] == 1.0
    assert metrics["final_equity"] == 2000000.0
    assert metrics["cagr"] > 0.90  # approximately 100% annual return
    assert metrics["sharpe"] > 0.0
    assert metrics["max_drawdown"] == 0.0  # Monotonically increasing equity


def test_strategy_without_conditions_runs_buy_and_hold_baseline():
    dates = pd.date_range("2025-01-01", periods=5, freq="D", tz="UTC")
    bars = pd.DataFrame(
        {
            "open": [100, 150, 200, 250, 300],
            "high": [110, 160, 210, 260, 310],
            "low": [90, 140, 190, 240, 290],
            "close": [100, 150, 200, 250, 300],
            "volume": [1000] * 5,
        },
        index=dates,
    )
    spec = BacktestSpec(
        root_condition=None,
        action_side=OrderSide.BUY,
        action_order_type=StrategyActionOrderType.MARKET,
        action_quantity=1,
        action_settlement_type=SettlementType.DELIVERY,
        action_limit_price=None,
        ticker="TEST",
    )

    result = simulate_strategy(
        bars,
        spec,
        BacktestConfig(sl_pct=None, tp_pct=None),
    )

    metrics = compute_metrics(result.equity, result.trades, initial_capital=1_000_000)
    assert result.error is None
    assert metrics["total_trades"] == 1
    assert metrics["total_pnl"] > 0
    assert metrics["final_equity"] > 1_000_000


@pytest.mark.asyncio
async def test_standard_backtest_service_persists_engine_metrics(monkeypatch):
    dates = pd.date_range("2025-01-01", periods=5, freq="D", tz="UTC")
    bars = pd.DataFrame(
        {
            "open": [100, 150, 200, 250, 300],
            "high": [110, 160, 210, 260, 310],
            "low": [90, 140, 190, 240, 290],
            "close": [100, 150, 200, 250, 300],
            "volume": [1000] * 5,
        },
        index=dates,
    )

    async def load_bars(*args, **kwargs):
        return bars

    class FakeSession:
        def __init__(self):
            self.records = []

        def add(self, record):
            self.records.append(record)

        async def commit(self):
            pass

        async def refresh(self, record):
            pass

    monkeypatch.setattr(backtest_service, "load_backtest_df", load_bars)
    db = FakeSession()
    result = await backtest_service.run_backtest(
        db=db,
        user=SimpleNamespace(id=uuid.uuid4()),
        strategy_id=None,
        ticker="TEST",
        timeframe="1d",
        start_date=dates[0].to_pydatetime(),
        end_date=(dates[-1] + pd.Timedelta(days=1)).to_pydatetime(),
    )

    assert result.status == BacktestStatus.COMPLETE
    assert result.total_trades == 1
    assert result.total_pnl > 0
    assert result.final_equity > result.initial_capital
    assert result.trade_ledger
    assert db.records == [result]

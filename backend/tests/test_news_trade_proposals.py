from datetime import datetime, timedelta, timezone
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pandas as pd
import pytest

from app.api.v1 import news as news_api
from app.models.order import (
    OrderSide,
    OrderStatus,
    OrderType,
    SettlementType,
    TriggeredBy,
)
from app.models.strategy import StrategyActionOrderType
from app.services.order_service import try_trigger_pending_order
from app.services.news_trade_proposal import build_trade_proposal
from app.services.strategy_service import fire_action, opposing_strategy_context


def _rising_bars(now: datetime, *, periods: int = 60) -> pd.DataFrame:
    index = pd.date_range(end=now, periods=periods, freq="D")
    closes = [100 + i for i in range(periods)]
    return pd.DataFrame(
        {
            "open": closes,
            "high": closes,
            "low": closes,
            "close": closes,
            "volume": [1000] * periods,
        },
        index=index,
    )


def _signal(now: datetime, **overrides) -> dict:
    signal = {
        "id": uuid4(),
        "ticker": "RELIANCE",
        "timestamp": now - timedelta(minutes=5),
        "score": 0.7,
        "impact": 0.6,
        "band": "MEDIUM",
        "article_count": 4,
    }
    return {**signal, **overrides}


def _falling_bars(now: datetime, *, periods: int = 60) -> pd.DataFrame:
    index = pd.date_range(end=now, periods=periods, freq="D")
    closes = [200 - i for i in range(periods)]
    return pd.DataFrame(
        {
            "open": closes,
            "high": closes,
            "low": closes,
            "close": closes,
            "volume": [1000] * periods,
        },
        index=index,
    )


def test_trade_proposal_requires_fresh_corroborated_aligned_news():
    now = datetime.now(timezone.utc)

    proposal = build_trade_proposal(
        _signal(now),
        Decimal("1500.25"),
        _rising_bars(now),
        "bullish",
        "bullish",
        now,
        now=now,
    )

    assert proposal is not None
    assert proposal["side"] == "BUY"
    assert proposal["order_type"] == "LIMIT"
    assert proposal["quantity"] == 1
    assert proposal["limit_price"] == 1500.25
    assert proposal["ticker"] == "RELIANCE"
    assert proposal["proposal_id"]


def test_bearish_proposal_only_exits_the_existing_long_position():
    now = datetime.now(timezone.utc)
    proposal = build_trade_proposal(
        _signal(now, score=-0.7, impact=-0.6),
        Decimal("1500.25"),
        _falling_bars(now),
        "bearish",
        "bearish",
        now,
        open_long_quantity=5,
        now=now,
    )

    assert proposal is not None
    assert proposal["side"] == "SELL"
    assert proposal["quantity"] == 5


def test_bearish_proposal_requires_a_long_position_and_fresh_market_bars():
    now = datetime.now(timezone.utc)
    signal = _signal(now, score=-0.7, impact=-0.6)

    assert build_trade_proposal(
        signal,
        Decimal("1500"),
        _falling_bars(now),
        "bearish",
        "bearish",
        now,
        open_long_quantity=0,
        now=now,
    ) is None
    assert build_trade_proposal(
        signal,
        Decimal("1500"),
        _falling_bars(now - timedelta(days=10)),
        "bearish",
        "bearish",
        now - timedelta(days=10),
        open_long_quantity=5,
        now=now,
    ) is None


@pytest.mark.parametrize(
    ("signal_changes", "market_trend", "market_sentiment", "price"),
    [
        ({"article_count": 1}, "bullish", "bullish", Decimal("1500")),
        ({"impact": 0.2, "band": "LOW"}, "bullish", "bullish", Decimal("1500")),
        ({"timestamp": datetime.now(timezone.utc) - timedelta(minutes=20)}, "bullish", "bullish", Decimal("1500")),
        ({}, "bearish", "bullish", Decimal("1500")),
        ({}, "bullish", "bearish", Decimal("1500")),
        ({}, "bullish", "bullish", None),
    ],
)
def test_trade_proposal_rejects_unqualified_or_unconfirmed_data(
    signal_changes, market_trend, market_sentiment, price
):
    now = datetime.now(timezone.utc)
    assert build_trade_proposal(
        _signal(now, **signal_changes),
        price,
        _rising_bars(now),
        market_trend,
        market_sentiment,
        now,
        now=now,
    ) is None


def test_trade_proposal_rejects_stale_daily_history():
    now = datetime.now(timezone.utc)
    stale_bars = _rising_bars(now - timedelta(days=10))

    assert build_trade_proposal(
        _signal(now),
        Decimal("1500"),
        stale_bars,
        "bullish",
        "bullish",
        now,
        now=now,
    ) is None


@pytest.mark.asyncio
@pytest.mark.parametrize("uses_sentiment", [False, True])
async def test_satisfied_strategy_creates_a_limit_proposal_not_an_order(
    monkeypatch, uses_sentiment
):
    from app.services import strategy_service

    strategy = SimpleNamespace(
        id=uuid4(),
        user_id=uuid4(),
        ticker="RELIANCE",
        name="Test strategy",
        timeframe=SimpleNamespace(value="15m"),
        root_condition={
            "type": "condition",
            "left": {
                "indicator": "SENTIMENT" if uses_sentiment else "PRICE",
                "params": {"window": "1h"} if uses_sentiment else {},
            },
            "operator": ">",
            "right": 0.2 if uses_sentiment else 100,
        },
        action_side=OrderSide.BUY,
        action_order_type=StrategyActionOrderType.MARKET,
        action_settlement_type=SettlementType.INTRADAY,
        action_quantity=3,
        action_limit_price=None,
        quantity_multiplier=1,
        last_triggered_at=None,
    )
    db = SimpleNamespace(commit=AsyncMock())
    monkeypatch.setattr(
        strategy_service,
        "get_price_or_derive",
        AsyncMock(return_value=Decimal("1525.50")),
    )
    proposal = SimpleNamespace(id=uuid4())
    create_proposal = AsyncMock(return_value=proposal)
    monkeypatch.setattr(strategy_service, "create_trade_proposal", create_proposal)
    monkeypatch.setattr(
        strategy_service,
        "top_headlines",
        AsyncMock(return_value=[]),
    )

    assert await fire_action(db, strategy) is True
    create_proposal.assert_awaited_once()
    assert create_proposal.await_args.kwargs["ticker"] == "RELIANCE"
    assert create_proposal.await_args.kwargs["quantity"] == 3
    assert create_proposal.await_args.kwargs["limit_price"] == Decimal("1525.50")
    assert create_proposal.await_args.kwargs["side"] == "BUY"
    db.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_strategy_pauses_when_daily_trend_opposes_its_direction(monkeypatch):
    from app.services import strategy_service

    now = datetime.now(timezone.utc)
    strategy = SimpleNamespace(
        id=uuid4(),
        ticker="RELIANCE",
        action_side=OrderSide.BUY,
    )
    monkeypatch.setattr(
        strategy_service,
        "_load_df",
        AsyncMock(return_value=_falling_bars(now)),
    )

    reason = await opposing_strategy_context(SimpleNamespace(), strategy)

    assert reason is not None
    assert reason.startswith("MARKET:")
    assert "bearish" in reason


@pytest.mark.asyncio
async def test_confirm_market_trade_submits_the_revalidated_limit_order(monkeypatch):
    signal_id = str(uuid4())
    proposal = {
        "proposal_id": "a" * 32,
        "signal_id": signal_id,
        "ticker": "RELIANCE",
        "side": "BUY",
        "order_type": "LIMIT",
        "quantity": 1,
        "settlement_type": "INTRADAY",
        "limit_price": 1500.25,
    }
    monkeypatch.setattr(news_api, "enforce_rate_limit", AsyncMock())
    monkeypatch.setattr(news_api, "_get_market_brief", AsyncMock(return_value={
        "trade_proposal": proposal,
    }))
    order = SimpleNamespace(id=uuid4(), status="PENDING")
    create_order = AsyncMock(return_value=order)
    monkeypatch.setattr(news_api, "create_order_service", create_order)

    db = SimpleNamespace(execute=AsyncMock(side_effect=[
        None,
        SimpleNamespace(scalar_one_or_none=lambda: None),
        SimpleNamespace(scalar_one_or_none=lambda: None),
    ]))
    user = SimpleNamespace(id=uuid4())
    result = await news_api.confirm_market_trade(
        news_api.NewsTradeConfirmationRequest(
            proposal_id="a" * 32,
            signal_id=signal_id,
        ),
        current_user=user,
        db=db,
    )

    assert result is order
    request = create_order.await_args.kwargs["request"]
    assert request.ticker == "RELIANCE"
    assert request.order_type == OrderType.LIMIT
    assert request.side == OrderSide.BUY
    assert request.settlement_type == SettlementType.INTRADAY
    assert request.quantity == 1
    assert request.limit_price == Decimal("1500.25")
    assert create_order.await_args.kwargs["triggered_by"] == TriggeredBy.NEWS_EVENT
    assert create_order.await_args.kwargs["updated_reason"] == f"NEWS_PROPOSAL:{signal_id}"


@pytest.mark.asyncio
async def test_confirm_market_trade_is_idempotent_for_existing_proposal(monkeypatch):
    existing_order = SimpleNamespace(id=uuid4(), status="PENDING")
    monkeypatch.setattr(news_api, "enforce_rate_limit", AsyncMock())
    brief_builder = AsyncMock()
    monkeypatch.setattr(news_api, "_get_market_brief", brief_builder)
    monkeypatch.setattr(news_api, "create_order_service", AsyncMock())
    db = SimpleNamespace(execute=AsyncMock(side_effect=[
        None,
        SimpleNamespace(scalar_one_or_none=lambda: existing_order),
    ]))

    result = await news_api.confirm_market_trade(
        news_api.NewsTradeConfirmationRequest(proposal_id="b" * 32, signal_id=uuid4()),
        current_user=SimpleNamespace(id=uuid4()),
        db=db,
    )

    assert result is existing_order
    brief_builder.assert_not_awaited()
    news_api.create_order_service.assert_not_awaited()


@pytest.mark.asyncio
async def test_confirm_market_trade_rejects_stale_proposal(monkeypatch):
    monkeypatch.setattr(news_api, "enforce_rate_limit", AsyncMock())
    monkeypatch.setattr(news_api, "_get_market_brief", AsyncMock(return_value={
        "trade_proposal": None,
    }))
    create_order = AsyncMock()
    monkeypatch.setattr(news_api, "create_order_service", create_order)
    db = SimpleNamespace(execute=AsyncMock(side_effect=[
        None,
        SimpleNamespace(scalar_one_or_none=lambda: None),
    ]))

    with pytest.raises(news_api.HTTPException) as error:
        await news_api.confirm_market_trade(
            news_api.NewsTradeConfirmationRequest(proposal_id="c" * 32, signal_id=uuid4()),
            current_user=SimpleNamespace(id=uuid4()),
            db=db,
        )

    assert error.value.status_code == 409
    create_order.assert_not_awaited()


@pytest.mark.asyncio
async def test_confirmed_news_sell_cancels_if_the_long_position_is_gone():
    order = SimpleNamespace(
        id=uuid4(),
        user_id=uuid4(),
        ticker="RELIANCE",
        order_type=OrderType.LIMIT,
        side=OrderSide.SELL,
        trigger_price=Decimal("1500"),
        quantity=1,
        status=OrderStatus.PENDING,
        triggered_by=TriggeredBy.NEWS_EVENT,
        updated_reason="NEWS_PROPOSAL:signal-id",
    )
    db = SimpleNamespace(
        execute=AsyncMock(return_value=SimpleNamespace(scalar_one_or_none=lambda: None)),
        commit=AsyncMock(),
    )

    result = await try_trigger_pending_order(db, order, Decimal("1500"))

    assert result is None
    assert order.status == OrderStatus.CANCELLED
    assert order.updated_reason.endswith(":POSITION_CHANGED")
    db.commit.assert_awaited_once()

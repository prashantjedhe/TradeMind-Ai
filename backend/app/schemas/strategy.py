from __future__ import annotations
import uuid
from datetime import datetime, time
from typing import List, Union, Literal, Optional
from pydantic import BaseModel, Field, model_validator
from decimal import Decimal

from app.models.order import OrderSide, SettlementType
from app.models.strategy import StrategyStatus, StrategyTimeframe, StrategyActionOrderType


# ── Indicator reference ──────────────────────────────────────────
class IndicatorRef(BaseModel):
    """A computed value: either an indicator or the raw price/volume."""
    indicator: Literal["RSI", "EMA", "SMA", "MACD", "MACD_SIGNAL", "MACD_HIST", "VOLUME", "PRICE", "SENTIMENT"]
    params: dict = Field(default_factory=dict)
    # e.g. {"period": 14} for RSI/EMA/SMA
    # e.g. {"fast": 12, "slow": 26, "signal": 9} for MACD/MACD_SIGNAL/MACD_HIST
    # e.g. {"period": 20} for VOLUME -> average volume over 20 bars
    # e.g. {"window": "1h", "metric": "score"} for SENTIMENT ->
    #   news signal series (score | zscore | count) for the strategy's
    #   ticker. window "15m" | "1h" | "1d" (or window_minutes int).


# ── Leaf condition: single comparison ────────────────────────────
class ConditionLeaf(BaseModel):
    type: Literal["condition"] = "condition"
    left: IndicatorRef
    operator: Literal["<", ">", "<=", ">=", "==", "crosses_above", "crosses_below"]
    right: Union[float, IndicatorRef]
    # right can be a constant (RSI < 30) or another indicator
    # (EMA(9) crosses_above EMA(21))


# ── Group: nested AND/OR tree ─────────────────────────────────────
class ConditionGroup(BaseModel):
    type: Literal["group"] = "group"
    logic: Literal["AND", "OR"]
    conditions: List[Union[ConditionLeaf, "ConditionGroup"]]


ConditionGroup.model_rebuild()

ConditionNode = Union[ConditionLeaf, ConditionGroup]


# ── Action fired when root condition evaluates True ──────────────
class ActionSchema(BaseModel):
    side: OrderSide
    order_type: StrategyActionOrderType
    quantity: int = Field(gt=0)
    settlement_type: SettlementType = SettlementType.INTRADAY
    limit_price: Optional[Decimal] = None  # required only if order_type == LIMIT


# ── Multi-leg option strategy configuration ─────────────────────
class OptionLeg(BaseModel):
    """One option contract leg in a multi-leg entry."""
    side: OrderSide
    option_type: Literal["CE", "PE"]
    expiry_type: Literal["WEEKLY", "MONTHLY", "NEXT_WEEKLY", "NEXT_MONTHLY"]
    strike_criteria: Literal["ATM", "ITM", "OTM", "STRIKE", "PREMIUM"]
    strike_offset: int = 0
    quantity_lots: int = Field(gt=0)

    @model_validator(mode="after")
    def validate_leg(self):
        result = self
        if result.strike_criteria == "STRIKE" and result.strike_offset < 0:
            raise ValueError("strike_offset must be non-negative for STRIKE criteria")
        return result


class RiskControls(BaseModel):
    """Optional controls shared by all legs of a strategy."""
    sl_type: Optional[Literal["POINTS", "PERCENT", "PREMIUM"]] = None
    sl_value: Optional[Decimal] = Field(default=None, ge=0)
    tp_type: Optional[Literal["POINTS", "PERCENT", "PREMIUM"]] = None
    tp_value: Optional[Decimal] = Field(default=None, ge=0)
    max_profit: Optional[Decimal] = Field(default=None, ge=0)
    max_loss: Optional[Decimal] = Field(default=None, ge=0)
    no_trade_after: Optional[time] = None
    trailing_mode: Optional[Literal["NONE", "POINTS", "PERCENT", "PREMIUM"]] = None
    move_sl_to_cost: bool = False
    exit_all: bool = True
    pre_punch: bool = False
    wait_and_trade: bool = False
    re_entry: bool = False
    premium_difference: Optional[Decimal] = Field(default=None, ge=0)
    trail_sl: Optional[Decimal] = Field(default=None, ge=0)


StrategyProduct = Literal["MIS", "CNC", "BTST"]


# ── Prompt library entries (English descriptions that map to
#    condition trees). Used when a user types a strategy in plain
#    language and the system resolves it to a condition tree.
STRATEGY_PROMPT_LIBRARY: dict[str, dict] = {
    "rsi-oversold-bounce": {
        "name": "RSI Oversold Bounce",
        "description": "Buy when RSI(14) dips below 30 and starts turning up",
        "condition": {
            "type": "group",
            "logic": "AND",
            "conditions": [
                {"type": "condition", "left": {"indicator": "RSI", "params": {"period": 14}}, "operator": "crosses_above", "right": 30},
                {"type": "condition", "left": {"indicator": "PRICE", "params": {}}, "operator": ">", "right": {"indicator": "EMA", "params": {"period": 20}}},
            ],
        },
        "action": {
            "side": "BUY",
            "order_type": "MARKET",
            "quantity": 25,
            "settlement_type": "INTRADAY",
        },
    },
    "golden-crossover": {
        "name": "Golden Crossover",
        "description": "EMA(50) crosses above EMA(200) with RSI > 50",
        "condition": {
            "type": "group",
            "logic": "AND",
            "conditions": [
                {"type": "condition", "left": {"indicator": "EMA", "params": {"period": 50}}, "operator": "crosses_above", "right": {"indicator": "EMA", "params": {"period": 200}}},
                {"type": "condition", "left": {"indicator": "RSI", "params": {"period": 14}}, "operator": ">", "right": 50},
            ],
        },
        "action": {
            "side": "BUY",
            "order_type": "MARKET",
            "quantity": 10,
            "settlement_type": "DELIVERY",
        },
    },
}


# ── Full strategy ─────────────────────────────────────────────────
class StrategyCreate(BaseModel):
    name: str
    ticker: str  # e.g. "RELIANCE.NS"
    timeframe: StrategyTimeframe  # extensible later; only these two have OHLCV data today
    root_condition: Optional[ConditionNode] = None
    action: Optional[ActionSchema] = None
    status: StrategyStatus = StrategyStatus.DRAFT
    prompt: Optional[str] = None  # e.g. "Buy when RSI falls below 30"
    # Optional multi-leg fields. Leaving these unset preserves the classic
    # single-action strategy API.
    strategy_type: Optional[Literal["SINGLE", "INDICATOR", "OPTIONS", "OPTIONS_TIME", "OPTIONS_INDICATOR", "MULTI_LEG"]] = None
    reference: Optional[Literal["SPOT", "FUTURE"]] = None
    product: Optional[StrategyProduct] = None
    order_mode: Optional[Literal["MARKET", "LIMIT"]] = None
    start_time: Optional[time] = None
    square_off_time: Optional[time] = None
    trading_days: Optional[List[Literal["MON", "TUE", "WED", "THU", "FRI"]]] = None
    legs: Optional[List[OptionLeg]] = None
    risk_controls: Optional[RiskControls] = None

    @model_validator(mode="after")
    def validate_strategy(self):
        result = self
        if result.legs is not None and len(result.legs) == 0:
            raise ValueError("legs must contain at least one leg")
        if result.strategy_type in ("OPTIONS", "OPTIONS_TIME", "OPTIONS_INDICATOR", "MULTI_LEG") and not result.legs:
            raise ValueError("legs are required for an options strategy")
        if result.start_time and result.square_off_time and result.start_time >= result.square_off_time:
            raise ValueError("square_off_time must be after start_time")
        return result


class StrategyUpdate(BaseModel):
    """Partial update - only fields present are changed."""
    name: Optional[str] = None
    ticker: Optional[str] = None
    timeframe: Optional[StrategyTimeframe] = None
    root_condition: Optional[ConditionNode] = None
    action: Optional[ActionSchema] = None
    status: Optional[StrategyStatus] = None
    prompt: Optional[str] = None
    strategy_type: Optional[Literal["SINGLE", "INDICATOR", "OPTIONS", "OPTIONS_TIME", "OPTIONS_INDICATOR", "MULTI_LEG"]] = None
    reference: Optional[Literal["SPOT", "FUTURE"]] = None
    product: Optional[StrategyProduct] = None
    order_mode: Optional[Literal["MARKET", "LIMIT"]] = None
    start_time: Optional[time] = None
    square_off_time: Optional[time] = None
    trading_days: Optional[List[Literal["MON", "TUE", "WED", "THU", "FRI"]]] = None
    legs: Optional[List[OptionLeg]] = None
    risk_controls: Optional[RiskControls] = None

    @classmethod
    def model_validate(cls, obj, *args, **kwargs):
        result = super().model_validate(obj, *args, **kwargs)
        if result.legs is not None and len(result.legs) == 0:
            raise ValueError("legs must contain at least one leg")
        if result.start_time and result.square_off_time and result.start_time >= result.square_off_time:
            raise ValueError("square_off_time must be after start_time")
        return result


class StrategyOut(StrategyCreate):
    id: uuid.UUID
    user_id: uuid.UUID
    last_triggered_at: Optional[datetime] = None
    paused_reason: Optional[str] = None
    news_event_id: Optional[uuid.UUID] = None
    quantity_multiplier: Decimal = Decimal("1.0000")
    multiplier_set_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
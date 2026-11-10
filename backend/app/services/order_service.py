"""
Order execution service.

MARKET orders execute immediately against the cached price.
LIMIT/SL/TP orders are saved as PENDING and later executed by a
separate Celery task (see workers/pending_orders.py) that compares
cached prices against each pending order's trigger_price.

Fill price rules (see check_trigger_condition / determine_fill_price):
- LIMIT and TP: fill at the exact trigger_price (guaranteed, no
  slippage - the whole point of specifying a target price).
- SL: fires when price crosses the trigger, but fills at the current
  market price WITH slippage applied - realistic, since stop orders
  become market orders once triggered and can slip in fast moves.

Concurrency safety: both the user's balance row and the relevant
open Position row are locked with SELECT ... FOR UPDATE inside a
single transaction, so concurrent fills cannot race each other into
an inconsistent balance or position state.
"""

from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.order import Order, OrderType, OrderSide, OrderStatus, TriggeredBy
from app.models.portfolio import Position, PositionStatus
from app.models.user import User
from app.schemas.order import OrderCreateRequest
from app.services.fee_calculator import calculate_fees
from app.services.position_service import apply_fill_to_position
from app.services.price_cache_service import get_cached_price, get_price_or_derive

SLIPPAGE_RATE = Decimal("0.0005")  # 0.05%, per project roadmap
PRICE_QUANTIZE = Decimal("0.01")


class PriceUnavailableError(Exception):
    """Raised when no fresh cached price exists for the requested ticker."""
    def __init__(self, ticker: str):
        self.ticker = ticker
        super().__init__(f"No fresh price available for {ticker}")


class InsufficientBalanceError(Exception):
    """Raised when the user's virtual balance can't cover the order cost."""
    def __init__(self, required: Decimal, available: Decimal):
        self.required = required
        self.available = available
        super().__init__(f"Insufficient balance: required {required}, available {available}")


def _apply_slippage(price: Decimal, side: OrderSide) -> Decimal:
    """Slippage always works against the trader: BUY fills higher, SELL fills lower."""
    if side == OrderSide.BUY:
        adjusted = price * (1 + SLIPPAGE_RATE)
    else:
        adjusted = price * (1 - SLIPPAGE_RATE)
    return adjusted.quantize(PRICE_QUANTIZE)


def check_trigger_condition(
    order_type: OrderType, side: OrderSide, trigger_price: Decimal, current_price: Decimal
) -> bool:
    """
    Determine whether a pending order's trigger condition has been met.

    LIMIT and TP share the same directional logic (favorable-price
    entry/exit): BUY fires when price drops to/below trigger, SELL
    fires when price rises to/above trigger.

    SL is the mirror image (adverse-price protection): BUY fires when
    price rises to/above trigger (covering a losing short), SELL fires
    when price drops to/below trigger (exiting a losing long).
    """
    if order_type in (OrderType.LIMIT, OrderType.TP):
        if side == OrderSide.BUY:
            return current_price <= trigger_price
        else:
            return current_price >= trigger_price
    elif order_type == OrderType.SL:
        if side == OrderSide.BUY:
            return current_price >= trigger_price
        else:
            return current_price <= trigger_price
    return False


def determine_fill_price(order_type: OrderType, side: OrderSide, trigger_price: Decimal, current_price: Decimal) -> Decimal:
    """
    LIMIT/TP: guaranteed fill at the exact trigger price, no slippage.
    SL: fills at the current market price WITH slippage (realistic -
    stop orders become market orders once triggered).
    """
    if order_type == OrderType.SL:
        return _apply_slippage(current_price, side)
    return trigger_price


async def _execute_fill(
    db: AsyncSession,
    user_id,
    ticker: str,
    order_type: OrderType,
    side: OrderSide,
    settlement_type,
    quantity: int,
    requested_price: Decimal,
    executed_price: Decimal,
    triggered_by: TriggeredBy,
    pending_order: Order | None = None,
) -> Order:
    """
    Shared fill logic used by both immediate MARKET execution and
    pending LIMIT/SL/TP trigger execution. Handles fee calculation,
    balance deduction/credit, and position update atomically.
    """
    slippage_amount = (abs(executed_price - requested_price) * quantity).quantize(PRICE_QUANTIZE)

    fees = calculate_fees(
        executed_price=executed_price,
        quantity=quantity,
        side=side,
        settlement_type=settlement_type,
        ticker=ticker,
    )

    turnover = (executed_price * quantity).quantize(PRICE_QUANTIZE)

    # --- Row-lock the user's balance row ---
    result = await db.execute(select(User).where(User.id == user_id).with_for_update())
    locked_user = result.scalar_one()

    if side == OrderSide.BUY:
        total_cost = turnover + fees.total_fees
        if locked_user.virtual_balance < total_cost:
            raise InsufficientBalanceError(required=total_cost, available=locked_user.virtual_balance)
        locked_user.virtual_balance -= total_cost
    else:
        net_proceeds = turnover - fees.total_fees
        locked_user.virtual_balance += net_proceeds

    # --- Row-lock the relevant open Position (if any) for this ticker ---
    result = await db.execute(
        select(Position)
        .where(
            Position.user_id == user_id,
            Position.ticker == ticker,
            Position.status == PositionStatus.OPEN,
        )
        .with_for_update()
    )
    position = result.scalar_one_or_none()

    current_quantity = position.quantity if position else 0
    current_avg_price = position.avg_entry_price if position else Decimal("0.00")

    pos_result = apply_fill_to_position(
        current_quantity=current_quantity,
        current_avg_entry_price=current_avg_price,
        fill_quantity=quantity,
        fill_price=executed_price,
        side=side,
    )

    now = datetime.now(timezone.utc)

    if position is None:
        position = Position(
            user_id=user_id,
            ticker=ticker,
            quantity=pos_result.new_quantity,
            avg_entry_price=pos_result.new_avg_entry_price,
            realised_pnl=pos_result.realized_pnl,
            status=PositionStatus.CLOSED if pos_result.is_closed else PositionStatus.OPEN,
        )
        db.add(position)
    else:
        position.quantity = pos_result.new_quantity
        position.avg_entry_price = pos_result.new_avg_entry_price
        position.realised_pnl = position.realised_pnl + pos_result.realized_pnl
        if pos_result.is_closed:
            position.status = PositionStatus.CLOSED
            position.closed_at = now

    if pending_order is not None:
        # Update the existing PENDING order row in place.
        order = pending_order
        order.requested_price = requested_price
        order.executed_price = executed_price
        order.status = OrderStatus.FILLED
        order.filled_at = now
    else:
        order = Order(
            user_id=user_id,
            ticker=ticker,
            order_type=order_type,
            side=side,
            settlement_type=settlement_type,
            quantity=quantity,
            requested_price=requested_price,
            executed_price=executed_price,
            status=OrderStatus.FILLED,
            triggered_by=triggered_by,
            filled_at=now,
        )
        db.add(order)

    order.slippage_amount = slippage_amount
    order.brokerage_fee = fees.brokerage_fee
    order.stt_fee = fees.stt_fee
    order.stamp_duty_fee = fees.stamp_duty_fee
    order.exchange_charge_fee = fees.exchange_charge_fee
    order.sebi_charge_fee = fees.sebi_charge_fee
    order.gst_fee = fees.gst_fee
    order.dp_charge_fee = fees.dp_charge_fee
    order.total_fees = fees.total_fees

    await db.commit()
    await db.refresh(order)
    return order


async def create_order(
    db: AsyncSession,
    user: User,
    request: OrderCreateRequest,
    triggered_by: TriggeredBy = TriggeredBy.USER,
    updated_reason: str | None = None,
) -> Order:
    """
    Entry point for direct user orders and explicitly confirmed
    strategy/news proposals.

    MARKET orders execute immediately. LIMIT/SL/TP orders are saved
    as PENDING and picked up later by the pending-order Celery task.
    `triggered_by` records direct user submission, a strategy action,
    or a news proposal explicitly confirmed by the user.
    """
    if request.order_type == OrderType.MARKET:
        requested_price = await get_price_or_derive(request.ticker)
        if requested_price is None:
            raise PriceUnavailableError(request.ticker)

        executed_price = _apply_slippage(requested_price, request.side)

        return await _execute_fill(
            db=db,
            user_id=user.id,
            ticker=request.ticker,
            order_type=request.order_type,
            side=request.side,
            settlement_type=request.settlement_type,
            quantity=request.quantity,
            requested_price=requested_price,
            executed_price=executed_price,
            triggered_by=triggered_by,
        )

    # LIMIT / SL / TP: save as PENDING, no execution yet.
    order = Order(
        user_id=user.id,
        ticker=request.ticker,
        order_type=request.order_type,
        side=request.side,
        settlement_type=request.settlement_type,
        quantity=request.quantity,
        trigger_price=request.limit_price,
        status=OrderStatus.PENDING,
        triggered_by=triggered_by,
        updated_reason=updated_reason,
    )
    db.add(order)
    await db.commit()
    await db.refresh(order)
    return order


async def try_trigger_pending_order(db: AsyncSession, order: Order, current_price: Decimal) -> Order | None:
    """
    Called by the pending-order Celery task for each PENDING order,
    with the latest cached price for its ticker. Returns the filled
    Order if triggered, or None if the trigger condition isn't met yet.
    """
    if not check_trigger_condition(order.order_type, order.side, order.trigger_price, current_price):
        return None

    if (
        order.triggered_by == TriggeredBy.NEWS_EVENT
        and (order.updated_reason or "").startswith("NEWS_PROPOSAL:")
        and order.side == OrderSide.SELL
    ):
        position_result = await db.execute(
            select(Position)
            .where(
                Position.user_id == order.user_id,
                Position.ticker == order.ticker,
                Position.status == PositionStatus.OPEN,
                Position.quantity >= order.quantity,
            )
            .with_for_update()
        )
        if position_result.scalar_one_or_none() is None:
            order.status = OrderStatus.CANCELLED
            order.updated_reason = f"{order.updated_reason}:POSITION_CHANGED"[:255]
            await db.commit()
            return None

    fill_price = determine_fill_price(order.order_type, order.side, order.trigger_price, current_price)

    return await _execute_fill(
        db=db,
        user_id=order.user_id,
        ticker=order.ticker,
        order_type=order.order_type,
        side=order.side,
        settlement_type=order.settlement_type,
        quantity=order.quantity,
        requested_price=current_price,
        executed_price=fill_price,
        triggered_by=order.triggered_by,
        pending_order=order,
    )

"""
Pure position-update logic: given an existing position (or none) and
a new fill, compute the resulting position state and any realized P&L.

Deliberately has ZERO database or Redis dependencies - this is pure
arithmetic, which makes it fully unit-testable in isolation before
it's ever wired into the real order execution flow.

Supports long, short, and positions flipping sign within a single
fill (e.g. selling more than currently held flips long -> short).
"""

from dataclasses import dataclass
from decimal import Decimal

from app.models.order import OrderSide


@dataclass
class PositionUpdateResult:
    new_quantity: int
    new_avg_entry_price: Decimal
    realized_pnl: Decimal
    is_closed: bool  # True if new_quantity == 0


def apply_fill_to_position(
    current_quantity: int,
    current_avg_entry_price: Decimal,
    fill_quantity: int,
    fill_price: Decimal,
    side: OrderSide,
) -> PositionUpdateResult:
    """
    current_quantity: signed - positive=long, negative=short, 0=no position
    current_avg_entry_price: average entry price of the CURRENT open
        quantity (ignored/0 if current_quantity is 0)
    fill_quantity: always positive (the traded quantity)
    fill_price: the executed price for this fill
    side: BUY or SELL for this specific order
    """
    delta = fill_quantity if side == OrderSide.BUY else -fill_quantity

    # Case 1: no existing position, or adding in the same direction
    # (same sign, or starting from zero) -> weighted-average entry price,
    # nothing realized yet.
    same_direction = current_quantity == 0 or (
        (current_quantity > 0 and delta > 0) or (current_quantity < 0 and delta < 0)
    )

    if same_direction:
        new_quantity = current_quantity + delta
        total_current_value = abs(current_quantity) * current_avg_entry_price
        total_new_value = fill_quantity * fill_price
        new_avg = (total_current_value + total_new_value) / abs(new_quantity)
        return PositionUpdateResult(
            new_quantity=new_quantity,
            new_avg_entry_price=new_avg,
            realized_pnl=Decimal("0.00"),
            is_closed=False,
        )

    # Case 2: delta opposes the current position -> closing/reducing,
    # and possibly flipping to the opposite side.
    closing_qty = min(fill_quantity, abs(current_quantity))

    if current_quantity > 0:  # long position being sold
        realized_pnl = (fill_price - current_avg_entry_price) * closing_qty
    else:  # short position being covered
        realized_pnl = (current_avg_entry_price - fill_price) * closing_qty

    remaining_fill_qty = fill_quantity - closing_qty

    if remaining_fill_qty > 0:
        # Flipped through zero: fully closed the old side, opened a
        # fresh position of `remaining_fill_qty` in the new direction.
        new_quantity = remaining_fill_qty if side == OrderSide.BUY else -remaining_fill_qty
        new_avg = fill_price
        is_closed = False
    else:
        # Partial or exact close, no flip.
        new_quantity = current_quantity + delta
        new_avg = current_avg_entry_price if new_quantity != 0 else Decimal("0.00")
        is_closed = new_quantity == 0

    return PositionUpdateResult(
        new_quantity=new_quantity,
        new_avg_entry_price=new_avg,
        realized_pnl=realized_pnl.quantize(Decimal("0.01")),
        is_closed=is_closed,
    )

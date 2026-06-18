"""Simulation event definitions and factory functions."""

import uuid
from enum import Enum
from decimal import Decimal
from dataclasses import dataclass, field
from typing import Optional

from src.core.types import TokenSymbol


class EventType(str, Enum):
    SWAP = "swap"
    ADD_LIQUIDITY = "add_liquidity"
    REMOVE_LIQUIDITY = "remove_liquidity"
    PRICE_SHOCK = "price_shock"  # External price shock


@dataclass(order=True)
class SimEvent:
    """
    A scheduled simulation event. Ordered by (scheduled_step, seq) for
    deterministic processing within each step.
    """
    scheduled_step: int
    seq: int = field(compare=True)
    event_type: EventType = field(compare=False)
    event_id: str = field(compare=False, default_factory=lambda: uuid.uuid4().hex[:8])
    initiator: str = field(compare=False, default="system")
    pool_id: str = field(compare=False, default="")
    payload: dict = field(compare=False, default_factory=dict)
    status: str = field(compare=False, default="pending")

    @property
    def sort_key(self) -> tuple:
        return (self.scheduled_step, self.seq)

    def execute_result(self, success: bool, result_data: dict | None = None) -> None:
        self.status = "executed" if success else "failed"
        if result_data:
            self.payload.update(result_data)

    def to_dict(self) -> dict:
        return {
            "event_id": self.event_id,
            "scheduled_step": self.scheduled_step,
            "event_type": self.event_type.value,
            "initiator": self.initiator,
            "pool_id": self.pool_id,
            "payload": self.payload,
            "status": self.status,
        }


# Factory functions for creating events
_seq_counter = 0


def _next_seq() -> int:
    global _seq_counter
    _seq_counter += 1
    return _seq_counter


def reset_seq():
    global _seq_counter
    _seq_counter = 0


def create_swap_event(
    step: int,
    pool_id: str,
    initiator: str,
    token_in: TokenSymbol,
    amount_in: Decimal,
    min_amount_out: Decimal = Decimal("0"),
) -> SimEvent:
    return SimEvent(
        scheduled_step=step,
        seq=_next_seq(),
        event_type=EventType.SWAP,
        initiator=initiator,
        pool_id=pool_id,
        payload={
            "token_in": token_in.value,
            "amount_in": str(amount_in),
            "min_amount_out": str(min_amount_out),
        },
    )


def create_add_liquidity_event(
    step: int,
    pool_id: str,
    initiator: str,
    amount_a: Decimal,
    amount_b: Decimal,
) -> SimEvent:
    return SimEvent(
        scheduled_step=step,
        seq=_next_seq(),
        event_type=EventType.ADD_LIQUIDITY,
        initiator=initiator,
        pool_id=pool_id,
        payload={
            "amount_a": str(amount_a),
            "amount_b": str(amount_b),
        },
    )


def create_remove_liquidity_event(
    step: int,
    pool_id: str,
    initiator: str,
    lp_amount: Decimal,
) -> SimEvent:
    return SimEvent(
        scheduled_step=step,
        seq=_next_seq(),
        event_type=EventType.REMOVE_LIQUIDITY,
        initiator=initiator,
        pool_id=pool_id,
        payload={
            "lp_amount": str(lp_amount),
        },
    )

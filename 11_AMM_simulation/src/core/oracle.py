"""TWAP (Time-Weighted Average Price) oracle."""

from decimal import Decimal

ONE = Decimal("1")
ZERO = Decimal("0")


class TWAPOracle:
    """
    Accumulates price-over-time for Time-Weighted Average Price calculation.

    Works with discrete simulation steps. Each step, the oracle is updated
    with the current spot price and the time delta (usually 1 step).

    TWAP = sum(price_i * time_i) / sum(time_i)
    """

    def __init__(self):
        self._price_cumulative_a: Decimal = ZERO
        self._price_cumulative_b: Decimal = ZERO
        self._total_time: Decimal = ZERO
        self._last_price_a: Decimal = ONE
        self._last_price_b: Decimal = ONE

    def update(self, price_a: Decimal, price_b: Decimal, time_delta: Decimal) -> None:
        """
        Accumulate price over time.

        Args:
            price_a: spot price of token_a in terms of token_b
            price_b: spot price of token_b in terms of token_a
            time_delta: time elapsed since last update
        """
        if time_delta <= ZERO:
            return
        if price_a <= ZERO or price_b <= ZERO:
            raise ValueError("Prices must be positive")

        self._price_cumulative_a += price_a * time_delta
        self._price_cumulative_b += price_b * time_delta
        self._total_time += time_delta
        self._last_price_a = price_a
        self._last_price_b = price_b

    def get_twap_a(self) -> Decimal:
        """Get TWAP of token_a in terms of token_b."""
        if self._total_time == ZERO:
            return self._last_price_a
        return self._price_cumulative_a / self._total_time

    def get_twap_b(self) -> Decimal:
        """Get TWAP of token_b in terms of token_a."""
        if self._total_time == ZERO:
            return self._last_price_b
        return self._price_cumulative_b / self._total_time

    @property
    def spot_price_a(self) -> Decimal:
        return self._last_price_a

    @property
    def spot_price_b(self) -> Decimal:
        return self._last_price_b

    @property
    def total_time(self) -> Decimal:
        return self._total_time

    def reset(self) -> None:
        """Reset the oracle state."""
        self._price_cumulative_a = ZERO
        self._price_cumulative_b = ZERO
        self._total_time = ZERO
        self._last_price_a = ONE
        self._last_price_b = ONE

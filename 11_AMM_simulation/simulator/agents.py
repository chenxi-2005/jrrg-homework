"""
Trading agents — autonomous actors in the simulation.

Each agent observes the current state and decides whether to produce
a SimEvent (swap, add/remove liquidity) for a future step.
"""

import random
from abc import ABC, abstractmethod
from decimal import Decimal
from typing import Optional

from src.core.types import TokenSymbol
from src.core.pool import LiquidityPool
from .clock import SimulationClock
from .events import (
    SimEvent,
    create_swap_event,
    create_add_liquidity_event,
    create_remove_liquidity_event,
)

ONE = Decimal("1")
ZERO = Decimal("0")


class TraderAgent(ABC):
    """Base class for all autonomous agents."""

    def __init__(self, user_id: str, rng: random.Random | None = None):
        self.user_id = user_id
        self._rng = rng or random.Random()

    @abstractmethod
    def decide_action(
        self,
        step: int,
        pools: dict[str, LiquidityPool],
        balances: dict[TokenSymbol, Decimal],
    ) -> Optional[SimEvent]:
        """
        Decide an action to take at the current step.

        Returns a SimEvent to schedule, or None to do nothing.
        """
        ...

    def set_seed(self, seed: int) -> None:
        self._rng = random.Random(seed)


class RandomTrader(TraderAgent):
    """
    Randomly swaps tokens in a random pool.

    Config:
        swap_probability: float = 0.3  — chance of swapping each step
        max_swap_fraction: float = 0.1 — max fraction of reserves to swap
        min_swap_fraction: float = 0.01
    """

    def __init__(self, user_id: str, rng=None, swap_probability=0.3,
                 max_swap_fraction=0.1, min_swap_fraction=0.01):
        super().__init__(user_id, rng)
        self.swap_probability = swap_probability
        self.max_swap_fraction = max_swap_fraction
        self.min_swap_fraction = min_swap_fraction

    def decide_action(self, step, pools, balances):
        if not pools or self._rng.random() > self.swap_probability:
            return None

        # Pick a random pool
        pool = self._rng.choice(list(pools.values()))

        # Decide direction: swap token_a or token_b
        if self._rng.random() < 0.5:
            token_in = pool.token_a
            reserve = pool.reserve_a
        else:
            token_in = pool.token_b
            reserve = pool.reserve_b

        # Skip if no balance
        bal = balances.get(token_in, ZERO)
        if bal <= ZERO:
            return None

        # Random swap size between min and max fraction of reserves
        fraction = Decimal(str(self._rng.uniform(self.min_swap_fraction, self.max_swap_fraction)))
        amount_in = reserve * fraction
        # Cap at user's balance
        amount_in = min(amount_in, bal)
        if amount_in <= ZERO:
            return None

        return create_swap_event(
            step=step + self._rng.randint(1, 3),
            pool_id=pool.pool_id,
            initiator=self.user_id,
            token_in=token_in,
            amount_in=amount_in,
        )


class Arbitrageur(TraderAgent):
    """
    Detects price discrepancies between pools holding the same token pair
    and executes arbitrage trades.

    For simplicity, arbitrage checks pairs of pools and trades on the cheaper one.
    """

    def __init__(self, user_id: str, rng=None, min_profit_bps: int = 10):
        super().__init__(user_id, rng)
        self.min_profit_bps = min_profit_bps  # minimum profit in basis points

    def decide_action(self, step, pools, balances):
        if len(pools) < 2:
            return None

        pool_list = list(pools.values())

        # Compare every pair of pools
        for i, p1 in enumerate(pool_list):
            for p2 in pool_list[i + 1:]:
                # Only compare pools with same token pair
                if {p1.token_a, p1.token_b} != {p2.token_a, p2.token_b}:
                    continue

                price1 = p1.get_spot_price()
                price2 = p2.get_spot_price()

                if price1 <= ZERO or price2 <= ZERO:
                    continue

                # Calculate profit opportunity in bps
                if price1 > price2:
                    diff_bps = int(((price1 - price2) / price2) * Decimal("10000"))
                    cheaper_pool, expensive_pool = p2, p1
                else:
                    diff_bps = int(((price2 - price1) / price1) * Decimal("10000"))
                    cheaper_pool, expensive_pool = p1, p2

                if diff_bps >= self.min_profit_bps:
                    # Buy from cheaper pool, sell to expensive pool
                    # Use a fraction of the cheaper pool's reserves
                    fraction = Decimal("0.05")
                    amount_in = cheaper_pool.reserve_a * fraction
                    if amount_in <= ZERO:
                        continue

                    return create_swap_event(
                        step=step + 1,
                        pool_id=cheaper_pool.pool_id,
                        initiator=self.user_id,
                        token_in=cheaper_pool.token_a,
                        amount_in=amount_in,
                    )

        return None


class TrendFollower(TraderAgent):
    """
    Follows price trends using a simple moving average heuristic.

    Config:
        lookback_steps: int = 5  — steps to look back for trend
        trade_fraction: float = 0.05 — fraction of reserves to trade
    """

    def __init__(self, user_id: str, rng=None, lookback_steps=5, trade_fraction=0.05):
        super().__init__(user_id, rng)
        self.lookback_steps = lookback_steps
        self.trade_fraction = trade_fraction
        self._price_history: dict[str, list[Decimal]] = {}  # pool_id -> [prices]

    def decide_action(self, step, pools, balances):
        if not pools:
            return None

        pool = self._rng.choice(list(pools.values()))
        pid = pool.pool_id

        # Track price
        current_price = pool.get_spot_price()
        self._price_history.setdefault(pid, []).append(current_price)

        prices = self._price_history[pid]
        if len(prices) < self.lookback_steps + 1:
            return None

        # Keep only recent prices
        self._price_history[pid] = prices[-self.lookback_steps - 1:]

        # Simple trend: compare recent average with older
        recent = sum(prices[-self.lookback_steps:], ZERO) / Decimal(str(self.lookback_steps))
        older = prices[0]

        if recent <= ZERO or older <= ZERO:
            return None

        trend = (recent - older) / older  # positive = uptrend

        fraction = Decimal(str(self.trade_fraction))

        if trend > Decimal("0.01"):
            # Uptrend: buy token_a (sell token_b)
            token_in = pool.token_b
            amount_in = pool.reserve_b * fraction
        elif trend < Decimal("-0.01"):
            # Downtrend: sell token_a (buy token_b)
            token_in = pool.token_a
            amount_in = pool.reserve_a * fraction
        else:
            return None

        bal = balances.get(token_in, ZERO)
        amount_in = min(amount_in, bal)
        if amount_in <= ZERO:
            return None

        return create_swap_event(
            step=step + 1,
            pool_id=pid,
            initiator=self.user_id,
            token_in=token_in,
            amount_in=amount_in,
        )


class LiquidityProvider(TraderAgent):
    """
    Adds or removes liquidity based on pool conditions.

    Config:
        add_probability: float = 0.1
        remove_probability: float = 0.05
        deposit_fraction: float = 0.1  — fraction of reserves to deposit
    """

    def __init__(self, user_id: str, rng=None, add_probability=0.1,
                 remove_probability=0.05, deposit_fraction=0.1):
        super().__init__(user_id, rng)
        self.add_probability = add_probability
        self.remove_probability = remove_probability
        self.deposit_fraction = deposit_fraction

    def decide_action(self, step, pools, balances):
        if not pools:
            return None

        pool = self._rng.choice(list(pools.values()))

        roll = self._rng.random()

        if roll < self.add_probability:
            # Add proportional liquidity
            fraction = Decimal(str(self.deposit_fraction))
            amount_a = pool.reserve_a * fraction
            amount_b = pool.reserve_b * fraction

            # Cap at user balances
            bal_a = balances.get(pool.token_a, ZERO)
            bal_b = balances.get(pool.token_b, ZERO)
            if bal_a < amount_a or bal_b < amount_b:
                return None

            return create_add_liquidity_event(
                step=step + 1,
                pool_id=pool.pool_id,
                initiator=self.user_id,
                amount_a=amount_a,
                amount_b=amount_b,
            )

        elif roll < self.add_probability + self.remove_probability:
            # Remove some liquidity
            lp_balance = pool.get_lp_balance(self.user_id)
            if lp_balance <= ZERO:
                return None

            remove_frac = Decimal(str(self._rng.uniform(0.1, 0.5)))
            lp_to_remove = lp_balance * remove_frac
            if lp_to_remove <= ZERO:
                return None

            return create_remove_liquidity_event(
                step=step + 1,
                pool_id=pool.pool_id,
                initiator=self.user_id,
                lp_amount=lp_to_remove,
            )

        return None


class WhaleAgent(TraderAgent):
    """
    Periodically executes large trades that cause significant price impact.

    Config:
        trade_interval: int = 10       — steps between whale trades
        trade_fraction: float = 0.2    — fraction of reserves per trade
    """

    def __init__(self, user_id: str, rng=None, trade_interval=10, trade_fraction=0.2):
        super().__init__(user_id, rng)
        self.trade_interval = trade_interval
        self.trade_fraction = trade_fraction
        self._last_trade_step: dict[str, int] = {}  # pool_id -> last trade step

    def decide_action(self, step, pools, balances):
        if not pools:
            return None

        pool = self._rng.choice(list(pools.values()))

        # Check if enough steps have passed
        last = self._last_trade_step.get(pool.pool_id, -self.trade_interval)
        if step - last < self.trade_interval:
            return None

        # Alternate direction
        direction = "sell" if self._rng.random() < 0.5 else "buy"
        fraction = Decimal(str(self.trade_fraction))

        if direction == "sell":
            token_in = pool.token_a
            amount_in = pool.reserve_a * fraction
        else:
            token_in = pool.token_b
            amount_in = pool.reserve_b * fraction

        bal = balances.get(token_in, ZERO)
        amount_in = min(amount_in, bal)
        if amount_in <= ZERO:
            return None

        self._last_trade_step[pool.pool_id] = step

        return create_swap_event(
            step=step + self._rng.randint(1, 3),
            pool_id=pool.pool_id,
            initiator=self.user_id,
            token_in=token_in,
            amount_in=amount_in,
        )


# Agent factory from config dict
def create_agent(agent_config: dict, rng: random.Random) -> TraderAgent:
    """Create an agent from a configuration dictionary."""
    agent_type = agent_config["type"]
    user_id = agent_config["user_id"]
    params = agent_config.get("params", {})

    agent_rng = random.Random(rng.randint(0, 2**31 - 1))

    match agent_type:
        case "random":
            return RandomTrader(user_id, agent_rng, **params)
        case "arbitrageur":
            return Arbitrageur(user_id, agent_rng, **params)
        case "trend_follower":
            return TrendFollower(user_id, agent_rng, **params)
        case "liquidity_provider":
            return LiquidityProvider(user_id, agent_rng, **params)
        case "whale":
            return WhaleAgent(user_id, agent_rng, **params)
        case _:
            raise ValueError(f"Unknown agent type: {agent_type}")

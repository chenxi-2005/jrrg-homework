"""
Simulation Engine — the central orchestrator.

Maintains the event queue, coordinates between pools, wallets, agents,
and the logger. Processes events step-by-step with deterministic ordering.
"""

import heapq
import random
from decimal import Decimal
from dataclasses import dataclass, field
from typing import Optional

from src.core.types import (
    TokenSymbol, PoolConfig, SimulationConfig, SwapResult,
)
from src.core.pool import LiquidityPool
from src.core.token import TokenLedger
from src.core.wallet import Wallet
from src.core.exceptions import AMMException, InsufficientBalanceError

from .clock import SimulationClock
from .events import SimEvent, EventType, reset_seq, _next_seq
from .agents import TraderAgent, create_agent
from .logger import StateLogger

ONE = Decimal("1")
ZERO = Decimal("0")


@dataclass
class StepResult:
    """Result of processing one simulation step."""
    step: int
    events_processed: int = 0
    events_failed: int = 0
    swaps_executed: int = 0
    liquidity_ops: int = 0
    agents_activated: int = 0
    new_events_scheduled: int = 0
    errors: list[str] = field(default_factory=list)


class SimulationEngine:
    """
    Event-driven AMM simulation engine.

    Usage:
        config = SimulationConfig(...)
        engine = SimulationEngine(config)
        engine.setup()
        engine.run_to_completion()
        results = engine.logger.snapshots_df()
    """

    def __init__(self, config: SimulationConfig):
        self.config = config
        self.clock = SimulationClock()
        self.ledger = TokenLedger()
        self.pools: dict[str, LiquidityPool] = {}
        self.wallets: dict[str, Wallet] = {}
        self.agents: list[TraderAgent] = []
        self._event_queue: list[tuple] = []  # (scheduled_step, seq, event)
        self._event_seq: int = 0
        self.logger = StateLogger()
        self._rng = random.Random(config.random_seed)
        self._running = False
        self._paused = False

    # ------------------------------------------------------------------
    # Setup
    # ------------------------------------------------------------------

    def setup(self) -> None:
        """Initialize pools, users, and agents from config."""
        reset_seq()
        self._event_queue.clear()
        self.clock.reset()
        self.ledger = TokenLedger()
        self.pools.clear()
        self.wallets.clear()
        self.agents.clear()
        self.logger.clear()
        self._running = False
        self._paused = False
        self._rng = random.Random(self.config.random_seed)

        self._setup_pools()
        self._setup_users()
        self._setup_agents()

        # Log initial snapshot
        self.logger.log_snapshot(self.clock.step, self.pools, self.ledger)

    def _setup_pools(self) -> None:
        for pc in self.config.pools:
            self.register_pool(pc)

    def _setup_users(self) -> None:
        for user_cfg in self.config.users:
            user_id = user_cfg["user_id"]
            balances = {}
            for tok_str, amount_str in user_cfg.get("balances", {}).items():
                balances[TokenSymbol(tok_str)] = Decimal(amount_str)
            self.register_user(user_id, balances)

    def _setup_agents(self) -> None:
        for agent_cfg in self.config.agents:
            agent = create_agent(agent_cfg, self._rng)
            self.agents.append(agent)

    # ------------------------------------------------------------------
    # Registration
    # ------------------------------------------------------------------

    def register_pool(self, config: PoolConfig, pool_id: str | None = None) -> LiquidityPool:
        """Create and register a new liquidity pool."""
        pool = LiquidityPool(config, pool_id=pool_id)
        self.pools[pool.pool_id] = pool
        return pool

    def register_user(
        self, user_id: str, initial_balances: dict[TokenSymbol, Decimal]
    ) -> Wallet:
        """Register a user with initial token balances."""
        self.ledger.register_user(user_id, initial_balances)
        wallet = Wallet(user_id, self.ledger)
        self.wallets[user_id] = wallet
        return wallet

    def register_agent(self, agent: TraderAgent) -> None:
        """Add an autonomous agent to the simulation."""
        self.agents.append(agent)

    # ------------------------------------------------------------------
    # Event scheduling
    # ------------------------------------------------------------------

    def schedule_event(self, event: SimEvent, delay: int = 0) -> None:
        """Schedule an event for `delay` steps from now."""
        target_step = self.clock.step + delay
        event.scheduled_step = target_step
        heapq.heappush(
            self._event_queue,
            (target_step, event.seq, event),
        )

    def get_pending_event_count(self) -> int:
        return len(self._event_queue)

    # ------------------------------------------------------------------
    # Step processing
    # ------------------------------------------------------------------

    def step(self) -> StepResult:
        """
        Advance the simulation by one step.

        1. Advance clock
        2. Pop and process all events scheduled for this step
        3. Ask each agent to decide and schedule new events
        4. Update oracles
        5. Log snapshot
        """
        if self._paused:
            return StepResult(step=self.clock.step)

        self.clock.advance()
        current_step = self.clock.step

        result = StepResult(step=current_step)

        # --- Process events ---
        while self._event_queue and self._event_queue[0][0] <= current_step:
            _, _, event = heapq.heappop(self._event_queue)
            try:
                self._process_event(event)
                result.events_processed += 1
            except AMMException as e:
                event.status = "failed"
                result.events_failed += 1
                result.errors.append(f"[{event.event_id}] {e}")
            self.logger.log_event(event)

        # --- Advance pool oracles ---
        for pool in self.pools.values():
            pool.advance_step(current_step)

        # --- Agent decisions ---
        if self._running or True:  # always let agents decide when stepping
            for agent in self.agents:
                balances = self.ledger.get_all_balances(agent.user_id)
                action = agent.decide_action(
                    current_step, self.pools, balances
                )
                if action is not None:
                    self.schedule_event(action)
                    result.new_events_scheduled += 1
                    result.agents_activated += 1

        # --- Log snapshot ---
        if current_step % self.config.log_snapshot_interval == 0:
            self.logger.log_snapshot(current_step, self.pools, self.ledger)

        return result

    def _process_event(self, event: SimEvent) -> None:
        """Dispatch an event to its handler."""
        match event.event_type:
            case EventType.SWAP:
                self._handle_swap(event)
            case EventType.ADD_LIQUIDITY:
                self._handle_add_liquidity(event)
            case EventType.REMOVE_LIQUIDITY:
                self._handle_remove_liquidity(event)
            case _:
                raise ValueError(f"Unknown event type: {event.event_type}")

    def _handle_swap(self, event: SimEvent) -> None:
        pool = self._get_pool(event.pool_id)
        token_in = TokenSymbol(event.payload["token_in"])
        amount_in = Decimal(event.payload["amount_in"])
        min_out = Decimal(event.payload.get("min_amount_out", "0"))

        # Determine output token
        token_out = pool.token_b if token_in == pool.token_a else pool.token_a

        # Check user balance
        user_bal = self.ledger.get_balance(event.initiator, token_in)
        if user_bal < amount_in:
            raise InsufficientBalanceError(
                event.initiator, token_in.value, str(amount_in), str(user_bal)
            )

        # Execute swap on pool
        result = pool.swap(token_in, amount_in)

        if result.amount_out < min_out:
            raise AMMException(
                f"Slippage exceeded: got {result.amount_out}, min {min_out}"
            )

        # Transfer tokens: user -> pool
        self.ledger.burn(event.initiator, token_in, amount_in)
        # Transfer tokens: pool -> user
        self.ledger.mint(event.initiator, token_out, result.amount_out)

        event.status = "executed"
        event.payload.update({
            "token_out": token_out.value,
            "amount_out": str(result.amount_out),
            "fee_collected": str(result.fee_collected),
            "price_impact_bps": result.price_impact_bps,
            "effective_price": str(result.effective_price),
        })

    def _handle_add_liquidity(self, event: SimEvent) -> None:
        pool = self._get_pool(event.pool_id)
        amount_a = Decimal(event.payload["amount_a"])
        amount_b = Decimal(event.payload["amount_b"])

        # Check balances
        bal_a = self.ledger.get_balance(event.initiator, pool.token_a)
        bal_b = self.ledger.get_balance(event.initiator, pool.token_b)
        if bal_a < amount_a:
            raise InsufficientBalanceError(
                event.initiator, pool.token_a.value, str(amount_a), str(bal_a)
            )
        if bal_b < amount_b:
            raise InsufficientBalanceError(
                event.initiator, pool.token_b.value, str(amount_b), str(bal_b)
            )

        # Burn user tokens (they go into the pool)
        self.ledger.burn(event.initiator, pool.token_a, amount_a)
        self.ledger.burn(event.initiator, pool.token_b, amount_b)

        # Add liquidity to pool
        lp_minted = pool.add_liquidity(event.initiator, amount_a, amount_b)

        event.status = "executed"
        event.payload["lp_minted"] = str(lp_minted)

    def _handle_remove_liquidity(self, event: SimEvent) -> None:
        pool = self._get_pool(event.pool_id)
        lp_amount = Decimal(event.payload["lp_amount"])

        amount_a, amount_b = pool.remove_liquidity(event.initiator, lp_amount)

        # Return tokens to user
        self.ledger.mint(event.initiator, pool.token_a, amount_a)
        self.ledger.mint(event.initiator, pool.token_b, amount_b)

        event.status = "executed"
        event.payload["amount_a_returned"] = str(amount_a)
        event.payload["amount_b_returned"] = str(amount_b)

    def _get_pool(self, pool_id: str) -> LiquidityPool:
        pool = self.pools.get(pool_id)
        if pool is None:
            raise AMMException(f"Pool '{pool_id}' not found")
        return pool

    # ------------------------------------------------------------------
    # Run control
    # ------------------------------------------------------------------

    def run_to_step(self, target_step: int) -> list[StepResult]:
        """Run simulation until the clock reaches target_step."""
        self._running = True
        results = []
        while self.clock.step < target_step:
            result = self.step()
            results.append(result)
        self._running = False
        return results

    def run_to_completion(self) -> list[StepResult]:
        """Run until max_steps from config is reached."""
        return self.run_to_step(self.config.max_steps)

    def pause(self) -> None:
        self._paused = True
        self.clock.pause()

    def resume(self) -> None:
        self._paused = False
        self.clock.resume()

    def reset(self) -> None:
        """Reset to initial state and re-run setup."""
        self.setup()

    # ------------------------------------------------------------------
    # State
    # ------------------------------------------------------------------

    @property
    def running(self) -> bool:
        return self._running

    @property
    def paused(self) -> bool:
        return self._paused

    @property
    def step_number(self) -> int:
        return self.clock.step

    def get_state_snapshot(self) -> dict:
        """Get a full JSON-serializable state snapshot."""
        pools_state = {}
        for pid, pool in self.pools.items():
            pools_state[pid] = pool.get_state(step=self.clock.step).model_dump()

        users_state = {}
        for uid in self.ledger.list_users():
            balances = self.ledger.get_all_balances(uid)
            users_state[uid] = {
                tok.value: str(bal) for tok, bal in balances.items()
            }

        return {
            "step": self.clock.step,
            "running": self._running,
            "paused": self._paused,
            "pools": pools_state,
            "users": users_state,
            "event_queue_size": len(self._event_queue),
        }

    def get_summary(self) -> dict:
        """Get simulation summary statistics."""
        log_summary = self.logger.export_summary()
        return {
            "step": self.clock.step,
            "max_steps": self.config.max_steps,
            "pools": len(self.pools),
            "users": len(self.wallets),
            "agents": len(self.agents),
            **log_summary,
        }

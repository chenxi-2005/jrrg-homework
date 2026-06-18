"""Tests for the SimulationEngine."""

import pytest
from decimal import Decimal

from src.core.types import (
    TokenSymbol, SimulationConfig, PoolConfig,
)
from simulator.engine import SimulationEngine


def make_simple_config() -> SimulationConfig:
    return SimulationConfig(
        name="test",
        random_seed=42,
        max_steps=10,
        pools=[
            PoolConfig(
                token_a=TokenSymbol.ETH,
                token_b=TokenSymbol.USDC,
                initial_reserve_a=Decimal("100"),
                initial_reserve_b=Decimal("200000"),
            ),
        ],
        users=[
            {
                "user_id": "alice",
                "balances": {"ETH": "50", "USDC": "100000"},
            },
            {
                "user_id": "bob",
                "balances": {"ETH": "30", "USDC": "50000"},
            },
        ],
        agents=[
            {"type": "random", "user_id": "alice", "params": {"swap_probability": 0.8}},
        ],
    )


class TestEngineSetup:
    def test_setup_creates_pools(self):
        config = make_simple_config()
        engine = SimulationEngine(config)
        engine.setup()
        assert len(engine.pools) == 1
        pool = list(engine.pools.values())[0]
        assert pool.token_a == TokenSymbol.ETH
        assert pool.token_b == TokenSymbol.USDC

    def test_setup_creates_users(self):
        config = make_simple_config()
        engine = SimulationEngine(config)
        engine.setup()
        assert "alice" in engine.wallets
        assert engine.ledger.get_balance("alice", TokenSymbol.ETH) == Decimal("50")

    def test_setup_creates_agents(self):
        config = make_simple_config()
        engine = SimulationEngine(config)
        engine.setup()
        assert len(engine.agents) == 1

    def test_setup_logs_initial_snapshot(self):
        config = make_simple_config()
        engine = SimulationEngine(config)
        engine.setup()
        df = engine.logger.snapshots_df()
        assert len(df) >= 1  # initial snapshot
        assert df.iloc[0]["step"] == 0


class TestStep:
    def test_single_step(self):
        config = make_simple_config()
        engine = SimulationEngine(config)
        engine.setup()
        result = engine.step()
        assert result.step == 1
        assert result.events_processed >= 0

    def test_multiple_steps(self):
        config = make_simple_config()
        engine = SimulationEngine(config)
        engine.setup()
        engine.run_to_step(5)
        assert engine.clock.step == 5

    def test_step_increments_clock(self):
        config = make_simple_config()
        engine = SimulationEngine(config)
        engine.setup()
        engine.step()
        assert engine.clock.step == 1
        engine.step()
        assert engine.clock.step == 2

    def test_deterministic_with_same_seed(self):
        config = make_simple_config()
        config.random_seed = 42

        engine1 = SimulationEngine(config)
        engine1.setup()
        engine1.run_to_step(5)

        engine2 = SimulationEngine(config)
        engine2.setup()
        engine2.run_to_step(5)

        # Same seed should produce identical results
        df1 = engine1.logger.events_df()
        df2 = engine2.logger.events_df()
        assert len(df1) == len(df2)


class TestRunControl:
    def test_pause_resume(self):
        config = make_simple_config()
        engine = SimulationEngine(config)
        engine.setup()
        engine.pause()
        result = engine.step()
        assert result.step == 0  # clock didn't advance
        engine.resume()
        result = engine.step()
        assert result.step == 1

    def test_reset(self):
        config = make_simple_config()
        engine = SimulationEngine(config)
        engine.setup()
        engine.run_to_step(3)
        engine.reset()
        assert engine.clock.step == 0

    def test_run_to_completion(self):
        config = make_simple_config()
        config.max_steps = 5
        engine = SimulationEngine(config)
        engine.setup()
        results = engine.run_to_completion()
        assert engine.clock.step == 5
        assert len(results) == 5


class TestSwapEventProcessing:
    def test_swap_transfers_tokens(self):
        config = make_simple_config()
        config.max_steps = 10
        # Set agent swap_probability to 0 so no agent-initiated events
        config.agents[0]["params"]["swap_probability"] = 0.0
        engine = SimulationEngine(config)
        engine.setup()

        # Manually schedule a swap
        from simulator.events import create_swap_event
        event = create_swap_event(
            step=1, pool_id=list(engine.pools.keys())[0],
            initiator="alice", token_in=TokenSymbol.ETH,
            amount_in=Decimal("1"),
        )
        engine.schedule_event(event, delay=1)

        # Step to process the event
        engine.step()  # step to 1 — event should fire
        # Check alice's balance changed
        eth_bal = engine.ledger.get_balance("alice", TokenSymbol.ETH)
        assert eth_bal < Decimal("50")  # spent some ETH

    def test_swap_with_insufficient_balance_fails(self):
        config = make_simple_config()
        config.agents[0]["params"]["swap_probability"] = 0.0
        engine = SimulationEngine(config)
        engine.setup()

        from simulator.events import create_swap_event
        event = create_swap_event(
            step=1, pool_id=list(engine.pools.keys())[0],
            initiator="alice", token_in=TokenSymbol.ETH,
            amount_in=Decimal("99999"),  # more than she has
        )
        engine.schedule_event(event)

        result = engine.step()
        # Should have a failed event
        assert result.events_failed >= 1

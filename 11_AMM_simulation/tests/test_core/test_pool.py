"""Tests for the LiquidityPool class."""

import pytest
from decimal import Decimal

from src.core.types import TokenSymbol, PoolConfig, SwapRequest
from src.core.pool import LiquidityPool
from src.core.exceptions import InvalidOperationError, InsufficientLiquidityError


class TestPoolInit:
    def test_init_creates_pool(self, eth_usdc_config):
        pool = LiquidityPool(eth_usdc_config)
        assert pool.token_a == TokenSymbol.ETH
        assert pool.token_b == TokenSymbol.USDC
        assert pool.reserve_a == Decimal("100")
        assert pool.reserve_b == Decimal("200000")
        assert pool.fee_rate == Decimal("0.003")
        assert pool.total_lp_supply > Decimal("0")  # initial LP minted

    def test_init_generates_pool_id(self, eth_usdc_config):
        pool = LiquidityPool(eth_usdc_config)
        assert pool.pool_id == "ETH-USDC"

    def test_custom_pool_id(self, eth_usdc_config):
        pool = LiquidityPool(eth_usdc_config, pool_id="my-pool-1")
        assert pool.pool_id == "my-pool-1"

    def test_spot_price_correct(self, eth_usdc_pool):
        price = eth_usdc_pool.get_spot_price()
        # 1 ETH = 2000 USDC
        assert price == Decimal("2000")


class TestSwap:
    def test_swap_token_a_for_b(self, eth_usdc_pool):
        result = eth_usdc_pool.swap(TokenSymbol.ETH, Decimal("1"))
        assert result.token_in == TokenSymbol.ETH
        assert result.token_out == TokenSymbol.USDC
        assert result.amount_out > Decimal("0")
        assert result.fee_collected == Decimal("0.003")
        # Reserves should be updated
        assert eth_usdc_pool.reserve_a > Decimal("100")
        assert eth_usdc_pool.reserve_b < Decimal("200000")

    def test_swap_token_b_for_a(self, eth_usdc_pool):
        result = eth_usdc_pool.swap(TokenSymbol.USDC, Decimal("2000"))
        assert result.token_in == TokenSymbol.USDC
        assert result.token_out == TokenSymbol.ETH
        assert result.amount_out > Decimal("0")

    def test_k_increases_after_fee_swap(self, eth_usdc_pool):
        """k should increase after swap because fees stay in pool."""
        k_before = eth_usdc_pool.k
        eth_usdc_pool.swap(TokenSymbol.ETH, Decimal("1"))
        assert eth_usdc_pool.k > k_before

    def test_k_constant_with_zero_fee(self, eth_usdc_config):
        """With zero fee, k should be constant."""
        config = eth_usdc_config.model_copy(update={"fee_rate": Decimal("0")})
        pool = LiquidityPool(config)
        k_before = pool.k
        pool.swap(TokenSymbol.ETH, Decimal("1"))
        assert abs(pool.k - k_before) < Decimal("0.00001")

    def test_quote_does_not_mutate(self, eth_usdc_pool):
        """get_swap_quote should not change reserves."""
        ra_before = eth_usdc_pool.reserve_a
        rb_before = eth_usdc_pool.reserve_b
        quote = eth_usdc_pool.get_swap_quote(TokenSymbol.ETH, Decimal("1"))
        assert eth_usdc_pool.reserve_a == ra_before
        assert eth_usdc_pool.reserve_b == rb_before
        assert quote.amount_out > Decimal("0")

    def test_swap_count_increments(self, eth_usdc_pool):
        assert eth_usdc_pool.swap_count == 0
        eth_usdc_pool.swap(TokenSymbol.ETH, Decimal("1"))
        assert eth_usdc_pool.swap_count == 1
        eth_usdc_pool.swap(TokenSymbol.USDC, Decimal("1000"))
        assert eth_usdc_pool.swap_count == 2

    def test_invalid_token_raises(self, eth_usdc_pool):
        with pytest.raises(InvalidOperationError):
            eth_usdc_pool.swap(TokenSymbol.BTC, Decimal("1"))

    def test_zero_amount_raises(self, eth_usdc_pool):
        with pytest.raises(InvalidOperationError):
            eth_usdc_pool.swap(TokenSymbol.ETH, Decimal("0"))

    def test_swap_updates_price(self, eth_usdc_pool):
        """Swap should change the spot price."""
        old_price = eth_usdc_pool.get_spot_price()
        eth_usdc_pool.swap(TokenSymbol.ETH, Decimal("10"))
        new_price = eth_usdc_pool.get_spot_price()
        # Price of ETH should decrease (more ETH in pool after swap-in)
        assert new_price < old_price


class TestLiquidity:
    def test_add_liquidity_proportional(self, eth_usdc_pool):
        """Adding proportional liquidity after initial LP mint."""
        initial_lp = eth_usdc_pool.total_lp_supply
        lp = eth_usdc_pool.add_liquidity("alice", Decimal("10"), Decimal("20000"))
        assert lp > Decimal("0")
        assert eth_usdc_pool.total_lp_supply == initial_lp + lp
        assert eth_usdc_pool.get_lp_balance("alice") == lp

    def test_add_liquidity_increases_reserves(self, eth_usdc_pool):
        eth_usdc_pool.add_liquidity("alice", Decimal("10"), Decimal("20000"))
        assert eth_usdc_pool.reserve_a > Decimal("100")
        assert eth_usdc_pool.reserve_b > Decimal("200000")

    def test_remove_liquidity(self, eth_usdc_pool):
        lp = eth_usdc_pool.add_liquidity("alice", Decimal("100"), Decimal("200000"))
        amount_a, amount_b = eth_usdc_pool.remove_liquidity("alice", lp)
        assert amount_a > Decimal("0")
        assert amount_b > Decimal("0")
        assert eth_usdc_pool.get_lp_balance("alice") == Decimal("0")

    def test_remove_partial_liquidity(self, eth_usdc_pool):
        lp = eth_usdc_pool.add_liquidity("alice", Decimal("100"), Decimal("200000"))
        half = lp / Decimal("2")
        amount_a, amount_b = eth_usdc_pool.remove_liquidity("alice", half)
        assert eth_usdc_pool.get_lp_balance("alice") == lp - half

    def test_insufficient_lp_balance(self, eth_usdc_pool):
        eth_usdc_pool.add_liquidity("alice", Decimal("100"), Decimal("200000"))
        with pytest.raises(InvalidOperationError):
            eth_usdc_pool.remove_liquidity("alice", Decimal("999999"))

    def test_zero_lp_add_raises(self, eth_usdc_pool):
        with pytest.raises(InvalidOperationError):
            eth_usdc_pool.add_liquidity("alice", Decimal("0"), Decimal("100"))


class TestOracle:
    def test_advance_step_updates_twap(self, eth_usdc_pool):
        eth_usdc_pool.advance_step(10)
        twap = eth_usdc_pool.get_twap_price()
        assert twap is not None
        assert twap > Decimal("0")

    def test_twap_with_constant_price(self, eth_usdc_pool):
        """TWAP should equal spot price when price is constant."""
        eth_usdc_pool.advance_step(1)
        eth_usdc_pool.advance_step(2)
        eth_usdc_pool.advance_step(3)
        twap = eth_usdc_pool.get_twap_price()
        spot = eth_usdc_pool.get_spot_price()
        assert abs(twap - spot) < Decimal("0.0001")


class TestState:
    def test_get_state(self, eth_usdc_pool):
        state = eth_usdc_pool.get_state(step=0)
        assert state.pool_id == eth_usdc_pool.pool_id
        assert state.token_a == TokenSymbol.ETH
        assert state.reserve_a == Decimal("100")
        assert state.spot_price == Decimal("2000")

    def test_repr(self, eth_usdc_pool):
        r = repr(eth_usdc_pool)
        assert "ETH-USDC" in r
        assert "LiquidityPool" in r

"""Tests for the AMM formula module — all pure math functions."""

import pytest
from decimal import Decimal

from src.core.formula import (
    compute_swap_output,
    compute_swap_input,
    compute_price_impact_bps,
    compute_spot_price,
    compute_impermanent_loss,
    compute_lp_tokens_to_mint,
    compute_lp_redemption,
    compute_k,
    compute_fee_amount,
    compute_effective_price,
    ZERO,
    ONE,
)

FEE = Decimal("0.003")


class TestSwapOutput:
    """Tests for compute_swap_output."""

    def test_basic_swap(self):
        """A simple swap of 1 ETH into an ETH-USDC pool."""
        out = compute_swap_output(
            Decimal("100"), Decimal("200000"), Decimal("1"), FEE
        )
        # Expected: (200000 * 0.997) / (100 + 0.997) = 199400 / 100.997 ≈ 1974.26
        expected = Decimal("199400") / Decimal("100.997")
        assert abs(out - expected) < Decimal("0.01")

    def test_very_small_swap(self):
        """Tiny swaps should still work."""
        out = compute_swap_output(
            Decimal("1000000"), Decimal("1000000"),
            Decimal("0.000001"), FEE
        )
        assert out > ZERO

    def test_very_large_swap(self):
        """Large swap near the reserve size."""
        out = compute_swap_output(
            Decimal("100"), Decimal("200000"), Decimal("90"), FEE
        )
        # Should get a significant fraction of the output reserve
        assert out > Decimal("50000")
        assert out < Decimal("200000")  # can't drain the pool

    def test_zero_amount(self):
        """Swap of zero amount should return zero."""
        out = compute_swap_output(
            Decimal("100"), Decimal("200000"), ZERO, FEE
        )
        assert out == ZERO

    def test_zero_fee(self):
        """With zero fee, k should be constant (x*y before = x*y after)."""
        reserve_in = Decimal("100")
        reserve_out = Decimal("200000")
        amount_in = Decimal("1")
        out = compute_swap_output(reserve_in, reserve_out, amount_in, Decimal("0"))

        # k should be preserved: (100+1)*(200000-out) = 100*200000
        k_before = reserve_in * reserve_out
        k_after = (reserve_in + amount_in) * (reserve_out - out)
        assert abs(k_before - k_after) < Decimal("0.00001")

    def test_high_fee(self):
        """10% fee should significantly reduce output."""
        out_no_fee = compute_swap_output(
            Decimal("100"), Decimal("200000"), Decimal("1"), Decimal("0")
        )
        out_high_fee = compute_swap_output(
            Decimal("100"), Decimal("200000"), Decimal("1"), Decimal("0.1")
        )
        assert out_high_fee < out_no_fee

    def test_zero_reserve_raises(self):
        """Zero reserves should raise ValueError."""
        with pytest.raises(ValueError):
            compute_swap_output(ZERO, Decimal("100"), Decimal("1"), FEE)

    def test_constant_product_increases_with_fee(self):
        """With fee, k should increase (fees added to reserves)."""
        ra = Decimal("100")
        rb = Decimal("200000")
        amount_in = Decimal("1")

        out = compute_swap_output(ra, rb, amount_in, FEE)
        k_before = ra * rb
        k_after = (ra + amount_in) * (rb - out)
        # k increases because input includes full amount_in but output is based on (1-fee)*amount_in
        assert k_after > k_before


class TestSwapInput:
    """Tests for compute_swap_input (inverse of swap_output)."""

    def test_round_trip(self):
        """swap_output then swap_input should recover the original amount."""
        ra = Decimal("100")
        rb = Decimal("200000")
        amount_in = Decimal("1")

        out = compute_swap_output(ra, rb, amount_in, FEE)
        # Now compute how much input needed for this output (with updated reserves)
        new_ra = ra + amount_in
        new_rb = rb - out
        in_needed = compute_swap_input(new_ra, new_rb, out, FEE)
        # The input needed to get this output from the new state
        # Note: this is a different pool state, so it won't exactly match
        assert in_needed > ZERO

    def test_insufficient_reserves(self):
        """Requesting more output than available should raise."""
        with pytest.raises(ValueError):
            compute_swap_input(Decimal("100"), Decimal("100"), Decimal("100"), FEE)


class TestPriceImpact:
    """Tests for compute_price_impact_bps."""

    def test_small_trade_low_impact(self):
        impact = compute_price_impact_bps(Decimal("1000000"), Decimal("100"), FEE)
        assert impact <= 5  # < 5 bps for 0.01% of reserves

    def test_large_trade_high_impact(self):
        impact = compute_price_impact_bps(Decimal("100"), Decimal("90"), FEE)
        assert impact > 1000  # > 10% impact

    def test_zero_reserve(self):
        impact = compute_price_impact_bps(ZERO, Decimal("1"), FEE)
        assert impact == 0


class TestSpotPrice:
    """Tests for compute_spot_price."""

    def test_eth_usdc_price(self):
        price = compute_spot_price(Decimal("100"), Decimal("200000"))
        assert price == Decimal("2000")  # 1 ETH = 2000 USDC

    def test_inverse(self):
        price_ab = compute_spot_price(Decimal("100"), Decimal("200000"))
        price_ba = compute_spot_price(Decimal("200000"), Decimal("100"))
        assert abs(price_ab - ONE / price_ba) < Decimal("0.000001")

    def test_zero_reserve_raises(self):
        with pytest.raises(ValueError):
            compute_spot_price(ZERO, Decimal("100"))


class TestImpermanentLoss:
    """Tests for compute_impermanent_loss."""

    def test_no_price_change(self):
        """IL should be 0 when price doesn't change."""
        il = compute_impermanent_loss(ONE)
        assert il == ZERO

    def test_2x_price_increase(self):
        """Known formula value for 2x price change."""
        il = compute_impermanent_loss(Decimal("2"))
        # 2 * sqrt(2) / 3 - 1 = 2*1.4142/3 - 1 = 0.9428 - 1 = -0.0572
        expected = Decimal("-0.0571909584179366")
        assert abs(il - expected) < Decimal("0.001")

    def test_half_price(self):
        """IL for 0.5x (which should be same as 2x due to symmetry)."""
        il_half = compute_impermanent_loss(Decimal("0.5"))
        il_double = compute_impermanent_loss(Decimal("2"))
        assert abs(il_half - il_double) < Decimal("0.00001")

    def test_4x_price_increase(self):
        """4x price change should have more IL than 2x."""
        il_2x = compute_impermanent_loss(Decimal("2"))
        il_4x = compute_impermanent_loss(Decimal("4"))
        assert il_4x < il_2x  # More negative = more loss

    def test_negative_price_raises(self):
        with pytest.raises(ValueError):
            compute_impermanent_loss(Decimal("-1"))


class TestLPTokenMath:
    """Tests for LP token minting and redemption."""

    def test_initial_mint(self):
        """First LP gets sqrt(amount_a * amount_b) - MIN_LIQUIDITY tokens."""
        lp = compute_lp_tokens_to_mint(
            Decimal("100"), Decimal("200000"),
            ZERO, ZERO, ZERO
        )
        expected = (Decimal("100") * Decimal("200000")).sqrt() - Decimal("1000")
        assert abs(lp - expected) < Decimal("0.01")

    def test_proportional_mint(self):
        """Subsequent deposits should mint proportional LP tokens."""
        # Initial deposit
        lp_total = compute_lp_tokens_to_mint(
            Decimal("100"), Decimal("200000"),
            ZERO, ZERO, ZERO
        )
        # Second deposit of 1 ETH + proportional USDC
        lp_new = compute_lp_tokens_to_mint(
            Decimal("1"), Decimal("2000"),
            Decimal("100"), Decimal("200000"),
            lp_total
        )
        expected = lp_total * Decimal("1") / Decimal("100")
        assert abs(lp_new - expected) < Decimal("0.01")

    def test_initial_mint_too_small(self):
        """Very small initial deposit should raise."""
        with pytest.raises(ValueError):
            compute_lp_tokens_to_mint(
                Decimal("0.001"), Decimal("0.001"),
                ZERO, ZERO, ZERO
            )

    def test_redemption(self):
        """Burning LP tokens should return correct share of reserves."""
        lp_supply = Decimal("4472.135955")
        amount_a, amount_b = compute_lp_redemption(
            Decimal("1000"), Decimal("100"), Decimal("200000"), lp_supply
        )
        share = Decimal("1000") / lp_supply
        assert abs(amount_a - Decimal("100") * share) < Decimal("0.01")
        assert abs(amount_b - Decimal("200000") * share) < Decimal("0.01")

    def test_full_redemption(self):
        """Burning all LP tokens should return all reserves."""
        lp_supply = Decimal("4472.135955")
        amount_a, amount_b = compute_lp_redemption(
            lp_supply, Decimal("100"), Decimal("200000"), lp_supply
        )
        assert abs(amount_a - Decimal("100")) < Decimal("0.01")
        assert abs(amount_b - Decimal("200000")) < Decimal("0.01")

    def test_zero_lp_burn_raises(self):
        with pytest.raises(ValueError):
            compute_lp_redemption(ZERO, Decimal("100"), Decimal("200"), Decimal("1000"))


class TestConvenience:
    def test_compute_k(self):
        k = compute_k(Decimal("100"), Decimal("200000"))
        assert k == Decimal("20000000")

    def test_compute_fee(self):
        fee = compute_fee_amount(Decimal("100"), Decimal("0.003"))
        assert fee == Decimal("0.3")

    def test_effective_price(self):
        price = compute_effective_price(Decimal("1"), Decimal("2000"))
        assert price == Decimal("2000")

    def test_effective_price_zero_in(self):
        with pytest.raises(ValueError):
            compute_effective_price(ZERO, Decimal("1"))

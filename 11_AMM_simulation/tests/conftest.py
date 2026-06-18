"""Shared test fixtures for the AMM simulation test suite."""

import pytest
from decimal import Decimal

from src.core.types import TokenSymbol, PoolConfig
from src.core.token import TokenLedger
from src.core.wallet import Wallet
from src.core.pool import LiquidityPool


@pytest.fixture
def ledger():
    """Fresh empty token ledger."""
    return TokenLedger()


@pytest.fixture
def funded_ledger():
    """Ledger with some funded users."""
    ledger = TokenLedger()
    ledger.register_user("alice", {TokenSymbol.ETH: Decimal("1000"), TokenSymbol.USDC: Decimal("1000000")})
    ledger.register_user("bob", {TokenSymbol.ETH: Decimal("500"), TokenSymbol.USDC: Decimal("500000")})
    ledger.register_user("charlie", {TokenSymbol.BTC: Decimal("50"), TokenSymbol.USDC: Decimal("2000000")})
    return ledger


@pytest.fixture
def alice_wallet(funded_ledger):
    return Wallet("alice", funded_ledger)


@pytest.fixture
def bob_wallet(funded_ledger):
    return Wallet("bob", funded_ledger)


@pytest.fixture
def eth_usdc_config():
    """Standard ETH-USDC pool configuration."""
    return PoolConfig(
        token_a=TokenSymbol.ETH,
        token_b=TokenSymbol.USDC,
        fee_rate=Decimal("0.003"),
        initial_reserve_a=Decimal("100"),      # 100 ETH
        initial_reserve_b=Decimal("200000"),    # 200,000 USDC
    )


@pytest.fixture
def eth_usdc_pool(eth_usdc_config):
    """A fresh ETH-USDC pool."""
    return LiquidityPool(eth_usdc_config)


@pytest.fixture
def btc_usdc_config():
    """Standard BTC-USDC pool configuration."""
    return PoolConfig(
        token_a=TokenSymbol.BTC,
        token_b=TokenSymbol.USDC,
        initial_reserve_a=Decimal("10"),         # 10 BTC
        initial_reserve_b=Decimal("500000"),      # 500,000 USDC
    )


@pytest.fixture
def btc_usdc_pool(btc_usdc_config):
    """A fresh BTC-USDC pool."""
    return LiquidityPool(btc_usdc_config)


@pytest.fixture
def empty_config():
    """Used for testing edge cases."""
    return PoolConfig(
        token_a=TokenSymbol.DAI,
        token_b=TokenSymbol.USDC,
        initial_reserve_a=Decimal("1"),
        initial_reserve_b=Decimal("1"),
    )

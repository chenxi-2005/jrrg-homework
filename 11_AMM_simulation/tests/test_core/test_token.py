"""Tests for the TokenLedger and Wallet classes."""

import pytest
from decimal import Decimal

from src.core.types import TokenSymbol
from src.core.token import TokenLedger
from src.core.wallet import Wallet
from src.core.exceptions import InsufficientBalanceError


class TestTokenLedger:
    def test_register_user(self, ledger):
        ledger.register_user("alice", {TokenSymbol.ETH: Decimal("100")})
        assert ledger.get_balance("alice", TokenSymbol.ETH) == Decimal("100")
        assert ledger.get_total_supply(TokenSymbol.ETH) == Decimal("100")

    def test_mint(self, ledger):
        ledger.mint("alice", TokenSymbol.USDC, Decimal("1000"))
        assert ledger.get_balance("alice", TokenSymbol.USDC) == Decimal("1000")

    def test_burn(self, ledger):
        ledger.mint("alice", TokenSymbol.ETH, Decimal("100"))
        ledger.burn("alice", TokenSymbol.ETH, Decimal("50"))
        assert ledger.get_balance("alice", TokenSymbol.ETH) == Decimal("50")

    def test_burn_insufficient(self, ledger):
        with pytest.raises(ValueError):
            ledger.burn("alice", TokenSymbol.ETH, Decimal("1"))

    def test_transfer(self, ledger):
        ledger.mint("alice", TokenSymbol.USDC, Decimal("1000"))
        ledger.transfer("alice", "bob", TokenSymbol.USDC, Decimal("300"))
        assert ledger.get_balance("alice", TokenSymbol.USDC) == Decimal("700")
        assert ledger.get_balance("bob", TokenSymbol.USDC) == Decimal("300")

    def test_transfer_insufficient(self, ledger):
        with pytest.raises(ValueError):
            ledger.transfer("alice", "bob", TokenSymbol.ETH, Decimal("1"))

    def test_zero_amount_raises(self, ledger):
        with pytest.raises(ValueError):
            ledger.transfer("alice", "bob", TokenSymbol.ETH, Decimal("0"))

    def test_list_users(self, ledger):
        ledger.register_user("alice")
        ledger.register_user("bob")
        users = ledger.list_users()
        assert "alice" in users
        assert "bob" in users

    def test_to_snapshot(self, ledger):
        ledger.mint("alice", TokenSymbol.ETH, Decimal("10"))
        snap = ledger.to_snapshot()
        assert snap["users"]["alice"]["ETH"] == "10"


class TestWallet:
    def test_balance(self, alice_wallet):
        assert alice_wallet.balance(TokenSymbol.ETH) == Decimal("1000")

    def test_deposit(self, alice_wallet):
        alice_wallet.deposit(TokenSymbol.DAI, Decimal("5000"))
        assert alice_wallet.balance(TokenSymbol.DAI) == Decimal("5000")

    def test_withdraw(self, alice_wallet):
        alice_wallet.withdraw(TokenSymbol.ETH, Decimal("100"))
        assert alice_wallet.balance(TokenSymbol.ETH) == Decimal("900")

    def test_withdraw_insufficient(self, alice_wallet):
        with pytest.raises(InsufficientBalanceError):
            alice_wallet.withdraw(TokenSymbol.ETH, Decimal("999999"))

    def test_send(self, alice_wallet, bob_wallet):
        alice_wallet.send(bob_wallet, TokenSymbol.USDC, Decimal("50000"))
        assert alice_wallet.balance(TokenSymbol.USDC) == Decimal("950000")
        assert bob_wallet.balance(TokenSymbol.USDC) == Decimal("550000")

    def test_snapshot(self, alice_wallet):
        snap = alice_wallet.snapshot()
        assert snap["user_id"] == "alice"
        assert "ETH" in snap["balances"]

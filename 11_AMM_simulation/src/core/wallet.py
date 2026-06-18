"""Wallet — per-user balance management backed by TokenLedger."""

from decimal import Decimal
from typing import Dict, Optional

from .token import TokenLedger
from .types import TokenSymbol
from .exceptions import InsufficientBalanceError


class Wallet:
    """
    A user's wallet, providing a high-level interface to the shared TokenLedger.

    Each Wallet is bound to a specific user_id. All balance operations
    delegate to the shared ledger.
    """

    def __init__(self, user_id: str, ledger: TokenLedger):
        self.user_id = user_id
        self._ledger = ledger

    # --- Balance queries ---

    def balance(self, token: TokenSymbol) -> Decimal:
        """Get balance of a specific token."""
        return self._ledger.get_balance(self.user_id, token)

    def all_balances(self) -> Dict[TokenSymbol, Decimal]:
        """Get all token balances."""
        return self._ledger.get_all_balances(self.user_id)

    # --- Operations ---

    def deposit(self, token: TokenSymbol, amount: Decimal) -> None:
        """Credit tokens to this wallet (from external source)."""
        self._ledger.mint(self.user_id, token, amount)

    def withdraw(self, token: TokenSymbol, amount: Decimal) -> None:
        """Remove tokens from this wallet."""
        bal = self.balance(token)
        if bal < amount:
            raise InsufficientBalanceError(
                self.user_id, token.value, str(amount), str(bal)
            )
        self._ledger.burn(self.user_id, token, amount)

    def send(self, to_wallet: "Wallet", token: TokenSymbol, amount: Decimal) -> None:
        """Transfer tokens to another wallet."""
        self._ledger.transfer(self.user_id, to_wallet.user_id, token, amount)

    # --- Snapshot ---

    def snapshot(self) -> dict:
        """Return wallet state as a serializable dict."""
        return {
            "user_id": self.user_id,
            "balances": {tok.value: str(amt) for tok, amt in self.all_balances().items()},
        }

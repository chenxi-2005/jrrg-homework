"""Token ledger — tracks total supply and per-user balances for each token."""

from decimal import Decimal
from typing import Dict, Optional

from .types import TokenSymbol


class TokenLedger:
    """
    Simple in-memory token balance ledger.

    Maps (user_id, token_symbol) -> balance.
    Supports minting (creating tokens) and burning (destroying tokens).
    """

    def __init__(self):
        self._balances: Dict[str, Dict[TokenSymbol, Decimal]] = {}
        self._total_supply: Dict[TokenSymbol, Decimal] = {}

    # --- Read ---

    def get_balance(self, user_id: str, token: TokenSymbol) -> Decimal:
        """Get a user's balance of a specific token."""
        return self._balances.get(user_id, {}).get(token, Decimal("0"))

    def get_all_balances(self, user_id: str) -> Dict[TokenSymbol, Decimal]:
        """Get all token balances for a user."""
        return dict(self._balances.get(user_id, {}))

    def get_total_supply(self, token: TokenSymbol) -> Decimal:
        """Get the total supply of a token."""
        return self._total_supply.get(token, Decimal("0"))

    # --- Write ---

    def mint(self, user_id: str, token: TokenSymbol, amount: Decimal) -> None:
        """Create new tokens and credit them to a user."""
        if amount <= Decimal("0"):
            raise ValueError("Mint amount must be positive")

        self._balances.setdefault(user_id, {})
        self._balances[user_id][token] = self._balances[user_id].get(token, Decimal("0")) + amount
        self._total_supply[token] = self._total_supply.get(token, Decimal("0")) + amount

    def burn(self, user_id: str, token: TokenSymbol, amount: Decimal) -> None:
        """Destroy tokens held by a user."""
        if amount <= Decimal("0"):
            raise ValueError("Burn amount must be positive")

        balance = self.get_balance(user_id, token)
        if balance < amount:
            raise ValueError(
                f"Insufficient {token.value} balance for {user_id}: "
                f"has {balance}, tried to burn {amount}"
            )

        self._balances[user_id][token] = balance - amount
        self._total_supply[token] = self._total_supply.get(token, Decimal("0")) - amount

    def transfer(
        self,
        from_user: str,
        to_user: str,
        token: TokenSymbol,
        amount: Decimal,
    ) -> None:
        """Transfer tokens from one user to another."""
        if amount <= Decimal("0"):
            raise ValueError("Transfer amount must be positive")

        from_balance = self.get_balance(from_user, token)
        if from_balance < amount:
            raise ValueError(
                f"Insufficient {token.value} balance for {from_user}: "
                f"has {from_balance}, tried to transfer {amount}"
            )

        # Deduct from sender
        self._balances[from_user][token] = from_balance - amount

        # Credit to receiver
        self._balances.setdefault(to_user, {})
        self._balances[to_user][token] = self._balances[to_user].get(token, Decimal("0")) + amount

    # --- Bulk ---

    def register_user(self, user_id: str, initial_balances: Optional[Dict[TokenSymbol, Decimal]] = None) -> None:
        """Register a user with optional initial balances (minted)."""
        self._balances.setdefault(user_id, {})
        if initial_balances:
            for token, amount in initial_balances.items():
                self.mint(user_id, token, amount)

    def list_users(self) -> list[str]:
        """Return list of registered user IDs."""
        return list(self._balances.keys())

    def to_snapshot(self) -> dict:
        """Export full ledger state as a JSON-serializable dict."""
        users = {}
        for uid, balances in self._balances.items():
            users[uid] = {tok.value: str(amt) for tok, amt in balances.items()}
        return {
            "users": users,
            "total_supply": {tok.value: str(amt) for tok, amt in self._total_supply.items()},
        }

"""
Liquidity Pool — the core AMM primitive.

Each pool holds reserves of two tokens and implements Uniswap-V2-style
constant-product automated market making. All arithmetic delegates to
the pure functions in `formula.py`.
"""

from decimal import Decimal

from .formula import (
    ZERO,
    ONE,
    compute_swap_output,
    compute_spot_price,
    compute_k,
    compute_fee_amount,
    compute_price_impact_bps,
    compute_lp_tokens_to_mint,
    compute_lp_redemption,
    compute_impermanent_loss,
)
from .oracle import TWAPOracle
from .types import TokenSymbol, SwapResult, PoolState, PoolConfig
from .exceptions import (
    InsufficientLiquidityError,
    SlippageExceededError,
    RatioMismatchError,
    InvalidOperationError,
)


class LiquidityPool:
    """
    Constant-product (x * y = k) liquidity pool.

    Holds reserves of two tokens, processes swaps and liquidity operations,
    and maintains a TWAP oracle.

    Usage:
        pool = LiquidityPool(PoolConfig(
            token_a=TokenSymbol.ETH, token_b=TokenSymbol.USDC,
            initial_reserve_a=Decimal("100"), initial_reserve_b=Decimal("200000"),
        ))
        result = pool.swap(TokenSymbol.ETH, Decimal("1"))
    """

    def __init__(self, config: PoolConfig, pool_id: str | None = None):
        self.pool_id = pool_id or f"{config.token_a.value}-{config.token_b.value}"
        self.token_a: TokenSymbol = config.token_a
        self.token_b: TokenSymbol = config.token_b
        self.reserve_a: Decimal = config.initial_reserve_a
        self.reserve_b: Decimal = config.initial_reserve_b
        self.fee_rate: Decimal = config.fee_rate
        self.total_lp_supply: Decimal = ZERO
        self._k_last: Decimal = compute_k(self.reserve_a, self.reserve_b)
        self._accumulated_fees_a: Decimal = ZERO
        self._accumulated_fees_b: Decimal = ZERO
        self._swap_count: int = 0
        self._total_volume_a: Decimal = ZERO
        self._total_volume_b: Decimal = ZERO

        # Oracle
        self._oracle = TWAPOracle()
        self._step: int = 0

        # LPs: user_id -> LP token balance
        self._lp_balances: dict[str, Decimal] = {}
        self._creator_id: str = config.creator_id

        # Mint initial LP tokens for the provided reserves
        self._mint_initial_lp()

    # ------------------------------------------------------------------
    # Swap
    # ------------------------------------------------------------------

    def swap(self, token_in: TokenSymbol, amount_in: Decimal) -> SwapResult:
        """
        Execute a swap of `amount_in` of `token_in` for the other token.

        Args:
            token_in: the token being sold into the pool
            amount_in: amount of `token_in` being swapped

        Returns:
            SwapResult with full trade details.

        Raises:
            InsufficientLiquidityError: if reserve_in is zero or swap would drain pool
            InvalidOperationError: if token_in is not a pool token
        """
        if amount_in <= ZERO:
            raise InvalidOperationError("Swap amount must be positive")

        # Determine input/output reserves
        if token_in == self.token_a:
            reserve_in, reserve_out = self.reserve_a, self.reserve_b
            token_out = self.token_b
        elif token_in == self.token_b:
            reserve_in, reserve_out = self.reserve_b, self.reserve_a
            token_out = self.token_a
        else:
            raise InvalidOperationError(
                f"Token {token_in.value} is not in pool {self.pool_id}"
            )

        # Compute output
        amount_out = compute_swap_output(reserve_in, reserve_out, amount_in, self.fee_rate)

        if amount_out <= ZERO:
            raise InsufficientLiquidityError(
                self.pool_id, token_in.value, str(amount_in), str(reserve_in)
            )

        fee_collected = compute_fee_amount(amount_in, self.fee_rate)
        impact_bps = compute_price_impact_bps(reserve_in, amount_in, self.fee_rate)

        # Old spot price (before update)
        old_price = compute_spot_price(self.reserve_a, self.reserve_b)

        # Update reserves
        if token_in == self.token_a:
            self.reserve_a += amount_in
            self.reserve_b -= amount_out
            self._accumulated_fees_a += fee_collected
            self._total_volume_a += amount_in
        else:
            self.reserve_b += amount_in
            self.reserve_a -= amount_out
            self._accumulated_fees_b += fee_collected
            self._total_volume_b += amount_in

        new_price = compute_spot_price(self.reserve_a, self.reserve_b)
        effective_price = amount_out / amount_in
        self._swap_count += 1

        return SwapResult(
            pool_id=self.pool_id,
            token_in=token_in,
            amount_in=amount_in,
            token_out=token_out,
            amount_out=amount_out,
            fee_collected=fee_collected,
            price_impact_bps=impact_bps,
            effective_price=effective_price,
            new_spot_price=new_price,
        )

    def get_swap_quote(self, token_in: TokenSymbol, amount_in: Decimal) -> SwapResult:
        """
        Dry-run a swap: return the expected SwapResult without mutating state.
        """
        if token_in == self.token_a:
            reserve_in, reserve_out = self.reserve_a, self.reserve_b
            token_out = self.token_b
        elif token_in == self.token_b:
            reserve_in, reserve_out = self.reserve_b, self.reserve_a
            token_out = self.token_a
        else:
            raise InvalidOperationError(f"Token {token_in.value} not in pool {self.pool_id}")

        amount_out = compute_swap_output(reserve_in, reserve_out, amount_in, self.fee_rate)
        fee_collected = compute_fee_amount(amount_in, self.fee_rate)
        impact_bps = compute_price_impact_bps(reserve_in, amount_in, self.fee_rate)

        # Simulate new reserves to get new spot price
        if token_in == self.token_a:
            new_ra = reserve_in + amount_in
            new_rb = reserve_out - amount_out
        else:
            new_rb = reserve_in + amount_in
            new_ra = reserve_out - amount_out

        new_price = compute_spot_price(new_ra, new_rb)
        effective_price = amount_out / amount_in

        return SwapResult(
            pool_id=self.pool_id,
            token_in=token_in,
            amount_in=amount_in,
            token_out=token_out,
            amount_out=amount_out,
            fee_collected=fee_collected,
            price_impact_bps=impact_bps,
            effective_price=effective_price,
            new_spot_price=new_price,
        )

    # ------------------------------------------------------------------
    # Liquidity
    # ------------------------------------------------------------------

    def _mint_initial_lp(self) -> None:
        """Mint initial LP tokens to the pool creator for the initial reserves."""
        if self.reserve_a > ZERO and self.reserve_b > ZERO:
            initial_lp = (self.reserve_a * self.reserve_b).sqrt()
            if initial_lp > Decimal("1000"):
                lp = initial_lp - Decimal("1000")
                self.total_lp_supply = lp
                self._lp_balances[self._creator_id] = lp

    def add_liquidity(
        self, user_id: str, amount_a: Decimal, amount_b: Decimal
    ) -> Decimal:
        """
        Deposit liquidity into the pool.

        For initial deposit: any ratio is accepted.
        For subsequent deposits: amounts must match the current pool ratio.
        Only the smaller share is used (proportional deposit).

        Returns the number of LP tokens minted.
        """
        if amount_a <= ZERO or amount_b <= ZERO:
            raise InvalidOperationError("Deposit amounts must be positive")

        lp_tokens = compute_lp_tokens_to_mint(
            amount_a, amount_b,
            self.reserve_a, self.reserve_b,
            self.total_lp_supply,
        )

        # Add reserves
        self.reserve_a += amount_a
        self.reserve_b += amount_b

        # Mint LP tokens
        self.total_lp_supply += lp_tokens
        self._lp_balances[user_id] = self._lp_balances.get(user_id, ZERO) + lp_tokens

        self._k_last = compute_k(self.reserve_a, self.reserve_b)
        return lp_tokens

    def remove_liquidity(
        self, user_id: str, lp_amount: Decimal
    ) -> tuple[Decimal, Decimal]:
        """
        Withdraw liquidity by burning LP tokens.

        Returns (amount_a, amount_b) returned to the user.
        """
        if lp_amount <= ZERO:
            raise InvalidOperationError("LP burn amount must be positive")

        lp_balance = self._lp_balances.get(user_id, ZERO)
        if lp_balance < lp_amount:
            raise InvalidOperationError(
                f"User {user_id} has {lp_balance} LP tokens, tried to burn {lp_amount}"
            )

        amount_a, amount_b = compute_lp_redemption(
            lp_amount, self.reserve_a, self.reserve_b, self.total_lp_supply
        )

        # Burn LP tokens
        self.total_lp_supply -= lp_amount
        self._lp_balances[user_id] = lp_balance - lp_amount

        # Remove reserves
        self.reserve_a -= amount_a
        self.reserve_b -= amount_b

        self._k_last = compute_k(self.reserve_a, self.reserve_b)
        return amount_a, amount_b

    def get_lp_balance(self, user_id: str) -> Decimal:
        """Get a user's LP token balance for this pool."""
        return self._lp_balances.get(user_id, ZERO)

    def get_all_lp_positions(self) -> dict[str, Decimal]:
        """Get all LP positions {user_id: lp_amount}."""
        return dict(self._lp_balances)

    # ------------------------------------------------------------------
    # Oracle / Step
    # ------------------------------------------------------------------

    def advance_step(self, step: int) -> None:
        """Advance the oracle clock and record current price."""
        time_delta = Decimal(str(step - self._step))
        if time_delta > ZERO:
            spot_a = compute_spot_price(self.reserve_a, self.reserve_b)
            spot_b = ONE / spot_a if spot_a > ZERO else ZERO
            self._oracle.update(spot_a, spot_b, time_delta)
        self._step = step

    # ------------------------------------------------------------------
    # Price
    # ------------------------------------------------------------------

    def get_spot_price(self) -> Decimal:
        """Get current spot price: how much token_b per 1 token_a."""
        return compute_spot_price(self.reserve_a, self.reserve_b)

    def get_twap_price(self) -> Decimal:
        """Get TWAP of token_a in terms of token_b."""
        return self._oracle.get_twap_a()

    def get_impermanent_loss(self, price_ratio: Decimal) -> Decimal:
        """Compute impermanent loss for a given price ratio since pool creation."""
        return compute_impermanent_loss(price_ratio)

    # ------------------------------------------------------------------
    # State / Snapshot
    # ------------------------------------------------------------------

    def get_state(self, step: int | None = None) -> PoolState:
        """Get a snapshot of the current pool state."""
        twap = self.get_twap_price() if self._oracle.total_time > ZERO else None
        return PoolState(
            pool_id=self.pool_id,
            token_a=self.token_a,
            token_b=self.token_b,
            reserve_a=self.reserve_a,
            reserve_b=self.reserve_b,
            fee_rate=self.fee_rate,
            total_lp_supply=self.total_lp_supply,
            k=compute_k(self.reserve_a, self.reserve_b),
            spot_price=self.get_spot_price(),
            twap_price=twap,
            step=step if step is not None else self._step,
        )

    @property
    def k(self) -> Decimal:
        return compute_k(self.reserve_a, self.reserve_b)

    @property
    def accumulated_fees_a(self) -> Decimal:
        return self._accumulated_fees_a

    @property
    def accumulated_fees_b(self) -> Decimal:
        return self._accumulated_fees_b

    @property
    def swap_count(self) -> int:
        return self._swap_count

    @property
    def total_volume_a(self) -> Decimal:
        return self._total_volume_a

    @property
    def total_volume_b(self) -> Decimal:
        return self._total_volume_b

    @property
    def step(self) -> int:
        return self._step

    def __repr__(self) -> str:
        return (
            f"LiquidityPool({self.pool_id}, "
            f"{self.token_a.value}/{self.token_b.value}, "
            f"k={self.k:.4f}, LP={self.total_lp_supply:.4f})"
        )

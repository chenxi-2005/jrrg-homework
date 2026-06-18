"""
Constant-Product AMM formula module.

All functions are pure: they take Decimal inputs and return Decimal outputs.
No state mutation, no I/O. The single source of truth for all AMM mathematics.

Reference: Uniswap V2 Core whitepaper
  - https://docs.uniswap.org/contracts/v2/concepts/protocol-overview/how-uniswap-works
"""

from decimal import Decimal, getcontext

# Set high precision for decimal arithmetic (28 significant digits)
getcontext().prec = 28

ONE = Decimal("1")
ZERO = Decimal("0")
MINIMUM_LIQUIDITY = Decimal("1000")  # Locked to prevent division by zero attacks


# ---------------------------------------------------------------------------
# Swap / Price functions
# ---------------------------------------------------------------------------

def compute_swap_output(
    reserve_in: Decimal,
    reserve_out: Decimal,
    amount_in: Decimal,
    fee_rate: Decimal,
) -> Decimal:
    """
    Calculate the amount of `token_out` received for a given `amount_in`.

    Formula:
        amount_out = (reserve_out * amount_in * (1 - fee)) /
                     (reserve_in + amount_in * (1 - fee))

    Args:
        reserve_in:  current reserve of the input token
        reserve_out: current reserve of the output token
        amount_in:   amount of input token being swapped
        fee_rate:    fee rate (e.g. 0.003 = 0.3%)

    Returns:
        Amount of output token to receive.

    Raises:
        ValueError: if reserves are zero or amount_in is zero
    """
    if reserve_in <= ZERO or reserve_out <= ZERO:
        raise ValueError("Reserves must be positive")
    if amount_in <= ZERO:
        return ZERO

    amount_in_after_fee = amount_in * (ONE - fee_rate)
    numerator = reserve_out * amount_in_after_fee
    denominator = reserve_in + amount_in_after_fee
    return numerator / denominator


def compute_swap_input(
    reserve_in: Decimal,
    reserve_out: Decimal,
    amount_out: Decimal,
    fee_rate: Decimal,
) -> Decimal:
    """
    Calculate `amount_in` required to receive exactly `amount_out`.

    Formula (inverse of swap_output):
        amount_in = (reserve_in * amount_out) /
                    ((reserve_out - amount_out) * (1 - fee))

    Args:
        reserve_in:  current reserve of the input token
        reserve_out: current reserve of the output token
        amount_out:  desired amount of output token
        fee_rate:    fee rate

    Returns:
        Required amount of input token.
    """
    if reserve_out <= amount_out:
        raise ValueError("Insufficient reserves for desired output")
    numerator = reserve_in * amount_out
    denominator = (reserve_out - amount_out) * (ONE - fee_rate)
    return numerator / denominator


def compute_price_impact_bps(
    reserve_in: Decimal,
    amount_in: Decimal,
    fee_rate: Decimal,
) -> int:
    """
    Calculate price impact in basis points (1 bps = 0.01%).

    Price impact measures how much the trade moves the spot price.
    Formula: impact = (amount_in_after_fee / (reserve_in + amount_in_after_fee)) * 10000

    Args:
        reserve_in: current reserve of the input token
        amount_in:  amount being swapped in
        fee_rate:   fee rate

    Returns:
        Price impact in basis points (integer).
    """
    if reserve_in <= ZERO:
        return 0
    amount_in_after_fee = amount_in * (ONE - fee_rate)
    impact = (amount_in_after_fee / (reserve_in + amount_in_after_fee)) * Decimal("10000")
    return int(impact.to_integral_value())


# ---------------------------------------------------------------------------
# Spot price
# ---------------------------------------------------------------------------

def compute_spot_price(
    reserve_a: Decimal,
    reserve_b: Decimal,
) -> Decimal:
    """
    Compute the spot price of token_a in terms of token_b.
    price = reserve_b / reserve_a  (how much token_b for 1 unit of token_a)
    """
    if reserve_a <= ZERO:
        raise ValueError("Reserve A must be positive")
    return reserve_b / reserve_a


# ---------------------------------------------------------------------------
# Impermanent Loss
# ---------------------------------------------------------------------------

def compute_impermanent_loss(price_ratio: Decimal) -> Decimal:
    """
    Compute impermanent loss given a price ratio.

    IL = 2 * sqrt(price_ratio) / (1 + price_ratio) - 1

    Where price_ratio = new_price / initial_price.
    IL is negative, representing the loss vs. simply holding.

    Args:
        price_ratio: new_price / initial_price

    Returns:
        IL as a decimal (e.g. -0.057 = -5.7%)
    """
    if price_ratio <= ZERO:
        raise ValueError("Price ratio must be positive")
    if price_ratio == ONE:
        return ZERO

    sqrt_pr = price_ratio.sqrt()
    il = (Decimal("2") * sqrt_pr) / (ONE + price_ratio) - ONE
    return il


# ---------------------------------------------------------------------------
# Liquidity Provider (LP) token math
# ---------------------------------------------------------------------------

def compute_lp_tokens_to_mint(
    amount_a: Decimal,
    amount_b: Decimal,
    reserve_a: Decimal,
    reserve_b: Decimal,
    total_lp_supply: Decimal,
) -> Decimal:
    """
    Calculate how many LP tokens to mint for a given deposit.

    For the initial deposit (total_lp_supply == 0):
        lp_tokens = sqrt(amount_a * amount_b) - MINIMUM_LIQUIDITY

    For subsequent deposits:
        lp_tokens = total_lp_supply * min(amount_a/reserve_a, amount_b/reserve_b)

    Args:
        amount_a: amount of token_a deposited
        amount_b: amount of token_b deposited
        reserve_a: current pool reserve of token_a
        reserve_b: current pool reserve of token_b
        total_lp_supply: current total LP tokens in circulation

    Returns:
        Number of LP tokens to mint.
    """
    if amount_a <= ZERO or amount_b <= ZERO:
        raise ValueError("Deposit amounts must be positive")

    if total_lp_supply == ZERO:
        # Initial liquidity provision
        initial = (amount_a * amount_b).sqrt()
        if initial <= MINIMUM_LIQUIDITY:
            raise ValueError("Initial liquidity too low")
        return initial - MINIMUM_LIQUIDITY

    # Proportional liquidity provision
    share_a = amount_a / reserve_a
    share_b = amount_b / reserve_b
    share = min(share_a, share_b)
    return total_lp_supply * share


def compute_lp_redemption(
    lp_amount: Decimal,
    reserve_a: Decimal,
    reserve_b: Decimal,
    total_lp_supply: Decimal,
) -> tuple[Decimal, Decimal]:
    """
    Calculate token amounts returned for burning LP tokens.

    amount_a = reserve_a * lp_amount / total_lp_supply
    amount_b = reserve_b * lp_amount / total_lp_supply

    Args:
        lp_amount: number of LP tokens to burn
        reserve_a: current pool reserve of token_a
        reserve_b: current pool reserve of token_b
        total_lp_supply: current total LP tokens in circulation

    Returns:
        (amount_a, amount_b) to return to the LP.
    """
    if lp_amount <= ZERO:
        raise ValueError("LP burn amount must be positive")
    if total_lp_supply <= ZERO:
        raise ValueError("No LP tokens in circulation")

    share = lp_amount / total_lp_supply
    amount_a = reserve_a * share
    amount_b = reserve_b * share
    return amount_a, amount_b


# ---------------------------------------------------------------------------
# Convenience / composite
# ---------------------------------------------------------------------------

def compute_k(reserve_a: Decimal, reserve_b: Decimal) -> Decimal:
    """Compute the constant product invariant k = x * y."""
    return reserve_a * reserve_b


def compute_fee_amount(amount_in: Decimal, fee_rate: Decimal) -> Decimal:
    """Compute the fee collected on a trade."""
    return amount_in * fee_rate


def compute_effective_price(
    amount_in: Decimal,
    amount_out: Decimal,
) -> Decimal:
    """Compute effective execution price: price = amount_out / amount_in."""
    if amount_in <= ZERO:
        raise ValueError("amount_in must be positive")
    return amount_out / amount_in

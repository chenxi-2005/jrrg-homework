"""Core AMM domain types and data models."""

from enum import Enum
from decimal import Decimal
from typing import Optional, Dict, List
from pydantic import BaseModel, Field, field_validator


class TokenSymbol(str, Enum):
    USDC = "USDC"
    ETH = "ETH"
    BTC = "BTC"
    DAI = "DAI"


class TokenConfig(BaseModel):
    """Token definition and metadata."""
    symbol: TokenSymbol
    name: str
    decimals: int = Field(default=18, ge=0, le=18)

    @property
    def unit(self) -> Decimal:
        return Decimal(10) ** Decimal(-self.decimals)


class PoolConfig(BaseModel):
    """Configuration for creating a new liquidity pool."""
    token_a: TokenSymbol
    token_b: TokenSymbol
    fee_rate: Decimal = Field(default=Decimal("0.003"), ge=0, le=Decimal("1"))
    initial_reserve_a: Decimal = Field(gt=Decimal("0"))
    initial_reserve_b: Decimal = Field(gt=Decimal("0"))
    creator_id: str = "system"

    @field_validator("token_a", "token_b")
    @classmethod
    def tokens_must_differ(cls, v: TokenSymbol, info) -> TokenSymbol:
        # This is checked at model level after all fields are set
        return v


class SwapRequest(BaseModel):
    """A swap/trade request."""
    pool_id: str
    token_in: TokenSymbol
    amount_in: Decimal = Field(gt=Decimal("0"))
    min_amount_out: Decimal = Field(default=Decimal("0"), ge=Decimal("0"))
    user_id: str = "anonymous"


class SwapResult(BaseModel):
    """Result of executing a swap."""
    pool_id: str
    token_in: TokenSymbol
    amount_in: Decimal
    token_out: TokenSymbol
    amount_out: Decimal
    fee_collected: Decimal
    price_impact_bps: int  # basis points (1 bps = 0.01%)
    effective_price: Decimal
    new_spot_price: Decimal


class LiquidityAddRequest(BaseModel):
    """Request to add liquidity to a pool."""
    pool_id: str
    amount_a: Decimal = Field(gt=Decimal("0"))
    amount_b: Decimal = Field(gt=Decimal("0"))
    min_lp: Decimal = Field(default=Decimal("0"), ge=Decimal("0"))
    user_id: str = "anonymous"


class LiquidityRemoveRequest(BaseModel):
    """Request to remove liquidity from a pool."""
    pool_id: str
    lp_amount: Decimal = Field(gt=Decimal("0"))
    user_id: str = "anonymous"


class PoolState(BaseModel):
    """Snapshot of pool state at a given step."""
    pool_id: str
    token_a: TokenSymbol
    token_b: TokenSymbol
    reserve_a: Decimal
    reserve_b: Decimal
    fee_rate: Decimal
    total_lp_supply: Decimal
    k: Decimal
    spot_price: Decimal
    twap_price: Optional[Decimal] = None
    step: int = 0


class UserState(BaseModel):
    """Snapshot of a user's balances."""
    user_id: str
    balances: Dict[str, str] = Field(default_factory=dict)  # token_symbol -> Decimal as string


class SimulationConfig(BaseModel):
    """Full simulation configuration."""
    name: str = "default"
    description: str = ""
    random_seed: int = 42
    max_steps: int = 100
    pools: List[PoolConfig] = Field(default_factory=list)
    users: List[dict] = Field(default_factory=list)  # {user_id, balances: {TOKEN: amount}}
    agents: List[dict] = Field(default_factory=list)  # {type, user_id, params}
    log_snapshot_interval: int = 1  # capture state every N steps

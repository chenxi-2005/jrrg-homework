"""REST API for pool management."""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ..dependencies import get_engine

router = APIRouter()


class CreatePoolRequest(BaseModel):
    token_a: str
    token_b: str
    initial_reserve_a: str
    initial_reserve_b: str
    fee_rate: str = "0.003"


@router.get("")
async def list_pools():
    """List all pools with current state."""
    engine = get_engine()
    pools = {}
    for pid, pool in engine.pools.items():
        state = pool.get_state(step=engine.clock.step)
        pools[pid] = {
            "pool_id": state.pool_id,
            "token_a": state.token_a.value,
            "token_b": state.token_b.value,
            "reserve_a": str(state.reserve_a),
            "reserve_b": str(state.reserve_b),
            "spot_price": str(state.spot_price),
            "twap_price": str(state.twap_price) if state.twap_price else None,
            "total_lp_supply": str(state.total_lp_supply),
            "fee_rate": str(state.fee_rate),
            "k": str(state.k),
            "swap_count": pool.swap_count,
            "step": state.step,
        }
    return {"pools": pools}


@router.get("/{pool_id}")
async def get_pool(pool_id: str):
    """Get detailed information for a single pool."""
    engine = get_engine()
    pool = engine.pools.get(pool_id)
    if pool is None:
        raise HTTPException(status_code=404, detail=f"Pool '{pool_id}' not found")

    state = pool.get_state(step=engine.clock.step)
    return {
        "pool_id": state.pool_id,
        "token_a": state.token_a.value,
        "token_b": state.token_b.value,
        "reserve_a": str(state.reserve_a),
        "reserve_b": str(state.reserve_b),
        "spot_price": str(state.spot_price),
        "twap_price": str(state.twap_price) if state.twap_price else None,
        "total_lp_supply": str(state.total_lp_supply),
        "fee_rate": str(state.fee_rate),
        "k": str(state.k),
        "swap_count": pool.swap_count,
        "accumulated_fees_a": str(pool.accumulated_fees_a),
        "accumulated_fees_b": str(pool.accumulated_fees_b),
        "lp_positions": {uid: str(amt) for uid, amt in pool.get_all_lp_positions().items()},
        "step": state.step,
    }


@router.get("/{pool_id}/price-history")
async def get_price_history(pool_id: str):
    """Get price history for a pool from logged snapshots."""
    engine = get_engine()
    df = engine.logger.snapshots_df()
    if df.empty:
        return {"history": []}

    import math
    pool_df = df[df["pool_id"] == pool_id]
    history = []
    for _, row in pool_df.iterrows():
        twap = row["twap_price"]
        if twap is None or (isinstance(twap, float) and math.isnan(twap)):
            twap = None
        history.append({
            "step": int(row["step"]),
            "spot_price": float(row["spot_price"]),
            "twap_price": twap,
        })
    return {"history": history}


@router.get("/{pool_id}/reserve-curve")
async def get_reserve_curve(pool_id: str):
    """Get data points for the x*y=k reserve curve."""
    engine = get_engine()
    pool = engine.pools.get(pool_id)
    if pool is None:
        raise HTTPException(status_code=404, detail=f"Pool '{pool_id}' not found")

    k = float(pool.k)
    current_ra = float(pool.reserve_a)
    current_rb = float(pool.reserve_b)

    # Generate curve points
    ra_min = current_ra * 0.2
    ra_max = current_ra * 5.0
    curve_points = []
    num_points = 100
    for i in range(num_points + 1):
        ra = ra_min + (ra_max - ra_min) * i / num_points
        rb = k / ra if ra > 0 else 0
        curve_points.append({"reserve_a": ra, "reserve_b": rb})

    return {
        "curve": curve_points,
        "current": {"reserve_a": current_ra, "reserve_b": current_rb},
        "k": k,
        "pool_id": pool_id,
    }


@router.post("")
async def create_pool(req: CreatePoolRequest):
    """Create a new liquidity pool."""
    from src.core.types import PoolConfig, TokenSymbol
    from decimal import Decimal

    engine = get_engine()
    try:
        config = PoolConfig(
            token_a=TokenSymbol(req.token_a),
            token_b=TokenSymbol(req.token_b),
            fee_rate=Decimal(req.fee_rate),
            initial_reserve_a=Decimal(req.initial_reserve_a),
            initial_reserve_b=Decimal(req.initial_reserve_b),
        )
        pool = engine.register_pool(config)
        return {
            "status": "created",
            "pool_id": pool.pool_id,
            "spot_price": str(pool.get_spot_price()),
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

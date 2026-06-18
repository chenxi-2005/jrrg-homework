"""REST API for liquidity management."""

from decimal import Decimal

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ..dependencies import get_engine

router = APIRouter()


class AddLiquidityRequest(BaseModel):
    pool_id: str
    user_id: str
    amount_a: str
    amount_b: str


class RemoveLiquidityRequest(BaseModel):
    pool_id: str
    user_id: str
    lp_amount: str


@router.post("/add")
async def add_liquidity(req: AddLiquidityRequest):
    """Add liquidity to a pool."""
    engine = get_engine()
    pool = engine.pools.get(req.pool_id)
    if pool is None:
        raise HTTPException(status_code=404, detail=f"Pool '{req.pool_id}' not found")

    try:
        lp_minted = pool.add_liquidity(
            req.user_id,
            Decimal(req.amount_a),
            Decimal(req.amount_b),
        )
        from ..dependencies import record_session_snapshot
        engine.logger.log_snapshot(engine.step_number, engine.pools, engine.ledger)
        record_session_snapshot()
        return {
            "status": "success",
            "pool_id": req.pool_id,
            "user_id": req.user_id,
            "lp_minted": str(lp_minted),
            "new_reserve_a": str(pool.reserve_a),
            "new_reserve_b": str(pool.reserve_b),
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/remove")
async def remove_liquidity(req: RemoveLiquidityRequest):
    """Remove liquidity from a pool."""
    engine = get_engine()
    pool = engine.pools.get(req.pool_id)
    if pool is None:
        raise HTTPException(status_code=404, detail=f"Pool '{req.pool_id}' not found")

    try:
        amount_a, amount_b = pool.remove_liquidity(
            req.user_id,
            Decimal(req.lp_amount),
        )
        from ..dependencies import record_session_snapshot
        engine.logger.log_snapshot(engine.step_number, engine.pools, engine.ledger)
        record_session_snapshot()
        return {
            "status": "success",
            "pool_id": req.pool_id,
            "user_id": req.user_id,
            "amount_a_returned": str(amount_a),
            "amount_b_returned": str(amount_b),
            "lp_remaining": str(pool.get_lp_balance(req.user_id)),
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/positions/{user_id}")
async def get_positions(user_id: str):
    """Get LP positions for a user across all pools."""
    engine = get_engine()
    positions = {}
    for pid, pool in engine.pools.items():
        lp_bal = pool.get_lp_balance(user_id)
        if lp_bal > Decimal("0"):
            state = pool.get_state()
            share = lp_bal / state.total_lp_supply if state.total_lp_supply > 0 else Decimal("0")
            positions[pid] = {
                "lp_amount": str(lp_bal),
                "share": str(share),
                "underlying_a": str(state.reserve_a * share),
                "underlying_b": str(state.reserve_b * share),
            }
    return {"user_id": user_id, "positions": positions}


@router.get("/impermanent-loss/{pool_id}")
async def get_il_data(pool_id: str):
    """Get impermanent loss data for a range of price ratios."""
    engine = get_engine()
    pool = engine.pools.get(pool_id)
    if pool is None:
        raise HTTPException(status_code=404, detail=f"Pool '{pool_id}' not found")

    il_data = []
    ratios = [0.1, 0.25, 0.5, 0.75, 1.0, 1.25, 1.5, 2.0, 3.0, 4.0, 5.0, 10.0]
    for r in ratios:
        il = pool.get_impermanent_loss(Decimal(str(r)))
        il_data.append({
            "price_ratio": r,
            "impermanent_loss_pct": float(il) * 100,
        })

    return {
        "pool_id": pool_id,
        "il_data": il_data,
    }

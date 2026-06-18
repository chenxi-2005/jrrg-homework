"""REST API for swap/trade operations."""

from decimal import Decimal

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from src.core.types import TokenSymbol
from ..dependencies import get_engine

router = APIRouter()


class SwapRequest(BaseModel):
    pool_id: str
    token_in: str
    amount_in: str
    min_amount_out: str = "0"


@router.post("/execute")
async def execute_swap(req: SwapRequest):
    """Execute a swap on a pool."""
    engine = get_engine()
    pool = engine.pools.get(req.pool_id)
    if pool is None:
        raise HTTPException(status_code=404, detail=f"Pool '{req.pool_id}' not found")

    try:
        result = pool.swap(
            TokenSymbol(req.token_in),
            Decimal(req.amount_in),
        )
        min_out = Decimal(req.min_amount_out)
        if result.amount_out < min_out:
            raise HTTPException(
                status_code=400,
                detail=f"Slippage exceeded: got {result.amount_out}, min {min_out}",
            )

        # Log snapshot so dashboard chart reflects manual swap
        from ..dependencies import record_session_snapshot
        engine.logger.log_snapshot(engine.step_number, engine.pools, engine.ledger)
        record_session_snapshot()

        return {
            "pool_id": result.pool_id,
            "token_in": result.token_in.value,
            "amount_in": str(result.amount_in),
            "token_out": result.token_out.value,
            "amount_out": str(result.amount_out),
            "fee_collected": str(result.fee_collected),
            "price_impact_bps": result.price_impact_bps,
            "effective_price": str(result.effective_price),
            "new_spot_price": str(result.new_spot_price),
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/quote")
async def get_quote(req: SwapRequest):
    """Get a swap quote without executing."""
    engine = get_engine()
    pool = engine.pools.get(req.pool_id)
    if pool is None:
        raise HTTPException(status_code=404, detail=f"Pool '{req.pool_id}' not found")

    try:
        result = pool.get_swap_quote(
            TokenSymbol(req.token_in),
            Decimal(req.amount_in),
        )
        return {
            "pool_id": result.pool_id,
            "token_in": result.token_in.value,
            "amount_in": str(result.amount_in),
            "token_out": result.token_out.value,
            "amount_out": str(result.amount_out),
            "fee_collected": str(result.fee_collected),
            "price_impact_bps": result.price_impact_bps,
            "effective_price": str(result.effective_price),
            "new_spot_price": str(result.new_spot_price),
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

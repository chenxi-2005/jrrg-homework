"""
FastAPI application factory for the AMM Simulation Web Interface.

Usage:
    python -m frontend.app          # Start with uvicorn
    uvicorn frontend.app:app        # Direct uvicorn
"""

import sys
from pathlib import Path

# Ensure project root is importable
sys.path.insert(0, str(Path(__file__).parent.parent))

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware

from .dependencies import init_engine, get_engine
from .routers import api_pools, api_swap, api_liquidity, api_simulation
from .routers import ws_simulation

# Template directory
TEMPLATES_DIR = Path(__file__).parent / "templates"
STATIC_DIR = Path(__file__).parent / "static"

templates = Jinja2Templates(directory=str(TEMPLATES_DIR))


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    app = FastAPI(
        title="AMM Exchange Simulation",
        description="DeFi 核心逻辑仿真系统 — Web Interface",
        version="1.0.0",
    )

    # CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Static files
    if STATIC_DIR.exists():
        app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

    # Startup
    @app.on_event("startup")
    async def startup():
        init_engine()

    # Register API routers
    app.include_router(api_pools.router, prefix="/api/pools", tags=["Pools"])
    app.include_router(api_swap.router, prefix="/api/swap", tags=["Swap"])
    app.include_router(api_liquidity.router, prefix="/api/liquidity", tags=["Liquidity"])
    app.include_router(api_simulation.router, prefix="/api/sim", tags=["Simulation"])

    # WebSocket
    app.include_router(ws_simulation.router, prefix="/ws", tags=["WebSocket"])

    # --- Page routes ---
    from fastapi import Request

    @app.get("/")
    async def page_dashboard(request: Request):
        return templates.TemplateResponse(request, "dashboard.html")

    @app.get("/pools/{pool_id}")
    async def page_pool_detail(request: Request, pool_id: str):
        return templates.TemplateResponse(request, "pool.html", {"pool_id": pool_id})

    @app.get("/trade")
    async def page_trade(request: Request):
        return templates.TemplateResponse(request, "trade.html")

    @app.get("/liquidity")
    async def page_liquidity(request: Request):
        return templates.TemplateResponse(request, "liquidity.html")

    @app.get("/simulation")
    async def page_simulation(request: Request):
        return templates.TemplateResponse(request, "simulation.html")

    # --- Session-level data (persists across resets) ---
    @app.get("/api/session/price-history/{pool_id}")
    async def get_session_price_history(pool_id: str):
        from .dependencies import get_session_price_history
        return {"history": get_session_price_history(pool_id)}

    # --- API root for convenience ---
    @app.get("/api/state")
    async def get_full_state():
        """Get complete simulation state snapshot."""
        engine = get_engine()
        return engine.get_state_snapshot()

    @app.get("/api/summary")
    async def get_summary():
        """Get simulation summary statistics."""
        engine = get_engine()
        return engine.get_summary()

    @app.get("/api/users")
    async def get_users():
        """List all users."""
        engine = get_engine()
        users = {}
        for uid in engine.ledger.list_users():
            balances = engine.ledger.get_all_balances(uid)
            users[uid] = {tok.value: str(bal) for tok, bal in balances.items()}
        return {"users": users}

    return app


# Create app instance
app = create_app()


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main():
    """Start the web server."""
    import uvicorn
    uvicorn.run(
        "frontend.app:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
    )


if __name__ == "__main__":
    main()

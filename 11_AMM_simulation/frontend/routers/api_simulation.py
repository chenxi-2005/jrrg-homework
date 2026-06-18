"""REST API for simulation control."""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ..dependencies import get_engine, reset_engine, load_scenario as dep_load_scenario

router = APIRouter()


class SimConfigRequest(BaseModel):
    max_steps: int | None = None
    random_seed: int | None = None
    log_snapshot_interval: int | None = None


class LoadScenarioRequest(BaseModel):
    scenario: str = "default"  # default, flash_crash, arbitrage


@router.get("/status")
async def get_status():
    """Get current simulation status."""
    engine = get_engine()
    return {
        "step": engine.step_number,
        "max_steps": engine.config.max_steps,
        "running": engine.running,
        "paused": engine.paused,
        "pools": len(engine.pools),
        "users": len(engine.wallets),
        "agents": len(engine.agents),
        "pending_events": engine.get_pending_event_count(),
    }


@router.post("/start")
async def start_simulation():
    """Start/resume the simulation from current state."""
    engine = get_engine()
    engine._running = True
    return {"status": "started", "step": engine.step_number}


@router.post("/step")
async def step_simulation(count: int = 1):
    """Advance simulation by N steps."""
    engine = get_engine()
    results = []
    for _ in range(count):
        result = engine.step()
        results.append({
            "step": result.step,
            "events_processed": result.events_processed,
            "events_failed": result.events_failed,
            "agents_activated": result.agents_activated,
        })
    from ..dependencies import record_session_snapshot
    record_session_snapshot()
    return {"results": results, "current_step": engine.step_number}


@router.post("/run")
async def run_simulation(steps: int | None = None):
    """Run simulation for N steps (or to completion)."""
    engine = get_engine()
    if steps:
        engine.run_to_step(engine.step_number + steps)
    else:
        engine.run_to_completion()
    return {
        "status": "completed",
        "final_step": engine.step_number,
        "summary": engine.get_summary(),
    }


@router.post("/pause")
async def pause_simulation():
    """Pause the simulation."""
    engine = get_engine()
    engine.pause()
    return {"status": "paused", "step": engine.step_number}


@router.post("/resume")
async def resume_simulation():
    """Resume the simulation."""
    engine = get_engine()
    engine.resume()
    return {"status": "resumed", "step": engine.step_number}


@router.post("/reset")
async def reset_simulation():
    """Reset simulation only (keeps dashboard session data)."""
    reset_engine()
    engine = get_engine()
    return {"status": "reset", "step": engine.step_number}


@router.post("/full-reset")
async def full_reset():
    """Full system reset: clears dashboard session + simulation."""
    from ..dependencies import clear_session
    clear_session()
    reset_engine()
    engine = get_engine()
    return {"status": "full_reset", "step": engine.step_number}


@router.put("/config")
async def update_config(req: SimConfigRequest):
    """Update simulation configuration."""
    engine = get_engine()
    if req.max_steps is not None:
        engine.config.max_steps = req.max_steps
    if req.random_seed is not None:
        engine.config.random_seed = req.random_seed
    if req.log_snapshot_interval is not None:
        engine.config.log_snapshot_interval = req.log_snapshot_interval
    return {"status": "updated"}


@router.get("/config")
async def get_config():
    """Get current simulation configuration."""
    engine = get_engine()
    return {
        "name": engine.config.name,
        "description": engine.config.description,
        "random_seed": engine.config.random_seed,
        "max_steps": engine.config.max_steps,
        "log_snapshot_interval": engine.config.log_snapshot_interval,
        "pool_count": len(engine.config.pools),
        "user_count": len(engine.config.users),
        "agent_count": len(engine.config.agents),
    }


@router.get("/events")
async def get_events(limit: int = 50):
    """Get recent simulation events."""
    engine = get_engine()
    df = engine.logger.events_df()
    if df.empty:
        return {"events": []}

    events = df.tail(limit).to_dict(orient="records")
    return {"events": events}


@router.post("/load-scenario")
async def load_scenario_endpoint(req: LoadScenarioRequest):
    """Load a named scenario and reset the simulation."""
    dep_load_scenario(req.scenario)
    engine = get_engine()
    return {
        "status": "loaded",
        "scenario": req.scenario,
        "step": engine.step_number,
        "max_steps": engine.config.max_steps,
    }


@router.get("/scenarios")
async def list_scenarios():
    """List available built-in scenarios."""
    return {
        "scenarios": [
            {"id": "default", "name": "日常交易", "description": "ETH-USDC 池：随机交易、趋势跟随、LP 做市、鲸鱼交易混合仿真"},
            {"id": "flash_crash", "name": "闪崩场景", "description": "鲸鱼持续大额抛售 ETH，测试价格冲击与 LP 抗压能力"},
            {"id": "arbitrage", "name": "跨池套利", "description": "两个 ETH-USDC 池不同初始价格，套利者捕获价差收益"},
        ]
    }


@router.get("/export")
async def export_data():
    """Get full simulation data for export."""
    engine = get_engine()
    return {
        "summary": engine.get_summary(),
        "state": engine.get_state_snapshot(),
    }

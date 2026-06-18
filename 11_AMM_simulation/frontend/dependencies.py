"""FastAPI dependency injection — provides singleton SimulationEngine and session-level data store."""

from simulator.engine import SimulationEngine
from simulator.scenarios import (
    create_default_scenario,
    create_flash_crash_scenario,
    create_arbitrage_scenario,
)

_engine: SimulationEngine | None = None

# Session-level data — persists across engine resets for dashboard charts
_session_snapshots: list[dict] = []
_session_step: int = 0  # independent counter, increments on each snapshot


def record_session_snapshot() -> None:
    """Record current pool state in the session-level log."""
    global _session_step
    engine = get_engine()
    for pid, pool in engine.pools.items():
        state = pool.get_state()
        _session_snapshots.append({
            "step": _session_step,
            "pool_id": pid,
            "spot_price": float(state.spot_price),
        })
    _session_step += 1


def get_session_price_history(pool_id: str) -> list[dict]:
    """Get price history for a pool from the session-level log."""
    import math
    result = []
    for s in _session_snapshots:
        if s["pool_id"] == pool_id:
            result.append({
                "step": s["step"],
                "spot_price": s["spot_price"],
            })
    return result


def init_engine() -> SimulationEngine:
    """Initialize the global simulation engine (no auto-run)."""
    global _engine
    if _engine is None:
        config = create_default_scenario()
        _engine = SimulationEngine(config)
        _engine.setup()
        _seed_session_from_engine_log()
    return _engine


def get_engine() -> SimulationEngine:
    """Get the global simulation engine (lazy init)."""
    global _engine
    if _engine is None:
        return init_engine()
    return _engine


def _seed_session_from_engine_log() -> None:
    """One-time: copy engine logger data into session store on init."""
    global _session_step
    df = _engine.logger.snapshots_df()
    if df.empty: return
    for _, row in df.iterrows():
        _session_snapshots.append({
            "step": _session_step, "pool_id": row["pool_id"],
            "spot_price": float(row["spot_price"]),
        })
        _session_step += 1


def clear_session() -> None:
    """Clear session-level data (only called by full system reset)."""
    global _session_step
    _session_snapshots.clear()
    _session_step = 0


def reset_engine(config=None) -> SimulationEngine:
    """Reset the engine (simulation only, does not touch dashboard session)."""
    global _engine
    if config is None:
        config = create_default_scenario()
    _engine = SimulationEngine(config)
    _engine.setup()
    return _engine


def load_scenario(name: str) -> SimulationEngine:
    """Load a named scenario (simulation only, does not touch dashboard session)."""
    global _engine
    match name:
        case "flash_crash":
            config = create_flash_crash_scenario()
        case "arbitrage":
            config = create_arbitrage_scenario()
        case _:
            config = create_default_scenario()
    _engine = SimulationEngine(config)
    _engine.setup()
    return _engine

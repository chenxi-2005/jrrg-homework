"""State logger — records simulation events and pool snapshots."""

from decimal import Decimal
from typing import Optional

import pandas as pd

from src.core.types import PoolState
from src.core.pool import LiquidityPool
from src.core.token import TokenLedger
from .events import SimEvent


class StateLogger:
    """
    Logs simulation events and periodic state snapshots.
    Exposes data as Pandas DataFrames for analysis and visualization.
    """

    def __init__(self):
        self._events: list[dict] = []
        self._snapshots: list[dict] = []

    # --- Event logging ---

    def log_event(self, event: SimEvent) -> None:
        """Record an executed event."""
        self._events.append(event.to_dict())

    def log_custom_event(
        self,
        step: int,
        event_type: str,
        initiator: str,
        pool_id: str = "",
        **kwargs,
    ) -> None:
        """Log a custom event not represented as a SimEvent."""
        self._events.append({
            "step": step,
            "event_type": event_type,
            "initiator": initiator,
            "pool_id": pool_id,
            **kwargs,
        })

    # --- Snapshot logging ---

    def log_snapshot(
        self,
        step: int,
        pools: dict[str, LiquidityPool],
        ledger: TokenLedger,
    ) -> None:
        """
        Record a full state snapshot.

        Creates one row per pool per step for easy time-series analysis.
        """
        for pool_id, pool in pools.items():
            state = pool.get_state(step=step)
            self._snapshots.append({
                "step": step,
                "pool_id": pool_id,
                "token_a": state.token_a.value,
                "token_b": state.token_b.value,
                "reserve_a": float(state.reserve_a),
                "reserve_b": float(state.reserve_b),
                "spot_price": float(state.spot_price),
                "twap_price": float(state.twap_price) if state.twap_price else None,
                "total_lp_supply": float(state.total_lp_supply),
                "k": float(state.k),
                "fee_rate": float(state.fee_rate),
                "swap_count": pool.swap_count,
            })

    # --- DataFrame access ---

    def events_df(self) -> pd.DataFrame:
        """Get all logged events as a DataFrame."""
        if not self._events:
            return pd.DataFrame()
        return pd.DataFrame(self._events)

    def snapshots_df(self) -> pd.DataFrame:
        """Get all state snapshots as a DataFrame (one row per pool per step)."""
        if not self._snapshots:
            return pd.DataFrame()
        return pd.DataFrame(self._snapshots)

    # --- Export ---

    def export_events_csv(self, path: str) -> None:
        """Export events log to CSV."""
        df = self.events_df()
        if not df.empty:
            df.to_csv(path, index=False)

    def export_snapshots_csv(self, path: str) -> None:
        """Export snapshots to CSV."""
        df = self.snapshots_df()
        if not df.empty:
            df.to_csv(path, index=False)

    def export_summary(self) -> dict:
        """Return summary statistics for the simulation run."""
        events = self.events_df()
        snaps = self.snapshots_df()
        return {
            "total_events": len(events),
            "total_snapshots": len(snaps),
            "steps_recorded": snaps["step"].nunique() if not snaps.empty else 0,
            "pools": snaps["pool_id"].nunique() if not snaps.empty else 0,
            "swap_events": len(events[events["event_type"] == "swap"]) if not events.empty else 0,
            "liquidity_events": len(events[events["event_type"].isin(["add_liquidity", "remove_liquidity"])]) if not events.empty else 0,
        }

    def clear(self) -> None:
        """Reset all logged data."""
        self._events.clear()
        self._snapshots.clear()

"""
一键运行 AMM 仿真系统 CLI 演示
- 运行默认场景 (50 步)
- 展示池状态、价格变化、事件统计
- 最后进入交互式 Shell

Usage:
    python run_cli.py              # 默认场景 50 步
    python run_cli.py flash_crash  # 闪崩场景
    python run_cli.py arbitrage    # 套利场景
"""

import sys
import os

PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, PROJECT_ROOT)

from decimal import Decimal

from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.text import Text
from rich import box
from rich.progress import Progress

from simulator.engine import SimulationEngine
from simulator.scenarios import (
    create_default_scenario,
    create_flash_crash_scenario,
    create_arbitrage_scenario,
)


def main():
    console = Console()

    # --- Header ---
    console.print()
    console.print(Panel.fit(
        "[bold cyan]AMM Exchange Simulation[/bold cyan]\n"
        "[dim]DeFi 核心逻辑仿真系统 — CLI 演示[/dim]",
        border_style="cyan",
    ))

    # --- Select scenario ---
    scenario_name = sys.argv[1] if len(sys.argv) > 1 else "default"

    match scenario_name:
        case "default":
            config = create_default_scenario()
            config.max_steps = 50
        case "flash_crash":
            config = create_flash_crash_scenario()
        case "arbitrage":
            config = create_arbitrage_scenario()
        case _:
            console.print(f"[red]Unknown scenario: {scenario_name}[/red]")
            console.print("Available: default, flash_crash, arbitrage")
            return

    # --- Setup engine ---
    engine = SimulationEngine(config)
    engine.setup()

    console.print(f"\n[bold]Scenario:[/bold] {config.name}")
    console.print(f"[dim]{config.description}[/dim]")
    console.print(f"Steps: {config.max_steps} | Pools: {len(config.pools)} | "
                  f"Users: {len(config.users)} | Agents: {len(config.agents)}")

    # --- Show initial state ---
    console.print("\n[bold yellow]Initial Pool State:[/bold yellow]")
    _print_pools_table(console, engine)

    # --- Run simulation ---
    console.print("\n[bold yellow]Running simulation...[/bold yellow]")
    with Progress() as progress:
        task = progress.add_task("[cyan]Simulating...", total=config.max_steps)
        for _ in range(config.max_steps):
            engine.step()
            progress.update(task, advance=1)

    results_summary = engine.get_summary()

    # --- Final state ---
    console.print("\n[bold green]Final Pool State:[/bold green]")
    _print_pools_table(console, engine)

    # --- Simulation summary ---
    console.print("\n[bold]Simulation Summary:[/bold]")
    summary_table = Table(box=box.ROUNDED)
    summary_table.add_column("Metric", style="cyan")
    summary_table.add_column("Value", justify="right", style="white")
    summary_table.add_row("Steps Executed", str(results_summary["step"]))
    summary_table.add_row("Total Events", str(results_summary["total_events"]))
    summary_table.add_row("Swap Events", str(results_summary["swap_events"]))
    summary_table.add_row("Liquidity Events", str(results_summary["liquidity_events"]))
    summary_table.add_row("Snapshots Recorded", str(results_summary["total_snapshots"]))
    summary_table.add_row("Pools", str(results_summary["pools"]))
    summary_table.add_row("Users", str(results_summary["users"]))
    summary_table.add_row("Agents", str(results_summary["agents"]))
    console.print(summary_table)

    # --- Price change ---
    console.print("\n[bold]Price Change Analysis:[/bold]")
    df = engine.logger.snapshots_df()
    if not df.empty:
        price_table = Table(box=box.ROUNDED)
        price_table.add_column("Pool ID", style="cyan")
        price_table.add_column("Initial Price", justify="right")
        price_table.add_column("Final Price", justify="right")
        price_table.add_column("Change %", justify="right")
        price_table.add_column("Max Price", justify="right")
        price_table.add_column("Min Price", justify="right")

        for pid in df["pool_id"].unique():
            pool_df = df[df["pool_id"] == pid]
            initial = pool_df.iloc[0]["spot_price"]
            final = pool_df.iloc[-1]["spot_price"]
            change = ((final - initial) / initial) * 100 if initial else 0
            max_p = pool_df["spot_price"].max()
            min_p = pool_df["spot_price"].min()

            change_style = "green" if change >= 0 else "red"
            price_table.add_row(
                pid,
                f"{initial:,.2f}",
                f"{final:,.2f}",
                f"[{change_style}]{change:+.2f}%[/{change_style}]",
                f"{max_p:,.2f}",
                f"{min_p:,.2f}",
            )
        console.print(price_table)

    # --- Recent events ---
    events_df = engine.logger.events_df()
    if not events_df.empty and len(events_df) > 0:
        console.print("\n[bold]Recent Events:[/bold]")
        event_table = Table(box=box.ROUNDED)
        event_table.add_column("Step", justify="right")
        event_table.add_column("Type", style="yellow")
        event_table.add_column("Pool", style="cyan")
        event_table.add_column("Initiator")
        event_table.add_column("Status")

        for _, evt in events_df.tail(15).iterrows():
            status_style = "green" if evt.get("status") == "executed" else "red"
            event_table.add_row(
                str(evt.get("scheduled_step", "?")),
                str(evt.get("event_type", "?")),
                str(evt.get("pool_id", ""))[:14],
                str(evt.get("initiator", "?")),
                f"[{status_style}]{evt.get('status', '?')}[/{status_style}]",
            )
        console.print(event_table)

    # --- Export ---
    engine.logger.export_snapshots_csv("exports/simulation_output.csv")
    engine.logger.export_events_csv("exports/events_output.csv")
    console.print("\n[dim]Data exported to exports/[/dim]")

    console.print("\n[bold green]Simulation complete![/bold green]\n")


def _print_pools_table(console, engine):
    """Render pools as a Rich table."""
    table = Table(title="Liquidity Pools", box=box.ROUNDED)
    table.add_column("Pool ID", style="cyan")
    table.add_column("Pair", style="white")
    table.add_column("Reserve A", justify="right")
    table.add_column("Reserve B", justify="right")
    table.add_column("Spot Price", justify="right")
    table.add_column("K", justify="right")
    table.add_column("Swaps", justify="right")

    for pool in engine.pools.values():
        state = pool.get_state()
        k_str = f"{float(state.k):,.0f}"
        table.add_row(
            pool.pool_id,
            f"{state.token_a.value}/{state.token_b.value}",
            f"{state.reserve_a:,.2f}",
            f"{state.reserve_b:,.2f}",
            f"{state.spot_price:,.2f}",
            k_str,
            str(pool.swap_count),
        )
    console.print(table)


if __name__ == "__main__":
    main()

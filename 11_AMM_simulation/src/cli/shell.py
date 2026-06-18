"""Interactive Rich-based shell for the AMM simulation."""

import sys
from decimal import Decimal

from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.layout import Layout
from rich.live import Live
from rich.text import Text
from rich import box

from src.core.types import TokenSymbol
from simulator.engine import SimulationEngine

console = Console()


def display_pools(engine: SimulationEngine) -> None:
    """Render pools as a Rich table."""
    table = Table(title="Liquidity Pools", box=box.ROUNDED)
    table.add_column("Pool ID", style="cyan")
    table.add_column("Pair", style="white")
    table.add_column("Reserve A", justify="right")
    table.add_column("Reserve B", justify="right")
    table.add_column("Spot Price", justify="right")
    table.add_column("TWAP", justify="right")
    table.add_column("Swaps", justify="right")

    for pool in engine.pools.values():
        state = pool.get_state()
        twap_str = f"{state.twap_price:,.2f}" if state.twap_price else "N/A"
        table.add_row(
            pool.pool_id,
            f"{state.token_a.value}/{state.token_b.value}",
            f"{state.reserve_a:,.2f}",
            f"{state.reserve_b:,.2f}",
            f"{state.spot_price:,.2f}",
            twap_str,
            str(pool.swap_count),
        )
    console.print(table)


def display_users(engine: SimulationEngine) -> None:
    """Render user balances as a Rich table."""
    table = Table(title="User Balances", box=box.ROUNDED)
    table.add_column("User ID", style="cyan")
    table.add_column("Token", style="yellow")
    table.add_column("Balance", justify="right")

    for uid in engine.ledger.list_users():
        balances = engine.ledger.get_all_balances(uid)
        first = True
        for tok, amt in balances.items():
            table.add_row(uid if first else "", tok.value, f"{amt:,.4f}")
            first = False
        if not balances:
            table.add_row(uid, "-", "0")
    console.print(table)


def display_summary(engine: SimulationEngine) -> None:
    """Render simulation summary."""
    summary = engine.get_summary()
    text = Text()
    text.append(f"Step: {summary['step']}/{summary['max_steps']}  |  ", style="bold")
    text.append(f"Pools: {summary['pools']}  |  ")
    text.append(f"Users: {summary['users']}  |  ")
    text.append(f"Agents: {summary['agents']}  |  ")
    text.append(f"Events: {summary['total_events']}")
    if engine.paused:
        text.append("  |  [PAUSED]", style="bold red")
    console.print(Panel(text, title="Simulation Status"))


HELP_TEXT = """
[bold cyan]AMM Simulation Interactive Shell[/bold cyan]

Commands:
  [yellow]pools[/yellow]              List all pools
  [yellow]users[/yellow]              List all users
  [yellow]status[/yellow]             Show simulation status
  [yellow]step [N][/yellow]           Advance N steps (default 1)
  [yellow]run [N][/yellow]            Run N steps (default: to completion)
  [yellow]run-scenario <name>[/yellow] Run a named scenario (default, flash_crash, arbitrage)
  [yellow]swap <pool_id> <token> <amount>[/yellow]  Execute a swap
  [yellow]quote <pool_id> <token> <amount>[/yellow] Get a quote
  [yellow]pool-info <pool_id>[/yellow] Show pool detail
  [yellow]user <user_id>[/yellow]     Show user balances
  [yellow]add-lp <pool_id> <user> <amt_a> <amt_b>[/yellow]  Add liquidity
  [yellow]remove-lp <pool_id> <user> <lp_amt>[/yellow]      Remove liquidity
  [yellow]export[/yellow]             Export snapshots to CSV
  [yellow]reset[/yellow]              Reset simulation
  [yellow]help[/yellow]               Show this help
  [yellow]quit[/yellow] / [yellow]exit[/yellow]    Exit
"""


class InteractiveShell:
    """Rich-based interactive simulation console."""

    def __init__(self, engine: SimulationEngine):
        self.engine = engine
        self.running = True

    def run(self) -> None:
        console.print(Panel.fit(
            "[bold cyan]AMM Exchange Simulation[/bold cyan]\n"
            "DeFi 核心逻辑仿真系统 — 交互式命令行",
            border_style="cyan",
        ))
        console.print(HELP_TEXT)
        display_summary(self.engine)
        display_pools(self.engine)

        while self.running:
            try:
                cmd = console.input("\n[bold green]amm>[/bold green] ").strip()
                if not cmd:
                    continue
                self._dispatch(cmd)
            except KeyboardInterrupt:
                console.print("\n[red]Interrupted.[/red]")
                break
            except EOFError:
                break

        console.print("\n[dim]Simulation ended.[/dim]")

    def _dispatch(self, cmd: str) -> None:
        parts = cmd.split()
        verb = parts[0].lower()
        args = parts[1:]

        match verb:
            case "pools" | "pool":
                display_pools(self.engine)

            case "users" | "user":
                if args:
                    self._cmd_user_balance(args[0])
                else:
                    display_users(self.engine)

            case "status":
                display_summary(self.engine)

            case "step":
                count = int(args[0]) if args else 1
                for _ in range(count):
                    result = self.engine.step()
                    console.print(f"  Step {result.step}: {result.events_processed} events, "
                                  f"{result.agents_activated} agent actions")
                display_pools(self.engine)

            case "run":
                if args:
                    target = int(args[0])
                    self.engine.run_to_step(target)
                else:
                    self.engine.run_to_completion()
                display_summary(self.engine)
                display_pools(self.engine)

            case "run-scenario":
                name = args[0] if args else "default"
                from simulator.scenarios import (
                    create_default_scenario, create_flash_crash_scenario,
                    create_arbitrage_scenario,
                )
                match name:
                    case "default": config = create_default_scenario()
                    case "flash_crash": config = create_flash_crash_scenario()
                    case "arbitrage": config = create_arbitrage_scenario()
                    case _:
                        console.print(f"[red]Unknown scenario: {name}[/red]")
                        return
                from src.cli.main import reset_engine
                reset_engine(config)
                console.print(f"[green]Loaded scenario: {config.name}[/green]")
                display_summary(self.engine)
                display_pools(self.engine)

            case "swap":
                if len(args) < 3:
                    console.print("[red]Usage: swap <pool_id> <token> <amount>[/red]")
                    return
                self._cmd_swap(args[0], args[1], args[2])

            case "quote":
                if len(args) < 3:
                    console.print("[red]Usage: quote <pool_id> <token> <amount>[/red]")
                    return
                self._cmd_quote(args[0], args[1], args[2])

            case "pool-info":
                if not args:
                    console.print("[red]Usage: pool-info <pool_id>[/red]")
                    return
                self._cmd_pool_info(args[0])

            case "add-lp":
                if len(args) < 4:
                    console.print("[red]Usage: add-lp <pool_id> <user> <amt_a> <amt_b>[/red]")
                    return
                self._cmd_add_lp(args[0], args[1], args[2], args[3])

            case "remove-lp":
                if len(args) < 3:
                    console.print("[red]Usage: remove-lp <pool_id> <user> <lp_amt>[/red]")
                    return
                self._cmd_remove_lp(args[0], args[1], args[2])

            case "export":
                self.engine.logger.export_snapshots_csv("exports/simulation_output.csv")
                self.engine.logger.export_events_csv("exports/events_output.csv")
                console.print("[green]Exported to exports/[/green]")

            case "reset":
                from src.cli.main import reset_engine
                reset_engine()
                console.print("[green]Simulation reset.[/green]")
                display_pools(self.engine)

            case "help" | "h":
                console.print(HELP_TEXT)

            case "quit" | "exit" | "q":
                self.running = False

            case _:
                console.print(f"[red]Unknown command: {verb}[/red]")

    def _cmd_swap(self, pool_id, token_str, amount_str):
        pool = self.engine.pools.get(pool_id)
        if pool is None:
            console.print(f"[red]Pool '{pool_id}' not found.[/red]")
            return
        try:
            result = pool.swap(TokenSymbol(token_str), Decimal(amount_str))
            console.print(f"  [green]Swap: {result.amount_in} {result.token_in.value} -> "
                          f"{result.amount_out:,.6f} {result.token_out.value}[/green]")
            console.print(f"  Price: 1 {result.token_in.value} = {result.effective_price:,.2f} "
                          f"{result.token_out.value} | Impact: {result.price_impact_bps/100:.2f}%")
        except Exception as e:
            console.print(f"[red]Swap failed: {e}[/red]")

    def _cmd_quote(self, pool_id, token_str, amount_str):
        pool = self.engine.pools.get(pool_id)
        if pool is None:
            console.print(f"[red]Pool '{pool_id}' not found.[/red]")
            return
        result = pool.get_swap_quote(TokenSymbol(token_str), Decimal(amount_str))
        console.print(f"  Quote: {result.amount_in} {result.token_in.value} -> "
                      f"{result.amount_out:,.6f} {result.token_out.value}")
        console.print(f"  Price: 1 {result.token_in.value} = {result.effective_price:,.2f} "
                      f"{result.token_out.value} | Impact: {result.price_impact_bps/100:.2f}%")

    def _cmd_pool_info(self, pool_id):
        pool = self.engine.pools.get(pool_id)
        if pool is None:
            console.print(f"[red]Pool '{pool_id}' not found.[/red]")
            return
        state = pool.get_state()
        table = Table(title=f"Pool: {pool_id}")
        table.add_column("Property")
        table.add_column("Value")
        table.add_row("Pair", f"{state.token_a.value}/{state.token_b.value}")
        table.add_row(f"Reserve {state.token_a.value}", f"{state.reserve_a:,.6f}")
        table.add_row(f"Reserve {state.token_b.value}", f"{state.reserve_b:,.6f}")
        table.add_row("K", f"{state.k:,.2f}")
        table.add_row("Spot Price", f"1 {state.token_a.value} = {state.spot_price:,.2f} {state.token_b.value}")
        if state.twap_price:
            table.add_row("TWAP", f"1 {state.token_a.value} = {state.twap_price:,.2f} {state.token_b.value}")
        table.add_row("Fee Rate", f"{float(state.fee_rate)*100:.1f}%")
        table.add_row("LP Supply", f"{state.total_lp_supply:,.6f}")
        table.add_row("Swaps", str(pool.swap_count))
        console.print(table)

    def _cmd_user_balance(self, user_id):
        balances = self.engine.ledger.get_all_balances(user_id)
        if not balances:
            console.print(f"User '{user_id}' not found.")
            return
        console.print(f"\n[bold]{user_id}[/bold]")
        for tok, amt in balances.items():
            console.print(f"  {tok.value}: {amt:,.4f}")

    def _cmd_add_lp(self, pool_id, user_id, amount_a, amount_b):
        pool = self.engine.pools.get(pool_id)
        if pool is None:
            console.print(f"[red]Pool '{pool_id}' not found.[/red]")
            return
        try:
            lp = pool.add_liquidity(user_id, Decimal(amount_a), Decimal(amount_b))
            console.print(f"[green]Added liquidity: {lp:,.6f} LP tokens[/green]")
        except Exception as e:
            console.print(f"[red]Failed: {e}[/red]")

    def _cmd_remove_lp(self, pool_id, user_id, lp_amount):
        pool = self.engine.pools.get(pool_id)
        if pool is None:
            console.print(f"[red]Pool '{pool_id}' not found.[/red]")
            return
        try:
            amt_a, amt_b = pool.remove_liquidity(user_id, Decimal(lp_amount))
            console.print(f"[green]Removed: {amt_a:,.6f} {pool.token_a.value} + {amt_b:,.6f} {pool.token_b.value}[/green]")
        except Exception as e:
            console.print(f"[red]Failed: {e}[/red]")

"""
CLI entry point for the AMM Exchange Simulation.

Usage:
    python -m src.cli.main shell          # Interactive shell
    python -m src.cli.main pool list      # List pools
    python -m src.cli.main swap <pool> <token> <amount>  # Execute swap
    python -m src.cli.main sim run default --steps 50     # Run scenario
"""

import sys
from decimal import Decimal

import click

from src.core.types import TokenSymbol, PoolConfig
from simulator.engine import SimulationEngine
from simulator.scenarios import (
    create_default_scenario,
    create_flash_crash_scenario,
    create_arbitrage_scenario,
    list_scenarios,
    load_scenario,
)

# Global engine instance
_engine: SimulationEngine | None = None


def get_engine() -> SimulationEngine:
    global _engine
    if _engine is None:
        config = create_default_scenario()
        _engine = SimulationEngine(config)
        _engine.setup()
    return _engine


def reset_engine(config=None):
    global _engine
    if config is None:
        config = create_default_scenario()
    _engine = SimulationEngine(config)
    _engine.setup()


# ---------------------------------------------------------------------------
# CLI Group
# ---------------------------------------------------------------------------

@click.group()
@click.pass_context
def cli(ctx):
    """AMM Exchange Simulation — DeFi 核心逻辑仿真系统"""
    ctx.ensure_object(dict)


# ---------------------------------------------------------------------------
# Pool commands
# ---------------------------------------------------------------------------

@cli.group()
def pool():
    """Manage liquidity pools."""


@pool.command("list")
def pool_list():
    """List all pools with current state."""
    engine = get_engine()
    from src.cli.shell import display_pools
    display_pools(engine)


@pool.command("info")
@click.argument("pool_id")
def pool_info(pool_id):
    """Show detailed pool information."""
    engine = get_engine()
    pool = engine.pools.get(pool_id)
    if pool is None:
        click.echo(f"Pool '{pool_id}' not found.")
        return
    state = pool.get_state(step=engine.clock.step)
    click.echo(f"\n{'='*60}")
    click.echo(f"  Pool: {pool.pool_id}")
    click.echo(f"  Pair: {state.token_a.value}/{state.token_b.value}")
    click.echo(f"  Reserve {state.token_a.value}: {state.reserve_a:,.6f}")
    click.echo(f"  Reserve {state.token_b.value}: {state.reserve_b:,.6f}")
    click.echo(f"  K (constant):  {state.k:,.2f}")
    click.echo(f"  Spot Price:    1 {state.token_a.value} = {state.spot_price:,.2f} {state.token_b.value}")
    if state.twap_price:
        click.echo(f"  TWAP:          1 {state.token_a.value} = {state.twap_price:,.2f} {state.token_b.value}")
    click.echo(f"  Fee Rate:      {float(state.fee_rate)*100:.1f}%")
    click.echo(f"  LP Supply:     {state.total_lp_supply:,.6f}")
    click.echo(f"  Swaps:         {pool.swap_count}")
    click.echo(f"  Step:          {state.step}")
    click.echo(f"{'='*60}\n")


@pool.command("create")
@click.option("--token-a", required=True, help="Token A symbol (ETH, USDC, BTC, DAI)")
@click.option("--token-b", required=True, help="Token B symbol")
@click.option("--reserve-a", required=True, type=str, help="Initial reserve of token A")
@click.option("--reserve-b", required=True, type=str, help="Initial reserve of token B")
@click.option("--fee-rate", default="0.003", help="Fee rate (default: 0.003 = 0.3%)")
def pool_create(token_a, token_b, reserve_a, reserve_b, fee_rate):
    """Create a new liquidity pool."""
    engine = get_engine()
    config = PoolConfig(
        token_a=TokenSymbol(token_a),
        token_b=TokenSymbol(token_b),
        fee_rate=Decimal(fee_rate),
        initial_reserve_a=Decimal(reserve_a),
        initial_reserve_b=Decimal(reserve_b),
    )
    pool = engine.register_pool(config)
    click.echo(f"Created pool: {pool.pool_id}")
    click.echo(f"  1 {token_a} = {pool.get_spot_price():,.2f} {token_b}")


# ---------------------------------------------------------------------------
# Swap commands
# ---------------------------------------------------------------------------

@cli.group()
def swap():
    """Execute and query token swaps."""


@swap.command("execute")
@click.argument("pool_id")
@click.argument("token_in")
@click.argument("amount_in")
@click.option("--min-out", default="0", help="Minimum output amount (slippage protection)")
def swap_execute(pool_id, token_in, amount_in, min_out):
    """Execute a swap on a pool."""
    engine = get_engine()
    pool = engine.pools.get(pool_id)
    if pool is None:
        click.echo(f"Pool '{pool_id}' not found.")
        return

    token = TokenSymbol(token_in)
    amount = Decimal(amount_in)

    try:
        result = pool.swap(token, amount)
        if result.amount_out < Decimal(min_out):
            click.echo(f"ERROR: Slippage exceeded. Got {result.amount_out}, min {min_out}")
            return
        click.echo(f"\n  Swap Executed:")
        click.echo(f"    Input:   {result.amount_in} {result.token_in.value}")
        click.echo(f"    Output:  {result.amount_out:,.6f} {result.token_out.value}")
        click.echo(f"    Fee:     {result.fee_collected} {result.token_in.value}")
        click.echo(f"    Price:   1 {result.token_in.value} = {result.effective_price:,.2f} {result.token_out.value}")
        click.echo(f"    Impact:  {result.price_impact_bps/100:.2f}%")
        click.echo(f"    New Spot: 1 {pool.token_a.value} = {result.new_spot_price:,.2f} {pool.token_b.value}\n")
    except Exception as e:
        click.echo(f"Swap failed: {e}")


@swap.command("quote")
@click.argument("pool_id")
@click.argument("token_in")
@click.argument("amount_in")
def swap_quote(pool_id, token_in, amount_in):
    """Get a quote for a swap without executing it."""
    engine = get_engine()
    pool = engine.pools.get(pool_id)
    if pool is None:
        click.echo(f"Pool '{pool_id}' not found.")
        return

    result = pool.get_swap_quote(TokenSymbol(token_in), Decimal(amount_in))
    click.echo(f"\n  Quote (dry-run):")
    click.echo(f"    Input:   {result.amount_in} {result.token_in.value}")
    click.echo(f"    Output:  {result.amount_out:,.6f} {result.token_out.value}")
    click.echo(f"    Fee:     {result.fee_collected} {result.token_in.value}")
    click.echo(f"    Price:   1 {result.token_in.value} = {result.effective_price:,.2f} {result.token_out.value}")
    click.echo(f"    Impact:  {result.price_impact_bps/100:.2f}%\n")


# ---------------------------------------------------------------------------
# Liquidity commands
# ---------------------------------------------------------------------------

@cli.group()
def liquidity():
    """Manage liquidity positions."""


@liquidity.command("add")
@click.argument("pool_id")
@click.argument("user_id")
@click.argument("amount_a")
@click.argument("amount_b")
def liquidity_add(pool_id, user_id, amount_a, amount_b):
    """Add liquidity to a pool."""
    engine = get_engine()
    pool = engine.pools.get(pool_id)
    if pool is None:
        click.echo(f"Pool '{pool_id}' not found.")
        return

    try:
        lp = pool.add_liquidity(user_id, Decimal(amount_a), Decimal(amount_b))
        click.echo(f"Added liquidity: {lp:,.6f} LP tokens minted")
        click.echo(f"  New reserves: {pool.reserve_a:,.4f} / {pool.reserve_b:,.4f}")
    except Exception as e:
        click.echo(f"Failed: {e}")


@liquidity.command("remove")
@click.argument("pool_id")
@click.argument("user_id")
@click.argument("lp_amount")
def liquidity_remove(pool_id, user_id, lp_amount):
    """Remove liquidity from a pool."""
    engine = get_engine()
    pool = engine.pools.get(pool_id)
    if pool is None:
        click.echo(f"Pool '{pool_id}' not found.")
        return

    try:
        amt_a, amt_b = pool.remove_liquidity(user_id, Decimal(lp_amount))
        click.echo(f"Removed liquidity: {amt_a:,.6f} {pool.token_a.value} + {amt_b:,.6f} {pool.token_b.value}")
    except Exception as e:
        click.echo(f"Failed: {e}")


@liquidity.command("positions")
@click.argument("pool_id")
def liquidity_positions(pool_id):
    """Show all LP positions for a pool."""
    engine = get_engine()
    pool = engine.pools.get(pool_id)
    if pool is None:
        click.echo(f"Pool '{pool_id}' not found.")
        return

    positions = pool.get_all_lp_positions()
    if not positions:
        click.echo("No LP positions.")
        return
    click.echo(f"\n  LP Positions for {pool_id}:")
    for uid, amt in positions.items():
        pct = (amt / pool.total_lp_supply * Decimal("100")) if pool.total_lp_supply > 0 else Decimal("0")
        click.echo(f"    {uid}: {amt:,.6f} LP ({pct:,.2f}%)")


@liquidity.command("il")
@click.argument("pool_id")
@click.argument("price_ratio")
def liquidity_il(pool_id, price_ratio):
    """Calculate impermanent loss for a given price ratio."""
    engine = get_engine()
    pool = engine.pools.get(pool_id)
    if pool is None:
        click.echo(f"Pool '{pool_id}' not found.")
        return

    il = pool.get_impermanent_loss(Decimal(price_ratio))
    click.echo(f"\n  Impermanent Loss at {price_ratio}x price change: {float(il)*100:,.4f}%")


# ---------------------------------------------------------------------------
# User commands
# ---------------------------------------------------------------------------

@cli.group()
def user():
    """Manage users and balances."""


@user.command("list")
def user_list():
    """List all users."""
    engine = get_engine()
    click.echo(f"\n  Users ({len(engine.wallets)}):")
    for uid, wallet in engine.wallets.items():
        click.echo(f"    {uid}")


@user.command("balance")
@click.argument("user_id")
def user_balance(user_id):
    """Show a user's balances."""
    engine = get_engine()
    balances = engine.ledger.get_all_balances(user_id)
    if not balances:
        click.echo(f"User '{user_id}' not found or has no balances.")
        return
    click.echo(f"\n  Balances for {user_id}:")
    for tok, amt in balances.items():
        click.echo(f"    {tok.value}: {amt:,.6f}")


# ---------------------------------------------------------------------------
# Simulation commands
# ---------------------------------------------------------------------------

@cli.group()
def sim():
    """Run and control simulations."""


@sim.command("run")
@click.argument("scenario", default="default")
@click.option("--steps", default=None, type=int, help="Number of steps to run")
def sim_run(scenario, steps):
    """Run a named scenario or a scenario file."""
    engine = get_engine()

    # Try named scenarios
    match scenario:
        case "default":
            config = create_default_scenario()
        case "flash_crash":
            config = create_flash_crash_scenario()
        case "arbitrage":
            config = create_arbitrage_scenario()
        case _:
            # Try loading from file
            config = load_scenario(scenario)

    if steps:
        config.max_steps = steps

    reset_engine(config)
    engine = get_engine()

    click.echo(f"\n  Running scenario: {config.name}")
    click.echo(f"  {config.description}")
    click.echo(f"  Steps: {config.max_steps} | Pools: {len(config.pools)} | Users: {len(config.users)} | Agents: {len(config.agents)}")
    click.echo()

    results = engine.run_to_completion()

    # Summary
    total_events = sum(r.events_processed for r in results)
    total_failed = sum(r.events_failed for r in results)
    click.echo(f"\n  Simulation Complete:")
    click.echo(f"    Steps executed:  {len(results)}")
    click.echo(f"    Events processed: {total_events}")
    click.echo(f"    Events failed:    {total_failed}")

    # Pool states
    click.echo(f"\n  Final Pool States:")
    for pool in engine.pools.values():
        state = pool.get_state(step=engine.clock.step)
        click.echo(f"    {pool.pool_id}: 1 {state.token_a.value} = {state.spot_price:,.2f} {state.token_b.value} "
                    f"| K={state.k:,.2f} | Swaps={pool.swap_count}")


@sim.command("step")
@click.option("--count", default=1, help="Number of steps to advance")
def sim_step(count):
    """Advance simulation by N steps."""
    engine = get_engine()
    for _ in range(count):
        result = engine.step()
        click.echo(f"  Step {result.step}: {result.events_processed} events, "
                    f"{result.events_failed} failed, {result.agents_activated} agent actions")
    # Show pool prices
    for pool in engine.pools.values():
        click.echo(f"    {pool.pool_id}: 1 {pool.token_a.value} = {pool.get_spot_price():,.2f} {pool.token_b.value}")


@sim.command("status")
def sim_status():
    """Show current simulation status."""
    engine = get_engine()
    summary = engine.get_summary()
    click.echo(f"\n  Simulation Status:")
    click.echo(f"    Step:     {summary['step']}/{summary['max_steps']}")
    click.echo(f"    Pools:    {summary['pools']}")
    click.echo(f"    Users:    {summary['users']}")
    click.echo(f"    Agents:   {summary['agents']}")
    click.echo(f"    Events:   {summary['total_events']} total ({engine.get_pending_event_count()} pending)")
    if engine.paused:
        click.echo(f"    State:    PAUSED")


@sim.command("reset")
def sim_reset():
    """Reset simulation to initial state."""
    reset_engine()
    click.echo("Simulation reset.")


# ---------------------------------------------------------------------------
# Export commands
# ---------------------------------------------------------------------------

@cli.group()
def export():
    """Export simulation data."""


@export.command("csv")
@click.option("--output", default="exports/simulation_output.csv", help="Output file path")
def export_csv(output):
    """Export snapshots to CSV."""
    engine = get_engine()
    engine.logger.export_snapshots_csv(output)
    click.echo(f"Exported snapshots to {output}")


@export.command("events")
@click.option("--output", default="exports/events_output.csv", help="Output file path")
def export_events(output):
    """Export event log to CSV."""
    engine = get_engine()
    engine.logger.export_events_csv(output)
    click.echo(f"Exported events to {output}")


@export.command("summary")
def export_summary():
    """Show simulation summary."""
    engine = get_engine()
    summary = engine.logger.export_summary()
    click.echo(f"\n  Simulation Summary:")
    for k, v in summary.items():
        click.echo(f"    {k}: {v}")


# ---------------------------------------------------------------------------
# Shell (interactive mode)
# ---------------------------------------------------------------------------

@cli.command("shell")
def shell_cmd():
    """Launch interactive simulation shell."""
    from src.cli.shell import InteractiveShell
    shell = InteractiveShell(get_engine())
    shell.run()


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main():
    """Main entry point for CLI."""
    if len(sys.argv) == 1:
        # No arguments: launch interactive shell
        from src.cli.shell import InteractiveShell
        shell = InteractiveShell(get_engine())
        shell.run()
    else:
        cli()


if __name__ == "__main__":
    main()

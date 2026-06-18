"""Scenario management — load, save, and list simulation scenarios."""

import json
import os
from pathlib import Path

from src.core.types import SimulationConfig, PoolConfig, TokenSymbol


# Default scenarios directory relative to project root
SCENARIOS_DIR = Path(__file__).parent.parent / "data"


def load_scenario(path: str | Path) -> SimulationConfig:
    """
    Load a simulation scenario from a JSON file.

    Args:
        path: Path to the JSON scenario file.

    Returns:
        A validated SimulationConfig.
    """
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return _dict_to_config(data)


def save_scenario(config: SimulationConfig, path: str | Path) -> None:
    """Save a SimulationConfig to a JSON file."""
    data = config.model_dump()
    # Convert enums to strings
    data["pools"] = [
        {**p, "token_a": p["token_a"].value if hasattr(p["token_a"], 'value') else p["token_a"],
              "token_b": p["token_b"].value if hasattr(p["token_b"], 'value') else p["token_b"]}
        for p in data["pools"]
    ]
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False, default=str)


def list_scenarios(scenarios_dir: str | Path | None = None) -> list[str]:
    """List all available scenario JSON files."""
    d = Path(scenarios_dir) if scenarios_dir else SCENARIOS_DIR
    if not d.exists():
        return []
    return sorted([f.name for f in d.glob("*.json")])


def _dict_to_config(data: dict) -> SimulationConfig:
    """Convert a raw dict to a SimulationConfig with proper types."""
    # Parse pools
    pools = []
    for p in data.get("pools", []):
        pools.append(PoolConfig(
            token_a=TokenSymbol(p["token_a"]),
            token_b=TokenSymbol(p["token_b"]),
            fee_rate=p.get("fee_rate", "0.003"),
            initial_reserve_a=p["initial_reserve_a"],
            initial_reserve_b=p["initial_reserve_b"],
            creator_id=p.get("creator_id", "system"),
        ))

    return SimulationConfig(
        name=data.get("name", "unnamed"),
        description=data.get("description", ""),
        random_seed=data.get("random_seed", 42),
        max_steps=data.get("max_steps", 100),
        pools=pools,
        users=data.get("users", []),
        agents=data.get("agents", []),
        log_snapshot_interval=data.get("log_snapshot_interval", 1),
    )


def create_default_scenario() -> SimulationConfig:
    """Create the default demo scenario: ETH-USDC pool with mixed agents."""
    return SimulationConfig(
        name="default",
        description="ETH-USDC 池日常交易：随机交易者、趋势跟随者、LP、鲸鱼混合仿真",
        random_seed=42,
        max_steps=50,
        pools=[
            PoolConfig(
                token_a=TokenSymbol.ETH,
                token_b=TokenSymbol.USDC,
                fee_rate="0.003",
                initial_reserve_a="100",
                initial_reserve_b="200000",
                creator_id="system",
            ),
        ],
        users=[
            {"user_id": "trader_1", "balances": {"ETH": "50", "USDC": "500000"}},
            {"user_id": "trader_2", "balances": {"ETH": "30", "USDC": "300000"}},
            {"user_id": "trend_1", "balances": {"ETH": "20", "USDC": "200000"}},
            {"user_id": "lp_1", "balances": {"ETH": "200", "USDC": "1000000"}},
            {"user_id": "whale_1", "balances": {"ETH": "500", "USDC": "5000000"}},
        ],
        agents=[
            {"type": "random", "user_id": "trader_1", "params": {"swap_probability": 0.4}},
            {"type": "random", "user_id": "trader_2", "params": {"swap_probability": 0.3}},
            {"type": "trend_follower", "user_id": "trend_1", "params": {"lookback_steps": 5}},
            {"type": "liquidity_provider", "user_id": "lp_1", "params": {"add_probability": 0.15}},
            {"type": "whale", "user_id": "whale_1", "params": {"trade_interval": 10, "trade_fraction": 0.15}},
        ],
    )


def create_flash_crash_scenario() -> SimulationConfig:
    """Scenario: flash crash with a whale dumping large amounts."""
    return SimulationConfig(
        name="flash_crash",
        description="Flash crash: whale dumps large ETH position, testing price impact and LP resilience.",
        random_seed=123,
        max_steps=60,
        pools=[
            PoolConfig(
                token_a=TokenSymbol.ETH,
                token_b=TokenSymbol.USDC,
                fee_rate="0.003",
                initial_reserve_a="500",
                initial_reserve_b="1000000",
                creator_id="system",
            ),
        ],
        users=[
            {"user_id": "whale", "balances": {"ETH": "2000", "USDC": "1000000"}},
            {"user_id": "retail_1", "balances": {"ETH": "10", "USDC": "20000"}},
            {"user_id": "retail_2", "balances": {"ETH": "5", "USDC": "10000"}},
            {"user_id": "lp_1", "balances": {"ETH": "100", "USDC": "200000"}},
        ],
        agents=[
            {"type": "whale", "user_id": "whale", "params": {"trade_interval": 3, "trade_fraction": 0.3}},
            {"type": "random", "user_id": "retail_1", "params": {"swap_probability": 0.2}},
            {"type": "random", "user_id": "retail_2", "params": {"swap_probability": 0.2}},
            {"type": "liquidity_provider", "user_id": "lp_1", "params": {"add_probability": 0.1, "remove_probability": 0.05}},
        ],
    )


def create_arbitrage_scenario() -> SimulationConfig:
    """Scenario: two ETH-USDC pools with arbitrageur."""
    return SimulationConfig(
        name="arbitrage",
        description="Two ETH-USDC pools with different starting prices + arbitrageur.",
        random_seed=456,
        max_steps=80,
        pools=[
            PoolConfig(
                token_a=TokenSymbol.ETH,
                token_b=TokenSymbol.USDC,
                fee_rate="0.003",
                initial_reserve_a="100",
                initial_reserve_b="200000",  # 1 ETH = 2000 USDC
                creator_id="system",
            ),
            PoolConfig(
                token_a=TokenSymbol.ETH,
                token_b=TokenSymbol.USDC,
                fee_rate="0.003",
                initial_reserve_a="50",
                initial_reserve_b="110000",  # 1 ETH = 2200 USDC (mis-priced)
                creator_id="system",
            ),
        ],
        users=[
            {"user_id": "arb", "balances": {"ETH": "100", "USDC": "1000000"}},
            {"user_id": "trader_1", "balances": {"ETH": "20", "USDC": "100000"}},
            {"user_id": "trader_2", "balances": {"ETH": "20", "USDC": "100000"}},
        ],
        agents=[
            {"type": "arbitrageur", "user_id": "arb", "params": {"min_profit_bps": 5}},
            {"type": "random", "user_id": "trader_1", "params": {"swap_probability": 0.3}},
            {"type": "random", "user_id": "trader_2", "params": {"swap_probability": 0.3}},
        ],
    )

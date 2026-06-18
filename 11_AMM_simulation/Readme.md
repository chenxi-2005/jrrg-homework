# AMM Exchange Simulation — DeFi 核心逻辑仿真系统

> **金融软件工程实验 · 期末大作业**
> 去中心化金融（DeFi）AMM 交易所仿真系统
> CLI 命令行 + Web 可视化双界面

---

## 功能概览

- **恒定乘积 AMM**：Uniswap V2 风格 x·y=k 做市模型
- **代币交换**：实时报价、滑点计算、价格冲击评估
- **流动性管理**：LP 存入/取出、LP 代币铸造/销毁、无常损失分析
- **多池多用户仿真**：事件驱动引擎、5 种自主交易代理
- **双界面**：Click+Rich CLI | FastAPI + ECharts Web 中文界面
- **完整测试**：82 项单元测试覆盖核心逻辑
- **丰富场景**：日常交易、闪崩、跨池套利等预定义场景

---

## 快速开始

### 环境要求

- Python 3.10+
- pip

### 安装

```bash
cd jrrg-homework
pip install -r requirements.txt
```

### 一键启动

```bash
# Windows 一键启动脚本
start_web.bat

# Web 界面 — 自动打开浏览器
python run_web.py

# CLI 仿真 — 终端显示结果
python run_cli.py              # 默认场景 50 步
python run_cli.py flash_crash  # 闪崩场景
python run_cli.py arbitrage    # 套利场景
```

### 高级用法

```bash
# CLI 交互式 Shell
python -m src.cli.main shell

# CLI 直接命令
python -m src.cli.main pool list
python -m src.cli.main sim run default --steps 20
python -m src.cli.main swap execute <pool_id> ETH 1

# Web 服务器（手动启动）
python -m frontend.app
```

浏览器访问: **http://localhost:8000**

| 页面 | 路径 | 说明 |
|------|------|------|
| 概览 | `/` | 池卡片、价格走势、储备曲线 |
| 池详情 | `/pools/{id}` | 池信息、x·y=k 曲线、LP 持仓 |
| 交易 | `/trade` | 代币兑换 + 实时报价 |
| 流动性 | `/liquidity` | LP 管理 + 无常损失图表 |
| 仿真控制 | `/simulation` | 运行控制 + 事件日志 |

### 运行测试

```bash
python -m pytest tests/ -v
# 82 passed
```

---

## 项目结构

```
jrrg-homework/
├── run_web.py                   # 一键启动 Web 界面（自动打开浏览器）
├── run_cli.py                   # 一键运行 CLI 仿真演示
├── start_web.bat                # Windows 一键启动脚本
├── README.md
├── requirements.txt
├── src/                         # 核心 AMM 逻辑
│   ├── core/                    # 纯数学与领域模型
│   │   ├── formula.py           # x·y=k 公式、滑点、无常损失
│   │   ├── pool.py              # 流动性池
│   │   ├── token.py             # 代币账本
│   │   ├── wallet.py            # 用户钱包
│   │   └── oracle.py            # TWAP 预言机
│   └── cli/                     # CLI 命令 + 交互式 Shell
│       ├── main.py              # Click 命令组
│       └── shell.py             # Rich 交互 Shell
├── simulator/                   # 仿真引擎
│   ├── engine.py                # 事件驱动核心
│   ├── agents.py                # 5 种交易代理
│   ├── events.py                # 事件定义
│   ├── scenarios.py             # 场景管理
│   └── logger.py                # 状态日志
├── frontend/                    # Web 界面
│   ├── app.py                   # FastAPI 应用
│   ├── routers/                 # REST + WebSocket API
│   ├── templates/               # Jinja2 页面（中文）
│   └── static/                  # CSS + ECharts
└── tests/                       # 82 项测试
```

---

## 核心概念

### 恒定乘积公式

$$x \cdot y = k$$

- $x$：代币 A 的储备量
- $y$：代币 B 的储备量
- $k$：恒定乘积（无手续费时不变）

### 交易输出

$$\Delta y = \frac{y \cdot \Delta x \cdot (1 - f)}{x + \Delta x \cdot (1 - f)}$$

其中 $f$ 为手续费率（默认 0.3%）。

### 无常损失

$$IL = \frac{2\sqrt{p_r}}{1 + p_r} - 1$$

$p_r$ 为价格变化倍数。当价格偏离初始价格时，LP 会遭受无常损失。

---

## 交易代理

| 代理 | 类名 | 策略 |
|------|------|------|
| 随机交易者 | RandomTrader | 随机选择池和方向交易 |
| 套利者 | Arbitrageur | 发现跨池价差并套利 |
| 趋势跟随者 | TrendFollower | 移动均线趋势跟踪 |
| 流动性提供者 | LiquidityProvider | 按比例存入/取出流动性 |
| 鲸鱼 | WhaleAgent | 周期性大额交易 |

---

## 场景配置

系统内置 default / flash_crash / arbitrage 三种场景，也可通过 JSON 自定义：

```json
{
  "name": "my_scenario",
  "random_seed": 42,
  "max_steps": 100,
  "pools": [
    {"token_a": "ETH", "token_b": "USDC", "fee_rate": "0.003",
     "initial_reserve_a": "100", "initial_reserve_b": "200000"}
  ],
  "users": [
    {"user_id": "trader1", "balances": {"ETH": "50", "USDC": "100000"}}
  ],
  "agents": [
    {"type": "random", "user_id": "trader1", "params": {"swap_probability": 0.3}}
  ]
}
```

---

## 技术栈

| 层次 | 技术 |
|------|------|
| 语言 | Python 3.10+ |
| 数值 | `decimal.Decimal`（28 位精度） |
| 数据模型 | Pydantic v2 |
| 数据分析 | Pandas |
| CLI | Click + Rich |
| Web 后端 | FastAPI + Uvicorn |
| Web 前端 | Jinja2 + Bootstrap 5 + ECharts |
| 测试 | Pytest（82 项测试） |

---

**© 2026 金融软件工程实验**

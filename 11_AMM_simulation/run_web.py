"""
一键启动 AMM 仿真系统 Web 界面
- 自动启动 FastAPI 服务器
- 自动打开浏览器访问 http://localhost:8000

Usage:
    python run_web.py
"""

import sys
import os
import threading
import webbrowser
import time

# Ensure project root is on Python path
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, PROJECT_ROOT)

from frontend.app import app
import uvicorn


def open_browser():
    """Wait for server to start, then open browser."""
    time.sleep(1.5)
    webbrowser.open("http://localhost:8000")
    print("\nBrowser opened -> http://localhost:8000")
    print("   按 Ctrl+C 停止服务器\n")


if __name__ == "__main__":
    print("=" * 60)
    print("  AMM Exchange Simulation — Web 界面")
    print("  DeFi 核心逻辑仿真系统")
    print("=" * 60)
    print()
    print("  启动服务器...")
    print()

    # Open browser in background thread
    threading.Thread(target=open_browser, daemon=True).start()

    # Start uvicorn server
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8000,
        log_level="info",
    )

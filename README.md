[README.md](https://github.com/user-attachments/files/28840170/README.md)
# jrrg-homework# AMM-simulation

基于 Python 与 Flask 的 AMM 去中心化交易所仿真系统，实现恒定乘积模型与流动性机制分析

# 启动方式

## 一键启动（推荐）

双击项目根目录下的 `start.bat`。

脚本会自动进入应用目录、检查依赖并启动服务。

## 手动启动

进入项目目录：

```powershell
cd C:\Users\chenx\Desktop\AMM-simulation-main\AMM-simulation
```

安装依赖：

```powershell
python -m pip install -r requirements.txt
```

启动系统：

```powershell
python run.py
```

如果当前终端还没有刷新环境变量，可以临时使用完整路径启动：

```powershell
& "C:\Users\chenx\AppData\Local\Python\bin\python.exe" run.py
```

系统会自动打开浏览器访问 http://127.0.0.1:5000。

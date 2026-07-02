#!/bin/bash
# 股票资金流向看板启动脚本

echo "===================================="
echo "  A股资金流向看板 - 启动"
echo "===================================="

# 检查Python
echo "[1/3] 检查Python环境..."
python3 --version 2>/dev/null || { echo "错误: 需要Python3"; exit 1; }

# 安装依赖
echo "[2/3] 安装依赖..."
pip install flask flask-cors -q 2>/dev/null || pip3 install flask flask-cors -q 2>/dev/null

# 启动服务
echo "[3/3] 启动Flask服务..."
echo ""
echo "服务将在以下地址可用:"
echo "  - 本地: http://127.0.0.1:5000"
echo "  - 局域网: http://$(hostname -I | awk '{print $1}' 2>/dev/null || echo '0.0.0.0'):5000"
echo ""
echo "按 Ctrl+C 停止服务"
echo "===================================="

python3 app.py

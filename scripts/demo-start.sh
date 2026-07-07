#!/usr/bin/env bash
# i-home.life 一键启动演示环境
# 启动后端服务器 + 打开浏览器

set -e

PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
DATA_DIR="$PROJECT_DIR/data"
VENV_DIR="$PROJECT_DIR/.venv"
PORT="${PORT:-8000}"

cd "$PROJECT_DIR"

echo "╔══════════════════════════════════════════╗"
echo "║  i-home.life  演示环境启动               ║"
echo "╠══════════════════════════════════════════╣"

# 初始化数据库和种子数据
echo "  📦 初始化数据库 + 种子数据..."
source "$VENV_DIR/bin/activate"
PYTHONPATH=. python scripts/seed.py 2>&1 | grep -v "INFO\|PRAGMA\|CREATE\|SELECT\|INSERT\|COMMIT\|FROM\|RETURNING\|BEGIN\|index\|FOREIGN\|UNIQUE\|PRIMARY\|idx\|ix\|ON\|TABLE\|user\|material\|supplier\|WHERE\|password\|avatar\|hashed\|id," | head -3

# 启动服务器
echo "  🚀 启动 FastAPI 服务器..."
nohup python -m uvicorn app.main:app --host 0.0.0.0 --port "$PORT" --reload > "$DATA_DIR/demo-server.log" 2>&1 &
SERVER_PID=$!
echo "  🔢 PID: $SERVER_PID"
echo $SERVER_PID > "$DATA_DIR/demo-server.pid"

# 等待服务器就绪
echo -n "  ⏳ 等待服务器就绪"
for i in $(seq 1 20); do
  if curl -sf "http://localhost:$PORT/health" > /dev/null 2>&1; then
    echo " ✅"
    break
  fi
  echo -n "."
  sleep 1
done

echo ""
echo "  演示环境已就绪!"
echo ""
echo "  📊 管理后台:   http://localhost:$PORT/docs"
echo "  🎨 设计台:     open $PROJECT_DIR/web/studio.html"
echo "  🖥  管理界面:   open $PROJECT_DIR/web/index.html"
echo "  🏠 3D 效果图:  open $PROJECT_DIR/web/3d-viewer.html"
echo ""
echo "  演示账号: 13800138000 / 123456"
echo ""
echo "  停止服务器: kill \$(cat $DATA_DIR/demo-server.pid)"
echo "  查看日志:   tail -f $DATA_DIR/demo-server.log"
echo ""
echo "╚══════════════════════════════════════════╝"

# 运行验证
echo ""
echo "  🧪 运行自动验证..."
bash "$PROJECT_DIR/scripts/verify-ac.sh" 2>&1 | grep -E "结果|通过率|🎉|⚠" | head -5

echo ""
echo "  ✅ 演示环境验证完成"

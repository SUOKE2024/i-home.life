#!/usr/bin/env bash
# i-home.life 一键部署脚本
# 用法: bash scripts/deploy.sh [start|stop|restart|status]

set -e

PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
VENV_DIR="$PROJECT_DIR/.venv"
DATA_DIR="$PROJECT_DIR/data"
PID_FILE="$DATA_DIR/server.pid"
LOG_FILE="$DATA_DIR/server.log"
HOST="${HOST:-0.0.0.0}"
PORT="${PORT:-8081}"
WORKERS="${WORKERS:-2}"

mkdir -p "$DATA_DIR"

cmd="${1:-start}"

case "$cmd" in
  start)
    if [ -f "$PID_FILE" ] && kill -0 "$(cat "$PID_FILE")" 2>/dev/null; then
      echo "⚠️  服务已在运行 (PID: $(cat "$PID_FILE"))"
      echo "   访问: http://localhost:$PORT"
      echo "   文档: http://localhost:$PORT/docs"
      exit 0
    fi

    echo "🚀 启动 i-home.life 服务..."
    echo "   项目目录: $PROJECT_DIR"
    echo "   端口: $PORT"

    cd "$PROJECT_DIR"
    source "$VENV_DIR/bin/activate"

    # Init DB (auto-seeds if empty)
    PYTHONPATH=. python -c "import asyncio; from app.database import init_db; asyncio.run(init_db())" 2>/dev/null

    nohup python -m uvicorn app.main:app \
      --host "$HOST" \
      --port "$PORT" \
      --workers "$WORKERS" \
      --log-level info \
      > "$LOG_FILE" 2>&1 &

    echo $! > "$PID_FILE"
    sleep 2

    if kill -0 "$(cat "$PID_FILE")" 2>/dev/null; then
      echo "✅ 服务启动成功!"
      echo "   访问: http://localhost:$PORT"
      echo "   文档: http://localhost:$PORT/docs"
      echo "   日志: tail -f $LOG_FILE"
      echo "   停止: bash scripts/deploy.sh stop"
    else
      echo "❌ 启动失败，查看日志: $LOG_FILE"
      exit 1
    fi
    ;;

  stop)
    if [ -f "$PID_FILE" ]; then
      PID=$(cat "$PID_FILE")
      if kill -0 "$PID" 2>/dev/null; then
        echo "🛑 停止服务 (PID: $PID)..."
        kill "$PID"
        rm -f "$PID_FILE"
        echo "✅ 已停止"
      else
        rm -f "$PID_FILE"
        echo "⚠️  PID 文件存在但进程已不存在，已清理"
      fi
    else
      echo "⚠️  服务未运行"
    fi
    ;;

  restart)
    bash "$0" stop
    sleep 1
    bash "$0" start
    ;;

  status)
    if [ -f "$PID_FILE" ] && kill -0 "$(cat "$PID_FILE")" 2>/dev/null; then
      echo "✅ 运行中 (PID: $(cat "$PID_FILE"))"
      echo "   端口: $PORT"
      curl -sf http://localhost:$PORT/health > /dev/null && echo "   API: 正常" || echo "   API: 异常"
    else
      echo "❌ 未运行"
    fi
    ;;

  logs)
    if [ -f "$LOG_FILE" ]; then
      tail -f "$LOG_FILE"
    else
      echo "日志文件不存在: $LOG_FILE"
    fi
    ;;

  *)
    echo "用法: bash scripts/deploy.sh {start|stop|restart|status|logs}"
    echo ""
    echo "  start   - 启动服务"
    echo "  stop    - 停止服务"
    echo "  restart - 重启服务"
    echo "  status  - 查看状态"
    echo "  logs    - 查看日志"
    echo ""
    echo "环境变量:"
    echo "  HOST     - 绑定地址 (默认 0.0.0.0)"
    echo "  PORT     - 端口 (默认 8000)"
    echo "  WORKERS  - 工作进程数 (默认 2)"
    ;;
esac

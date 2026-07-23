#!/usr/bin/env bash
# i-home.life 一键部署脚本
# 用法: bash scripts/deploy.sh [start|stop|restart|status|logs|deploy|rollback [backup_ts]]
#
# [v1.2.1] P0-4 修复：部署前 DB 备份 + 回滚脚本
#   违规项：原部署流程无 DB 备份步骤，直接违反项目硬约束
#           "所有生产改动必须配套回滚方案，先验证回滚脚本再上线"。
#   修复内容：
#     1. start / deploy 前自动 pg_dump 备份生产 PostgreSQL
#        （DATABASE_URL 从 .env.production 读取）
#     2. 备份路径：$BACKUP_DIR/db_backup_YYYYMMDD_HHMMSS.sql.gz
#        （默认 /opt/ihome/backups，可经 BACKUP_DIR 环境变量覆盖）
#     3. 备份失败立即中止部署（set -e）；保留最近 10 个备份，自动清理更老备份
#     4. 新增 rollback [backup_ts] 子命令：
#        恢复指定备份 + 回滚代码到备份时版本 + 重启服务
#     5. 不使用 Docker：直接调用 pg_dump/psql（假设生产服务器已装 postgresql-client）

set -e

PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
VENV_DIR="$PROJECT_DIR/.venv"
DATA_DIR="$PROJECT_DIR/data"
PID_FILE="$DATA_DIR/server.pid"
LOG_FILE="$DATA_DIR/server.log"
HOST="${HOST:-0.0.0.0}"
PORT="${PORT:-8081}"
WORKERS="${WORKERS:-2}"

# [v1.2.1 P0-4] 备份相关配置
BACKUP_DIR="${BACKUP_DIR:-/opt/ihome/backups}"
ENV_PRODUCTION="$PROJECT_DIR/.env.production"
BACKUP_KEEP_COUNT="${BACKUP_KEEP_COUNT:-10}"

mkdir -p "$DATA_DIR"

# ----------------------------------------------------------------------------
# [v1.2.1 P0-4] 从 .env.production 加载 DATABASE_URL，并转换为 libpq 连接串
#   - asyncpg 驱动 URL (postgresql+asyncpg://) 需剥离 "+asyncpg" 才能被
#     pg_dump / psql (libpq) 识别
#   - SQLite / 未配置 / 无 .env.production 视为非生产环境，跳过备份（返回 1）
#   - 成功时通过 stdout 之外的方式设置全局 PG_URL，返回 0
# ----------------------------------------------------------------------------
load_db_url() {
  local raw_url
  if [ ! -f "$ENV_PRODUCTION" ]; then
    echo "ℹ️  未找到 .env.production，跳过 DB 备份（非生产环境）"
    return 1
  fi
  raw_url=$(grep -E "^DATABASE_URL=" "$ENV_PRODUCTION" | head -1 | cut -d= -f2- | tr -d '"' | tr -d "'")
  if [ -z "$raw_url" ]; then
    echo "ℹ️  .env.production 未配置 DATABASE_URL，跳过 DB 备份"
    return 1
  fi
  case "$raw_url" in
    sqlite*)
      echo "ℹ️  检测到 SQLite，跳过 DB 备份（仅生产 PostgreSQL 环境备份）"
      return 1
      ;;
    postgresql+asyncpg://*)
      # 剥离 "+asyncpg" 驱动标记：postgresql+asyncpg://... → postgresql://...
      # 用 ${var#prefix} 前缀剥离，避免 ${var/pat/rep} 中反斜杠转义歧义
      PG_URL="postgresql://${raw_url#postgresql+asyncpg://}"
      ;;
    postgresql://*)
      PG_URL="$raw_url"
      ;;
    *)
      echo "⚠️  无法识别的 DATABASE_URL 格式，跳过 DB 备份：$raw_url"
      return 1
      ;;
  esac
  export PG_URL
  return 0
}

# ----------------------------------------------------------------------------
# [v1.2.1 P0-4] 备份生产 PostgreSQL
#   - pg_dump --clean --if-exists --no-owner：生成的 dump 含 DROP 语句，便于回滚恢复
#   - gzip 压缩；空文件视为失败
#   - 记录备份时的 git HEAD 到 .commit 附带文件，供 rollback 精确回滚代码
#   - 备份后执行 rotate_backups 保留最近 BACKUP_KEEP_COUNT 个
# ----------------------------------------------------------------------------
backup_db() {
  if ! load_db_url; then
    # 非生产环境跳过备份，不视为错误
    return 0
  fi
  if ! command -v pg_dump >/dev/null 2>&1; then
    echo "❌ 未找到 pg_dump，请先安装 postgresql-client"
    echo "   Ubuntu/Debian: sudo apt-get install -y postgresql-client"
    echo "   CentOS/RHEL:   sudo yum install -y postgresql"
    return 1
  fi
  mkdir -p "$BACKUP_DIR"
  local ts backup_file
  ts=$(date +%Y%m%d_%H%M%S)
  backup_file="$BACKUP_DIR/db_backup_${ts}.sql.gz"
  echo "📦 备份生产数据库 → $backup_file"
  # pg_dump 失败（返回非 0）或管道下游 gzip 失败均触发 return 1
  if ! pg_dump --clean --if-exists --no-owner "$PG_URL" 2>/tmp/pgdump_$$.err | gzip > "$backup_file"; then
    rm -f "$backup_file"
    echo "❌ DB 备份失败，中止部署（set -e）："
    tail -20 /tmp/pgdump_$$.err 2>/dev/null
    rm -f /tmp/pgdump_$$.err
    return 1
  fi
  rm -f /tmp/pgdump_$$.err
  if [ ! -s "$backup_file" ]; then
    echo "❌ DB 备份文件为空，中止部署"
    rm -f "$backup_file"
    return 1
  fi
  # 记录备份时的 git HEAD，供 rollback 精确回滚代码版本
  if command -v git >/dev/null 2>&1 && git -C "$PROJECT_DIR" rev-parse HEAD >/dev/null 2>&1; then
    git -C "$PROJECT_DIR" rev-parse HEAD > "$backup_file.commit"
  fi
  rotate_backups
  echo "✅ 备份完成 ($(du -h "$backup_file" | cut -f1))"
  return 0
}

# ----------------------------------------------------------------------------
# [v1.2.1 P0-4] 保留最近 BACKUP_KEEP_COUNT 个备份，清理更老的（含 .commit 附带文件）
# ----------------------------------------------------------------------------
rotate_backups() {
  local count
  count=$(ls -1 "$BACKUP_DIR"/db_backup_*.sql.gz 2>/dev/null | wc -l | tr -d ' ')
  if [ "$count" -le "$BACKUP_KEEP_COUNT" ]; then
    return 0
  fi
  echo "🧹 清理旧备份（保留最近 $BACKUP_KEEP_COUNT 个）..."
  # 按修改时间倒序，跳过前 BACKUP_KEEP_COUNT 个，删除其余
  ls -1t "$BACKUP_DIR"/db_backup_*.sql.gz 2>/dev/null \
    | tail -n +$((BACKUP_KEEP_COUNT + 1)) \
    | while IFS= read -r old; do
        rm -f "$old" "${old}.commit"
        echo "   已删除: $(basename "$old")"
      done
}

# ----------------------------------------------------------------------------
# [v1.2.1 P0-4] 从备份恢复 PostgreSQL
#   入参：$1 = 备份文件路径（.sql.gz）
# ----------------------------------------------------------------------------
restore_db() {
  local backup_file="$1"
  if [ -z "$backup_file" ] || [ ! -f "$backup_file" ]; then
    echo "❌ 备份文件不存在：$backup_file"
    return 1
  fi
  if ! load_db_url; then
    echo "❌ 无法加载生产 DATABASE_URL，回滚中止"
    return 1
  fi
  if ! command -v psql >/dev/null 2>&1; then
    echo "❌ 未找到 psql，请先安装 postgresql-client"
    return 1
  fi
  echo "♻️  从备份恢复数据库：$backup_file"
  local restore_log="/tmp/restore_$$.log"
  # dump 由 pg_dump --clean 生成，含 DROP ... IF EXISTS，可直接覆写恢复
  if ! gunzip -c "$backup_file" | psql "$PG_URL" -v ON_ERROR_STOP=1 > "$restore_log" 2>&1; then
    echo "❌ 数据库恢复失败："
    tail -30 "$restore_log"
    rm -f "$restore_log"
    return 1
  fi
  rm -f "$restore_log"
  echo "✅ 数据库恢复完成"
  return 0
}

cmd="${1:-start}"

case "$cmd" in
  start)
    if [ -f "$PID_FILE" ] && kill -0 "$(cat "$PID_FILE")" 2>/dev/null; then
      echo "⚠️  服务已在运行 (PID: $(cat "$PID_FILE"))"
      echo "   访问: http://localhost:$PORT"
      echo "   文档: http://localhost:$PORT/docs"
      exit 0
    fi

    # [v1.2.1 P0-4] 部署前 DB 备份（应用迁移/启动服务前）
    # SKIP_BACKUP=1 时跳过（供 deploy 子命令已完成备份后调用 start 时使用）
    if [ "${SKIP_BACKUP:-0}" != "1" ]; then
      backup_db || { echo "❌ 部署中止：DB 备份失败"; exit 1; }
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

  # [v1.2.1 P0-4] 标准生产部署流程：备份 → 迁移 → 重启
  deploy)
    echo "🚀 开始生产部署流程..."
    cd "$PROJECT_DIR"
    # 1. 部署前 DB 备份（硬约束：所有生产改动必须配套回滚方案）
    backup_db || { echo "❌ 部署中止：DB 备份失败"; exit 1; }
    # 2. 应用数据库迁移（alembic 优先，回退到 init_db）
    source "$VENV_DIR/bin/activate"
    if command -v alembic >/dev/null 2>&1; then
      echo "⬆️  应用 Alembic 迁移 (alembic upgrade head)..."
      alembic upgrade head || { echo "❌ 迁移失败，请执行: bash scripts/deploy.sh rollback"; exit 1; }
    else
      echo "ℹ️  alembic 未安装，回退到 init_db..."
      PYTHONPATH=. python -c "import asyncio; from app.database import init_db; asyncio.run(init_db())"
    fi
    # 3. 重启服务（SKIP_BACKUP=1 避免重复备份）
    export SKIP_BACKUP=1
    bash "$0" restart
    echo "✅ 部署完成"
    echo "   如需回滚: bash scripts/deploy.sh rollback"
    ;;

  # [v1.2.1 P0-4] 回滚：恢复 DB + 回滚代码 + 重启
  # 用法: bash scripts/deploy.sh rollback [backup_ts]
  #   backup_ts 为备份时间戳（YYYYMMDD_HHMMSS）；省略则使用最新备份
  rollback)
    backup_ts="${2:-}"
    if [ -n "$backup_ts" ]; then
      backup_file="$BACKUP_DIR/db_backup_${backup_ts}.sql.gz"
    else
      backup_file=$(ls -1t "$BACKUP_DIR"/db_backup_*.sql.gz 2>/dev/null | head -1)
      if [ -z "$backup_file" ]; then
        echo "❌ 未找到任何备份文件于 $BACKUP_DIR"
        echo "   可用备份："
        ls -1t "$BACKUP_DIR"/db_backup_*.sql.gz 2>/dev/null || echo "   （无）"
        exit 1
      fi
      echo "ℹ️  未指定 backup_ts，使用最新备份: $(basename "$backup_file")"
    fi

    echo "⚠️  即将执行回滚操作："
    echo "   备份文件: $backup_file"
    echo "   此操作将【覆盖当前数据库】并【回退代码版本】！"
    read -r -p "确认回滚? [y/N] " confirm
    if [ "$confirm" != "y" ] && [ "$confirm" != "Y" ]; then
      echo "已取消回滚"
      exit 0
    fi

    # 1. 停止服务
    bash "$0" stop || true

    # 2. 恢复数据库
    restore_db "$backup_file" || { echo "❌ 回滚失败：DB 恢复出错"; exit 1; }

    # 3. 回滚代码到备份时版本（优先使用 .commit 记录，回退到 HEAD~1）
    commit_file="${backup_file}.commit"
    if [ -f "$commit_file" ]; then
      target_commit=$(cat "$commit_file")
      echo "⏪ 回滚代码到备份时版本: $target_commit"
      git -C "$PROJECT_DIR" checkout "$target_commit" || { echo "❌ git checkout 失败，请手动处理"; exit 1; }
    else
      echo "⏪ 未找到备份时 commit 记录，回滚到上一版本 (HEAD~1)"
      git -C "$PROJECT_DIR" checkout HEAD~1 || { echo "❌ git checkout HEAD~1 失败，请手动处理"; exit 1; }
    fi

    # 4. 重启服务（跳过备份，避免覆盖刚恢复的备份基线）
    SKIP_BACKUP=1 bash "$0" start
    echo "✅ 回滚完成"
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

  # [v1.2.1 P0-4] 列出可用备份，便于选择 rollback 目标
  backups)
    echo "可用备份（$BACKUP_DIR，按时间倒序）："
    if [ ! -d "$BACKUP_DIR" ]; then
      echo "   备份目录不存在: $BACKUP_DIR"
      exit 0
    fi
    ls -1t "$BACKUP_DIR"/db_backup_*.sql.gz 2>/dev/null | while IFS= read -r f; do
      ts=$(basename "$f" | sed 's/^db_backup_//; s/\.sql\.gz$//')
      size=$(du -h "$f" | cut -f1)
      commit=""
      if [ -f "${f}.commit" ]; then
        commit=" commit=$(cut -c1-8 "${f}.commit")"
      fi
      echo "   $ts  ($size)$commit"
    done
    ;;

  *)
    echo "用法: bash scripts/deploy.sh {start|stop|restart|status|logs|deploy|rollback [backup_ts]|backups}"
    echo ""
    echo "  start              - 启动服务（生产环境会先自动备份 DB）"
    echo "  stop               - 停止服务"
    echo "  restart            - 重启服务（生产环境会先自动备份 DB）"
    echo "  deploy             - 生产部署：备份 DB → 迁移 → 重启"
    echo "  rollback [ts]      - 回滚：恢复 DB + 回退代码 + 重启（ts=YYYYMMDD_HHMMSS）"
    echo "  backups            - 列出可用备份"
    echo "  status             - 查看状态"
    echo "  logs               - 查看日志"
    echo ""
    echo "环境变量:"
    echo "  HOST               - 绑定地址 (默认 0.0.0.0)"
    echo "  PORT               - 端口 (默认 8081)"
    echo "  WORKERS            - 工作进程数 (默认 2)"
    echo "  BACKUP_DIR         - 备份目录 (默认 /opt/ihome/backups)"
    echo "  BACKUP_KEEP_COUNT  - 保留备份数 (默认 10)"
    echo "  SKIP_BACKUP=1      - 跳过 start 前的 DB 备份（内部使用）"
    ;;
esac

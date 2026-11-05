#!/usr/bin/env bash
# i-home.life SSH 推送式部署（push deploy）
#
# 用法：
#   bash scripts/deploy-push.sh                 # 正式推送（含代码快照 + DB 备份 + 健康校验 + 失败自动回滚）
#   bash scripts/deploy-push.sh --dry-run       # 演练：只打印将要做什么，不改远端
#   bash scripts/deploy-push.sh --migrate       # 额外执行 alembic upgrade head（默认不迁移）
#   bash scripts/deploy-push.sh --rollback 20261105_153000   # 回滚到指定快照
#
# 设计红线（2026-11-05 按生产实测修正）：
#   1. 绝不推送 .env / .env.production —— 生产用的是 /opt/ihome/.env，本地那份含 CHANGE_ME 占位。
#   2. 远端非 git 仓库，没有版本可退 → 推前必须做「代码 tar 快照 + pg_dump」双备份。
#   3. 健康校验不过 → 自动回滚代码并重启，并保留 DB 备份供人工决定是否恢复数据。
#   4. 不 --delete：远端独有文件（.env、data、日志）不做删除，避免误伤。

set -uo pipefail

# ---------- 可覆盖配置 ----------
HOST="${IHOME_HOST:-root@118.31.223.213}"
REMOTE_DIR="${IHOME_DIR:-/opt/ihome}"
SERVICE="${IHOME_SERVICE:-ihome}"
SSH_OPTS=(-o BatchMode=yes -o ConnectTimeout=10 -o ServerAliveInterval=15)
TS="$(date +%Y%m%d_%H%M%S)"
BACKUP_DIR="$REMOTE_DIR/backups"
LOCAL_DIR="$(cd "$(dirname "$0")/.." && pwd)"
KEEP_BACKUPS="${KEEP_BACKUPS:-10}"

# ---------- 同步范围 ----------
# 注意：webapp/dist 默认不推（远端 10-30 已有一份可用构建；推本地新构建等于同时改线上前端，
#      需显式 --with-web 才纳入，避免"发个后端修复顺手换了整个前端"）
PUSH_ITEMS=(app scripts alembic alembic.ini requirements.txt)
EXCLUDES=(
  --exclude='.env' --exclude='.env.*' --exclude='*.env'
  --exclude='.venv' --exclude='venv' --exclude='node_modules'
  --exclude='.git' --exclude='__pycache__' --exclude='*.pyc'
  --exclude='.pytest_cache' --exclude='.mypy_cache' --exclude='.ruff_cache'
  --exclude='data' --exclude='*.log' --exclude='*.sqlite3' --exclude='*.db'
  --exclude='private.*.key' --exclude='*.pem'
)

DRY_RUN=0; DO_MIGRATE=0; ROLLBACK_TS=""; WITH_WEB=0
while [[ $# -gt 0 ]]; do
  case "$1" in
    --dry-run) DRY_RUN=1; shift ;;
    --migrate) DO_MIGRATE=1; shift ;;
    --with-web) WITH_WEB=1; shift ;;
    --rollback) ROLLBACK_TS="${2:-}"; shift 2 ;;
    --host) HOST="$2"; shift 2 ;;
    -h|--help) sed -n '2,20p' "$0"; exit 0 ;;
    *) echo "未知参数: $1"; exit 2 ;;
  esac
done

# webapp/dist 仅在显式 --with-web 时纳入
if (( WITH_WEB )); then PUSH_ITEMS+=(webapp/dist); fi

say()  { printf '%s\n' "$*"; }
step() { printf '\n\033[1;36m== %s ==\033[0m\n' "$*"; }
ok()   { printf '  \033[32m✓\033[0m %s\n' "$*"; }
warn() { printf '  \033[33m!\033[0m %s\n' "$*"; }
die()  { printf '  \033[31m✗ %s\033[0m\n' "$*"; exit 1; }

rsh() { ssh "${SSH_OPTS[@]}" "$HOST" "$@"; }

# ============================================================
# 回滚模式
# ============================================================
if [[ -n "$ROLLBACK_TS" ]]; then
  step "回滚到快照 $ROLLBACK_TS"
  rsh "test -f '$BACKUP_DIR/code_$ROLLBACK_TS.tar.gz'" || die "快照不存在：$BACKUP_DIR/code_$ROLLBACK_TS.tar.gz"
  rsh "cd '$REMOTE_DIR' && tar xzf '$BACKUP_DIR/code_$ROLLBACK_TS.tar.gz' && systemctl restart '$SERVICE'" \
    || die "回滚执行失败"
  sleep 4
  code=$(rsh "curl -s -o /dev/null -w '%{http_code}' --max-time 6 http://127.0.0.1:8001/health" || echo 000)
  [[ "$code" == "200" ]] && ok "回滚完成，/health 200" || die "回滚后 /health=$code，需人工介入"
  say ""
  say "如需同时回滚数据库（危险，会覆盖当前数据）："
  say "  ssh $HOST \"cd $REMOTE_DIR && psql \\\$DATABASE_URL -f <(gunzip -c $BACKUP_DIR/db_$ROLLBACK_TS.sql.gz)\""
  exit 0
fi

# ============================================================
# 1. 本地预检
# ============================================================
step "1/7 本地预检"
cd "$LOCAL_DIR" || die "进不了仓库目录 $LOCAL_DIR"

if [[ -d .git ]]; then
  DIRTY=$(git status --porcelain | wc -l | tr -d ' ')
  HEAD_SHA=$(git rev-parse --short HEAD)
  say "  HEAD：$HEAD_SHA"
  if [[ "$DIRTY" != "0" ]]; then
    warn "工作树有 $DIRTY 条未提交改动（推送的是工作树内容，不是 HEAD）"
  else
    ok "工作树干净"
  fi
fi

for item in "${PUSH_ITEMS[@]}"; do
  [[ -e "$item" ]] || die "缺少待发布内容：$item"
done
ok "待发布内容齐全（${PUSH_ITEMS[*]}）"

[[ -e .env ]] && warn "本地存在 .env，已被排除，不会推送（生产用自己的 $REMOTE_DIR/.env）"

# ============================================================
# 2. 远端预检
# ============================================================
step "2/7 远端预检"
rsh "true" >/dev/null 2>&1 || die "SSH 连不上 $HOST"
ok "SSH 可达 $HOST"

rsh "test -d '$REMOTE_DIR'" || die "远端目录不存在：$REMOTE_DIR"
rsh "systemctl cat '$SERVICE' >/dev/null 2>&1" || die "远端没有 systemd 单元：$SERVICE"
ok "目录与 systemd 单元存在"

SVC_STATE=$(rsh "systemctl is-active '$SERVICE' 2>/dev/null || true")
say "  当前服务状态：$SVC_STATE"

FREE_G=$(rsh "df -Pk '$REMOTE_DIR' | awk 'NR==2{printf \"%d\", \$4/1024/1024}'")
say "  /opt 可用空间：${FREE_G}G"
(( FREE_G >= 2 )) || die "磁盘可用不足 2G，中止（避免备份写不下）"
ok "磁盘空间充足"

OWNER=$(rsh "stat -c '%u:%g' '$REMOTE_DIR'")
say "  远端属主：$OWNER"
rsh "command -v pg_dump >/dev/null" || warn "远端无 pg_dump，DB 备份将跳过"
rsh "test -f '$REMOTE_DIR/.env'" && ok "远端 .env 存在（部署不会改动它）" || warn "远端无 .env，服务可能依赖环境变量"

if (( DRY_RUN )); then
  step "DRY-RUN：以下是将会执行的动作，不做任何修改"
  say "  rsync ${PUSH_ITEMS[*]} → $HOST:$REMOTE_DIR/"
  say "  远端备份 → $BACKUP_DIR/code_$TS.tar.gz + db_$TS.sql.gz"
  say "  pip install -r requirements.txt（仅当 requirements 变化）"
  say "  alembic upgrade head：$([[ $DO_MIGRATE == 1 ]] && echo 是 || echo '否（未加 --migrate）')"
  say "  systemctl restart $SERVICE"
  say "  健康校验 http://127.0.0.1:8001/health 与 8081/health"
  say ""
  say "  实际 rsync 影响面："
  rsync -az --dry-run --itemize-changes "${EXCLUDES[@]}" "${PUSH_ITEMS[@]}" "$HOST:$REMOTE_DIR/" 2>&1 | head -40
  say "  ...（以上为影响面摘要）"
  exit 0
fi

# ============================================================
# 3. 远端备份（代码快照 + DB dump）
# ============================================================
step "3/7 远端备份"
rsh "mkdir -p '$BACKUP_DIR' && chmod 700 '$BACKUP_DIR'"

rsh "cd '$REMOTE_DIR' && tar czf '$BACKUP_DIR/code_$TS.tar.gz' \
  --exclude='.venv' --exclude='node_modules' --exclude='.git' --exclude='__pycache__' \
  --exclude='data' --exclude='backups' --exclude='.env' --exclude='.env.*' \
  app scripts alembic alembic.ini requirements.txt webapp/dist 2>/dev/null" \
  && ok "代码快照 → $BACKUP_DIR/code_$TS.tar.gz ($(rsh "du -h '$BACKUP_DIR/code_$TS.tar.gz' | cut -f1"))" \
  || die "代码快照失败，中止部署"

if rsh "command -v pg_dump >/dev/null"; then
  # 坑（2026-11-05 实测踩到）：生产 DATABASE_URL 用 SQLAlchemy 方言 postgresql+asyncpg://，
  # pg_dump 不认该方言会静默产出空文件。必须先剥掉 +driver，再校验产物非空才算备份成功。
  rsh "cd '$REMOTE_DIR' && set -a && . ./.env && set +a && \
       PGURL=\$(printf '%s' \"\$DATABASE_URL\" | sed -E 's#^(postgresql|postgres)\+[a-zA-Z0-9_]+://#\1://#') && \
       pg_dump --no-owner --no-privileges \"\$PGURL\" | gzip > '$BACKUP_DIR/db_$TS.sql.gz'"
  DUMP_BYTES=$(rsh "stat -c %s '$BACKUP_DIR/db_$TS.sql.gz' 2>/dev/null || echo 0")
  DUMP_RAW=$(rsh "gunzip -c '$BACKUP_DIR/db_$TS.sql.gz' 2>/dev/null | wc -c" || echo 0)
  if (( DUMP_RAW < 1024 )); then
    rsh "rm -f '$BACKUP_DIR/db_$TS.sql.gz'"
    die "DB 备份产物为空（原始 $DUMP_RAW 字节），中止部署——红线：无有效备份不发布"
  fi
  ok "DB 备份 → $BACKUP_DIR/db_$TS.sql.gz（压缩 ${DUMP_BYTES}B / 解压 ${DUMP_RAW}B，已校验非空）"
else
  warn "跳过 DB 备份（远端无 pg_dump）"
fi

# 只保留最近 N 份
rsh "ls -1t '$BACKUP_DIR'/code_*.tar.gz 2>/dev/null | tail -n +$((KEEP_BACKUPS+1)) | xargs -r rm -f; \
     ls -1t '$BACKUP_DIR'/db_*.sql.gz 2>/dev/null | tail -n +$((KEEP_BACKUPS+1)) | xargs -r rm -f"

# ============================================================
# 4. 推送代码
# ============================================================
step "4/7 推送代码（rsync，排除 .env / .venv / data）"
REQ_BEFORE=$(rsh "md5sum '$REMOTE_DIR/requirements.txt' 2>/dev/null | cut -d' ' -f1" || echo none)

rsync -az --human-readable --stats "${EXCLUDES[@]}" "${PUSH_ITEMS[@]}" "$HOST:$REMOTE_DIR/" \
  | grep -E "Number of files transferred|Total transferred file size|sent .* bytes" | sed 's/^/  /'
[[ ${PIPESTATUS[0]} -eq 0 ]] || die "rsync 推送失败"
ok "代码已推送"

rsh "chown -R '$OWNER' '$REMOTE_DIR'/app '$REMOTE_DIR'/scripts '$REMOTE_DIR'/alembic '$REMOTE_DIR'/alembic.ini '$REMOTE_DIR'/requirements.txt '$REMOTE_DIR'/webapp/dist 2>/dev/null || true"
ok "属主已校正为 $OWNER"

# ============================================================
# 5. 依赖与迁移
# ============================================================
step "5/7 依赖与数据库迁移"
REQ_AFTER=$(rsh "md5sum '$REMOTE_DIR/requirements.txt' | cut -d' ' -f1")
if [[ "$REQ_BEFORE" != "$REQ_AFTER" ]]; then
  say "  requirements 有变化，安装依赖..."
  rsh "cd '$REMOTE_DIR' && ./.venv/bin/pip install -q -r requirements.txt 2>&1 | tail -3" \
    && ok "依赖安装完成" || die "依赖安装失败（代码已推送，可 rollback $TS）"
else
  ok "requirements 无变化，跳过依赖安装"
fi

if (( DO_MIGRATE )); then
  say "  执行 alembic upgrade head ..."
  rsh "cd '$REMOTE_DIR' && set -a && . ./.env && set +a && ./.venv/bin/alembic upgrade head 2>&1 | tail -5" \
    && ok "迁移完成" || die "迁移失败（DB 备份在 $BACKUP_DIR/db_$TS.sql.gz）"
else
  warn "未加 --migrate，跳过数据库迁移"
fi

# ============================================================
# 6. 重启 + 健康校验（失败自动回滚）
# ============================================================
step "6/7 重启服务并校验健康"
rsh "systemctl restart '$SERVICE'" || die "重启失败"
say "  等待服务就绪..."

HEALTH_OK=0
for i in $(seq 1 20); do
  sleep 1
  c1=$(rsh "curl -s -o /dev/null -w '%{http_code}' --max-time 4 http://127.0.0.1:8001/health" 2>/dev/null || echo 000)
  c2=$(rsh "curl -s -o /dev/null -w '%{http_code}' --max-time 4 http://127.0.0.1:8081/health" 2>/dev/null || echo 000)
  printf '  [%02d] 8001=%s 8081=%s\n' "$i" "$c1" "$c2"
  if [[ "$c1" == "200" && "$c2" == "200" ]]; then HEALTH_OK=1; break; fi
done

if (( HEALTH_OK == 1 )); then
  ok "健康校验通过（8001/8081 均 200）"
else
  warn "健康校验失败，自动回滚到 $TS ..."
  rsh "cd '$REMOTE_DIR' && tar xzf '$BACKUP_DIR/code_$TS.tar.gz' && systemctl restart '$SERVICE'"
  sleep 5
  c1=$(rsh "curl -s -o /dev/null -w '%{http_code}' --max-time 6 http://127.0.0.1:8001/health" || echo 000)
  echo ""
  die "部署失败已自动回滚。回滚后 8001/health=$c1。代码快照 code_$TS.tar.gz，DB 备份 db_$TS.sql.gz（数据未回滚）"
fi

# ============================================================
# 7. 收尾
# ============================================================
step "7/7 收尾"
rsh "systemctl is-active '$SERVICE'; journalctl -u '$SERVICE' -n 5 --no-pager 2>/dev/null | tail -5" | sed 's/^/  /'
echo ""
say "部署完成 ✅"
say "  快照：$BACKUP_DIR/code_$TS.tar.gz"
say "  DB 备份：$BACKUP_DIR/db_$TS.sql.gz"
say "  回滚：bash scripts/deploy-push.sh --rollback $TS"
say "  日志：ssh $HOST 'journalctl -u $SERVICE -f'"

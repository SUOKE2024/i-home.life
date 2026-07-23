#!/usr/bin/env bash
# 快捷 Web 部署：仅同步 web/ 目录到生产服务器
# 用法: bash scripts/quick-deploy-web.sh [remote_host] [remote_path]
#
# v1.2.1 修复：部署前自动备份服务器现有 web/，rsync --delete 不再破坏性删除
# 回滚: bash scripts/quick-deploy-web.sh rollback [remote_host] [remote_path] [backup_ts]

set -e

REMOTE_HOST="${1:-root@118.31.223.213}"
REMOTE_PATH="${2:-/opt/ihome/web}"
LOCAL_WEB="$(cd "$(dirname "$0")/../web" && pwd)"
TIMESTAMP="$(date +%Y%m%d_%H%M%S)"
BACKUP_DIR="${REMOTE_PATH}.backup_${TIMESTAMP}"

# ── 回滚子命令 ──
if [[ "${1:-}" == "rollback" ]]; then
  ROLLBACK_HOST="${2:-root@118.31.223.213}"
  ROLLBACK_PATH="${3:-/opt/ihome/web}"
  ROLLBACK_TS="${4:-}"
  if [[ -z "$ROLLBACK_TS" ]]; then
    echo "用法: bash scripts/quick-deploy-web.sh rollback <remote_host> <remote_path> <backup_ts>"
    echo "可用的备份:"
    ssh "$ROLLBACK_HOST" "ls -dt ${ROLLBACK_PATH}.backup_* 2>/dev/null | head -5"
    exit 1
  fi
  echo "⏪ 回滚: 从 ${ROLLBACK_PATH}.backup_${ROLLBACK_TS} 恢复到 ${ROLLBACK_PATH}"
  ssh "$ROLLBACK_HOST" "rm -rf ${ROLLBACK_PATH}.rollback_tmp && cp -a ${ROLLBACK_PATH}.backup_${ROLLBACK_TS} ${ROLLBACK_PATH}.rollback_tmp && rm -rf ${ROLLBACK_PATH} && mv ${ROLLBACK_PATH}.rollback_tmp ${ROLLBACK_PATH}"
  ssh "$ROLLBACK_HOST" "nginx -t && nginx -s reload" || echo "⚠️ Nginx 重载失败，请手动检查"
  echo "✅ 回滚完成: ${ROLLBACK_PATH} 已恢复到 backup_${ROLLBACK_TS}"
  exit 0
fi

# ── 前置校验：本地 web/index.html 必须存在 ──
if [[ ! -f "$LOCAL_WEB/index.html" ]]; then
  echo "❌ 本地 $LOCAL_WEB/index.html 不存在，拒绝部署（避免空目录覆盖生产）"
  exit 1
fi

echo "📦 部署 Web 静态文件到 $REMOTE_HOST:$REMOTE_PATH ..."

# ── 步骤 1：备份服务器现有 web/（防止 --delete 误删后无法恢复）──
echo "🗂  备份服务器现有 $REMOTE_PATH → $BACKUP_DIR"
ssh "$REMOTE_HOST" "if [[ -d '$REMOTE_PATH' ]]; then cp -a '$REMOTE_PATH' '$BACKUP_DIR' && echo '备份完成: $BACKUP_DIR'; else echo '服务器无现有 web 目录，跳过备份'; fi"

# ── 步骤 2：rsync 同步（--delete 安全：已先备份）──
rsync -avz --delete \
  --exclude='.DS_Store' \
  --exclude='wallpaper/' \
  --exclude='.git/' \
  "$LOCAL_WEB/" "$REMOTE_HOST:$REMOTE_PATH/"

echo "✅ Web 部署完成（备份: $BACKUP_DIR）"
echo ""
echo "如需回滚: bash scripts/quick-deploy-web.sh rollback $REMOTE_HOST $REMOTE_PATH $TIMESTAMP"

# ── 步骤 3：可选重载 Nginx ──
read -p "是否重载 Nginx？(y/N): " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
  ssh "$REMOTE_HOST" "nginx -t && nginx -s reload"
  echo "✅ Nginx 已重载"
fi

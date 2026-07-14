#!/usr/bin/env bash
# 快捷 Web 部署：仅同步 web/ 目录到生产服务器
# 用法: bash scripts/quick-deploy-web.sh [remote_host] [remote_path]

set -e

REMOTE_HOST="${1:-root@118.31.223.213}"
REMOTE_PATH="${2:-/opt/ihome/web}"
LOCAL_WEB="$(cd "$(dirname "$0")/../web" && pwd)"

echo "📦 部署 Web 静态文件到 $REMOTE_HOST:$REMOTE_PATH ..."
rsync -avz --delete --exclude='.DS_Store' --exclude='wallpaper/' "$LOCAL_WEB/" "$REMOTE_HOST:$REMOTE_PATH/"
echo "✅ Web 部署完成"

# 可选：重载 Nginx
read -p "是否重载 Nginx？(y/N): " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
  ssh "$REMOTE_HOST" "nginx -t && nginx -s reload"
  echo "✅ Nginx 已重载"
fi

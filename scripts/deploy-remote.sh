#!/usr/bin/env bash
# 索克家居 远程部署脚本
# 用法: bash scripts/deploy-remote.sh [full|backend|web|restart|status|seed]
#
#   full    - 完整部署：后端代码 + Web 静态资源 + 重启服务 (默认)
#   backend - 仅部署后端 Python 代码 + 重启 uvicorn
#   web     - 仅同步 Web 静态资源（含 LOGO/壁纸/头像）+ 重载 Nginx
#   restart - 仅重启远程 uvicorn 服务
#   status  - 查看远程服务状态
#   seed    - 重新加载种子数据（物料库、测试用户等）

set -e

REMOTE_HOST="${REMOTE_HOST:-root@118.31.223.213}"
BACKEND_DEPLOY_DIR="/opt/i-home.life"      # 后端代码部署路径
WEB_DEPLOY_DIR="/opt/ihome/web"            # nginx 静态文件路径
PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"

GREEN='\033[0;32m'
BLUE='\033[0;34m'
NC='\033[0m'

cmd="${1:-full}"

echo -e "${BLUE}╔════════════════════════════════════════════╗"
echo -e "║  索克家居 远程部署 → ${REMOTE_HOST}  ║"
echo -e "╚════════════════════════════════════════════╝${NC}"
echo ""

case "$cmd" in
  full)
    echo -e "${GREEN}📦 [1/3] 同步后端代码 → ${BACKEND_DEPLOY_DIR}${NC}"
    rsync -avz --delete \
      --exclude='.venv' \
      --exclude='venv' \
      --exclude='.git' \
      --exclude='__pycache__' \
      --exclude='*.pyc' \
      --exclude='.DS_Store' \
      --exclude='.env' \
      --exclude='.env.*' \
      --exclude='reports' \
      --exclude='flutter_app' \
      --exclude='docs' \
      --exclude='node_modules' \
      --exclude='web' \
      --exclude='assets/guide' \
      --exclude='assets/legal' \
      --exclude='data' \
      --exclude='logs' \
      "$PROJECT_DIR/" "$REMOTE_HOST:$BACKEND_DEPLOY_DIR/"

    rsync -avz "$PROJECT_DIR/.env.production" "$REMOTE_HOST:$BACKEND_DEPLOY_DIR/.env"

    echo ""
    echo -e "${GREEN}📦 [2/3] 同步 Web 静态资源（LOGO/壁纸/头像/CSS/JS） → ${WEB_DEPLOY_DIR}${NC}"
    rsync -avz --delete \
      --exclude='.DS_Store' \
      "$PROJECT_DIR/web/" "$REMOTE_HOST:$WEB_DEPLOY_DIR/"

    echo ""
    echo -e "${GREEN}🔄 [3/3] 远程安装依赖 & 重启服务${NC}"
    ssh "$REMOTE_HOST" "bash -s" << 'REMOTE_SCRIPT'
set -e
BACKEND_DIR=/opt/i-home.life
cd "$BACKEND_DIR"

# 创建虚拟环境（如不存在）
if [ ! -d "venv" ]; then
  echo "    创建 Python 虚拟环境..."
  python3.11 -m venv venv
fi

source venv/bin/activate

# 安装/更新依赖（使用阿里云镜像加速）
echo "    安装 Python 依赖..."
MIRROR="https://mirrors.aliyun.com/pypi/simple/"
pip install -q --upgrade pip -i "$MIRROR" 2>&1 | tail -1
pip install -q -i "$MIRROR" fastapi 'uvicorn[standard]' sqlalchemy asyncpg aiosqlite 'passlib[bcrypt]' \
  'python-multipart' openpyxl httpx pydantic-settings structlog aiofiles \
  pillow requests 'python-jose[cryptography]' webauthn paseto prometheus-client pendulum 2>&1 | tail -1

# 初始化数据库（建表）
echo "    初始化数据库..."
mkdir -p data
PYTHONPATH=. python -c "
import asyncio
from app.database import init_db
asyncio.run(init_db())
" 2>&1 | tail -1

# 加载种子数据
echo "    加载种子数据..."
PYTHONPATH=. python scripts/seed.py 2>&1 | tail -2

# 更新 systemd 服务配置
cp "$BACKEND_DIR/scripts/ihome.service" /etc/systemd/system/ihome.service
systemctl daemon-reload

echo "    重启服务..."
systemctl restart ihome
sleep 2

echo ""
echo "    服务状态:"
systemctl status ihome --no-pager | head -6

# 重新加载 nginx
nginx -t && nginx -s reload && echo "    Nginx: ✅ 已重载" || echo "    Nginx: ⚠️ 跳过"
REMOTE_SCRIPT
    ;;

  backend)
    echo -e "${GREEN}🔧 仅部署后端代码 → ${BACKEND_DEPLOY_DIR}${NC}"

    rsync -avz --delete \
      --exclude='.venv' \
      --exclude='venv' \
      --exclude='.git' \
      --exclude='__pycache__' \
      --exclude='*.pyc' \
      --exclude='.DS_Store' \
      --exclude='.env' \
      --exclude='.env.*' \
      --exclude='reports' \
      --exclude='flutter_app' \
      --exclude='docs' \
      --exclude='node_modules' \
      --exclude='web' \
      --exclude='assets/guide' \
      --exclude='assets/legal' \
      --exclude='data' \
      --exclude='logs' \
      "$PROJECT_DIR/" "$REMOTE_HOST:$BACKEND_DEPLOY_DIR/"

    rsync -avz "$PROJECT_DIR/.env.production" "$REMOTE_HOST:$BACKEND_DEPLOY_DIR/.env"

    ssh "$REMOTE_HOST" "cd $BACKEND_DEPLOY_DIR && source venv/bin/activate && pip install -q fastapi uvicorn[standard] sqlalchemy asyncpg aiosqlite 'passlib[bcrypt]' 'python-multipart' openpyxl httpx pydantic-settings structlog aiofiles pillow requests 'python-jose[cryptography]' webauthn 2>&1 | tail -1 && systemctl restart ihome && echo '✅ 后端已重启'"
    ;;

  web)
    echo -e "${GREEN}🌐 仅同步 Web 静态资源 → ${WEB_DEPLOY_DIR}${NC}"

    rsync -avz --delete \
      --exclude='.DS_Store' \
      "$PROJECT_DIR/web/" "$REMOTE_HOST:$WEB_DEPLOY_DIR/"

    ssh "$REMOTE_HOST" "nginx -t && nginx -s reload && echo '✅ Nginx 已重载'"
    ;;

  restart)
    echo -e "${GREEN}🔄 重启远程服务...${NC}"
    ssh "$REMOTE_HOST" "systemctl restart ihome && sleep 1 && systemctl status ihome --no-pager | head -6"
    ;;

  status)
    echo -e "${GREEN}📊 远程服务状态${NC}"
    echo ""
    echo "--- systemd ---"
    ssh "$REMOTE_HOST" "systemctl status ihome --no-pager 2>/dev/null | head -10"
    echo ""
    echo "--- 健康检查 ---"
    curl -s http://118.31.223.213:8081/health 2>/dev/null && echo "" || echo "  ❌ 无法连接"
    echo ""
    echo "--- 资源文件 ---"
    ssh "$REMOTE_HOST" "echo '  LOGO:    ' && ls ${WEB_DEPLOY_DIR}/assets/images/icons/desktop/suoke-logo-*.png 2>/dev/null | wc -l | xargs echo '    files'; echo '  壁纸:    ' && ls ${WEB_DEPLOY_DIR}/assets/images/wallpaper/*.webp 2>/dev/null | wc -l | xargs echo '    files'; echo '  用户头像:' && ls ${WEB_DEPLOY_DIR}/assets/images/avatars/hand-drawn-profiles/*.png 2>/dev/null | wc -l | xargs echo '    files'"
    echo ""
    echo "  API 文档: http://118.31.223.213:8081/api/docs"
    echo "  站点首页: http://118.31.223.213:8081/"
    ;;

  seed)
    echo -e "${GREEN}🌱 重新加载种子数据...${NC}"
    ssh "$REMOTE_HOST" "cd $BACKEND_DEPLOY_DIR && source venv/bin/activate && PYTHONPATH=. python scripts/seed.py 2>&1 | tail -5"
    ;;

  *)
    echo "用法: bash scripts/deploy-remote.sh {full|backend|web|restart|status|seed}"
    echo ""
    echo "  full    - 完整部署：后端代码 + Web 资源 + 重启"
    echo "  backend - 仅部署后端 Python 代码 + 重启 uvicorn"
    echo "  web     - 仅同步 Web 静态资源（含 LOGO/壁纸/头像）"
    echo "  restart - 仅重启远程 uvicorn 服务"
    echo "  status  - 查看远程服务状态和资源文件"
    echo "  seed    - 重新加载种子数据"
    echo ""
    echo "环境变量:"
    echo "  REMOTE_HOST - SSH 目标 (默认 root@118.31.223.213)"
    ;;
esac

echo ""
echo -e "${BLUE}╔════════════════════════════════════════════╗"
echo -e "║  部署完成                                   ║"
echo -e "║  URL:   http://118.31.223.213:8081         ║"
echo -e "║  API:   http://118.31.223.213:8081/api     ║"
echo -e "║  文档:  http://118.31.223.213:8081/api/docs║"
echo -e "╚════════════════════════════════════════════╝${NC}"

#!/usr/bin/env bash
# 索克家居 远程部署脚本
# 用法: bash scripts/deploy-remote.sh [full|backend|web|restart|status|seed]
#
#   full    - 完整部署：后端代码 + Web 静态资源 + 重启服务 (默认)
#   backend - 仅部署后端 Python 代码 + 重启 uvicorn
#   web     - 仅同步 Web 静态资源（含 LOGO/壁纸/头像）+ 重载 Nginx
#   restart - 仅重启远程 uvicorn 服务（含配置预检 + 健康探针 + 失败回滚）
#   rollback- 回滚到上一次部署前的代码快照并复验
#   status  - 查看远程服务状态
#   seed    - 重新加载种子数据（物料库、测试用户等）

set -e

REMOTE_HOST="${REMOTE_HOST:-root@118.31.223.213}"
BACKEND_DEPLOY_DIR="/opt/ihome"            # 后端代码部署路径（v1.1.26: 与 CI deploy 对齐）
WEB_DEPLOY_DIR="/opt/ihome/webapp/dist"    # webapp 静态产物路径（2026-08-08 起替代旧 /opt/ihome/web）
PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"

GREEN='\033[0;32m'
BLUE='\033[0;34m'
NC='\033[0m'

# ── 发布安全闸门（对齐方案 M1/M2）────────────────────────────────────────────
# 生产 /opt/ihome/.env 是运行态唯一权威（SSOT）；仓库**只读校验、绝不覆盖**，
# 避免仓库 .env.production（Ed25519 两键为空）在部署时清空生产 PASETO 密钥。
env_preflight() {
  echo -e "${GREEN}🔒 发布前预检：生产 .env 关键键非空${NC}"
  ssh "$REMOTE_HOST" "bash -s" <<'GUARD'
required="PASETO_PRIVATE_KEY PASETO_PUBLIC_KEY PASETO_SECRET_KEY DATABASE_URL REDIS_URL"
miss=""
for k in $required; do
  v=$(grep -E "^${k}=" /opt/ihome/.env 2>/dev/null | head -1 | cut -d= -f2-)
  [ -z "$v" ] && miss="$miss $k"
done
if [ -n "$miss" ]; then
  echo "✗ 生产 .env 缺失/为空键:$miss —— 拒绝发布（fail-closed）"; exit 1
fi
echo "✓ 生产 .env 关键键非空"

# 小程序键：缺失不阻断发布（后端对登录 fail-closed 返回 502），但必须显式提示，
# 避免"发布成功但小程序登录全挂"这种静默故障。
warn=""
for k in MINIPROGRAM_APP_ID MINIPROGRAM_APP_SECRET; do
  v=$(grep -E "^${k}=" /opt/ihome/.env 2>/dev/null | head -1 | cut -d= -f2-)
  [ -z "$v" ] && warn="$warn $k"
done
if [ -n "$warn" ]; then
  echo "⚠ 生产 .env 未配置:$warn —— 小程序登录将返回 502（Web 端不受影响）"
fi
w=$(grep -E "^OPS_ALERT_WEBHOOK=" /opt/ihome/.env 2>/dev/null | head -1 | cut -d= -f2-)
[ -z "$w" ] && echo "⚠ 生产 .env 未配置 OPS_ALERT_WEBHOOK —— 新改造需求只记日志，不会推送到运营群"
GUARD
}

# 发布后门禁：配置预检（重启前）→ 重启 → 健康探针 → 失败回滚代码
#
# 修正（2026-10-24）：原实现失败分支只执行 `systemctl restart ihome`，
# 即把**同一份坏代码**再启一次，并不是回滚。现改为：
#   1. 代码同步**之前**先打快照（code_snapshot），失败时用快照还原；
#   2. 配置预检提前到 restart **之前**——坏配置根本不会让服务重启，
#      把"发布事故"降级为"发布被拦"；
#   3. 健康探针失败 → 还原快照 + 重启 + 复验，失败则明确要求人工介入。
SNAPSHOT_POINTER="/opt/ihome/backups/.last-code-snapshot"

code_snapshot() {
  echo -e "${GREEN}📸 预部署代码快照（失败回滚用）${NC}"
  ssh "$REMOTE_HOST" "bash -s" <<'SNAP'
cd /opt/ihome || exit 1
mkdir -p backups
snap="backups/code-pre-$(date +%Y%m%d%H%M%S).tar.gz"
tar -czf "$snap" app migrations alembic.ini 2>/dev/null || tar -czf "$snap" app 2>/dev/null
if [ ! -s "$snap" ]; then echo "✗ 快照生成失败，拒绝继续发布（fail-closed）"; exit 1; fi
echo "$snap" > backups/.last-code-snapshot
echo "    快照: $snap ($(du -h "$snap" | cut -f1))"
# 只保留最近 5 份
ls -t backups/code-pre-*.tar.gz 2>/dev/null | tail -n +6 | xargs -r rm -f
SNAP
}

rollback_code() {
  ssh "$REMOTE_HOST" "bash -s" <<'RB'
cd /opt/ihome || exit 1
snap=$(cat backups/.last-code-snapshot 2>/dev/null || true)
if [ -z "$snap" ] || [ ! -f "$snap" ]; then
  echo "    ⚠ 无可用代码快照：仅重启（可能仍运行故障代码，需人工介入）"
  systemctl restart ihome
  exit 1
fi
echo "    ↩ 回滚代码：$snap"
rm -rf app migrations
tar -xzf "$snap" -C . || { echo "    ✗ 解包失败，需人工介入"; exit 1; }
systemctl restart ihome
for i in $(seq 1 30); do
  if curl -fsS --max-time 3 http://127.0.0.1:8001/health >/dev/null 2>&1; then
    echo "    ✓ 回滚后 /health 就绪（${i}s）"; exit 0
  fi
  sleep 1
done
echo "    ✗ 回滚后 30s 内仍未就绪，需人工介入（快照保留在 $snap）"
exit 1
RB
}

restart_gate() {
  echo -e "${GREEN}🛡️ 发布门禁：配置预检 → 重启 → 健康探针 → 失败回滚${NC}"
  # ① 重启前配置预检：坏配置不该有机会重启服务
  if ! ssh "$REMOTE_HOST" "cd /opt/ihome && .venv/bin/python -c 'from app.config import get_settings; get_settings()'" >/dev/null 2>&1; then
    echo "✗ 配置预检失败（服务未重启）→ 请检查 /opt/ihome/.env 与最近代码改动"
    echo "  如需还原代码：bash scripts/deploy-remote.sh rollback"
    exit 1
  fi
  echo "✓ 配置可加载（未重启）"

  # ② 重启并等待就绪
  ssh "$REMOTE_HOST" "cd /opt/ihome && cp -a .env \"backups/.env.\$(date +%Y%m%d%H%M%S).bak\" 2>/dev/null; systemctl restart ihome"
  ready=0
  for i in $(seq 1 30); do
    if ssh "$REMOTE_HOST" "curl -fsS --max-time 3 http://127.0.0.1:8001/health" >/dev/null 2>&1; then
      ready=$i; break
    fi
    sleep 1
  done
  echo "    健康探针就绪耗时: ${ready}s（0 表示 30s 内未就绪）"

  # ③ 双探针
  if [ "$ready" = "0" ] \
     || ! ssh "$REMOTE_HOST" "curl -fsS --max-time 10 http://127.0.0.1:8001/health" >/dev/null 2>&1 \
     || ! ssh "$REMOTE_HOST" "curl -fsS --max-time 10 http://127.0.0.1:8001/api/health/detail" >/dev/null 2>&1; then
    echo "✗ 健康探针失败 → 回滚代码"
    rollback_code
    exit 1
  fi
  echo "✓ 门禁通过：配置可加载 + /health + /api/health/detail 均 200"
}

cmd="${1:-full}"

echo -e "${BLUE}╔════════════════════════════════════════════╗"
echo -e "║  索克家居 远程部署 → ${REMOTE_HOST}  ║"
echo -e "╚════════════════════════════════════════════╝${NC}"
echo ""

case "$cmd" in
  full)
    env_preflight
    echo -e "${GREEN}📦 [1/3] 同步后端代码 → ${BACKEND_DEPLOY_DIR}${NC}"
    code_snapshot
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
      --exclude='backups' \
      "$PROJECT_DIR/" "$REMOTE_HOST:$BACKEND_DEPLOY_DIR/"

    # 生产 .env 由环境隔离管理：仓库**不覆盖**（防 .env.production 清空 PASETO 密钥）

    echo -e "${GREEN}📦 [2/3] 同步 WebApp 构建产物（webapp/dist，需先本地 npm run build） → ${WEB_DEPLOY_DIR}${NC}"
    rsync -avz --delete \
      --exclude='.DS_Store' \
      "$PROJECT_DIR/webapp/dist/" "$REMOTE_HOST:$WEB_DEPLOY_DIR/"

    echo ""
    echo -e "${GREEN}🔄 [3/3] 远程安装依赖 & 重启服务${NC}"
    ssh "$REMOTE_HOST" "bash -s" << 'REMOTE_SCRIPT'
set -e
BACKEND_DIR=/opt/ihome
cd "$BACKEND_DIR"

# 创建虚拟环境（如不存在）
if [ ! -d ".venv" ]; then
  echo "    创建 Python 虚拟环境..."
  python3.11 -m venv .venv
fi

source .venv/bin/activate

# 安装/更新依赖（使用阿里云镜像加速，从 requirements.txt 读取完整列表）
echo "    安装 Python 依赖..."
MIRROR="https://mirrors.aliyun.com/pypi/simple/"
pip install -q --upgrade pip -i "$MIRROR" 2>&1 | tail -1
pip install -q -i "$MIRROR" -r requirements.txt 2>&1 | tail -3

# 初始化数据库（建表）
echo "    初始化数据库..."
mkdir -p data
PYTHONPATH=. python -c "
import asyncio
import app.models  # 触发所有模型注册到 Base.metadata，否则 create_all 只创建已导入的表
from app.database import init_db
asyncio.run(init_db())
" 2>&1 | tail -1

# 加载种子数据
echo "    加载种子数据..."
PYTHONPATH=. python scripts/seed.py 2>&1 | tail -2

# 更新 systemd 服务配置
cp "$BACKEND_DIR/scripts/ihome.service" /etc/systemd/system/ihome.service
systemctl daemon-reload
echo "    依赖/建表/种子数据就绪，交由本地门禁重启并验活"
REMOTE_SCRIPT

    restart_gate
    ssh "$REMOTE_HOST" "nginx -t && nginx -s reload && echo '    Nginx: ✅ 已重载' || echo '    Nginx: ⚠️ 跳过'"
    ;;

  backend)
    env_preflight
    echo -e "${GREEN}🔧 仅部署后端代码 → ${BACKEND_DEPLOY_DIR}${NC}"

    code_snapshot

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
      --exclude='backups' \
      "$PROJECT_DIR/" "$REMOTE_HOST:$BACKEND_DEPLOY_DIR/"

    # 生产 .env 由环境隔离管理：仓库**不覆盖**（防 .env.production 清空 PASETO 密钥）

    ssh "$REMOTE_HOST" "cd $BACKEND_DEPLOY_DIR && source .venv/bin/activate && pip install -q -i https://mirrors.aliyun.com/pypi/simple/ -r requirements.txt 2>&1 | tail -3"
    restart_gate
    ;;

  web)
    echo -e "${GREEN}🌐 仅同步 WebApp 构建产物 → ${WEB_DEPLOY_DIR}${NC}"

    rsync -avz --delete \
      --exclude='.DS_Store' \
      "$PROJECT_DIR/webapp/dist/" "$REMOTE_HOST:$WEB_DEPLOY_DIR/"

    ssh "$REMOTE_HOST" "nginx -t && nginx -s reload && echo '✅ Nginx 已重载'"
    ;;

  restart)
    restart_gate
    ;;

  rollback)
    echo -e "${GREEN}↩ 手动回滚到上一次部署前的代码快照${NC}"
    ssh "$REMOTE_HOST" "cat /opt/ihome/backups/.last-code-snapshot 2>/dev/null || echo '（无快照记录）'"
    rollback_code
    ;;

  status)
    echo -e "${GREEN}📊 远程服务状态${NC}"
    echo ""
    echo "--- systemd ---"
    ssh "$REMOTE_HOST" "systemctl status ihome --no-pager 2>/dev/null | head -10"
    echo ""
    echo "--- 健康检查 ---"
    echo -n "  HTTPS 域名: " && curl -s -w "HTTP %{http_code}\n" https://i-home.life/health 2>/dev/null || echo "  ❌ 无法连接"
    echo -n "  HTTPS 8081: " && curl -sk -w "HTTP %{http_code}\n" https://118.31.223.213:8081/health 2>/dev/null || echo "  ❌ 无法连接"
    echo ""
    echo "--- 资源文件 (webapp/dist) ---"
    ssh "$REMOTE_HOST" "echo '  LOGO:    ' && ls ${WEB_DEPLOY_DIR}/logo.png ${WEB_DEPLOY_DIR}/favicon.png 2>/dev/null | wc -l | xargs echo '    files'; echo '  前端产物: ' && ls ${WEB_DEPLOY_DIR}/index.html ${WEB_DEPLOY_DIR}/assets/*.js ${WEB_DEPLOY_DIR}/assets/*.css 2>/dev/null | wc -l | xargs echo '    files'; echo '  版本:    ' && cat ${WEB_DEPLOY_DIR}/version.json 2>/dev/null"
    echo ""
    echo "  API 文档: https://i-home.life/api/docs"
    echo "  站点首页: https://i-home.life/"
    ;;

  seed)
    echo -e "${GREEN}🌱 重新加载种子数据...${NC}"
    ssh "$REMOTE_HOST" "cd $BACKEND_DEPLOY_DIR && source .venv/bin/activate && PYTHONPATH=. python scripts/seed.py 2>&1 | tail -2 && PYTHONPATH=. python scripts/seed_demo_data.py 2>&1 | tail -2"
    ;;

  *)
    echo "用法: bash scripts/deploy-remote.sh {full|backend|web|restart|rollback|status|seed}"
    echo ""
    echo "  full     - 完整部署：后端代码 + Web 资源 + 重启"
    echo "  backend  - 仅部署后端 Python 代码 + 重启 uvicorn"
    echo "  web      - 仅同步 Web 静态资源（含 LOGO/壁纸/头像）"
    echo "  restart  - 仅重启远程 uvicorn 服务（含配置预检 + 健康探针）"
    echo "  rollback - 回滚到上一次部署前的代码快照并复验"
    echo "  status   - 查看远程服务状态和资源文件"
    echo "  seed     - 重新加载种子数据"
    echo ""
    echo "环境变量:"
    echo "  REMOTE_HOST - SSH 目标 (默认 root@118.31.223.213)"
    ;;
esac

echo ""
echo -e "${BLUE}╔════════════════════════════════════════════╗"
echo -e "║  部署完成                                   ║"
echo -e "║  站点:   https://i-home.life               ║"
echo -e "║  API:    https://i-home.life/api           ║"
echo -e "║  文档:   https://i-home.life/api/docs      ║"
echo -e "║  兼容:   https://118.31.223.213:8081       ║"
echo -e "╚════════════════════════════════════════════╝${NC}"

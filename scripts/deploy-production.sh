#!/usr/bin/env bash
# i-home.life 生产环境部署
set -e

PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
DEPLOY_DIR="${DEPLOY_DIR:-/opt/ihome}"
VENV_DIR="$PROJECT_DIR/.venv"
CONFIG_FILE="$PROJECT_DIR/.env.production"

echo "╔════════════════════════════════════════════╗"
echo "║  i-home.life 生产环境部署                    ║"
echo "╠════════════════════════════════════════════╣"

# 检查配置文件
if [ ! -f "$CONFIG_FILE" ]; then
  echo "  📝 创建 .env.production..."
  cat > "$CONFIG_FILE" << 'EOF'
DATABASE_URL=postgresql+asyncpg://ihome:CHANGE_ME@localhost:5432/ihome
SECRET_KEY=CHANGE_ME_TO_RANDOM_64_CHARS
APP_NAME=i-home.life
APP_VERSION=0.3.0
DEEPSEEK_API_KEY=
EOF
  echo "  ⚠️  请编辑 $CONFIG_FILE 填入真实密钥"
  echo "     DATABASE_URL: PostgreSQL 连接串"
  echo "     SECRET_KEY:   64 位随机字符串"
  echo "     DEEPSEEK_API_KEY: DeepSeek API Key (可选)"
  exit 1
fi

source "$CONFIG_FILE"

# 部署到目标目录
if [ "$PROJECT_DIR" != "$DEPLOY_DIR" ]; then
  echo "  📦 部署到 $DEPLOY_DIR..."
  sudo mkdir -p "$DEPLOY_DIR"
  sudo rsync -av --exclude='.venv' --exclude='.git' --exclude='__pycache__' --exclude='*.pyc' \
    --exclude='reports' --exclude='.dart_tool' "$PROJECT_DIR/" "$DEPLOY_DIR/"
  echo "  ✅ 文件已同步"
fi

# 创建虚拟环境并安装依赖
echo "  🐍 安装 Python 依赖..."
cd "$DEPLOY_DIR"
python3 -m venv "$VENV_DIR" 2>/dev/null || true
source "$VENV_DIR/bin/activate"
pip install -q fastapi uvicorn sqlalchemy asyncpg aiosqlite passlib python-multipart openpyxl httpx 2>&1 | tail -1

# 初始化数据库
echo "  🗄️  初始化数据库..."
PYTHONPATH=. python -c "
import asyncio
from app.database import init_db, engine, Base
async def setup():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    print('  ✅ 数据库表已创建')
asyncio.run(setup())
" 2>&1

# 种子数据
echo "  🌱 加载种子数据..."
PYTHONPATH=. python scripts/seed.py 2>&1 | grep -v "INFO\|PRAGMA\|CREATE\|SELECT\|INSERT\|COMMIT\|FROM\|RETURNING\|BEGIN\|index\|FOREIGN\|UNIQUE\|PRIMARY\|idx\|ix\|ON\|TABLE\|user\|material\|supplier\|WHERE\|password\|avatar\|hashed\|id," | head -3

# 配置 nginx
NGINX_CONF="/etc/nginx/sites-available/ihome"
if [ ! -f "$NGINX_CONF" ]; then
  echo "  🌐 配置 nginx..."
  sudo cp "$PROJECT_DIR/scripts/nginx-ihome.conf" "$NGINX_CONF"
  sudo sed -i '' "s|/opt/ihome/web|$DEPLOY_DIR/web|g" "$NGINX_CONF"
  sudo ln -sf "$NGINX_CONF" /etc/nginx/sites-enabled/
  sudo nginx -t && sudo nginx -s reload
  echo "  ✅ nginx 已配置"
else
  echo "  ⏭️  nginx 已配置，跳过"
fi

# 配置 systemd (Linux) 或 launchd (macOS)
if [[ "$OSTYPE" == "darwin"* ]]; then
  PLIST="$HOME/Library/LaunchAgents/com.ihome.life.plist"
  if [ ! -f "$PLIST" ]; then
    echo "  🍎 配置 launchd (macOS)..."
    cat > "$PLIST" << PLISTEOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.ihome.life</string>
    <key>ProgramArguments</key>
    <array>
        <string>$DEPLOY_DIR/.venv/bin/python</string>
        <string>-m</string>
        <string>uvicorn</string>
        <string>app.main:app</string>
        <string>--host</string>
        <string>0.0.0.0</string>
        <string>--port</string>
        <string>8000</string>
        <string>--workers</string>
        <string>4</string>
    </array>
    <key>WorkingDirectory</key>
    <string>$DEPLOY_DIR</string>
    <key>EnvironmentVariables</key>
    <dict>
        <key>PATH</key>
        <string>/usr/local/bin:/usr/bin:/bin</string>
    </dict>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <true/>
    <key>StandardOutPath</key>
    <string>$DEPLOY_DIR/data/server.log</string>
    <key>StandardErrorPath</key>
    <string>$DEPLOY_DIR/data/server-error.log</string>
</dict>
</plist>
PLISTEOF
    launchctl load "$PLIST"
    echo "  ✅ launchd 已配置并启动"
  fi
elif [[ "$OSTYPE" == "linux"* ]]; then
  echo "  🐧 请手动配置 systemd:"
  echo "     sudo cp scripts/ihome.service /etc/systemd/system/"
  echo "     sudo systemctl enable --now ihome"
fi

# HTTPS 提示
echo ""
echo "  🔒 HTTPS 配置提示:"
echo "     sudo certbot --nginx -d i-home.life -d www.i-home.life"
echo ""

echo "╠════════════════════════════════════════════╣"
echo "║  ✅ 生产环境部署完成                        ║"
echo "║                                            ║"
echo "║  服务: http://localhost:8081               ║"
echo "║  文档: http://localhost:8081/docs          ║"
echo "║  日志: tail -f $DEPLOY_DIR/data/server.log ║"
echo "║                                            ║"
echo "║  管理命令:                                  ║"
echo "║    launchctl stop com.ihome.life           ║"
echo "║    launchctl start com.ihome.life          ║"
echo "║    launchctl list | grep ihome             ║"
echo "╚════════════════════════════════════════════╝"

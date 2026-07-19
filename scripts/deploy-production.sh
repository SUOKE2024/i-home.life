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
GLM_API_KEY=
EOF
  echo "  ⚠️  请编辑 $CONFIG_FILE 填入真实密钥"
  echo "     DATABASE_URL: PostgreSQL 连接串"
  echo "     SECRET_KEY:   64 位随机字符串"
  echo "     DEEPSEEK_API_KEY: DeepSeek V4 API Key (可选)"
  echo "     GLM_API_KEY:      GLM-5.2 API Key (可选)"
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

# 生成自签名 SSL 证书（IP 直连场景无法使用 Let's Encrypt）
SSL_DIR="/etc/nginx/ssl"
SSL_CRT="$SSL_DIR/ihome-self-signed.crt"
SSL_KEY="$SSL_DIR/ihome-self-signed.key"
if [ ! -f "$SSL_CRT" ] || [ ! -f "$SSL_KEY" ]; then
  echo "  🔐 生成自签名 SSL 证书（用于 https://118.31.223.213:8081 兼容访问）..."
  sudo mkdir -p "$SSL_DIR"
  sudo openssl req -x509 -newkey rsa:2048 -nodes \
    -keyout "$SSL_KEY" -out "$SSL_CRT" \
    -days 3650 \
    -subj "/C=CN/ST=Shanghai/L=Shanghai/O=i-home.life/OU=IT/CN=118.31.223.213" \
    -addext "subjectAltName=IP:118.31.223.213,DNS:i-home.life,DNS:www.i-home.life" 2>&1 | tail -2
  sudo chmod 644 "$SSL_CRT"
  sudo chmod 600 "$SSL_KEY"
  echo "  ✅ 自签名证书已生成: $SSL_CRT (有效期 10 年)"
fi

# 检查 Nginx 版本（同端口 HTTP+HTTPS 需要 Nginx >= 1.25.1）
NGINX_VERSION=$(nginx -v 2>&1 | grep -oE '[0-9]+\.[0-9]+\.[0-9]+' | head -1)
NGINX_MAJOR=$(echo "$NGINX_VERSION" | cut -d. -f1)
NGINX_MINOR=$(echo "$NGINX_VERSION" | cut -d. -f2)
NGINX_PATCH=$(echo "$NGINX_VERSION" | cut -d. -f3)
echo "  ℹ️  Nginx 版本: $NGINX_VERSION"
if [ "$NGINX_MAJOR" -lt 1 ] || ([ "$NGINX_MAJOR" -eq 1 ] && [ "$NGINX_MINOR" -lt 25 ]) || \
   ([ "$NGINX_MAJOR" -eq 1 ] && [ "$NGINX_MINOR" -eq 25 ] && [ "$NGINX_PATCH" -lt 1 ]); then
  echo "  ⚠️  Nginx < 1.25.1 不支持「同端口 HTTP+HTTPS」特性"
  echo "      升级方法: sudo apt update && sudo apt install --only-upgrade nginx"
  echo "      或要求用户使用 http://118.31.223.213:8081 访问"
fi

# 配置 nginx（始终同步最新配置，确保 WebSocket/gzip/安全头等更新生效）
NGINX_CONF="/etc/nginx/sites-available/ihome"
echo "  🌐 同步 nginx 配置..."
sudo cp "$PROJECT_DIR/scripts/nginx-ihome.conf" "$NGINX_CONF"
# 跨平台 sed: 兼容 BSD (macOS) 与 GNU (Linux)
if [[ "$OSTYPE" == "darwin"* ]]; then
  sudo sed -i '' "s|/opt/ihome/web|$DEPLOY_DIR/web|g" "$NGINX_CONF"
else
  sudo sed -i "s|/opt/ihome/web|$DEPLOY_DIR/web|g" "$NGINX_CONF"
fi
sudo ln -sf "$NGINX_CONF" /etc/nginx/sites-enabled/
sudo nginx -t && sudo nginx -s reload
echo "  ✅ nginx 已同步并重载（含 8081 HTTP+HTTPS 兼容、/ws/ WebSocket、gzip、安全头）"

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
        <string>8001</string>
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
echo "║  文档: http://localhost:8081/api/docs      ║"
echo "║  日志: tail -f $DEPLOY_DIR/data/server.log ║"
echo "║                                            ║"
echo "║  管理命令:                                  ║"
echo "║    launchctl stop com.ihome.life           ║"
echo "║    launchctl start com.ihome.life          ║"
echo "║    launchctl list | grep ihome             ║"
echo "╚════════════════════════════════════════════╝"

#!/usr/bin/env bash
# 修复 https://118.31.223.213:8081 ERR_SSL_PROTOCOL_ERROR
# 原因：v1.0.8 将 8081 改为纯 HTTP，用户用 https:// 访问会失败
# 方案：8081 端口同时监听 HTTP+HTTPS（自签名证书），兼容两种协议
#
# 使用方法（在服务器上执行）：
#   cd /path/to/i-home.life
#   git pull
#   sudo bash scripts/fix-8081-https.sh
set -e

PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
SSL_DIR="/etc/nginx/ssl"
SSL_CRT="$SSL_DIR/ihome-self-signed.crt"
SSL_KEY="$SSL_DIR/ihome-self-signed.key"

echo "╔════════════════════════════════════════════╗"
echo "║  修复 8081 端口 HTTPS 访问                   ║"
echo "╠════════════════════════════════════════════╣"

# ── 1. 检查 Nginx 版本 ──
echo "  ℹ️  检查 Nginx 版本..."
if ! command -v nginx >/dev/null 2>&1; then
  echo "  ❌ 未找到 nginx 命令，请先安装 nginx"
  exit 1
fi
NGINX_VERSION=$(nginx -v 2>&1 | grep -oE '[0-9]+\.[0-9]+\.[0-9]+' | head -1)
NGINX_MAJOR=$(echo "$NGINX_VERSION" | cut -d. -f1)
NGINX_MINOR=$(echo "$NGINX_VERSION" | cut -d. -f2)
NGINX_PATCH=$(echo "$NGINX_VERSION" | cut -d. -f3)
echo "     Nginx 版本: $NGINX_VERSION"

SUPPORTS_SAME_PORT=false
if [ "$NGINX_MAJOR" -gt 1 ] || \
   ([ "$NGINX_MAJOR" -eq 1 ] && [ "$NGINX_MINOR" -gt 25 ]) || \
   ([ "$NGINX_MAJOR" -eq 1 ] && [ "$NGINX_MINOR" -eq 25 ] && [ "$NGINX_PATCH" -ge 1 ]); then
  SUPPORTS_SAME_PORT=true
  echo "  ✅ 支持「同端口 HTTP+HTTPS」特性（Nginx >= 1.25.1）"
else
  echo "  ⚠️  Nginx < 1.25.1 不支持「同端口 HTTP+HTTPS」特性"
  echo "      升级方法: sudo apt update && sudo apt install --only-upgrade nginx"
  echo "      升级后重新执行本脚本"
  echo "      或暂时要求用户使用 http://118.31.223.213:8081 访问"
  exit 1
fi

# ── 2. 生成自签名 SSL 证书 ──
if [ ! -f "$SSL_CRT" ] || [ ! -f "$SSL_KEY" ]; then
  echo "  🔐 生成自签名 SSL 证书（用于 https://118.31.223.213:8081 兼容访问）..."
  sudo mkdir -p "$SSL_DIR"
  sudo openssl req -x509 -newkey rsa:2048 -nodes \
    -keyout "$SSL_KEY" -out "$SSL_CRT" \
    -days 3650 \
    -subj "/C=CN/ST=Shanghai/L=Shanghai/O=i-home.life/OU=IT/CN=118.31.223.213" \
    -addext "subjectAltName=IP:118.31.223.213,DNS:i-home.life,DNS:www.i-home.life"
  sudo chmod 644 "$SSL_CRT"
  sudo chmod 600 "$SSL_KEY"
  echo "  ✅ 自签名证书已生成（有效期 10 年）"
  echo "     证书: $SSL_CRT"
  echo "     私钥: $SSL_KEY"
else
  echo "  ✅ 自签名证书已存在，跳过生成"
fi

# ── 3. 同步 nginx 配置 ──
NGINX_CONF="/etc/nginx/sites-available/ihome"
echo "  🌐 同步 nginx 配置..."
sudo cp "$PROJECT_DIR/scripts/nginx-ihome.conf" "$NGINX_CONF"

# 处理 deploy 目录差异（如果生产环境部署在 /opt/ihome 之外）
DEPLOY_DIR="${DEPLOY_DIR:-/opt/ihome}"
if [ -d "$DEPLOY_DIR/web" ]; then
  sudo sed -i "s|/opt/ihome/web|$DEPLOY_DIR/web|g" "$NGINX_CONF"
fi

sudo ln -sf "$NGINX_CONF" /etc/nginx/sites-enabled/

# ── 4. 测试并重载 nginx ──
echo "  🧪 测试 nginx 配置..."
if sudo nginx -t; then
  echo "  🔄 重载 nginx..."
  sudo nginx -s reload
  echo "  ✅ nginx 已重载"
else
  echo "  ❌ nginx 配置测试失败，请检查错误信息"
  exit 1
fi

# ── 5. 验证修复效果 ──
echo ""
echo "  🔍 验证修复效果..."
sleep 1

echo -n "     HTTP  http://118.31.223.213:8081/health ... "
HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" -m 5 http://118.31.223.213:8081/health 2>/dev/null || echo "FAIL")
echo "$HTTP_CODE"

echo -n "     HTTPS https://118.31.223.213:8081/health ... "
HTTPS_CODE=$(curl -sk -o /dev/null -w "%{http_code}" -m 5 https://118.31.223.213:8081/health 2>/dev/null || echo "FAIL")
echo "$HTTPS_CODE (证书警告可忽略，-k 跳过验证)"

echo ""
echo "╠════════════════════════════════════════════╣"
if [ "$HTTP_CODE" = "200" ] && [ "$HTTPS_CODE" = "200" ]; then
  echo "║  ✅ 修复成功                                 ║"
  echo "║                                              ║"
  echo "║  现在浏览器访问 https://118.31.223.213:8081   ║"
  echo "║  会出现证书警告，点击「高级 → 继续」即可。   ║"
  echo "║  推荐使用 http:// 协议访问避免证书警告。     ║"
else
  echo "║  ⚠️  修复可能未完全生效                       ║"
  echo "║  HTTP: $HTTP_CODE                                    ║"
  echo "║  HTTPS: $HTTPS_CODE (期望 200)                          ║"
  echo "║  请检查:                                      ║"
  echo "║  - sudo nginx -t                              ║"
  echo "║  - sudo systemctl status nginx                ║"
  echo "║  - sudo tail -50 /var/log/nginx/error.log     ║"
fi
echo "╚════════════════════════════════════════════╝"

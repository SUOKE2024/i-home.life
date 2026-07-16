#!/usr/bin/env bash
# 修复 8081 端口同时支持 HTTP + HTTPS 访问
# 方案：stream ssl_preread 协议检测分流（兼容 Nginx 1.20+）
#   外部 8081 → stream ssl_preread → 内部 8084(HTTP) / 8085(HTTPS)
#
# 使用方法（在服务器上执行）：
#   cd /path/to/i-home.life
#   git pull
#   sudo bash scripts/fix-8081-https.sh
set -e

PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
SSL_DIR="/etc/nginx/ssl"
SSL_CRT="$SSL_DIR/ihome-cert.pem"
SSL_KEY="$SSL_DIR/ihome-key.pem"
STREAM_DIR="/etc/nginx/stream.d"
NGINX_CONF="/etc/nginx/nginx.conf"

echo "╔════════════════════════════════════════════╗"
echo "║  修复 8081 端口 HTTP + HTTPS 双协议访问     ║"
echo "╠════════════════════════════════════════════╣"

# ── 1. 检查 Nginx 及 stream 模块 ──
echo "  ℹ️  检查 Nginx 版本和模块..."
if ! command -v nginx >/dev/null 2>&1; then
  echo "  ❌ 未找到 nginx 命令，请先安装 nginx"
  exit 1
fi

NGINX_VERSION=$(nginx -v 2>&1 | grep -oE '[0-9]+\.[0-9]+\.[0-9]+' | head -1)
echo "     Nginx 版本: $NGINX_VERSION"

# 检查 stream 模块是否可用（动态或静态编译）
if nginx -V 2>&1 | grep -q 'with-stream'; then
  echo "  ✅ stream 模块可用"
else
  echo "  ❌ 未检测到 stream 模块，请安装 nginx-mod-stream"
  echo "     安装命令: yum install -y nginx-mod-stream"
  exit 1
fi

# ── 2. 确保 stream 模块已加载 ──
echo "  🔧 配置 nginx.conf..."
if ! grep -q 'ngx_stream_module' "$NGINX_CONF"; then
  # 在 include modules 行后添加 load_module
  sed -i '/^include \/usr\/share\/nginx\/modules/a load_module /usr/lib64/nginx/modules/ngx_stream_module.so;' "$NGINX_CONF"
  echo "     ✅ 已添加 load_module"
else
  echo "     ✅ stream 模块已加载"
fi

# 添加 stream 块（如果不存在）
if ! grep -q '^stream {' "$NGINX_CONF"; then
  cat >> "$NGINX_CONF" << 'NEOF'

# ── Stream 模块（TCP 层协议检测分流） ──
stream {
    include /etc/nginx/stream.d/*.conf;
}
NEOF
  echo "     ✅ 已添加 stream 块"
else
  echo "     ✅ stream 块已存在"
fi

# ── 3. 生成/检查自签名 SSL 证书 ──
echo "  🔐 检查 SSL 证书..."
if [ ! -f "$SSL_CRT" ] || [ ! -f "$SSL_KEY" ]; then
  echo "     生成自签名 SSL 证书（用于 https:// 兼容访问）..."
  sudo mkdir -p "$SSL_DIR"
  sudo openssl req -x509 -newkey rsa:2048 -nodes \
    -keyout "$SSL_KEY" -out "$SSL_CRT" \
    -days 3650 \
    -subj "/C=CN/ST=Shanghai/L=Shanghai/O=i-home.life/OU=IT/CN=118.31.223.213" \
    -addext "subjectAltName=IP:118.31.223.213,DNS:i-home.life,DNS:www.i-home.life"
  sudo chmod 644 "$SSL_CRT"
  sudo chmod 600 "$SSL_KEY"
  echo "     ✅ 自签名证书已生成（有效期 10 年）"
else
  echo "     ✅ 自签名证书已存在"
fi

# ── 4. 同步 stream 配置 ──
echo "  🌐 同步 stream ssl_preread 配置..."
mkdir -p "$STREAM_DIR"
cp "$PROJECT_DIR/scripts/nginx-stream-ihome.conf" "$STREAM_DIR/ihome-8081.conf"
echo "     ✅ $STREAM_DIR/ihome-8081.conf"

# ── 5. 同步 http 配置 ──
echo "  🌐 同步 http server 配置..."
cp "$PROJECT_DIR/scripts/nginx-ihome.conf" /etc/nginx/conf.d/ihome.conf
echo "     ✅ /etc/nginx/conf.d/ihome.conf"

# ── 6. 测试并重载 nginx ──
echo ""
echo "  🧪 测试 nginx 配置..."
if sudo nginx -t 2>&1; then
  echo ""
  echo "  🔄 重载 nginx..."
  sudo nginx -s reload
  echo "  ✅ nginx 已重载"
else
  echo "  ❌ nginx 配置测试失败，请检查错误信息"
  exit 1
fi

# ── 7. 验证修复效果 ──
echo ""
echo "  🔍 验证修复效果..."
sleep 2

echo -n "     HTTP  http://118.31.223.213:8081/health ... "
HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" -m 5 http://118.31.223.213:8081/health 2>/dev/null || echo "FAIL")
echo "$HTTP_CODE"

echo -n "     HTTPS https://118.31.223.213:8081/health ... "
HTTPS_CODE=$(curl -sk -o /dev/null -w "%{http_code}" -m 5 https://118.31.223.213:8081/health 2>/dev/null || echo "FAIL")
echo "$HTTPS_CODE (自签名证书，-k 跳过验证)"

echo ""
echo "╠════════════════════════════════════════════╣"
if [ "$HTTP_CODE" = "200" ] && [ "$HTTPS_CODE" = "200" ]; then
  echo "║  ✅ 修复成功                                 ║"
  echo "║                                              ║"
  echo "║  http://118.31.223.213:8081   正常            ║"
  echo "║  https://118.31.223.213:8081  正常 (证书警告) ║"
  echo "║  http://i-home.life:8081      正常            ║"
  echo "║  https://i-home.life:8081     正常 (证书警告) ║"
else
  echo "║  ⚠️  可能需要进一步排查                      ║"
  echo "║  HTTP: $HTTP_CODE                                    ║"
  echo "║  HTTPS: $HTTPS_CODE (期望 200)                          ║"
  echo "║  请检查:                                      ║"
  echo "║  - sudo nginx -t                              ║"
  echo "║  - sudo systemctl status nginx                ║"
  echo "║  - sudo tail -50 /var/log/nginx/error.log     ║"
fi
echo "╚════════════════════════════════════════════╝"

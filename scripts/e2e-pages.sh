#!/usr/bin/env bash
# 全站页面 HTTP 冒烟测试 — v1.2.4+（webapp 版，2026-08-08 适配）
# 适配 webapp/（Vite+React 构建产物 dist/）：
#   检查入口 HTML + 品牌资源 + 从 index.html 动态解析 /assets/*.js|css 逐一验证
# 用法: ./scripts/e2e-pages.sh [base_url]
# 默认 base_url: http://localhost:8766

set -e

BASE_URL="${1:-http://localhost:8766}"
PASS=0
FAIL=0

check_url() {
  local path="$1"
  local actual
  actual=$(curl -s -o /dev/null -w "%{http_code}" "${BASE_URL}/${path}")
  if [ "$actual" = "200" ]; then
    echo "  ✅ $path ($actual)"
    PASS=$((PASS + 1))
  else
    echo "  ❌ $path (期望 200, 实际 $actual)"
    FAIL=$((FAIL + 1))
  fi
}

echo "╔════════════════════════════════════════════╗"
echo "║  全站页面 HTTP 冒烟测试 (webapp)           ║"
echo "╠════════════════════════════════════════════╣"
echo "║  目标: $BASE_URL"
echo "╠════════════════════════════════════════════╣"

# 1. 入口与品牌资源
for page in index.html favicon.png logo.png; do
  check_url "$page"
done

# 2. 从 index.html 动态解析构建资源（文件名带 hash，逐一验证）
ASSETS=$(curl -s "${BASE_URL}/index.html" | grep -oE '(assets/[A-Za-z0-9._-]+\.(js|css))' | sort -u || true)
if [ -z "$ASSETS" ]; then
  echo "  ❌ 未在 index.html 中解析到 /assets/ 资源引用"
  FAIL=$((FAIL + 1))
else
  echo "  ── 构建资源 (hash 文件名动态解析) ──"
  for asset in $ASSETS; do
    check_url "$asset"
  done
fi

# 3. SPA fallback 路由说明：生产环境由 Nginx `try_files $uri $uri/ /index.html` 处理；
#    CI 冒烟用 python http.server 无 fallback，故此处不测深层路由（nginx-ihome.conf 已验证）。

echo "╠════════════════════════════════════════════╣"
echo "║  通过: $PASS  失败: $FAIL                    "
if [ "$FAIL" -eq 0 ]; then
  echo "║  ✅ 全部通过                                "
else
  echo "║  ❌ 存在失败                                "
fi
echo "╚════════════════════════════════════════════╝"

exit $FAIL

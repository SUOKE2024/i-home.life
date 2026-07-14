#!/usr/bin/env bash
# 全站页面 HTTP 冒烟测试
# 用法: ./scripts/e2e-pages.sh [base_url]
# 默认 base_url: http://localhost:8766

set -e

BASE_URL="${1:-http://localhost:8766}"
PASS=0
FAIL=0

# 测试页面列表（路径, 期望状态码）
PAGES=(
  "index.html 200"
  "login.html 200"
  "workbench.html 200"
  "our-story.html 200"
  "settings.html 200"
  "project-detail.html 200"
  "materials.html 200"
  "quality-report.html 200"
  "manifest.json 200"
  "sw.js 200"
  "sitemap.xml 200"
  "robots.txt 200"
  "assets/css/workbench.css 200"
  "assets/js/api-client.js 200"
  "assets/js/im-client.js 200"
  "assets/js/agent-router.js 200"
  "assets/js/message-renderers.js 200"
  "assets/js/demo-narrative.js 200"
  "assets/js/story-narrative.js 200"
  "assets/js/analytics.js 200"
)

echo "╔════════════════════════════════════════════╗"
echo "║  全站页面 HTTP 冒烟测试                    ║"
echo "╠════════════════════════════════════════════╣"
echo "║  目标: $BASE_URL"
echo "╠════════════════════════════════════════════╣"

for entry in "${PAGES[@]}"; do
  page=$(echo "$entry" | awk '{print $1}')
  expected=$(echo "$entry" | awk '{print $2}')
  actual=$(curl -s -o /dev/null -w "%{http_code}" "${BASE_URL}/${page}")
  if [ "$actual" = "$expected" ]; then
    echo "  ✅ $page ($actual)"
    PASS=$((PASS + 1))
  else
    echo "  ❌ $page (期望 $expected, 实际 $actual)"
    FAIL=$((FAIL + 1))
  fi
done

echo "╠════════════════════════════════════════════╣"
echo "║  通过: $PASS  失败: $FAIL                    "
if [ "$FAIL" -eq 0 ]; then
  echo "║  ✅ 全部通过                                "
else
  echo "║  ❌ 存在失败                                "
fi
echo "╚════════════════════════════════════════════╝"

exit $FAIL

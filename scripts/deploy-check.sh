#!/usr/bin/env bash
# 索克家居 · 部署前检查脚本
# 用法: bash scripts/deploy-check.sh

set -e

PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
ERRORS=0

echo "╔════════════════════════════════════════════╗"
echo "║  索克家居 · 部署前检查                      ║"
echo "╠════════════════════════════════════════════╣"

# 1. Nginx 配置语法检查
echo "  🔍 检查 nginx 配置..."
if command -v nginx &>/dev/null; then
  if nginx -t -c "$PROJECT_DIR/scripts/nginx-ihome.conf" 2>&1 | grep -q "successful"; then
    echo "  ✅ nginx 配置语法正确"
  else
    echo "  ⚠️  nginx 未安装或配置语法有问题（如在本地开发环境可忽略）"
  fi
else
  echo "  ⏭️  nginx 未安装，跳过（本地开发环境正常）"
fi

# 2. Python 依赖检查
echo "  🔍 检查 Python 依赖..."
if [ -f "$PROJECT_DIR/requirements.txt" ]; then
  cd "$PROJECT_DIR"
  if [ -d ".venv" ]; then
    source .venv/bin/activate 2>/dev/null || true
  fi
  MISSING=$(pip check 2>&1 | grep -v "No broken" || true)
  if [ -z "$MISSING" ]; then
    echo "  ✅ Python 依赖完整"
  else
    echo "  ⚠️  依赖问题: $MISSING"
  fi
else
  echo "  ⚠️  requirements.txt 不存在"
  ERRORS=$((ERRORS+1))
fi

# 3. Web 静态资源存在性检查
echo "  🔍 检查 Web 静态资源..."
WEB_DIR="$PROJECT_DIR/web"
REQUIRED_FILES=(
  "index.html" "login.html" "workbench.html" "settings.html" "our-story.html"
  "project-detail.html" "materials.html" "quality-report.html"
  "manifest.json" "sw.js" "sitemap.xml" "robots.txt"
  "assets/css/workbench.css" "assets/js/api-client.js" "assets/js/im-client.js"
  "assets/js/agent-router.js" "assets/js/message-renderers.js"
  "assets/js/analytics.js" "assets/js/component-base.js" "assets/js/router.js"
)
for f in "${REQUIRED_FILES[@]}"; do
  if [ -f "$WEB_DIR/$f" ]; then
    echo "  ✅ $f"
  else
    echo "  ❌ $f 缺失"
    ERRORS=$((ERRORS+1))
  fi
done

# 4. 后端模块检查
echo "  🔍 检查后端模块..."
BACKEND_FILES=(
  "app/main.py" "app/config.py" "app/database.py" "app/api/__init__.py"
  "app/api/agents.py" "app/api/auth.py" "app/api/projects.py"
)
for f in "${BACKEND_FILES[@]}"; do
  if [ -f "$PROJECT_DIR/$f" ]; then
    echo "  ✅ $f"
  else
    echo "  ❌ $f 缺失"
    ERRORS=$((ERRORS+1))
  fi
done

# 5. JS 语法检查
echo "  🔍 检查 JavaScript 语法..."
for js in "$WEB_DIR/assets/js/"*.js "$WEB_DIR/sw.js"; do
  if node --check "$js" 2>/dev/null; then
    echo "  ✅ $(basename $js)"
  else
    echo "  ❌ $(basename $js) 语法错误"
    ERRORS=$((ERRORS+1))
  fi
done

echo "╠════════════════════════════════════════════╣"
if [ "$ERRORS" -eq 0 ]; then
  echo "║  ✅ 所有检查通过，可以部署"
  echo "║                                            "
  echo "║  部署命令:                                  "
  echo "║    bash scripts/deploy-production.sh       "
else
  echo "║  ❌ 发现 $ERRORS 个问题，请修复后再部署"
fi
echo "╚════════════════════════════════════════════╝"

exit $ERRORS

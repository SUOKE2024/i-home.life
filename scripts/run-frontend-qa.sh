#!/usr/bin/env bash
# ═══════════════════════════════════════════════════════════════
# P1 前端修复 QA — 本地一键执行脚本（console Playwright + Flutter test）
#
# 用法:
#   bash scripts/run-frontend-qa.sh          # 全量（console + flutter）
#   bash scripts/run-frontend-qa.sh console  # 仅 console Playwright
#   bash scripts/run-frontend-qa.sh flutter  # 仅 Flutter 3 页
#
# 退出码: 0=全部通过 1=console 失败 2=flutter 失败 3=全失败
# ═══════════════════════════════════════════════════════════════
set -u

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CONSOLE_SPEC="tests/visual/p1-qa.spec.ts"
FLUTTER_TESTS="test/pages/b2b_delivery_page_test.dart test/pages/sketch_to_3d_page_test.dart test/pages/ifc_export_page_test.dart"

MODE="${1:-all}"
EXIT=0

run_console() {
  echo "── console Playwright: $CONSOLE_SPEC ──"
  (cd "$ROOT/console-src" && npx playwright test "$CONSOLE_SPEC")
  local code=$?
  echo "── console Playwright 退出码: $code ──"
  return $code
}

run_flutter() {
  echo "── Flutter test: $FLUTTER_TESTS ──"
  # --concurrency=1：3 个测试文件串行执行，避免并行 isolate 竞争导致 flaky
  (cd "$ROOT/flutter_app" && flutter test --concurrency=1 $FLUTTER_TESTS)
  local code=$?
  echo "── Flutter test 退出码: $code ──"
  return $code
}

if [ "$MODE" = "console" ]; then
  run_console; EXIT=$?
elif [ "$MODE" = "flutter" ]; then
  run_flutter; EXIT=$?
else
  run_console; C=$?
  [ $C -ne 0 ] && EXIT=$((EXIT | 1))
  run_flutter; F=$?
  [ $F -ne 0 ] && EXIT=$((EXIT | 2))
fi

echo ""
if [ "$EXIT" -eq 0 ]; then
  # macOS bash 3.2 多字节解析：中文括号紧邻 $VAR 会被并入变量名 → 用 ${} 包裹
  echo "✅ P1 QA 全部通过（${MODE}）"
else
  echo "❌ P1 QA 存在失败（exit=${EXIT}，bit1=console bit2=flutter）"
fi
exit "$EXIT"

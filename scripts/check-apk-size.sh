#!/usr/bin/env bash
# 索克家居 · APK / HAP 体积预算检查 (F6)
#
# 用法:
#   bash scripts/check-apk-size.sh                    # 检查已构建的 APK/HAP
#   BUDGET_MB=55 bash scripts/check-apk-size.sh       # 自定义预算上限
#   bash scripts/check-apk-size.sh --build            # 先构建 release APK 再检查
#
# 体积预算（可通过环境变量覆盖）:
#   BUDGET_MB   — Android APK 体积上限，默认 60 MB
#   HAP_BUDGET_MB — HarmonyOS HAP 体积上限，默认 80 MB
#
# 退出码:
#   0 — 所有产物均在预算内
#   1 — 存在超预算产物（CI 应标记失败）
#   2 — 未找到任何构建产物
#
# 设计依据: Flutter release APK 通常 20-80 MB；本应用含 sensors_plus /
# geolocator / local_auth / cached_network_image 等原生插件，预算设为 60 MB
# 留出 20% 安全余量。超预算时打印构成提示，便于定位膨胀来源。

set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
FLUTTER_DIR="$PROJECT_DIR/flutter_app"

# ── 预算配置 ──
BUDGET_MB="${BUDGET_MB:-60}"
HAP_BUDGET_MB="${HAP_BUDGET_MB:-80}"
BUILD_FIRST=false

if [[ "${1:-}" == "--build" ]]; then
  BUILD_FIRST=true
fi

echo "╔════════════════════════════════════════════╗"
echo "║  索克家居 · 体积预算检查 (F6)               ║"
echo "╠════════════════════════════════════════════╣"
echo "║  APK 预算: ${BUDGET_MB} MB  HAP 预算: ${HAP_BUDGET_MB} MB"
echo "╚════════════════════════════════════════════╝"
echo ""

# ── 可选: 先构建 ──
if $BUILD_FIRST; then
  echo "🔨 构建 release APK..."
  cd "$FLUTTER_DIR"
  flutter build apk --release 2>&1 | tail -5
  echo ""
fi

EXIT_CODE=0
FOUND_ANY=false

# ── 辅助函数: 检查单个产物体积 ──
# 参数: $1=产物路径  $2=预算(MB)  $3=产物类型标签
check_artifact() {
  local artifact="$1"
  local budget_mb="$2"
  local label="$3"

  if [[ ! -f "$artifact" ]]; then
    return 0  # 产物不存在，跳过（不报错）
  fi

  FOUND_ANY=true
  local size_bytes
  size_bytes=$(stat -f%z "$artifact" 2>/dev/null || stat -c%s "$artifact" 2>/dev/null)
  local size_mb
  size_mb=$(awk "BEGIN {printf \"%.2f\", $size_bytes / 1048576}")
  local pct
  pct=$(awk "BEGIN {printf \"%.1f\", $size_bytes / 1048576 / $budget_mb * 100}")

  local status="✅"
  if (( $(awk "BEGIN {print ($size_mb > $budget_mb)}") )); then
    status="❌"
    EXIT_CODE=1
  elif (( $(awk "BEGIN {print ($pct > 85)}") )); then
    status="⚠️"
  fi

  printf "  %s %-8s %8s MB / %s MB  (%s%%)  %s\n" \
    "$status" "$label" "$size_mb" "$budget_mb" "$pct" "$(basename "$artifact")"

  # 超预算时给出排查提示
  if [[ "$status" == "❌" ]]; then
    echo "       💡 排查建议:"
    echo "          - flutter build apk --analyze-size        # 生成 size 诊断报告"
    echo "          - 检查 assets/images/ 是否含未压缩大图"
    echo "          - 检查是否引入了未使用的原生插件 (flutter pub deps)"
    echo "          - 考虑拆分 ABI: flutter build apk --split-per-abi"
  fi
}

# ── 检查 Android APK ──
echo "📦 Android APK:"
APK_DIR="$FLUTTER_DIR/build/app/outputs/flutter-apk"
check_artifact "$APK_DIR/app-release.apk" "$BUDGET_MB" "APK"

# split-per-abi 产物（如果使用了分架构构建）
check_artifact "$APK_DIR/app-arm64-v8a-release.apk" "$BUDGET_MB" "APK"
check_artifact "$APK_DIR/app-armeabi-v7a-release.apk" "$BUDGET_MB" "APK"
check_artifact "$APK_DIR/app-x86_64-release.apk" "$BUDGET_MB" "APK"

# ── 检查 HarmonyOS HAP ──
echo ""
echo "📦 HarmonyOS HAP:"
# DevEco Studio 构建产物路径（ohos/entry 模块）
HAP_DIR="$FLUTTER_DIR/ohos/entry/build/default/outputs/default"
check_artifact "$HAP_DIR/entry-default-signed.hap" "$HAP_BUDGET_MB" "HAP"
check_artifact "$HAP_DIR/entry-default-unsigned.hap" "$HAP_BUDGET_MB" "HAP"

echo ""
if ! $FOUND_ANY; then
  echo "⚠️  未找到任何构建产物。"
  echo "   先执行: bash scripts/check-apk-size.sh --build"
  echo "   或手动: cd flutter_app && flutter build apk --release"
  exit 2
fi

if [[ $EXIT_CODE -eq 0 ]]; then
  echo "✅ 所有产物均在体积预算内。"
else
  echo ""
  echo "❌ 存在超预算产物，请优化后重新构建。"
fi

exit $EXIT_CODE

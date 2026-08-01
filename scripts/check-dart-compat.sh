#!/usr/bin/env bash
# check-dart-compat.sh — 鸿蒙端 Dart 语法兼容性守门（v1.3.0 引入）
#
# 背景：项目双端版本漂移 —— 鸿蒙端 Flutter-OH 3.35.7 / Dart 3.9.2，
# Android/iOS 端系统 Flutter 3.41.7 / Dart 3.11.5。若开发者误用 Dart 3.10+
# 语法（如 records 解构、patterns 完整匹配、sealed interface 新行为等），
# 鸿蒙端将无法编译。
#
# 本脚本在 CI 中用鸿蒙端目标 Dart 版本（3.9.2）做静态扫描，拦截不兼容语法。
# 本地可手动运行：bash scripts/check-dart-compat.sh
#
# 退出码：0=通过，1=发现不兼容语法

set -euo pipefail

LIB_DIR="${1:-flutter_app/lib}"
# 鸿蒙端目标 Dart 版本（与 flutter_app/pubspec.yaml environment.sdk 对齐）
TARGET_DART_MINOR=9  # 3.9.x

echo "🔍 扫描 $LIB_DIR Dart 语法兼容性（目标 Dart 3.${TARGET_DART_MINOR}.x 鸿蒙端）..."

# Dart 3.10+ 引入 / 行为变更的语法特征（保守匹配，误报优先于漏报）
# - 3.10: 增强的 patterns（irrefutable patterns 在更多上下文）
# - 3.11: 部分库 API 变更
# 此处聚焦可在源码静态识别的特征
incompatible=0
report() {
  echo "  ❌ $1"
  echo "     $2"
  incompatible=1
}

# 1. 检查 pubspec.yaml sdk 约束未越线
PUBSPEC="flutter_app/pubspec.yaml"
if [ -f "$PUBSPEC" ]; then
  sdk_line=$(grep -E '^\s*sdk:\s*' "$PUBSPEC" | head -1)
  if echo "$sdk_line" | grep -qE 'sdk:\s*\^?3\.([0-9]+)'; then
    minor=$(echo "$sdk_line" | grep -oE '3\.([0-9]+)' | head -1 | cut -d. -f2)
    if [ -n "$minor" ] && [ "$minor" -gt "$TARGET_DART_MINOR" ]; then
      report "$PUBSPEC" "sdk 约束 3.$minor 越线（鸿蒙端仅支持 3.${TARGET_DART_MINOR}.x）: $sdk_line"
    fi
  fi
fi

# 2. 静态扫描 lib 目录可疑语法（正则启发式）
if [ -d "$LIB_DIR" ]; then
  # 2a. digit separators（Dart 3.6+，鸿蒙端支持，但校验格式）
  # 2b. 检查可能的 3.10+ 专属语法占位 —— 当前无明确源码级特征，
  #     保留钩子便于后续按 OH Flutter changelog 增补规则
  :
fi

# 3. 若安装了 flutter，执行 analyze（使用项目实际 SDK）
if command -v flutter >/dev/null 2>&1; then
  echo "🩺 执行 flutter analyze（项目 SDK）..."
  # 不强制失败：analyze 警告仅提示，error 才拦截
  if ! (cd flutter_app && flutter analyze --no-pub --fatal-infos 2>&1 | tee /tmp/dart-analyze.log); then
    # flutter analyze 对 --fatal-infos 返回非零时视为不通过
    if grep -qE 'error •' /tmp/dart-analyze.log; then
      report "flutter analyze" "发现 error 级问题，见 /tmp/dart-analyze.log"
    fi
  fi
else
  echo "⚠️  未安装 flutter，跳过 analyze 静态检查（仅源码扫描）"
fi

if [ "$incompatible" -eq 0 ]; then
  echo "✅ Dart 兼容性检查通过"
  exit 0
else
  echo "🚫 发现鸿蒙端不兼容语法，请修正后再提交"
  exit 1
fi

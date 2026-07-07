#!/usr/bin/env bash
# i-home.life HarmonyOS 开发环境诊断脚本
# 适配版本: Flutter-OH 3.35.7-ohos-0.0.3
#
# 检查项:
#   1. Flutter doctor 鸿蒙支持
#   2. DEVECO_SDK_HOME 环境变量
#   3. ohpm / hvigor / node 工具链
#   4. OpenHarmony API 版本 ≥ 23
#   5. DevEco Studio 版本 ≥ 6.0.2
#   6. Java 版本 ≥ 17
#
# 用法: bash scripts/check-ohos-env.sh

# 不使用 set -e,以便输出完整诊断报告而非在第一处错误退出
PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
FLUTTER_DIR="$PROJECT_DIR/flutter_app"
DEVECO_APP="/Applications/DevEco-Studio.app"

# 版本要求
REQUIRED_DEVECO="6.0.2"
REQUIRED_JAVA=17
REQUIRED_API=23
REQUIRED_OHOS="3.35.7-ohos-0.0.3"

# 统计计数
PASS_COUNT=0
WARN_COUNT=0
FAIL_COUNT=0

# 颜色辅助函数 (纯文本,无 ANSI 转义以兼容 MatePad 终端)
mark_pass() { echo "  ✅ $1"; PASS_COUNT=$((PASS_COUNT + 1)); }
mark_warn() { echo "  ⚠️  $1"; WARN_COUNT=$((WARN_COUNT + 1)); }
mark_info() { echo "  ℹ️  $1"; }
mark_fail() { echo "  ❌ $1"; FAIL_COUNT=$((FAIL_COUNT + 1)); }

echo "╔════════════════════════════════════════════════╗"
echo "║  i-home.life  HarmonyOS 环境诊断               ║"
echo "║  目标: Flutter-OH ${REQUIRED_OHOS}        ║"
echo "╠════════════════════════════════════════════════╣"
echo ""

# ============ 1. Flutter doctor 鸿蒙支持 ============
echo "【1/6】Flutter doctor 鸿蒙支持检查"
echo "────────────────────────────────────────"
if command -v flutter >/dev/null 2>&1; then
  FLUTTER_PATH=$(command -v flutter)
  mark_info "Flutter 路径: $FLUTTER_PATH"
  FLUTTER_VER=$(flutter --version 2>/dev/null | head -1 || true)
  if [ -n "$FLUTTER_VER" ]; then
    mark_info "Flutter 版本: $FLUTTER_VER"
    if echo "$FLUTTER_VER" | grep -q "ohos-0.0.3"; then
      mark_pass "Flutter OHOS 适配版本正确 (${REQUIRED_OHOS})"
    elif echo "$FLUTTER_VER" | grep -q "ohos"; then
      mark_warn "Flutter OHOS 版本非 0.0.3 (建议切换 oh-3.35.7-dev 分支)"
    else
      mark_warn "当前 Flutter 非鸿蒙适配版本 (DevEco Studio 自带插件可绕过)"
    fi
  else
    mark_warn "flutter --version 无输出 (可能 SDK 未正确安装)"
  fi

  # flutter doctor 鸿蒙通道
  DOCTOR_OUT=$(flutter doctor -v 2>&1 || true)
  if echo "$DOCTOR_OUT" | grep -qi "harmonyos\|ohos"; then
    mark_pass "flutter doctor 检测到 HarmonyOS 工具链"
  else
    mark_info "flutter doctor 未检测到 HarmonyOS 通道 (DevEco Studio 不依赖此通道)"
  fi

  # 检查 enable-ohos
  HAS_OHOS=$(flutter config --list 2>/dev/null | grep "enable-ohos" || true)
  if [ -n "$HAS_OHOS" ]; then
    mark_pass "Flutter OHOS 插件已启用: $HAS_OHOS"
  else
    mark_info "Flutter OHOS 插件未启用 (可选,启用命令: flutter config --enable-ohos)"
  fi
else
  mark_warn "系统未找到 flutter 命令"
  mark_info "克隆命令: git clone -b oh-3.35.7-dev https://atomgit.com/openharmony-tpc/flutter_flutter.git"
  mark_info "然后将 <path>/flutter_flutter/bin 加入 PATH"
fi
echo ""

# ============ 2. DEVECO_SDK_HOME 环境变量 ============
echo "【2/6】DEVECO_SDK_HOME 环境变量检查"
echo "────────────────────────────────────────"
if [ -n "$DEVECO_SDK_HOME" ]; then
  mark_pass "DEVECO_SDK_HOME 已设置: $DEVECO_SDK_HOME"
  if [ -d "$DEVECO_SDK_HOME" ]; then
    mark_pass "目录存在"
  else
    mark_warn "目录不存在,请检查路径"
  fi
else
  mark_warn "DEVECO_SDK_HOME 未设置"
  mark_info "建议在 ~/.zshrc 添加:"
  mark_info "  export DEVECO_SDK_HOME=\"/Applications/DevEco-Studio.app/Contents/sdk\""
fi

if [ -n "$TOOL_HOME" ]; then
  mark_pass "TOOL_HOME 已设置: $TOOL_HOME"
else
  mark_warn "TOOL_HOME 未设置"
  mark_info "建议在 ~/.zshrc 添加:"
  mark_info "  export TOOL_HOME=\"/Applications/DevEco-Studio.app/Contents/tools\""
fi

if [ -n "$PUB_HOSTED_URL" ]; then
  mark_pass "PUB_HOSTED_URL 已设置: $PUB_HOSTED_URL"
else
  mark_warn "PUB_HOSTED_URL 未设置 (国内用户建议设置 pub 镜像)"
  mark_info "  export PUB_HOSTED_URL=\"https://pub.flutter-io.cn\""
fi
echo ""

# ============ 3. ohpm / hvigor / node 工具链 ============
echo "【3/6】ohpm / hvigor / node 工具链检查"
echo "────────────────────────────────────────"
DEVECO_TOOLS="$DEVECO_APP/Contents/tools"

# ohpm
OHPM_BIN=""
if command -v ohpm >/dev/null 2>&1; then
  OHPM_BIN=$(command -v ohpm)
  mark_pass "ohpm (PATH): $OHPM_BIN"
elif [ -x "$DEVECO_TOOLS/ohpm/bin/ohpm" ]; then
  OHPM_BIN="$DEVECO_TOOLS/ohpm/bin/ohpm"
  mark_pass "ohpm (DevEco): $OHPM_BIN"
else
  mark_warn "ohpm 未找到"
  mark_info "DevEco Studio 安装后应在 PATH 加入: $DEVECO_TOOLS/ohpm/bin"
fi
if [ -n "$OHPM_BIN" ]; then
  OHPM_VER=$("$OHPM_BIN" -v 2>/dev/null || true)
  [ -n "$OHPM_VER" ] && mark_info "ohpm 版本: $OHPM_VER"
fi

# hvigor
HVIGOR_BIN=""
if command -v hvigor >/dev/null 2>&1; then
  HVIGOR_BIN=$(command -v hvigor)
  mark_pass "hvigor (PATH): $HVIGOR_BIN"
elif [ -x "$DEVECO_TOOLS/hvigor/bin/hvigor" ]; then
  HVIGOR_BIN="$DEVECO_TOOLS/hvigor/bin/hvigor"
  mark_pass "hvigor (DevEco): $HVIGOR_BIN"
else
  mark_warn "hvigor 命令未找到 (项目通过 hvigor-config.json5 指向 DevEco 本地安装,可不依赖 PATH)"
fi

# hvigor 本地依赖检查 (项目约定)
HVIGOR_CFG="$FLUTTER_DIR/ohos/hvigor/hvigor-config.json5"
if [ -f "$HVIGOR_CFG" ]; then
  if grep -q "file:/Applications/DevEco-Studio.app" "$HVIGOR_CFG" 2>/dev/null; then
    mark_pass "hvigor-config.json5 已指向 DevEco Studio 本地安装 (项目约定)"
  elif grep -q "file:" "$HVIGOR_CFG" 2>/dev/null; then
    mark_pass "hvigor-config.json5 使用 file: 协议引用本地 hvigor"
  else
    mark_warn "hvigor-config.json5 未使用 file: 协议,可能引用远程依赖"
  fi
else
  mark_warn "hvigor-config.json5 不存在: $HVIGOR_CFG"
fi

# node
NODE_BIN=""
if command -v node >/dev/null 2>&1; then
  NODE_BIN=$(command -v node)
  mark_pass "node (PATH): $NODE_BIN"
elif [ -x "$DEVECO_TOOLS/node/bin/node" ]; then
  NODE_BIN="$DEVECO_TOOLS/node/bin/node"
  mark_pass "node (DevEco): $NODE_BIN"
else
  mark_warn "node 未找到"
  mark_info "DevEco Studio 自带 node,路径: $DEVECO_TOOLS/node/bin"
fi
if [ -n "$NODE_BIN" ]; then
  NODE_VER=$("$NODE_BIN" -v 2>/dev/null || true)
  [ -n "$NODE_VER" ] && mark_info "node 版本: $NODE_VER"
fi
echo ""

# ============ 4. OpenHarmony API 版本 ============
echo "【4/6】OpenHarmony API 版本检查 (要求 ≥ ${REQUIRED_API})"
echo "────────────────────────────────────────"
SDK_DIR="${DEVECO_SDK_HOME:-$DEVECO_APP/Contents/sdk}"
if [ -d "$SDK_DIR" ]; then
  mark_pass "DevEco SDK 目录存在: $SDK_DIR"
  # 在 sdk 目录下查找 openharmony 子目录
  OHOS_SDK_DIRS=$(find "$SDK_DIR" -maxdepth 4 -type d -name "openharmony" 2>/dev/null || true)
  if [ -n "$OHOS_SDK_DIRS" ]; then
    mark_pass "OpenHarmony SDK 已安装"
    API_FOUND=0
    for d in $OHOS_SDK_DIRS; do
      # 尝试读取 api-version 文件
      if [ -f "$d/api-version" ]; then
        API_VER=$(cat "$d/api-version" 2>/dev/null | head -1 || true)
        if [ -n "$API_VER" ]; then
          mark_info "API 版本: $API_VER (来自 $d/api-version)"
          if [ "$API_VER" -ge "$REQUIRED_API" ] 2>/dev/null; then
            mark_pass "API 版本符合要求 (≥ ${REQUIRED_API})"
            API_FOUND=1
          else
            mark_warn "API 版本偏低 (当前 $API_VER,要求 ≥ ${REQUIRED_API})"
            mark_info "请在 DevEco Studio: File → Settings → SDK Manager 下载 API ${REQUIRED_API}+"
          fi
        fi
      fi
    done
    # 若 api-version 文件不存在,尝试通过目录名推断
    if [ "$API_FOUND" -eq 0 ]; then
      # 查找形如 6.0.0(14) 或 api23 的目录
      if find "$SDK_DIR" -maxdepth 5 -type d 2>/dev/null | grep -qE "6\.0\.0\(1[4-9]\)|api2[3-9]"; then
        mark_pass "检测到 API ${REQUIRED_API}+ 对应的 SDK 目录"
      else
        mark_info "未找到 api-version 文件,请确认 DevEco Studio 已下载 API ${REQUIRED_API}+ SDK"
        mark_info "路径: DevEco Studio → Settings → SDK Manager"
      fi
    fi
  else
    mark_warn "OpenHarmony SDK 未找到"
    mark_info "请在 DevEco Studio 中下载 API ${REQUIRED_API}+ SDK"
  fi
else
  mark_warn "DevEco SDK 目录不存在: $SDK_DIR"
  mark_info "请安装 DevEco Studio ${REQUIRED_DEVECO} Release 及以上"
fi

# 项目 build-profile.json5 配置验证
BUILD_PROFILE="$FLUTTER_DIR/ohos/build-profile.json5"
if [ -f "$BUILD_PROFILE" ]; then
  if grep -q "6.0.0(14)" "$BUILD_PROFILE" 2>/dev/null; then
    mark_pass "build-profile.json5 targetSdkVersion = 6.0.0(14) / API ${REQUIRED_API}+"
  elif grep -q "5.0.0(12)" "$BUILD_PROFILE" 2>/dev/null; then
    mark_warn "build-profile.json5 targetSdkVersion 仍为 5.0.0(12),建议升级至 6.0.0(14)"
  fi
fi
echo ""

# ============ 5. DevEco Studio 版本 ============
echo "【5/6】DevEco Studio 版本检查 (要求 ≥ ${REQUIRED_DEVECO})"
echo "────────────────────────────────────────"
if [ -d "$DEVECO_APP" ]; then
  mark_pass "DevEco Studio 安装目录存在: $DEVECO_APP"
  # 尝试多种版本信息文件
  DEVECO_VER=""
  for vf in \
    "$DEVECO_APP/Contents/Resources/product-info.json" \
    "$DEVECO_APP/Contents/Info.plist" \
    "$DEVECO_APP/Contents/Resources/about/product-info.json"; do
    if [ -f "$vf" ]; then
      DEVECO_VER=$(grep -oE '"version"[[:space:]]*:[[:space:]]*"[0-9.]+"' "$vf" 2>/dev/null | head -1 | grep -oE '[0-9.]+' || true)
      if [ -z "$DEVECO_VER" ]; then
        # Info.plist 形式
        DEVECO_VER=$(grep -A1 "CFBundleShortVersionString" "$vf" 2>/dev/null | grep -oE '[0-9.]+' | head -1 || true)
      fi
      [ -n "$DEVECO_VER" ] && break
    fi
  done
  if [ -n "$DEVECO_VER" ]; then
    mark_info "DevEco Studio 版本: $DEVECO_VER"
    DEVECO_MAJOR=$(echo "$DEVECO_VER" | cut -d. -f1)
    DEVECO_MINOR=$(echo "$DEVECO_VER" | cut -d. -f2)
    DEVECO_PATCH=$(echo "$DEVECO_VER" | cut -d. -f3)
    REQ_MAJOR=$(echo "$REQUIRED_DEVECO" | cut -d. -f1)
    REQ_MINOR=$(echo "$REQUIRED_DEVECO" | cut -d. -f2)
    REQ_PATCH=$(echo "$REQUIRED_DEVECO" | cut -d. -f3)
    if [ -n "$DEVECO_MAJOR" ] && [ "$DEVECO_MAJOR" -gt "$REQ_MAJOR" ] 2>/dev/null \
       || { [ "$DEVECO_MAJOR" -eq "$REQ_MAJOR" ] 2>/dev/null \
            && [ "$DEVECO_MINOR" -gt "$REQ_MINOR" ] 2>/dev/null; }; then
      mark_pass "DevEco Studio 版本符合要求 (≥ ${REQUIRED_DEVECO})"
    elif [ -n "$DEVECO_MAJOR" ] && [ "$DEVECO_MAJOR" -eq "$REQ_MAJOR" ] 2>/dev/null \
         && [ "$DEVECO_MINOR" -eq "$REQ_MINOR" ] 2>/dev/null \
         && [ "${DEVECO_PATCH:-0}" -ge "${REQ_PATCH:-0}" ] 2>/dev/null; then
      mark_pass "DevEco Studio 版本符合要求 (≥ ${REQUIRED_DEVECO})"
    else
      mark_warn "DevEco Studio 版本偏低 (当前 $DEVECO_VER,要求 ≥ ${REQUIRED_DEVECO})"
      mark_info "下载: https://developer.huawei.com/consumer/cn/deveco-studio/"
    fi
  else
    mark_info "无法自动读取版本,请在 DevEco Studio 中 Help → About 确认 ≥ ${REQUIRED_DEVECO}"
  fi
else
  mark_warn "DevEco Studio 未安装 (推荐路径: $DEVECO_APP)"
  mark_info "下载: https://developer.huawei.com/consumer/cn/deveco-studio/"
  mark_info "要求版本: ${REQUIRED_DEVECO} Release 及以上"
fi
echo ""

# ============ 6. Java 版本 ============
echo "【6/6】Java 版本检查 (要求 ≥ ${REQUIRED_JAVA})"
echo "────────────────────────────────────────"
if command -v java >/dev/null 2>&1; then
  JAVA_VER_LINE=$(java -version 2>&1 | head -1 || true)
  mark_info "java: $JAVA_VER_LINE"
  JAVA_VER=$(echo "$JAVA_VER_LINE" | grep -oE '"[0-9.]+"' | tr -d '"' || true)
  if [ -n "$JAVA_VER" ]; then
    JAVA_MAJOR=$(echo "$JAVA_VER" | cut -d. -f1)
    # 兼容 1.8 老版本号格式
    if [ "$JAVA_MAJOR" = "1" ]; then
      JAVA_MAJOR=$(echo "$JAVA_VER" | cut -d. -f2)
    fi
    if [ -n "$JAVA_MAJOR" ] && [ "$JAVA_MAJOR" -ge "$REQUIRED_JAVA" ] 2>/dev/null; then
      mark_pass "Java 版本符合要求 (≥ ${REQUIRED_JAVA})"
    else
      mark_warn "Java 版本偏低 (当前 $JAVA_MAJOR,要求 ≥ ${REQUIRED_JAVA})"
      mark_info "DevEco Studio ${REQUIRED_DEVECO} 自带 JBR ${REQUIRED_JAVA},可直接使用 IDE 内置 JDK"
    fi
  else
    mark_warn "无法解析 java -version 输出"
  fi
else
  mark_warn "系统 java 未找到"
  mark_info "DevEco Studio ${REQUIRED_DEVECO} 自带 JBR ${REQUIRED_JAVA},可使用 IDE 内置 JDK"
  mark_info "或独立安装: brew install openjdk@17"
fi
echo ""

# ============ 项目配置一致性检查 ============
echo "【附加】项目配置一致性检查"
echo "────────────────────────────────────────"
PUBSPEC="$FLUTTER_DIR/pubspec.yaml"
if [ -f "$PUBSPEC" ]; then
  if grep -q "sdk: ^3.9.2" "$PUBSPEC" 2>/dev/null; then
    mark_pass "pubspec.yaml sdk = ^3.9.2 (匹配 Flutter 3.35.7 / Dart 3.9.2)"
  else
    mark_warn "pubspec.yaml sdk 非 ^3.9.2 (当前: $(grep '^  sdk:' "$PUBSPEC" | head -1))"
  fi
fi

APP_JSON5="$FLUTTER_DIR/ohos/AppScope/app.json5"
if [ -f "$APP_JSON5" ]; then
  if grep -q "1001000" "$APP_JSON5" 2>/dev/null; then
    mark_pass "app.json5 versionCode = 1001000"
  else
    mark_warn "app.json5 versionCode 非 1001000"
  fi
  if grep -q "minAPIVersion" "$APP_JSON5" 2>/dev/null; then
    mark_pass "app.json5 minAPIVersion 已设置"
  else
    mark_warn "app.json5 未设置 minAPIVersion"
  fi
fi

ENTRY_OHPKG="$FLUTTER_DIR/ohos/entry/oh-package.json5"
if [ -f "$ENTRY_OHPKG" ]; then
  if grep -q "modelVersion" "$ENTRY_OHPKG" 2>/dev/null; then
    mark_pass "entry/oh-package.json5 已包含 modelVersion"
  else
    mark_warn "entry/oh-package.json5 缺少 modelVersion"
  fi
fi
echo ""

# ============ 总结 ============
echo "╔════════════════════════════════════════════════╗"
echo "║  诊断总结                                       ║"
echo "╠════════════════════════════════════════════════╣"
echo "  ✅ 通过: $PASS_COUNT"
echo "  ⚠️  警告: $WARN_COUNT"
echo "  ❌ 失败: $FAIL_COUNT"
echo ""

if [ "$FAIL_COUNT" -gt 0 ]; then
  echo "  ❌ 存在失败项,请先解决再进行构建"
elif [ "$WARN_COUNT" -gt 0 ]; then
  echo "  ⚠️  存在警告项,部分功能可能受限"
  echo "     多数警告可通过 DevEco Studio IDE 内置工具链绕过"
else
  echo "  🎉 环境完全就绪,可以执行: bash scripts/deploy-ohos.sh"
fi
echo ""
echo "  📖 升级指南: flutter_app/OHOS_UPGRADE_GUIDE.md"
echo "  📦 部署脚本: bash scripts/deploy-ohos.sh"
echo "╚════════════════════════════════════════════════╝"

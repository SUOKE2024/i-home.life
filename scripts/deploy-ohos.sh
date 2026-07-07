#!/usr/bin/env bash
# i-home.life HarmonyOS HAP 构建部署脚本
#
# 适配版本: Flutter-OH 3.35.7-ohos-0.0.3
# 配套要求: DevEco Studio 6.0.2 Release / Java 17 / OpenHarmony API 23+
#
# 重要说明:
#   - 项目约定不使用 Docker
#   - Flutter OHOS SDK 与 Dart SDK 版本差异较大时,
#     标准 `flutter build hap` 可能失败
#   - 推荐使用 DevEco Studio 进行编译(项目根 flutter_app/ohos/)
#   - hvigor 配置已指向 DevEco Studio 本地安装路径

set -e

PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
FLUTTER_DIR="$PROJECT_DIR/flutter_app"
DEVECO_APP="/Applications/DevEco-Studio.app"
HDC="$DEVECO_APP/Contents/sdk/default/openharmony/toolchains/hdc"

# 版本要求
REQUIRED_DEVECO_MAJOR=6
REQUIRED_DEVECO_MINOR=0
REQUIRED_DEVECO_PATCH=2
REQUIRED_JAVA_MAJOR=17
REQUIRED_API_LEVEL=23
REQUIRED_OHOS_VERSION="3.35.7-ohos-0.0.3"

echo "╔════════════════════════════════════════════════╗"
echo "║  i-home.life  HarmonyOS 部署脚本               ║"
echo "║  适配: Flutter-OH ${REQUIRED_OHOS_VERSION}        ║"
echo "╠════════════════════════════════════════════════╣"

# 1. 环境检查
echo ""
echo "  [1/6] 检查 HarmonyOS 环境..."

# 1.1 DevEco Studio 版本检查
if [ -d "$DEVECO_APP" ]; then
  echo "  ✅ DevEco Studio 安装目录: $DEVECO_APP"
  # 尝试读取版本信息
  DEVECO_VER_FILE="$DEVECO_APP/Contents/Resources/product-info.json"
  if [ -f "$DEVECO_VER_FILE" ]; then
    DEVECO_VER=$(grep -oE '"version"[[:space:]]*:[[:space:]]*"[0-9.]+"' "$DEVECO_VER_FILE" 2>/dev/null | head -1 | grep -oE '[0-9.]+' || true)
    if [ -n "$DEVECO_VER" ]; then
      echo "  ✅ DevEco Studio 版本: $DEVECO_VER"
      DEVECO_MAJOR=$(echo "$DEVECO_VER" | cut -d. -f1)
      DEVECO_MINOR=$(echo "$DEVECO_VER" | cut -d. -f2)
      DEVECO_PATCH=$(echo "$DEVECO_VER" | cut -d. -f3)
      if [ -n "$DEVECO_MAJOR" ] && [ "$DEVECO_MAJOR" -gt "$REQUIRED_DEVECO_MAJOR" ] 2>/dev/null \
         || { [ "$DEVECO_MAJOR" -eq "$REQUIRED_DEVECO_MAJOR" ] 2>/dev/null \
              && [ "$DEVECO_MINOR" -gt "$REQUIRED_DEVECO_MINOR" ] 2>/dev/null; }; then
        echo "  ✅ DevEco Studio 版本符合要求 (≥ ${REQUIRED_DEVECO_MAJOR}.${REQUIRED_DEVECO_MINOR}.${REQUIRED_DEVECO_PATCH})"
      elif [ -n "$DEVECO_MAJOR" ] && [ "$DEVECO_MAJOR" -eq "$REQUIRED_DEVECO_MAJOR" ] 2>/dev/null \
           && [ "$DEVECO_MINOR" -eq "$REQUIRED_DEVECO_MINOR" ] 2>/dev/null \
           && [ "${DEVECO_PATCH:-0}" -ge "$REQUIRED_DEVECO_PATCH" ] 2>/dev/null; then
        echo "  ✅ DevEco Studio 版本符合要求 (≥ ${REQUIRED_DEVECO_MAJOR}.${REQUIRED_DEVECO_MINOR}.${REQUIRED_DEVECO_PATCH})"
      else
        echo "  ⚠️  DevEco Studio 版本偏低,建议升级至 ${REQUIRED_DEVECO_MAJOR}.${REQUIRED_DEVECO_MINOR}.${REQUIRED_DEVECO_PATCH} Release 及以上"
      fi
    fi
  else
    echo "  ℹ️  无法读取 DevEco Studio 版本文件,请在 IDE 中 Help → About 确认 ≥ ${REQUIRED_DEVECO_MAJOR}.${REQUIRED_DEVECO_MINOR}.${REQUIRED_DEVECO_PATCH}"
  fi
else
  echo "  ⚠️  DevEco Studio 未安装 (推荐路径: $DEVECO_APP)"
  echo "     下载: https://developer.huawei.com/consumer/cn/deveco-studio/"
  echo "     要求版本: ${REQUIRED_DEVECO_MAJOR}.${REQUIRED_DEVECO_MINOR}.${REQUIRED_DEVECO_PATCH} Release 及以上"
fi

# 1.2 Java 版本检查
if command -v java >/dev/null 2>&1; then
  JAVA_VER=$(java -version 2>&1 | head -1 | grep -oE '"[0-9.]+"' | tr -d '"' || true)
  if [ -n "$JAVA_VER" ]; then
    JAVA_MAJOR=$(echo "$JAVA_VER" | cut -d. -f1)
    # 兼容 1.8 老版本号格式
    if [ "$JAVA_MAJOR" = "1" ]; then
      JAVA_MAJOR=$(echo "$JAVA_VER" | cut -d. -f2)
    fi
    echo "  ✅ Java: $JAVA_VER"
    if [ "$JAVA_MAJOR" -ge "$REQUIRED_JAVA_MAJOR" ] 2>/dev/null; then
      echo "  ✅ Java 版本符合要求 (≥ ${REQUIRED_JAVA_MAJOR})"
    else
      echo "  ⚠️  Java 版本偏低 (当前 $JAVA_MAJOR,要求 ≥ ${REQUIRED_JAVA_MAJOR}),DevEco Studio 6.0.2 自带 JBR 17"
    fi
  fi
else
  echo "  ℹ️  系统 java 未找到 (DevEco Studio 6.0.2 自带 JBR ${REQUIRED_JAVA_MAJOR},可跳过)"
fi

# 1.3 Flutter OHOS 版本检查
if command -v flutter >/dev/null 2>&1; then
  FLUTTER_VER=$(flutter --version 2>/dev/null | head -1)
  echo "  ✅ Flutter: $FLUTTER_VER"
  if echo "$FLUTTER_VER" | grep -q "ohos-0.0.3"; then
    echo "  ✅ Flutter OHOS 适配版本正确 (${REQUIRED_OHOS_VERSION})"
  elif echo "$FLUTTER_VER" | grep -q "ohos"; then
    echo "  ⚠️  Flutter OHOS 版本非 0.0.3,建议切换到 oh-3.35.7-dev 分支"
  else
    echo "  ℹ️  当前 flutter 非鸿蒙适配版本 (DevEco Studio 自带 Flutter 插件,可跳过命令行构建)"
  fi
  HAS_OHOS=$(flutter config --list 2>/dev/null | grep "enable-ohos" || true)
  if [ -n "$HAS_OHOS" ]; then
    echo "  ✅ Flutter OHOS 已启用"
  else
    echo "  ℹ️  Flutter OHOS 插件未启用 (可选,DevEco Studio 不依赖此插件)"
  fi
else
  echo "  ℹ️  系统 flutter 未找到 (DevEco Studio 自带 Flutter 插件,可跳过)"
fi

# 1.4 OpenHarmony API 版本检查
SDK_DIR="$DEVECO_APP/Contents/sdk"
if [ -d "$SDK_DIR" ]; then
  # 查找 openharmony sdk 版本目录
  API_DIRS=$(find "$SDK_DIR" -maxdepth 3 -type d -name "openharmony" 2>/dev/null || true)
  if [ -n "$API_DIRS" ]; then
    echo "  ✅ OpenHarmony SDK 已安装"
    # 尝试读取 api 版本
    for d in $API_DIRS; do
      if [ -f "$d/api-version" ]; then
        API_VER=$(cat "$d/api-version" 2>/dev/null | head -1 || true)
        if [ -n "$API_VER" ]; then
          echo "  ✅ OpenHarmony API: $API_VER"
          if [ "$API_VER" -ge "$REQUIRED_API_LEVEL" ] 2>/dev/null; then
            echo "  ✅ API 版本符合要求 (≥ ${REQUIRED_API_LEVEL})"
          else
            echo "  ⚠️  API 版本偏低 (当前 $API_VER,要求 ≥ ${REQUIRED_API_LEVEL})"
            echo "     请在 DevEco Studio: File → Settings → SDK Manager 下载 API ${REQUIRED_API_LEVEL}+"
          fi
        fi
      fi
    done
  else
    echo "  ⚠️  OpenHarmony SDK 未找到,请在 DevEco Studio 中下载 API ${REQUIRED_API_LEVEL}+"
  fi
else
  echo "  ℹ️  DevEco SDK 目录不存在 ($SDK_DIR)"
fi

# 2. ohpm 依赖检查
echo ""
echo "  [2/6] 检查 ohos 依赖..."
OHPKG="$FLUTTER_DIR/ohos/oh-package.json5"
HVIGOR_CFG="$FLUTTER_DIR/ohos/hvigor/hvigor-config.json5"
BUILD_PROFILE="$FLUTTER_DIR/ohos/build-profile.json5"

if [ -f "$OHPKG" ]; then
  echo "  ✅ oh-package.json5 存在"
  # 验证未包含禁止的远程依赖
  if grep -q "@ohos/hvigor" "$OHPKG" && ! grep -q "file:" "$OHPKG"; then
    echo "  ⚠️  oh-package.json5 引用了远程 @ohos/hvigor,应改为 file: 协议或删除"
  fi
fi
if [ -f "$HVIGOR_CFG" ]; then
  echo "  ✅ hvigor-config.json5 存在"
  if grep -q "hvigor_dir" "$HVIGOR_CFG" 2>/dev/null || grep -q "file:" "$HVIGOR_CFG"; then
    echo "  ✅ hvigor 已指向本地 DevEco Studio 安装"
  fi
fi
if [ -f "$BUILD_PROFILE" ]; then
  echo "  ✅ build-profile.json5 存在"
  if grep -q "6.0.0(14)" "$BUILD_PROFILE" 2>/dev/null; then
    echo "  ✅ targetSdkVersion 已升级至 6.0.0(14) / API ${REQUIRED_API_LEVEL}+"
  elif grep -q "5.0.0(12)" "$BUILD_PROFILE" 2>/dev/null; then
    echo "  ⚠️  targetSdkVersion 仍为 5.0.0(12),建议升级至 6.0.0(14)"
  fi
fi

# 3. 尝试构建
echo ""
echo "  [3/6] 构建 HarmonyOS HAP..."
BUILD_MODE="${1:-debug}"

# 优先尝试 DevEco Studio 命令行
if [ -x "$DEVECO_APP/Contents/bin/devecostudio" ]; then
  echo "  🔨 使用 DevEco Studio 命令行编译 ($BUILD_MODE)..."
  cd "$FLUTTER_DIR/ohos"
  if "$DEVECO_APP/Contents/bin/devecostudio" --build "$BUILD_MODE" 2>&1; then
    echo "  ✅ DevEco Studio 构建成功"
  else
    echo "  ⚠️  DevEco Studio 命令行构建失败,请尝试在 IDE 中手动构建"
  fi
elif command -v flutter >/dev/null 2>&1; then
  echo "  🔨 尝试 flutter build hap ($BUILD_MODE)..."
  cd "$FLUTTER_DIR"
  flutter pub get > /dev/null 2>&1 || true
  if flutter build hap --"$BUILD_MODE" 2>&1; then
    echo "  ✅ flutter build hap 成功"
  else
    echo "  ⚠️  flutter build hap 失败 (已知问题: OHOS SDK 版本不匹配)"
    echo "     推荐: 用 DevEco Studio 打开 flutter_app/ohos/ 进行编译"
  fi
else
  echo "  ℹ️  跳过命令行构建,需在 DevEco Studio 中手动构建"
fi

# 4. 查找构建产物
echo ""
echo "  [4/6] 查找构建产物..."
HAP_FILE=$(find "$FLUTTER_DIR" -name "*.hap" -not -path "*/.hvigor/*" 2>/dev/null | head -1)
if [ -n "$HAP_FILE" ]; then
  HAP_SIZE=$(ls -lh "$HAP_FILE" | awk '{print $5}')
  echo "  ✅ HAP: $HAP_FILE ($HAP_SIZE)"
else
  echo "  ⚠️  未找到 .hap 文件"
  echo "  💡 DevEco Studio 手动构建步骤:"
  echo "     1. 打开 DevEco Studio (≥ ${REQUIRED_DEVECO_MAJOR}.${REQUIRED_DEVECO_MINOR}.${REQUIRED_DEVECO_PATCH})"
  echo "     2. File → Open → $FLUTTER_DIR/ohos/"
  echo "     3. 等待 IDE 索引完成"
  echo "     4. Run → Run 'ihome_app' 或 Build → Build HAP(s)"
  echo "     5. 或在 flutter_app/ohos/ 执行: ohpm install --strict_ssl false"
fi

# 5. 部署到 MatePad
echo ""
echo "  [5/6] 部署到 HUAWEI MatePad Pro..."
if [ -x "$HDC" ]; then
  DEVICE=$("$HDC" list targets 2>/dev/null | head -1)
  if [ -n "$DEVICE" ] && [ "$DEVICE" != "[Empty]" ]; then
    echo "  ✅ MatePad 已连接: $DEVICE"
    if [ -n "$HAP_FILE" ]; then
      echo "  📦 安装 HAP..."
      if "$HDC" install "$HAP_FILE" 2>&1; then
        echo "  ✅ 安装成功"
      else
        echo "  ⚠️  安装失败,请检查签名配置 flutter_app/ohos/signing/"
      fi
    fi
  else
    echo "  ℹ️  MatePad 未连接 (请插 USB 并开启 USB 调试)"
  fi
else
  echo "  ℹ️  hdc 未找到 ($HDC)"
  echo "     手动安装: hdc install <HAP_FILE>"
fi

# 6. 完成提示
echo ""
echo "  [6/6] 完成"
echo ""
echo "  🌐 Web 工具验证 (无需安装 HAP):"
echo "     1. 启动后端: bash scripts/deploy.sh start"
echo "     2. MatePad 浏览器打开: http://<HOST_IP>:8000/docs"
echo "     3. 设计台: http://<HOST_IP>:9090/studio.html"
echo ""
echo "  📋 环境诊断: bash scripts/check-ohos-env.sh"
echo "  📖 升级指南: flutter_app/OHOS_UPGRADE_GUIDE.md"
echo ""
echo "╚════════════════════════════════════════════════╝"

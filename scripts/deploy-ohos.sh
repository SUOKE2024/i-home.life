#!/usr/bin/env bash
# i-home.life HarmonyOS HAP 构建部署脚本
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

echo "╔════════════════════════════════════════════════╗"
echo "║  i-home.life  HarmonyOS 部署脚本               ║"
echo "╠════════════════════════════════════════════════╣"

# 1. 环境检查
echo "  [1/5] 检查 HarmonyOS 环境..."

if [ -d "$DEVECO_APP" ]; then
  echo "  ✅ DevEco Studio: $DEVECO_APP"
else
  echo "  ⚠️  DevEco Studio 未安装 (推荐路径: $DEVECO_APP)"
  echo "     下载: https://developer.huawei.com/consumer/cn/deveco-studio/"
fi

if command -v flutter >/dev/null 2>&1; then
  FLUTTER_VER=$(flutter --version 2>/dev/null | head -1)
  echo "  ✅ Flutter: $FLUTTER_VER"
  HAS_OHOS=$(flutter config --list 2>/dev/null | grep "enable-ohos" || true)
  if [ -n "$HAS_OHOS" ]; then
    echo "  ✅ Flutter OHOS 已启用"
  else
    echo "  ℹ️  Flutter OHOS 插件未启用 (可选,DevEco Studio 不依赖此插件)"
  fi
else
  echo "  ℹ️  系统 flutter 未找到 (DevEco Studio 自带 Flutter 插件,可跳过)"
fi

# 2. ohpm 依赖检查
echo ""
echo "  [2/5] 检查 ohos 依赖..."
OHPKG="$FLUTTER_DIR/ohos/oh-package.json5"
HVIGOR_CFG="$FLUTTER_DIR/ohos/hvigor/hvigor-config.json5"
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

# 3. 尝试构建
echo ""
echo "  [3/5] 构建 HarmonyOS HAP..."
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
echo "  [4/5] 查找构建产物..."
HAP_FILE=$(find "$FLUTTER_DIR" -name "*.hap" -not -path "*/.hvigor/*" 2>/dev/null | head -1)
if [ -n "$HAP_FILE" ]; then
  HAP_SIZE=$(ls -lh "$HAP_FILE" | awk '{print $5}')
  echo "  ✅ HAP: $HAP_FILE ($HAP_SIZE)"
else
  echo "  ⚠️  未找到 .hap 文件"
  echo "  💡 DevEco Studio 手动构建步骤:"
  echo "     1. 打开 DevEco Studio"
  echo "     2. File → Open → $FLUTTER_DIR/ohos/"
  echo "     3. 等待 IDE 索引完成"
  echo "     4. Run → Run 'ihome_app' 或 Build → Build HAP(s)"
  echo "     5. 或在 flutter_app/ohos/ 执行: ohpm install --strict_ssl false"
fi

# 5. 部署到 MatePad
echo ""
echo "  [5/5] 部署到 HUAWEI MatePad Pro..."
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

echo ""
echo "  🌐 Web 工具验证 (无需安装 HAP):"
echo "     1. 启动后端: bash scripts/deploy.sh start"
echo "     2. MatePad 浏览器打开: http://<HOST_IP>:8000/docs"
echo "     3. 设计台: http://<HOST_IP>:9090/studio.html"
echo ""
echo "╚════════════════════════════════════════════════╝"

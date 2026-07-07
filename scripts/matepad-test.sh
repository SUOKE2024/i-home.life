#!/usr/bin/env bash
# i-home.life MatePad Pro 真机一键测试
# 用法: bash scripts/matepad-test.sh

set -e
PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
LAN_IP="${LAN_IP:-118.31.223.213}"
HOST_IP=$(ifconfig 2>/dev/null | grep "inet " | grep -v 127.0.0.1 | awk 'NR==1{print $2}')
[ -n "$HOST_IP" ] && LAN_IP="$HOST_IP"
API="http://$LAN_IP:8000"
STATIC="http://$LAN_IP:9090"
HDC="/Applications/DevEco-Studio.app/Contents/sdk/default/openharmony/toolchains/hdc"
REPORT="$PROJECT_DIR/reports/matepad-ac-$(date +%Y%m%d-%H%M%S).md"

echo "╔══════════════════════════════════════════════╗"
echo "║  i-home.life  MatePad Pro 真机测试           ║"
echo "╠══════════════════════════════════════════════╣"

# 1. 环境检查
echo ""
echo "[1/5] 环境检查"

if [ -f "$HDC" ]; then
  DEVICE=$("$HDC" list targets 2>/dev/null | head -1)
  if [ -n "$DEVICE" ]; then
    echo "  ✅ MatePad 已连接: $DEVICE"
  else
    echo "  ⚠️  MatePad 未连接 (请插 USB)"
  fi
else
  echo "  ⚠️  hdc 未找到 (跳过设备操作)"
fi

if curl -sf "$API/health" > /dev/null 2>&1; then
  echo "  ✅ 后端 API: $API"
else
  echo "  ❌ 后端未启动: bash scripts/demo-start.sh"
  exit 1
fi

if curl -sf "$STATIC/studio.html" > /dev/null 2>&1; then
  echo "  ✅ 静态服务: $STATIC"
else
  echo "  ⚠️  静态服务未启动，启动中..."
  cd "$PROJECT_DIR/web" && python3 -m http.server 9090 --bind 0.0.0.0 &
  sleep 2
fi

# 2. 自动化测试
echo ""
echo "[2/5] 自动化验收"
bash "$PROJECT_DIR/scripts/verify-ac.sh" 2>&1 | grep -E "结果|通过率|🎉" | head -3

# 3. 全链路 Demo
echo ""
echo "[3/5] 全链路 Demo"
bash "$PROJECT_DIR/scripts/e2e-demo.sh" 2>&1 | grep -E "Step|✅|🎉" | tail -15

# 4. 生成 MatePad 测试报告
cat > "$REPORT" << REPORT
# i-home.life MatePad Pro AC-8 真机测试报告

**日期**: $(date '+%Y-%m-%d %H:%M')
**设备**: HUAWEI MatePad Pro
**连接**: $($HDC list targets 2>/dev/null || echo "未知")
**LAN IP**: $LAN_IP

---

## 🌐 Web 测试 URL

在 MatePad 浏览器中打开以下 URL:

| 页面 | URL |
|------|-----|
| 🎨 设计台 | $STATIC/studio.html |
| 🏠 3D 效果图 | $STATIC/3d-viewer.html |
| 📋 API 文档 | $API/docs |
| 🖥 管理后台 | $STATIC/index.html |

---

## 📊 AC-8 性能测试矩阵

### 测试 1: studio.html (最重要)

\`\`\`
URL: $STATIC/studio.html
操作: 点击 "126㎡三室" 预设 → 查看右下角 FPS
\`\`\`

| 指标 | 目标 | 实测 | 状态 |
|------|------|------|------|
| 126㎡ 加载时间 | < 3s | _____ | ⏳ |
| 3D FPS (日光) | ≥ 30 | _____ | ⏳ |
| 3D FPS (夜间) | ≥ 30 | _____ | ⏳ |
| 3D FPS (暖光) | ≥ 30 | _____ | ⏳ |
| 矩形手指拖动 | 流畅 | _____ | ⏳ |
| 双指缩放 | 平滑 | _____ | ⏳ |
| M-Pencil 绘图 | 精准 | _____ | ⏳ |

### 测试 2: 3d-viewer.html

| 指标 | 目标 | 实测 | 状态 |
|------|------|------|------|
| 126㎡ 加载时间 | < 3s | _____ | ⏳ |
| FPS | ≥ 30 | _____ | ⏳ |
| OrbitControls 旋转 | 流畅 | _____ | ⏳ |

### 测试 3: AI 功能

| 指令 | 预期 | 实测 |
|------|------|------|
| "生成126㎡户型" | 7 间房 | _____ |
| "添加书房 3×3" | 新矩形 | _____ |
| "删除卧室" | 移除 | _____ |

---

## 🖊 M-Pencil 专项

| 操作 | 结果 |
|------|------|
| 轻触 → 线宽 | _____ px |
| 重压 → 线宽 | _____ px |
| 双击笔杆 → 切换工具 | _____ |
| 悬停 → 光标显示 | _____ |
| 倾斜 → 笔触变化 | _____ |

---

## ✅ AC-8 判定

\`\`\`
AC-8 指标: FPS ≥ 30, 200面以内

实测 FPS (126㎡): _______
判定: _______ (PASS / FAIL)

实测 FPS (160㎡): _______
判定: _______ (PASS / FAIL)
\`\`\`

---

## ⚠️ Flutter HAP 编译说明

推荐通过 DevEco Studio 编译(项目约定 hvigor 已指向本地安装):

\`\`\`bash
# 1. 打开 DevEco Studio
# 2. File → Open → flutter_app/ohos/
# 3. 等待 IDE 索引完成
# 4. Run → Run 'ihome_app'
# 5. 或 Build → Build HAP(s)
# 6. 或在 flutter_app/ohos/ 执行: ohpm install --strict_ssl false
\`\`\`

也可使用部署脚本: \`bash scripts/deploy-ohos.sh\`

---

*报告由 matepad-test.sh 自动生成*
REPORT

echo ""
echo "[4/5] 测试报告: $REPORT"

# 5. 打印 MatePad 操作指南
echo ""
echo "[5/5] 📱 请在 MatePad 上执行以下操作:"
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  Step 1: 打开设计台"
echo "    $STATIC/studio.html"
echo ""
echo "  Step 2: 加载 126㎡ 预设户型"
echo "    点击侧栏 \"126㎡ 三室\" 按钮"
echo ""
echo "  Step 3: 查看右下角 FPS 数字"
echo "    如果 ≥ 30，AC-8 PASS ✅"
echo ""
echo "  Step 4: 用 M-Pencil 画矩形"
echo "    轻触后重压，观察线宽变化"
echo ""
echo "  Step 5: 填写报告 ___ 字段"
echo "    open $REPORT"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

echo ""
echo "╚══════════════════════════════════════════════╝"

# 自动打开报告
open "$REPORT" 2>/dev/null || true

#!/bin/bash
# 性能基线采集脚本（v1.1.27）
#
# 用法:
#   bash scripts/bench-baseline.sh [--flutter]
#
# 输出:
#   reports/perf-baseline-v{VERSION}.json  — 后端 API 基线
#   reports/apk-size-v{VERSION}.json       — Flutter apk 体积（--flutter 时）
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$PROJECT_DIR"

# 从 app/config.py 读取版本号
VERSION=$(python3 -c "from app.config import get_settings; print(get_settings().app_version)")
TIMESTAMP=$(date +%Y%m%d-%H%M%S)
REPORTS_DIR="$PROJECT_DIR/reports"
mkdir -p "$REPORTS_DIR"

RUN_FLUTTER=false
[[ "${1:-}" == "--flutter" ]] && RUN_FLUTTER=true

echo "=========================================="
echo "  性能基线采集 v${VERSION}"
echo "  时间: ${TIMESTAMP}"
echo "=========================================="

# ── 1. 后端 API 基线 ──
echo ""
echo "[1/2] 后端 API 基线..."
if [[ ! -f ".venv/bin/activate" ]]; then
    echo "  WARNING: .venv 未找到，跳过后端基线"
else
    source .venv/bin/activate

    # 检查后端是否在运行
    if curl -sf http://localhost:8766/api/health > /dev/null 2>&1; then
        echo "  后端运行中，开始基准测试..."
        python3 scripts/bench-api.py \
            --url http://localhost:8766 \
            --concurrency 10 \
            --requests 50 \
            2>&1 | tee "$REPORTS_DIR/perf-baseline-v${VERSION}-${TIMESTAMP}.log"
        echo "  ✅ 后端基线已保存"
    else
        echo "  WARNING: 后端未运行 (localhost:8766)，跳过后端基线"
        echo "  启动后端: source .venv/bin/activate && python -m app.main"
    fi
fi

# ── 2. Flutter 基线（可选）──
if $RUN_FLUTTER; then
    echo ""
    echo "[2/2] Flutter 基线..."
    FLUTTER_DIR="$PROJECT_DIR/flutter_app"

    if [[ ! -d "$FLUTTER_DIR" ]]; then
        echo "  WARNING: flutter_app 目录不存在，跳过 Flutter 基线"
    else
        cd "$FLUTTER_DIR"

        # apk 体积分析
        echo "  构建 release apk 并分析体积..."
        flutter build apk --release --analyze-size \
            --out "$REPORTS_DIR/apk-size-v${VERSION}-${TIMESTAMP}.json" 2>&1 | \
            tee "$REPORTS_DIR/apk-build-v${VERSION}-${TIMESTAMP}.log"

        if [[ -f "build/app/outputs/flutter-apk/app-release.apk" ]]; then
            SIZE_MB=$(du -m build/app/outputs/flutter-apk/app-release.apk | cut -f1)
            echo "  ✅ release apk 体积: ${SIZE_MB}MB"
            echo "${SIZE_MB}" > "$REPORTS_DIR/apk-size-mb-v${VERSION}-${TIMESTAMP}.txt"
        fi

        # integration_test 性能基线（如果存在）
        if [[ -f "integration_test/perf_baseline_test.dart" ]]; then
            echo "  运行 integration_test 性能基线..."
            flutter drive --profile \
                --driver=test_driver/perf.dart \
                --target=integration_test/perf_baseline_test.dart \
                2>&1 | tee "$REPORTS_DIR/flutter-perf-v${VERSION}-${TIMESTAMP}.log" || \
                echo "  WARNING: integration_test 失败（可能是模拟器未启动）"
        fi

        cd "$PROJECT_DIR"
    fi
fi

echo ""
echo "=========================================="
echo "  基线采集完成"
echo "  报告目录: $REPORTS_DIR"
echo "=========================================="

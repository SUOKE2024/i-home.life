#!/usr/bin/env bash
# 通用版本回滚脚本（v1.8.0+）
#
# 用途：按版本号关闭该版本新增的 feature flag，使服务行为回退到上一基线
# 符合 memory 约定"所有生产改动必须配套回滚方案，先验证回滚脚本再上线"
#
# 使用方式：
#   bash scripts/rollback.sh <version> [.env.production] [--dry-run]
#   bash scripts/rollback.sh v1.3.0                     # 回滚 v1.3.0 到 .env.production
#   bash scripts/rollback.sh v1.3.0 .env.staging        # 指定环境文件
#   bash scripts/rollback.sh v1.3.0 --dry-run           # 仅打印变更不写入
#   bash scripts/rollback.sh --list                     # 列出所有支持的版本
#
# 设计原则（CLAUDE.md 协作四原则）：
#   - Simplicity First：case 加载对应版本 flag 清单，复用 update_flag 函数
#   - Surgical Changes：保留旧 rollback-v1.3.0.sh 不删（向后兼容），本脚本为通用入口
#
# 新增版本回滚支持：在 case 分支添加 version → ROLLBACK_FLAGS 映射即可
# 验证：执行后重启服务，全量 pytest 应恢复上一基线行为

set -euo pipefail

# ── 参数解析 ──
VERSION=""
ENV_FILE=".env.production"
DRY_RUN=""

while [[ $# -gt 0 ]]; do
    case "$1" in
        --dry-run)
            DRY_RUN="--dry-run"
            shift
            ;;
        --list)
            echo "支持的回滚版本："
            echo "  v1.3.0  — MCP 2026-07-28 对齐 / 缓存隔离 / AI 渲染契约 / H-IFC / MEP"
            echo "  v1.6.0  — 商业运营 Agent / PASETO 撤销列表 / lifecycle 全链路"
            echo "  v1.8.0  — project_phase / quick_install_package / board_trace_henf"
            echo "  v1.9.0  — 前沿研究第二轮 6 flag（内容标识/MCP 硬化/OTel/GBZ185/协议矩阵/记忆门控）"
            echo "  v1.10.0 — 全链路诊断（diagnostics_enabled / RUM / 慢查询治理）"
            echo "  v1.10.1 — EverMind 自进化管线（agent_case_extraction / skill_distillation / skill_evolution）"
            echo "  v1.10.2 — 自进化边界测试补全（无新 flag，复用 v1.10.1 回滚清单）"
            echo "  v1.12.0 — 智能体系统性打磨（轨迹持久化 / 编排管线 / LLM 响应缓存 / 分级路由）"
            echo "  v1.13.0 — 工具纪律（tool_argument_validation / parallel_tool_calls）"
            echo "  v1.14.1 — 全景评估修复（PASETO 撤销 Redis 化；自进化周期复用 v1.10.1 清单）"
            exit 0
            ;;
        --help|-h)
            sed -n '1,20p' "$0" | sed 's/^# \?//'
            exit 0
            ;;
        v*)
            VERSION="$1"
            shift
            ;;
        *)
            # 非 flag 参数视为 env 文件
            if [[ -z "$VERSION" ]]; then
                echo "❌ 第一个非 flag 参数应为版本号（如 v1.3.0），收到: $1" >&2
                exit 1
            fi
            ENV_FILE="$1"
            shift
            ;;
    esac
done

if [[ -z "$VERSION" ]]; then
    echo "❌ 缺少版本号参数" >&2
    echo "用法: bash scripts/rollback.sh <version> [.env.production] [--dry-run]" >&2
    echo "示例: bash scripts/rollback.sh v1.3.0 --dry-run" >&2
    echo "列表: bash scripts/rollback.sh --list" >&2
    exit 1
fi

if [[ ! -f "$ENV_FILE" ]]; then
    echo "❌ 环境文件不存在: $ENV_FILE" >&2
    exit 1
fi

# ── 版本 → 回滚 flag 清单映射 ──
# 每个版本新增的 feature flag → 回滚目标值
# 注意：只关闭"该版本新增"的 flag，不动更早版本的 flag
declare -a ROLLBACK_FLAGS
case "$VERSION" in
    v1.3.0)
        # P1 MCP 2026-07-28 对齐子开关（回退到 v1.2.9 无新端点状态）
        # P2 缓存用户隔离硬约束 / P3 AI 渲染接入契约 / P4 H-IFC / MEP
        ROLLBACK_FLAGS=(
            "MCP_DISCOVER_ENABLED=false"
            "MCP_MRTR_ENABLED=false"
            "MCP_TASKS_EXTENSION_ENABLED=false"
            "CACHE_USER_ISOLATION_STRICT=false"
            "AI_RENDER_CONTRACT_STRICT=false"
            "IFC_H_IFC_EXTENSION_ENABLED=false"
            "CONSTRUCTION_DRAWING_MEP_ENABLED=false"
        )
        ;;
    v1.6.0)
        # 商业运营 Agent 4 个 + Orchestrator + 以销定产
        # PASETO 撤销列表（v1.8.1 引入，v1.6.0 时未启用，此处显式关闭防灰度误开）
        ROLLBACK_FLAGS=(
            "GROWTH_AGENT_ENABLED=false"
            "MARKETING_AGENT_ENABLED=false"
            "COMPETITOR_RESEARCH_AGENT_ENABLED=false"
            "FINANCE_RECON_AGENT_ENABLED=false"
            "BUSINESS_OPS_ORCHESTRATOR_ENABLED=false"
            "PROCUREMENT_DEMAND_DRIVEN_ENABLED=false"
        )
        ;;
    v1.8.0)
        # v1.8.0 新增 feature flag（如有）— 当前 v1.8.0 主要是 schema 迁移，
        # 无新增 feature flag；project_phase 等为 schema 变更，回滚需 alembic downgrade
        ROLLBACK_FLAGS=()
        echo "⚠️  v1.8.0 无 feature flag 回滚项（schema 变更需 alembic downgrade）" >&2
        echo "   回滚 schema: alembic downgrade -1" >&2
        ;;
    v1.9.0)
        # 前沿研究 2026 第二轮 6 项灰度 flag（默认 false，灰度开启后回滚置 false）
        # P0 AI 内容标识 / 高 MCP 安全硬化 / 高 OTel GenAI / 高 GBZ185 身份码 /
        # 中 协议兼容矩阵 / 中 记忆冲突门控
        ROLLBACK_FLAGS=(
            "AI_CONTENT_LABELING_ENABLED=false"
            "MCP_SECURITY_HARDENING_ENABLED=false"
            "OTEL_GENAI_SEMCONV_ENABLED=false"
            "GBZ185_AGENT_CARD_ENABLED=false"
            "SMART_PROTOCOL_COMPLIANCE_ENABLED=false"
            "MEMORY_CONFLICT_GATE_ENABLED=false"
        )
        ;;
    v1.10.0)
        # v1.10.0 全链路诊断（默认 false，灰度开启后回滚置 false）
        ROLLBACK_FLAGS=(
            "DIAGNOSTICS_ENABLED=false"
            "DIAGNOSTICS_RUM_ENABLED=false"
        )
        ;;
    v1.10.1)
        # v1.10.1 EverMind 自进化管线（默认全 false，灰度开启后回滚置 false）
        ROLLBACK_FLAGS=(
            "AGENT_CASE_EXTRACTION_ENABLED=false"
            "AGENT_SKILL_DISTILLATION_ENABLED=false"
            "AGENT_SKILL_EVOLUTION_ENABLED=false"
        )
        ;;
    v1.10.2)
        # v1.10.2 自进化边界测试补全（无新 flag，复用 v1.10.1 自进化管线回滚清单）
        ROLLBACK_FLAGS=(
            "AGENT_CASE_EXTRACTION_ENABLED=false"
            "AGENT_SKILL_DISTILLATION_ENABLED=false"
            "AGENT_SKILL_EVOLUTION_ENABLED=false"
        )
        ;;
    v1.12.0)
        # v1.12.0 智能体系统性打磨（默认 true，灰度开启后回滚置 false）
        # 轨迹持久化关闭 = 零落库零开销；编排管线关闭 = 维持单意图分类路由；
        # LLM 响应缓存关闭 = 每次重复调用；分级路由关闭 = 统一全价模型
        ROLLBACK_FLAGS=(
            "AGENT_TRACE_PERSIST_ENABLED=false"
            "AGENT_ORCHESTRATION_PIPELINE_ENABLED=false"
            "LLM_RESPONSE_CACHE_ENABLED=false"
            "COST_TIERED_ROUTING_ENABLED=false"
        )
        ;;
    v1.13.0)
        # v1.13.0 工具纪律（默认 true，灰度开启后回滚置 false）
        # 参数契约校验关闭 = 恢复原样透传；并行关闭 = 恢复串行（均零回归）
        ROLLBACK_FLAGS=(
            "TOOL_ARGUMENT_VALIDATION_ENABLED=false"
            "PARALLEL_TOOL_CALLS_ENABLED=false"
        )
        ;;
    v1.14.1)
        # v1.14.1 全景评估修复（2026-08-16）
        # PASETO 撤销列表 Redis 化默认开启 → 回滚置 false（恢复进程内 dict 行为）
        # 自进化周期端点/DRAFT 试用期注入复用 v1.10.1 三 flag（关闭即回退静态行为）
        ROLLBACK_FLAGS=(
            "PASETO_REVOCATION_REDIS_ENABLED=false"
        )
        ;;
    *)
        echo "❌ 不支持的版本: $VERSION" >&2
        echo "运行 'bash scripts/rollback.sh --list' 查看支持的版本" >&2
        exit 1
        ;;
esac

# ── 空 flag 清单直接退出 ──
if [[ ${#ROLLBACK_FLAGS[@]} -eq 0 ]]; then
    echo "✅ $VERSION 无需回滚 feature flag"
    exit 0
fi

echo "=========================================="
echo "  $VERSION 通用回滚脚本"
echo "  环境文件: $ENV_FILE"
echo "  模式: ${DRY_RUN:-apply（写入）}"
echo "  回滚 flag 数: ${#ROLLBACK_FLAGS[@]}"
echo "=========================================="

# ── update_flag 函数（复用自 rollback-v1.3.0.sh）──
update_flag() {
    local flag_name="$1"
    local flag_value="$2"
    local file="$3"

    if grep -qE "^${flag_name}=" "$file"; then
        if [[ -n "$DRY_RUN" ]]; then
            echo "  [dry-run] $flag_name → $flag_value (替换)"
        else
            local tmp
            tmp="$(mktemp)"
            sed "s|^${flag_name}=.*|${flag_name}=${flag_value}|" "$file" > "$tmp" && mv "$tmp" "$file"
            echo "  ✅ $flag_name=$flag_value (已更新)"
        fi
    else
        if [[ -n "$DRY_RUN" ]]; then
            echo "  [dry-run] $flag_name → $flag_value (追加)"
        else
            echo "${flag_name}=${flag_value}" >> "$file"
            echo "  ✅ $flag_name=$flag_value (已追加)"
        fi
    fi
}

echo ""
echo "▶ 关闭 $VERSION 新增 feature flag ..."
for entry in "${ROLLBACK_FLAGS[@]}"; do
    name="${entry%%=*}"
    value="${entry##*=}"
    update_flag "$name" "$value" "$ENV_FILE"
done

echo ""
echo "=========================================="
if [[ -n "$DRY_RUN" ]]; then
    echo "  [dry-run 完成] 未写入文件，请去掉 --dry-run 实际执行"
else
    echo "  ✅ 回滚配置已写入 $ENV_FILE"
    echo ""
    echo "  ▶ 下一步：重启服务使配置生效"
    echo "    sudo systemctl restart ihome"
    echo ""
    echo "  ▶ 验证回滚后行为（应恢复上一基线）："
    echo "    source .venv/bin/activate"
    echo "    python -u -m pytest tests/ -q --timeout=60"
fi
echo "=========================================="
echo ""
echo "恢复 ${VERSION}（反向操作）：将上述 flag 反向设为 true 即可"

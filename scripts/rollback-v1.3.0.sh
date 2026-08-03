#!/usr/bin/env bash
# v1.3.0 一键回滚脚本
# 用途：关闭 v1.3.0 新增的所有 feature flag，使服务行为回退到 v1.2.9 基线
#
# 回滚范围（按 memory 约定，所有生产改动必须配套回滚方案）：
#   P1 MCP 2026-07-28 对齐        → 关闭 discover / MRTR / Tasks 子开关（保留 mcp_enabled）
#   P2 缓存用户隔离硬约束          → 关闭 cache_user_isolation_strict（回退非隔离 key 构造）
#   P3 AI 渲染接入契约             → 关闭 ai_render_contract_strict（回退到无契约降级）
#   P4 H-IFC 扩展 / 施工图 MEP     → 关闭 ifc_h_ifc_extension_enabled / construction_drawing_mep_enabled
#                                     （两者默认已 false，此处显式关闭防灰度误开）
#
# 使用方式：
#   bash scripts/rollback-v1.3.0.sh          # 在生产服务器执行
#   bash scripts/rollback-v1.3.0.sh --dry-run # 仅打印变更不写入
#
# 验证：执行后重启服务，全量 pytest 应恢复 v1.2.9 行为基线
# 恢复 v1.3.0：反向设置各 flag 为 true（见脚本末尾注释）

set -euo pipefail

ENV_FILE="${1:-.env.production}"
DRY_RUN="${2:-}"

# 支持 --dry-run 作为第一参数
if [[ "${1:-}" == "--dry-run" ]]; then
    ENV_FILE=".env.production"
    DRY_RUN="--dry-run"
fi

if [[ ! -f "$ENV_FILE" ]]; then
    echo "❌ 环境文件不存在: $ENV_FILE" >&2
    echo "用法: bash scripts/rollback-v1.3.0.sh [.env.production] [--dry-run]" >&2
    exit 1
fi

echo "=========================================="
echo "  v1.3.0 回滚脚本"
echo "  环境文件: $ENV_FILE"
echo "  模式: ${DRY_RUN:-apply（写入）}"
echo "=========================================="

# v1.3.0 新增 feature flag → 回滚目标值
# 格式：FLAG_NAME=ROLLBACK_VALUE
ROLLBACK_FLAGS=(
    # P1 MCP 2026-07-28 对齐子开关（回退到 v1.2.9 无新端点状态）
    "MCP_DISCOVER_ENABLED=false"
    "MCP_MRTR_ENABLED=false"
    "MCP_TASKS_EXTENSION_ENABLED=false"
    # P2 缓存用户隔离硬约束（回退到非 strict 模式，key 不强制含 user_id）
    "CACHE_USER_ISOLATION_STRICT=false"
    # P3 AI 渲染接入契约（回退到无契约严格模式）
    "AI_RENDER_CONTRACT_STRICT=false"
    # P4 H-IFC / MEP（两者本默认 false，显式关闭防灰度误开）
    "IFC_H_IFC_EXTENSION_ENABLED=false"
    "CONSTRUCTION_DRAWING_MEP_ENABLED=false"
)

update_flag() {
    local flag_name="$1"
    local flag_value="$2"
    local file="$3"

    if grep -qE "^${flag_name}=" "$file"; then
        # 已存在 → 原地替换
        if [[ -n "$DRY_RUN" ]]; then
            echo "  [dry-run] $flag_name → $flag_value (替换)"
        else
            # 兼容 macOS sed（不使用 -i ''）
            local tmp
            tmp="$(mktemp)"
            sed "s|^${flag_name}=.*|${flag_name}=${flag_value}|" "$file" > "$tmp" && mv "$tmp" "$file"
            echo "  ✅ $flag_name=$flag_value (已更新)"
        fi
    else
        # 不存在 → 追加
        if [[ -n "$DRY_RUN" ]]; then
            echo "  [dry-run] $flag_name → $flag_value (追加)"
        else
            echo "${flag_name}=${flag_value}" >> "$file"
            echo "  ✅ $flag_name=$flag_value (已追加)"
        fi
    fi
}

echo ""
echo "▶ 关闭 v1.3.0 新增 feature flag ..."
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
    echo "  ▶ 验证回滚后行为（应恢复 v1.2.9 基线）："
    echo "    source .venv/bin/activate"
    echo "    python -u -m pytest tests/ -q --timeout=60"
fi
echo "=========================================="
echo ""
echo "恢复 v1.3.0（反向操作）："
echo "  MCP_DISCOVER_ENABLED=true"
echo "  MCP_MRTR_ENABLED=true"
echo "  MCP_TASKS_EXTENSION_ENABLED=true"
echo "  CACHE_USER_ISOLATION_STRICT=true"
echo "  AI_RENDER_CONTRACT_STRICT=true"
echo "  # IFC_H_IFC_EXTENSION_ENABLED / CONSTRUCTION_DRAWING_MEP_ENABLED 保持 false（灰度未开）"

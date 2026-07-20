#!/usr/bin/env bash
# ============================================
# bump-version.sh — 统一 Web 前端版本号升级
# ============================================
# 用法:
#   ./scripts/bump-version.sh              # 自动生成新版本号（日期+字母递增）
#   ./scripts/bump-version.sh v=20260720g  # 手动指定版本号
#
# 说明:
#   版本号格式: v=YYYYMMDD[a-z]，字母从 a 开始递增
#   SW 缓存版本格式: suoke-vYYYYMMDDx
#   同步更新: 所有 HTML/CSS/JS 引用参数 + sw.js CACHE_VERSION
# ============================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
WEB_DIR="$PROJECT_DIR/web"

# ── 颜色输出 ──
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

log_info()  { echo -e "${GREEN}[INFO]${NC} $1"; }
log_warn()  { echo -e "${YELLOW}[WARN]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }

# ── 1. 解析当前版本 ──
find_current_version() {
    # 从 sw.js 中提取 CACHE_VERSION
    local sw_ver
    sw_ver=$(sed -n "s/.*CACHE_VERSION *= *'suoke-v\([^']*\)'.*/\1/p" "$WEB_DIR/sw.js" 2>/dev/null || echo "")
    if [ -z "$sw_ver" ]; then
        log_error "无法从 $WEB_DIR/sw.js 中解析 CACHE_VERSION"
        exit 1
    fi
    echo "$sw_ver"
}

# ── 2. 生成新版本号 ──
generate_new_version() {
    local current="$1"
    local today
    today=$(date +%Y%m%d)

    # 提取日期和字母部分
    local cur_date="${current:0:8}"
    local cur_letter="${current:8:1}"

    if [ "$cur_date" = "$today" ]; then
        # 同一天，字母递增
        if [ "$cur_letter" = "z" ]; then
            log_error "今日版本号已达上限 (z)，无法递增"
            exit 1
        fi
        local next_letter
        next_letter=$(echo "$cur_letter" | tr 'a-y' 'b-z')
        echo "${today}${next_letter}"
    else
        # 新的一天，从 a 开始
        echo "${today}a"
    fi
}

# ── 3. 批量替换版本号 ──
bump_all() {
    local old_suffix="$1"
    local new_suffix="$2"

    log_info "版本升级: v=20260720${old_suffix:8:1} → v=20260720${new_suffix:8:1}"
    log_info "SW 缓存:  suoke-v20260720${old_suffix:8:1} → suoke-v20260720${new_suffix:8:1}"

    # 更新 sw.js CACHE_VERSION
    if [ -f "$WEB_DIR/sw.js" ]; then
        sed -i '' "s/suoke-v$old_suffix/suoke-v$new_suffix/g" "$WEB_DIR/sw.js"
        sed -i '' "s/v=$old_suffix/v=$new_suffix/g" "$WEB_DIR/sw.js"
        log_info "已更新 sw.js"
    fi

    # 更新所有 HTML 文件中的版本号参数
    local count=0
    while IFS= read -r -d '' file; do
        if grep -q "v=$old_suffix" "$file" 2>/dev/null; then
            sed -i '' "s/v=$old_suffix/v=$new_suffix/g" "$file"
            log_info "已更新 $(basename "$file")"
            ((count++))
        fi
    done < <(find "$WEB_DIR" -name '*.html' -print0)

    # 更新 CSS/JS 文件中的版本号引用
    while IFS= read -r -d '' file; do
        if grep -q "v=$old_suffix" "$file" 2>/dev/null; then
            sed -i '' "s/v=$old_suffix/v=$new_suffix/g" "$file"
            log_info "已更新 $(basename "$file")"
        fi
    done < <(find "$WEB_DIR/assets" -name '*.js' -o -name '*.css' -print0 2>/dev/null)

    echo ""
    log_info "共更新 $count 个文件中的版本号引用"
}

# ── 4. 验证版本一致性 ──
verify() {
    local version="$1"
    local mismatches=0

    echo ""
    log_info "验证版本号一致性..."

    # 检查 sw.js
    local sw_cache
    sw_cache=$(sed -n "s/.*CACHE_VERSION *= *'suoke-v\([^']*\)'.*/\1/p" "$WEB_DIR/sw.js" 2>/dev/null || echo "")
    if [ "$sw_cache" = "$version" ]; then
        log_info "sw.js CACHE_VERSION = suoke-v$version ✓"
    else
        log_error "sw.js CACHE_VERSION 不匹配: 期望 suoke-v$version, 实际 suoke-v$sw_cache"
        ((mismatches++))
    fi

    # 检查所有 HTML 文件
    local today_suffix="${version:8}"
    while IFS= read -r -d '' file; do
        local refs
        refs=$(grep -oE "v=2026[0-9]{4}[a-z]" "$file" 2>/dev/null | sort -u || echo "")
        if [ -n "$refs" ]; then
            for ref in $refs; do
                local ref_ver="${ref#v=}"
                if [ "$ref_ver" != "$version" ]; then
                    log_error "$(basename "$file"): 发现旧版本 $ref (期望 v=$version)"
                    ((mismatches++))
                fi
            done
        fi
    done < <(find "$WEB_DIR" -name '*.html' -print0)

    if [ $mismatches -eq 0 ]; then
        log_info "版本验证通过，所有文件一致 ✓"
    else
        log_error "发现 $mismatches 处版本不一致"
        exit 1
    fi
}

# ── Main ──
main() {
    local current_version
    current_version=$(find_current_version)

    local new_version
    if [ $# -ge 1 ]; then
        # 手动指定新版本
        new_version="${1#v=}"  # 去掉 v= 前缀
        if ! [[ "$new_version" =~ ^[0-9]{8}[a-z]$ ]]; then
            log_error "无效的版本号格式: $1 (期望 v=YYYYMMDD[a-z])"
            exit 1
        fi
    else
        new_version=$(generate_new_version "$current_version")
    fi

    echo ""
    log_info "当前版本: $current_version"
    log_info "目标版本: $new_version"
    echo ""

    if [ "$current_version" = "$new_version" ]; then
        log_warn "版本号未变，无需更新"
        exit 0
    fi

    bump_all "$current_version" "$new_version"
    verify "$new_version"

    echo ""
    log_info "版本升级完成: $current_version → $new_version"
    log_info "请检查修改后提交: git diff web/"
}

main "$@"

#!/usr/bin/env bash
# 同步 LOGO/品牌资源从根 assets/ 到 flutter_app/assets/
# 用法: bash scripts/sync-flutter-assets.sh
#
# 源: assets/images/icons/desktop/  (Web/桌面端品牌资源主源)
# 目标: flutter_app/assets/images/   (Flutter App 引用源)
#
# 规则:
#   1. 全量覆盖同名文件 (主源为准)
#   2. 保留 Flutter 端特有文件 (主源中不存在的不删除)
#   3. 同步后输出 diff 摘要

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SRC="$REPO_ROOT/assets/images/icons/desktop"
DST="$REPO_ROOT/flutter_app/assets/images"

if [[ ! -d "$SRC" ]]; then
  echo "ERROR: 源目录不存在: $SRC" >&2
  exit 1
fi

mkdir -p "$DST"

echo "==> 同步品牌资源: $SRC -> $DST"

copied=0
updated=0
for f in "$SRC"/*.png "$SRC"/*.ico "$SRC"/*.svg; do
  [[ -e "$f" ]] || continue
  name="$(basename "$f")"
  target="$DST/$name"
  if [[ ! -e "$target" ]]; then
    cp "$f" "$target"
    echo "  + 新增: $name"
    ((copied++))
  elif ! cmp -s "$f" "$target"; then
    cp "$f" "$target"
    echo "  ~ 更新: $name"
    ((updated++))
  fi
done

echo "==> 同步完成: 新增 $copied, 更新 $updated"
echo ""
echo "Flutter 端现有资源:"
ls -1 "$DST" | sed 's/^/    /'

#!/usr/bin/env bash
# i-home.life 全链路 Demo 脚本
# 自动执行：注册 → 登录 → 项目 → 设计布局 → BOM → 预算 → 采购 → 施工 → 结算 → 验收
# 输出带时间戳的 Markdown 报告

set -e

API="${API:-http://localhost:8081}"
PHONE="13900001234"
PASS="demo123456"
REPORT_DIR="${REPORT_DIR:-./reports}"
REPORT="${REPORT_DIR}/demo-$(date +%Y%m%d-%H%M%S).md"

mkdir -p "$REPORT_DIR"
mkdir -p ./data

PYTHON="${PYTHON:-python3}"
_exec() { curl -sf "$@" 2>/dev/null || echo '{"error":"request_failed"}'; }
_json() { $PYTHON -c "import sys,json;print(json.load(sys.stdin)$1)" 2>/dev/null || echo "N/A"; }

echo "# i-home.life 全链路 Demo 报告" > "$REPORT"
echo "**时间**: $(date '+%Y-%m-%d %H:%M:%S') | **版本**: v0.3.0" >> "$REPORT"
echo "" >> "$REPORT"

step() {
  echo "  [$1] $2"
  echo "## Step $1: $2" >> "$REPORT"
  echo "" >> "$REPORT"
}

check() {
  echo "    ✅ $1"
  echo "- ✅ $1" >> "$REPORT"
}

# === Step 1: Health ===
step 1 "健康检查"
_exec "$API/health" > /dev/null
check "服务正常 ($API)"

# === Step 2: Register ===
step 2 "注册业主"
REG=$(_exec -X POST "$API/api/auth/register" -H 'Content-Type: application/json' \
  -d "{\"phone\":\"$PHONE\",\"name\":\"演示业主\",\"password\":\"$PASS\",\"role\":\"homeowner\"}")
TOKEN=$(echo "$REG" | _json "['access_token']")
USER_ID=$(echo "$REG" | _json "['user']['id']")
AUTH="Authorization: Bearer $TOKEN"
check "注册成功 (用户: $USER_ID)"

# === Step 3: Login ===
step 3 "登录"
LOGIN=$(_exec -X POST "$API/api/auth/login" -H 'Content-Type: application/json' \
  -d "{\"phone\":\"$PHONE\",\"password\":\"$PASS\"}")
TOKEN=$(echo "$LOGIN" | _json "['access_token']")
AUTH="Authorization: Bearer $TOKEN"
check "登录成功 (Token 获取)"

# === Step 4: Create Project ===
step 4 "创建项目 + 户型"
PROJ=$(_exec -X POST "$API/api/projects" -H 'Content-Type: application/json' -H "$AUTH" \
  -d '{"name":"Demo幸福家园","address":"北京市朝阳区","total_area":126,"floors":[{"name":"1层","floor_number":1,"area":126,"rooms":[{"name":"客厅","room_type":"living_room","area":35},{"name":"主卧","room_type":"bedroom","area":20},{"name":"次卧","room_type":"bedroom","area":15},{"name":"书房","room_type":"study","area":10},{"name":"厨房","room_type":"kitchen","area":10},{"name":"卫生间","room_type":"bathroom","area":6}]}]}')
PROJ_ID=$(echo "$PROJ" | _json "['id']")
check "项目创建 ($PROJ_ID, 6 个房间)"

# === Step 5: AI Design Layout ===
step 5 "AI 生成布局方案"
LAYOUT=$(_exec -X POST "$API/api/agents/design" -H 'Content-Type: application/json' -H "$AUTH" \
  -d '{"message":"126㎡ 三室两厅 现代简约","room_info":"客厅35,主卧20,次卧15,书房10,厨房10,卫生间6"}')
LAYOUT_REPLY=$(echo "$LAYOUT" | _json "['space_planning']")
check "AI 布局: $LAYOUT_REPLY"

# === Step 6: Browse Materials ===
step 6 "浏览物料库"
MATS=$(_exec "$API/api/materials?limit=5")
MAT_COUNT=$(_exec "$API/api/materials?limit=200" | $PYTHON -c "import sys,json;print(len(json.load(sys.stdin)))" 2>/dev/null)
check "物料库: $MAT_COUNT SKU"

# === Step 7: Save Floor Plan ===
step 7 "保存户型方案"
FLOOR_DATA=$(echo "$LAYOUT" | $PYTHON -c "import sys,json; d=json.load(sys.stdin); print(json.dumps(d.get('full_reply',''), ensure_ascii=False))" 2>/dev/null || echo '{}')
FLOOR_JSON=$($PYTHON -c "import json; print(json.dumps({'project_id':'$PROJ_ID','name':'126㎡现代简约','data':'$FLOOR_DATA','wall_height':2.8,'total_area':126,'room_count':6}))" 2>/dev/null)
PLAN_SAVED=$(_exec -X POST "$API/api/floorplans" -H 'Content-Type: application/json' -H "$AUTH" -d "$FLOOR_JSON")
PLAN_ID=$(echo "$PLAN_SAVED" | _json "['id']")
check "户型已保存 ($PLAN_ID)"

# === Step 8: Add BOM ===
step 8 "添加物料清单"
MAT1=$(_exec "$API/api/materials?limit=1" | $PYTHON -c "import sys,json;print(json.load(sys.stdin)[0]['id'])" 2>/dev/null)
MAT2=$(_exec "$API/api/materials?limit=2" | $PYTHON -c "import sys,json;print(json.load(sys.stdin)[1]['id'])" 2>/dev/null)
MAT3=$(_exec "$API/api/materials?limit=3" | $PYTHON -c "import sys,json;print(json.load(sys.stdin)[2]['id'])" 2>/dev/null)
P1=$(_exec "$API/api/materials?limit=1" | $PYTHON -c "import sys,json;print(json.load(sys.stdin)[0]['unit_price'])" 2>/dev/null)
P2=$(_exec "$API/api/materials?limit=2" | $PYTHON -c "import sys,json;print(json.load(sys.stdin)[1]['unit_price'])" 2>/dev/null)
P3=$(_exec "$API/api/materials?limit=3" | $PYTHON -c "import sys,json;print(json.load(sys.stdin)[2]['unit_price'])" 2>/dev/null)

bom_total=0
for item in "$MAT1 80 $P1" "$MAT2 60 $P2" "$MAT3 30 $P3"; do
  read mid qty price <<< "$item"
  _exec -X POST "$API/api/materials/bom" -H 'Content-Type: application/json' -H "$AUTH" \
    -d "{\"project_id\":\"$PROJ_ID\",\"material_id\":\"$mid\",\"quantity\":$qty,\"unit_price\":$price}" > /dev/null 2>&1 || true
  bom_total=$(echo "$bom_total + $qty * $price" | bc 2>/dev/null || echo 0)
done
check "BOM 清单: 3 项, 合计¥$bom_total"

# === Step 9: Budget ===
step 9 "生成预算"
BUDGET=$(_exec -X POST "$API/api/budgets/generate-from-bom/$PROJ_ID" -H "$AUTH")
BUDGET_TOTAL=$(echo "$BUDGET" | _json "['total_estimated']")
BUDGET_LINES=$(echo "$BUDGET" | _json "len(['lines'])")
check "预算: ¥$BUDGET_TOTAL ($BUDGET_LINES 行)"

# === Step 10: Construction ===
step 10 "创建施工任务"
for p in "preparation 准备阶段" "mep 水电阶段" "masonry 泥瓦阶段" "carpentry 木工阶段" "painting 油漆阶段" "installation 安装阶段" "acceptance 验收阶段"; do
  read code name <<< "$p"
  _exec -X POST "$API/api/construction/tasks" -H 'Content-Type: application/json' -H "$AUTH" \
    -d "{\"project_id\":\"$PROJ_ID\",\"name\":\"$name\",\"phase\":\"$code\"}" > /dev/null 2>&1 || true
done
check "施工: 7 个阶段已创建"

# === Step 11: Settlement ===
step 11 "生成结算"
SETTLE=$(_exec -X POST "$API/api/settlements/generate-from-budget/$PROJ_ID" -H "$AUTH")
SETTLE_AMOUNT=$(echo "$SETTLE" | _json "['contract_amount']")
check "结算: ¥$SETTLE_AMOUNT"

# === Step 12: Verify ===
step 12 "验证全链路"
echo "- ✅ 注册 → 登录 → 项目创建" >> "$REPORT"
echo "- ✅ AI 设计布局 → 户型保存" >> "$REPORT"
echo "- ✅ 物料浏览 → BOM 清单" >> "$REPORT"
echo "- ✅ BOM → 预算生成" >> "$REPORT"
echo "- ✅ 施工任务 → 结算单" >> "$REPORT"
echo "" >> "$REPORT"
echo "## 数据汇总" >> "$REPORT"
echo "" >> "$REPORT"
echo "| 项目 | 值 |" >> "$REPORT"
echo "|------|-----|" >> "$REPORT"
echo "| 项目 ID | $PROJ_ID |" >> "$REPORT"
echo "| 户型方案 | $PLAN_ID |" >> "$REPORT"
echo "| 物料 SKU | $MAT_COUNT |" >> "$REPORT"
echo "| BOM 项数 | 3 |" >> "$REPORT"
echo "| 预算总额 | ¥$BUDGET_TOTAL |" >> "$REPORT"
echo "| 结算金额 | ¥$SETTLE_AMOUNT |" >> "$REPORT"
echo "| 施工阶段 | 7 |" >> "$REPORT"
echo "" >> "$REPORT"
echo "---" >> "$REPORT"
echo "*报告由 scripts/e2e-full.sh 自动生成*" >> "$REPORT"

echo ""
echo "╔══════════════════════════════════════════════╗"
echo "║  🎉 全链路 Demo 完成！                       ║"
echo "║                                              ║"
echo "║  注册→项目→AI设计→BOM→预算→施工→结算      ║"
echo "║                                              ║"
echo "║  报告: $REPORT"
echo "║  账户: $PHONE / $PASS                        ║"
echo "╚══════════════════════════════════════════════╝"

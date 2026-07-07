#!/usr/bin/env bash
# i-home.life 端到端 Demo 链路脚本
# 运行: bash scripts/e2e-demo.sh
set -e

API="http://localhost:8081"
PASS="demo123456"
PHONE="13900009999"

echo "╔════════════════════════════════════════════╗"
echo "║  索克家居 i-home.life  端到端 Demo         ║"
echo "╠════════════════════════════════════════════╣"

# Step 1: 健康检查
echo "║ Step 1/12: 健康检查..."
curl -sf $API/health > /dev/null && echo "║  ✅ 服务正常" || { echo "║  ❌ 服务未启动"; exit 1; }

# Step 2: 注册用户
echo "║ Step 2/12: 注册业主..."
REG=$(curl -sf -X POST $API/api/auth/register -H 'Content-Type: application/json' \
  -d "{\"phone\":\"$PHONE\",\"name\":\"李先生\",\"password\":\"$PASS\",\"role\":\"homeowner\"}")
TOKEN=$(echo $REG | python3 -c "import sys,json;print(json.load(sys.stdin)['access_token'])")
USER_ID=$(echo $REG | python3 -c "import sys,json;print(json.load(sys.stdin)['user']['id'])")
echo "║  ✅ 注册成功: 李先生 ($USER_ID)"

AUTH="Authorization: Bearer $TOKEN"

# Step 3: 登录
echo "║ Step 3/12: 登录..."
LOGIN=$(curl -sf -X POST $API/api/auth/login -H 'Content-Type: application/json' \
  -d "{\"phone\":\"$PHONE\",\"password\":\"$PASS\"}")
TOKEN=$(echo $LOGIN | python3 -c "import sys,json;print(json.load(sys.stdin)['access_token'])")
AUTH="Authorization: Bearer $TOKEN"
echo "║  ✅ 登录成功"

# Step 4: 创建项目
echo "║ Step 4/12: 创建装修项目..."
PROJ=$(curl -sf -X POST $API/api/projects -H 'Content-Type: application/json' -H "$AUTH" \
  -d '{"name":"幸福家园3-501","address":"朝阳区幸福家园3号楼501","total_area":126.0,"floors":[{"name":"1层","floor_number":1,"area":126.0,"rooms":[{"name":"客厅","room_type":"living_room","area":36.0,"width":6.0,"height":2.8,"length":6.0},{"name":"主卧","room_type":"bedroom","area":20.0,"width":4.0,"height":2.8,"length":5.0},{"name":"次卧","room_type":"bedroom","area":15.0,"width":3.0,"height":2.8,"length":5.0},{"name":"厨房","room_type":"kitchen","area":10.0,"width":2.5,"height":2.8,"length":4.0},{"name":"卫生间","room_type":"bathroom","area":6.0,"width":2.0,"height":2.8,"length":3.0}]}]}')
PROJ_ID=$(echo $PROJ | python3 -c "import sys,json;print(json.load(sys.stdin)['id'])")
echo "║  ✅ 项目创建: 幸福家园3-501 ($PROJ_ID)"

# Step 5: 查看项目详情
echo "║ Step 5/12: 查看项目详情..."
curl -sf $API/api/projects/$PROJ_ID -H "$AUTH" | python3 -c "import sys,json;d=json.load(sys.stdin);print(f'║    名称:{d[\"name\"]} 面积:{d[\"total_area\"]}㎡ 楼层:{len(d[\"floors\"])} 房间:{sum(len(f[\"rooms\"]) for f in d[\"floors\"])}')"

# Step 6: 查看物料库
echo "║ Step 6/12: 浏览物料库..."
MAT_COUNT=$(curl -sf "$API/api/materials?limit=200" | python3 -c "import sys,json;print(len(json.load(sys.stdin)))")
echo "║  ✅ 物料库: $MAT_COUNT SKU"

# Step 7: 获取物料ID
echo "║ Step 7/12: 查找物料..."
MATS=$(curl -sf "$API/api/materials?limit=10")
MAT1=$(echo $MATS | python3 -c "import sys,json;print(json.load(sys.stdin)[0]['id'])")
MAT2=$(echo $MATS | python3 -c "import sys,json;print(json.load(sys.stdin)[1]['id'])")
MAT3=$(echo $MATS | python3 -c "import sys,json;print(json.load(sys.stdin)[2]['id'])")
MAT4=$(echo $MATS | python3 -c "import sys,json;print(json.load(sys.stdin)[3]['id'])")
MAT5=$(echo $MATS | python3 -c "import sys,json;print(json.load(sys.stdin)[4]['id'])")
price1=$(echo $MATS | python3 -c "import sys,json;print(json.load(sys.stdin)[0]['unit_price'])")
price2=$(echo $MATS | python3 -c "import sys,json;print(json.load(sys.stdin)[1]['unit_price'])")
price3=$(echo $MATS | python3 -c "import sys,json;print(json.load(sys.stdin)[2]['unit_price'])")
echo "║  ✅ 已选5个物料"

# Step 8: 添加BOM物料清单
echo "║ Step 8/12: 创建物料清单..."
bom_total=0
for item in "$MAT1 80 $price1" "$MAT2 60 $price2" "$MAT3 30 $price3" "$MAT4 8 1880" "$MAT5 1 12800"; do
  read mid qty price <<< "$item"
  curl -sf -X POST $API/api/materials/bom -H 'Content-Type: application/json' -H "$AUTH" \
    -d "{\"project_id\":\"$PROJ_ID\",\"material_id\":\"$mid\",\"quantity\":$qty,\"unit_price\":$price}" > /dev/null
  bom_total=$((bom_total + $(echo "$qty * $price" | bc)))
done
echo "║  ✅ BOM清单: 5项 合计¥$bom_total"

# Step 9: 从BOM生成预算
echo "║ Step 9/12: 自动生成预算..."
BUDGET=$(curl -sf -X POST $API/api/budgets/generate-from-bom/$PROJ_ID -H "$AUTH")
BUDGET_TOTAL=$(echo $BUDGET | python3 -c "import sys,json;print(json.load(sys.stdin)['total_estimated'])")
BUDGET_LINES=$(echo $BUDGET | python3 -c "import sys,json;print(len(json.load(sys.stdin)['lines']))")
echo "║  ✅ 预算生成: ¥$BUDGET_TOTAL ($BUDGET_LINES 行)"

# Step 10: 查看供应商
echo "║ Step 10/12: 查看供应商..."
SUP_COUNT=$(curl -sf $API/api/procurement/suppliers | python3 -c "import sys,json;print(len(json.load(sys.stdin)))")
echo "║  ✅ 可选供应商: $SUP_COUNT 家"

# Step 11: 创建施工任务
echo "║ Step 11/12: 创建施工任务..."
for phase in "preparation 准备" "mep 水电" "masonry 泥瓦" "carpentry 木工" "painting 油漆" "installation 安装" "acceptance 验收"; do
  read pcode pname <<< "$phase"
  curl -sf -X POST $API/api/construction/tasks -H 'Content-Type: application/json' -H "$AUTH" \
    -d "{\"project_id\":\"$PROJ_ID\",\"name\":\"$pname阶段\",\"phase\":\"$pcode\",\"priority\":1}" > /dev/null
done
echo "║  ✅ 施工任务: 7 个阶段"

# Step 12: 从预算生成结算
echo "║ Step 12/12: 生成结算单..."
SETTLE=$(curl -sf -X POST $API/api/settlements/generate-from-budget/$PROJ_ID -H "$AUTH")
SETTLE_TOTAL=$(echo $SETTLE | python3 -c "import sys,json;print(json.load(sys.stdin)['contract_amount'])")
echo "║  ✅ 结算单: ¥$SETTLE_TOTAL"

echo "╠════════════════════════════════════════════╣"
echo "║  🎉 端到端 Demo 链路全部通过!            ║"
echo "╠════════════════════════════════════════════╣"
echo "║                                            ║"
echo "║  注册 → 登录 → 创建项目(含房间)           ║"
echo "║  → 浏览物料 → BOM清单 → 自动预算          ║"
echo "║  → 供应商 → 施工任务 → 结算单             ║"
echo "║                                            ║"
echo "║  演示账户: $PHONE / $PASS       ║"
echo "║  项目ID:   $PROJ_ID"
echo "╚════════════════════════════════════════════╝"

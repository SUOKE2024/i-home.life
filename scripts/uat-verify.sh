#!/usr/bin/env bash
# i-home.life UAT 全量验证脚本
# 验证: 核心业务 API + 新 Agent 端点 + Feature Flags + 代码质量
set -e

API="${1:-http://118.31.223.213:8081}"
PASS=0
FAIL=0

check() {
  local label="$1" code="$2" expected="${3:-200}"
  if [ "$code" = "$expected" ]; then
    echo "  ✅ $label → $code"
    PASS=$((PASS + 1))
  elif [ "$expected" = "4xx" ] && [ "${code:0:1}" = "4" ]; then
    echo "  ✅ $label → $code (expected 4xx)"
    PASS=$((PASS + 1))
  else
    echo "  ❌ $label → $code (expected $expected)"
    FAIL=$((FAIL + 1))
  fi
}

echo "╔════════════════════════════════════════════╗"
echo "║  索克家居 v1.1.21 UAT 全量验证              ║"
echo "╠════════════════════════════════════════════╣"
echo "║  目标: $API"
echo "╠════════════════════════════════════════════╣"

# ── Phase 1: 健康检查 ──
echo "Phase 1: 健康检查"
check "health" "$(curl -s -o /dev/null -w "%{http_code}" "$API/api/health")" 200
check "health(api)" "$(curl -s -o /dev/null -w "%{http_code}" "$API/health")" 200

# ── Phase 2: 认证 ──
echo ""
echo "Phase 2: 认证"
LOGIN=$(curl -s -X POST "$API/api/auth/login" -H 'Content-Type: application/json' -d '{"phone":"13800138000","password":"123456"}')
TOKEN=$(echo "$LOGIN" | python3 -c "import sys,json; print(json.load(sys.stdin).get('access_token',''))" 2>/dev/null)
if [ -n "$TOKEN" ] && [ "$TOKEN" != "None" ]; then
  AUTH="Authorization: Bearer $TOKEN"
  echo "  ✅ login → token obtained (${TOKEN:0:16}...)"
  PASS=$((PASS + 1))
  check "me" "$(curl -s -o /dev/null -w "%{http_code}" "$API/api/auth/me" -H "$AUTH")" 200
  check "register (dup) " "$(curl -s -o /dev/null -w "%{http_code}" "$API/api/auth/register" -X POST -H 'Content-Type: application/json' -d '{"phone":"13800138000","name":"Test","password":"123456","role":"homeowner"}')" "4xx"
else
  echo "  ❌ login failed"
  FAIL=$((FAIL + 1))
fi

# ── Phase 3: 核心业务 API ──
echo ""
echo "Phase 3: 核心业务 API"
check "projects list" "$(curl -s -o /dev/null -w "%{http_code}" "$API/api/projects" -H "$AUTH")" 200
check "materials cats" "$(curl -s -o /dev/null -w "%{http_code}" "$API/api/materials/categories" -H "$AUTH")" 200
check "materials list" "$(curl -s -o /dev/null -w "%{http_code}" "$API/api/materials?limit=5" -H "$AUTH")" 200
check "crews list" "$(curl -s -o /dev/null -w "%{http_code}" "$API/api/crews" -H "$AUTH")" 200
check "workers list" "$(curl -s -o /dev/null -w "%{http_code}" "$API/api/workers" -H "$AUTH")" 200
check "points account" "$(curl -s -o /dev/null -w "%{http_code}" "$API/api/points/account" -H "$AUTH")" 200
check "notif devices" "$(curl -s -o /dev/null -w "%{http_code}" "$API/api/notifications/devices" -H "$AUTH")" 200
check "archived floorplans" "$(curl -s -o /dev/null -w "%{http_code}" "$API/api/floorplans" -X POST -H 'Content-Type: application/json' -H "$AUTH" -d '{"project_id":"test","name":"test"}')" "4xx"

# ── Phase 4: 新 Agent 端点 (v1.1.21) ──
echo ""
echo "Phase 4: 新 Agent 端点 (v1.1.21)"
AGENTS=(kitchen bathroom mep appliance furniture door-window files products identity notifications takeoff ifc-export)
for agent in "${AGENTS[@]}"; do
  # identity is admin-only, expect 403
  if [ "$agent" = "identity" ]; then
    check "agent/$agent" "$(curl -s -o /dev/null -w "%{http_code}" "$API/api/agents/$agent" -X POST -H 'Content-Type: application/json' -H "$AUTH" -d '{"message":"test"}' 2>/dev/null)" 403
  else
    check "agent/$agent" "$(curl -s -o /dev/null -w "%{http_code}" "$API/api/agents/$agent" -X POST -H 'Content-Type: application/json' -H "$AUTH" -d '{"message":"test"}' 2>/dev/null)" 200
  fi
done

# ── Phase 5: 已有 Agent 端点 ──
echo ""
echo "Phase 5: 已有 Agent 端点"
check "chat/stream" "$(curl -s -o /dev/null -w "%{http_code}" "$API/api/agents/chat/stream" -X POST -H 'Content-Type: application/json' -H "$AUTH" -d '{"message":"test","agent_type":"kitchen"}' 2>/dev/null)" 200
check "design" "$(curl -s -o /dev/null -w "%{http_code}" "$API/api/agents/design" -X POST -H 'Content-Type: application/json' -H "$AUTH" -d '{"message":"test"}' 2>/dev/null)" 200
check "budget" "$(curl -s -o /dev/null -w "%{http_code}" "$API/api/agents/budget" -X POST -H 'Content-Type: application/json' -H "$AUTH" -d '{"message":"test"}' 2>/dev/null)" 200
check "procurement" "$(curl -s -o /dev/null -w "%{http_code}" "$API/api/agents/procurement" -X POST -H 'Content-Type: application/json' -H "$AUTH" -d '{"message":"test"}' 2>/dev/null)" 200
check "construction" "$(curl -s -o /dev/null -w "%{http_code}" "$API/api/agents/construction" -X POST -H 'Content-Type: application/json' -H "$AUTH" -d '{"message":"test"}' 2>/dev/null)" 200
check "qa-inspector" "$(curl -s -o /dev/null -w "%{http_code}" "$API/api/agents/qa-inspector/defects" -X POST -H 'Content-Type: application/json' -H "$AUTH" -d '{"message":"test"}' 2>/dev/null)" 200
check "settlement" "$(curl -s -o /dev/null -w "%{http_code}" "$API/api/agents/chat" -X POST -H 'Content-Type: application/json' -H "$AUTH" -d '{"message":"结算","agent_type":"settlement"}' 2>/dev/null)" 200
check "concierge" "$(curl -s -o /dev/null -w "%{http_code}" "$API/api/agents/concierge/chat" -X POST -H 'Content-Type: application/json' -H "$AUTH" -d '{"message":"test","name":"test","phone":"13800138000"}' 2>/dev/null)" 200

# ── Phase 6: Feature Flags ──
echo ""
echo "Phase 6: Feature Flags"
FLAGS=$(curl -s "$API/api/config/feature-flags" -H "$AUTH")
if echo "$FLAGS" | python3 -c "import sys,json; d=json.load(sys.stdin); assert 'mcp_enabled' in d; assert 'ai_render_enabled' in d; assert 'voice_audio_prompt_enabled' in d; print('OK: all flags present')" 2>/dev/null; then
  echo "  ✅ all feature flags present"
  PASS=$((PASS + 1))
else
  echo "  ❌ feature flags missing"
  FAIL=$((FAIL + 1))
fi

# ── Phase 7: 代码质量 ──
echo ""
echo "Phase 7: 代码质量"
cd "$(dirname "$0")/.."
FLAKE8=$(python3 -m flake8 app/ --max-line-length=120 2>&1 | wc -l)
if [ "$FLAKE8" -eq 0 ]; then
  echo "  ✅ flake8: 0 errors"
  PASS=$((PASS + 1))
else
  echo "  ❌ flake8: $FLAKE8 errors"
  FAIL=$((FAIL + 1))
fi

# ── Summary ──
echo ""
echo "╠════════════════════════════════════════════╣"
echo "║  UAT 结果                                  ║"
echo "╠════════════════════════════════════════════╣"
echo "║  通过: $PASS                                "
if [ "$FAIL" -eq 0 ]; then
  echo "║  失败: 0                                   "
  echo "║  ✅ 全部通过 — 可发布                      ║"
else
  echo "║  失败: $FAIL                                "
  echo "║  ❌ 存在失败项                              ║"
fi
echo "╚════════════════════════════════════════════╝"
exit $FAIL

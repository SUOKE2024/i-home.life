#!/usr/bin/env bash
# =============================================================================
# 索克家居 · 施工边缘盒子端侧包一键部署（v1.4.x，借鉴 OWLFY"端侧零 TOKEN"）
#
# 场景：工地/内网/弱网环境。将低成本 AI 推理端点部署在现场边缘盒子上，
# 让 economy 档 Agent（客服/通知/积分/文件/身份）优先走本地推理：
#   - 数据不出现场（隐私/合规硬边界）
#   - 本地推理不计 token，成本归零
#   - 断网可用（离线兜底）
#
# 架构说明（守住项目红线）：
#   - 不引入 K8s/容器编排，主链路仍是阿里云 FC
#   - 本脚本仅在边缘盒子上安装 Ollama（OpenAI 兼容端点），
#     后端通过 PROVIDER_REGISTRY["local"] 接入，economy_providers="local,qwen,glm"
#   - local 未配置 key 时后端自动 fallback 到 qwen/glm（不 mock、不伪装）
#
# 用法：
#   ./scripts/edge-box/setup.sh [模型]        # 默认 qwen2.5:7b
#   EDGE_MODEL=qwen3:4b ./scripts/edge-box/setup.sh
#
# 部署后需在 .env 追加（见脚本末尾输出）：
#   LOCAL_LLM_API_KEY=ollama
#   LOCAL_LLM_API_BASE=http://<边缘盒IP>:11434/v1
#   LOCAL_LLM_MODEL=qwen2.5:7b
#   ECONOMY_PROVIDERS=local,qwen,glm
#   COST_TIERED_ROUTING_ENABLED=true
# =============================================================================
set -euo pipefail

EDGE_MODEL="${EDGE_MODEL:-qwen2.5:7b}"
OLLAMA_PORT="${OLLAMA_PORT:-11434}"
OLLAMA_HOST="${OLLAMA_HOST:-0.0.0.0}"
API_URL="http://localhost:${OLLAMA_PORT}/v1"

log() { printf '\033[1;34m[edge-box]\033[0m %s\n' "$*"; }
die() { printf '\033[1;31m[edge-box] 错误:\033[0m %s\n' "$*" >&2; exit 1; }

# ── 1. 检测并安装 Ollama ──────────────────────────────────────────────
if ! command -v ollama >/dev/null 2>&1; then
  log "未检测到 ollama，开始安装..."
  case "$(uname -s)" in
    Darwin)
      command -v brew >/dev/null 2>&1 || die "macOS 需要先安装 Homebrew: https://brew.sh"
      brew install ollama
      ;;
    Linux)
      curl -fsSL https://ollama.com/install.sh | sh || die "Ollama 安装失败，请参考 https://ollama.com/download/linux"
      ;;
    *)
      die "不支持的系统: $(uname -s)"
      ;;
  esac
else
  log "ollama 已安装: $(ollama --version)"
fi

# ── 2. 启动 Ollama 服务（监听局域网，供 App/后端访问）──────────────────
if ! curl -fsS "${API_URL}/models" >/dev/null 2>&1; then
  log "启动 ollama serve (OLLAMA_HOST=${OLLAMA_HOST}:${OLLAMA_PORT})..."
  OLLAMA_HOST="${OLLAMA_HOST}" OLLAMA_PORT="${OLLAMA_PORT}" \
    nohup ollama serve >/tmp/edge-box-ollama.log 2>&1 &
  sleep 3
  curl -fsS "${API_URL}/models" >/dev/null 2>&1 || die "ollama serve 启动失败，见 /tmp/edge-box-ollama.log"
fi
log "Ollama 服务已就绪: ${API_URL}"

# ── 3. 拉取量化小模型（可离线复用，后续断网也能推理）───────────────────
log "拉取模型 ${EDGE_MODEL}（首次约 4-8GB，请耐心等待）..."
ollama pull "${EDGE_MODEL}"

# ── 4. 冒烟验证 OpenAI 兼容端点 ────────────────────────────────────────
log "验证 /v1/chat/completions..."
curl -fsS "${API_URL}/chat/completions" \
  -H 'Content-Type: application/json' \
  -d "{\"model\":\"${EDGE_MODEL}\",\"messages\":[{\"role\":\"user\",\"content\":\"回复 OK\"}],\"stream\":false}" \
  >/dev/null 2>&1 && log "推理验证通过" || die "推理验证失败"

# ── 5. 输出后端 .env 配置片段 ──────────────────────────────────────────
cat <<EOF

====================================================
边缘盒子部署完成。请在索克家居后端 .env 追加以下配置，
然后让 economy 档 Agent 优先走本地端点：

  LOCAL_LLM_API_KEY=ollama
  LOCAL_LLM_API_BASE=${API_URL}
  LOCAL_LLM_MODEL=${EDGE_MODEL}
  ECONOMY_PROVIDERS=local,qwen,glm
  COST_TIERED_ROUTING_ENABLED=true

说明：
- LOCAL_LLM_API_KEY 必填（占位即可），未配置时后端将 local 视为
  不可用并自动 fallback 到 qwen/glm（不 mock、不伪装）。
- 断网后 economy 档仍可在本盒子上完成推理；standard 档（设计/预算/
  施工等高价值意图）继续走云端大模型，不受影响。
- 本方案不改变阿里云 FC 主链路架构。
====================================================
EOF

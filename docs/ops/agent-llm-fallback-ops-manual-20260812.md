# Agent LLM Fallback 链运维操作手册（v1.13.2）

> 更新日期：2026-08-12
> 适用：运维/排障人员
> 关联技术文档：[agent-llm-fallback-optimization-20260812.md](agent-llm-fallback-optimization-20260812.md)
> 背景：v1.13.2 修复「无 key 的 provider 直接返回 mock 中断降级链」问题，并补齐 Agent 层 LLM 密钥。

## 1. 背景速览

| 项 | 说明 |
|----|------|
| 供应商链 | deepseek（主）→ qwen → glm → doubao（economy 档 qwen/glm 优先，deepseek 兜底） |
| 核心改动 | 无 key 的 provider 抛 `ConnectionError` 跳过，不再返回 mock 中断链 |
| 新增配置 | `QWEN_API_KEY` / `GLM_API_KEY` / `DOUBAO_API_KEY` |
| 生产状态 | v1.13.1（代码已同步新逻辑），密钥：QWEN✅ GLM✅(余额不足) DOUBAO⏸(待ep接入点) |

## 2. 配置位置

生产配置：`/opt/ihome/.env`（由本地 `.env.production` 经 `deploy-remote.sh backend` 同步）

```bash
# 查看各供应商 key 是否配置（不泄露明文）
ssh root@118.31.223.213 "grep -nE 'DEEPSEEK_API_KEY|QWEN_API_KEY|GLM_API_KEY|DOUBAO_API_KEY' /opt/ihome/.env | sed 's/=.*/=***/'"
```

| 供应商 | key 字段 | 当前状态 |
|--------|---------|---------|
| DeepSeek | `DEEPSEEK_API_KEY` | ✅ 已配置（主） |
| Qwen | `QWEN_API_KEY` | ✅ 已配置（fallback 2 档） |
| GLM | `GLM_API_KEY` | ✅ 已配置但**余额不足**（智谱 code 1113），充值后生效 |
| Doubao | `DOUBAO_API_KEY` | ⏸ 未配置（需方舟控制台创建 `ep-` 推理接入点） |

## 3. 降级链行为速查

| 场景 | 修复前行为 | 修复后行为 |
|------|-----------|-----------|
| qwen 无 key（economy 档） | 返回 `[mock]` 假回复，链中断 | 抛错跳过 → 降级 glm/deepseek 真实回复 |
| 任意 provider 无 key | 返回 mock 中断 | 跳过继续 fallback |
| 整条链全部无 key | 返回 mock | 兜底返回 mock（诚实标注，不抛异常） |
| local 未配置 | 抛错 | 抛错（与其他供应商一致） |

## 4. 验证步骤

### 4.1 快速验证脚本（推荐）

本地模拟「QWEN_API_KEY 缺失」场景，验证降级链真实触发：

```bash
cd /Users/netsong/Developer/i-home.life
source .venv/bin/activate
python scripts/verify_fallback_qwen_missing.py
```

**通过标准**（日志中应出现）：

```
WARNING ... 供应商 qwen 未配置 API key，跳过降级 (error=qwen LLM endpoint not configured (API key unset))
INFO httpx: POST https://open.bigmodel.cn/... "HTTP/1.1 400 Bad Request"   ← GLM 被真实尝试
WARNING ... 供应商 glm 失败，降级到下一个
INFO httpx: POST https://api.deepseek.com/... "HTTP/1.1 200 OK"             ← deepseek 兜底成功
```

若最后一行出现 `[mock]` 而非真实回复，说明兜底逻辑异常。

### 4.2 生产实测

```bash
# 触发一次 economy 档 Agent 调用（concierge）
curl -s https://i-home.life/api/agents/chat -H "Authorization: Bearer <token>" \
  -d '{"message":"你们有售后服务吗","agent_type":"concierge"}'

# 查看降级日志
ssh root@118.31.223.213 "journalctl -u ihome --since '5 min ago' --no-pager | grep -E '供应商|降级|mock'"
```

### 4.3 单元测试回归

```bash
source .venv/bin/activate
python -m pytest tests/test_v1128_suoke_borrowed.py tests/test_cost_tier_routing.py -q
# 期望：49 passed（含 test_chat_fallback_on_no_key / test_chat_all_no_key_returns_mock）
```

## 5. 故障排查

### 5.1 症状：日志出现「API key 为空」

**旧代码特征**（修复前）：`API key 为空，返回 mock 响应 (provider=qwen)`
- 处理：确认代码已更新（grep `API key unset` 于 `/opt/ihome/app/agents/base.py`），未更新则重新部署

**新代码特征**（修复后）：`供应商 xxx 未配置 API key，跳过降级`
- 处理：属正常降级，检查该供应商 key 是否应配置（见第 2 节）

### 5.2 症状：日志出现「供应商 glm 失败，降级到下一个」

- 常见原因：GLM 余额不足（`400 Bad Request` / code 1113）
- 处理：登录智谱开放平台充值；充值后无需改配置，自动生效
- 影响：仅 glm 档不可用，deepseek/qwen 正常，无用户可见影响

### 5.3 症状：日志出现「全部供应商失败」

- 含义：链内所有有 key 的 provider 均调用失败（非无 key）
- 排查顺序：① 各供应商 key 是否过期/被禁用 ② 网络是否可达（`curl` 直连测试） ③ 账户余额
- 处理：恢复后重试；期间用户会收到 500

## 6. 配置变更操作

### 6.1 新增/修改供应商 key

1. 本地编辑 `.env.production`（如 `GLM_API_KEY=xxx`）
2. 部署：`bash scripts/deploy-remote.sh backend`
3. 验证：`ssh root@118.31.223.213 "grep GLM_API_KEY /opt/ihome/.env | sed 's/=.*/=***/'"`

### 6.2 新增 Doubao 推理接入点（待办）

1. 火山引擎方舟控制台 → 在线推理 → 创建接入点，得到 `ep-` 开头 ID
2. `.env.production` 填 `DOUBAO_API_KEY=ep-xxx`
3. 部署 + 用第 4.1 节脚本验证（将 doubao 注入后观察是否被尝试）

### 6.3 回滚

```bash
# 代码回滚
git checkout app/agents/base.py tests/test_v1128_suoke_borrowed.py
bash scripts/deploy-remote.sh backend
# 配置回滚（移除某 key）：本地 .env.production 置空 → 重新部署
```

## 7. 关键文件

| 文件 | 作用 |
|------|------|
| `/opt/ihome/app/agents/base.py` | fallback 链逻辑（线上） |
| `/Users/netsong/Developer/i-home.life/app/agents/base.py` | 本地源码 |
| `scripts/verify_fallback_qwen_missing.py` | 降级链验证脚本 |
| `scripts/deploy-remote.sh` | 远程部署脚本 |
| `docs/ops/agent-llm-fallback-optimization-20260812.md` | 技术设计文档 |

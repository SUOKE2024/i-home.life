# Agent LLM Fallback 链优化与密钥配置（v1.13.2）

> 更新日期：2026-08-12
> 适用版本：v1.13.2（当前生产 v1.13.1 已部署）
> 背景：生产日志出现 16 条 `API key 为空，返回 mock 响应 (provider=qwen)` 告警，排查发现两个问题：① Agent 层 Qwen provider 的 `QWEN_API_KEY` 未配置；② 无 key 的 provider 直接返回 mock 会中断 fallback 链，导致 economy 档请求拿到假回复而非降级到真实供应商。

## 1. 问题根因

### 1.1 `QWEN_API_KEY` 缺失

Agent 层 fallback 链（`app/agents/base.py` 的 `PROVIDER_REGISTRY`）中：

```python
"qwen": {
    "api_base": lambda: settings.qwen_api_base,
    "api_key": lambda: settings.qwen_api_key,   # ← 读取 QWEN_API_KEY 环境变量
    "model": lambda: settings.qwen_model,
    ...
}
```

而生产 `.env.production` 只有语音专用的 `QWEN_AUDIO_API_KEY`（供实时语音 WS 使用），**没有** Agent 层 `QWEN_API_KEY`。导致 qwen 档始终「无 key → mock」。

### 1.2 无 key 返回 mock 中断降级链

原逻辑（[base.py `_chat_single_provider`](file:///Users/netsong/Developer/i-home.life/app/agents/base.py)）：

```python
if not cfg["api_key"]():
    if provider == "local":
        raise ConnectionError(...)          # 仅 local 抛错
    logger.warning("... API key 为空，返回 mock 响应 ...")
    return f"[mock] {self.agent_name} 响应：API key 未配置"   # 其余直接 mock
```

**问题**：非 local 供应商无 key 时返回 mock 字符串，`_chat` 循环将其视为「成功」直接 return，**不再继续 fallback** 到链内下一个有 key 的供应商。economy 档（qwen/glm 优先）在 qwen 无 key 时，用户拿到 `[mock]` 假回复而非降级到 deepseek 真实回答。

## 2. 修复内容

### 2.1 代码改动（`app/agents/base.py`）

**`_chat_single_provider`**：无 key 统一抛 `ConnectionError`（不再返回 mock）：

```python
if not cfg["api_key"]():
    raise ConnectionError(
        f"{provider} LLM endpoint not configured (API key unset)"
    )
```

**`_chat` 循环**：捕获 `ConnectionError` 且含 `API key unset` 时跳过该 provider，继续 fallback；整条链全部无 key 时兜底返回 mock（诚实降级标注，不抛异常）：

```python
except ConnectionError as e:
    if "API key unset" in str(e):
        no_key_providers.append(provider)
        continue  # 跳过，继续 fallback
    ...
# 全链无 key → 兜底 mock
if no_key_providers and len(no_key_providers) == len(chain) and last_error is None:
    return f"[mock] {self.agent_name} 响应：API key 未配置"
raise last_error
```

**行为对比**：

| 场景 | 修复前 | 修复后 |
|------|--------|--------|
| qwen 无 key（economy 档） | 返回 mock，中断降级 | 抛错跳过 → 继续 fallback 到 deepseek |
| local 未配置 | 抛错（唯一特例） | 抛错（与其他供应商一致） |
| 整条链全部无 key | 返回 mock | 兜底返回 mock（不变） |

### 2.2 配置改动（`.env.production`）

新增 Agent 层 LLM 供应商密钥：

```bash
# Qwen（fallback 链第二档，与 QWEN_AUDIO_API_KEY 同源 DashScope key）
QWEN_API_KEY=sk-...
QWEN_API_BASE=https://dashscope.aliyuncs.com/compatible-mode/v1
QWEN_MODEL=qwen-plus

# GLM（第三档；key 有效但账户余额不足，充值后生效，失败自动降级）
GLM_API_KEY=cde4...
GLM_API_BASE=https://open.bigmodel.cn/api/paas/v4
GLM_MODEL=glm-4-plus

# Doubao（末端；暂未配置可用推理接入点，留空自动跳过）
DOUBAO_API_KEY=
DOUBAO_API_BASE=https://ark.cn-beijing.volces.com/api/v3
DOUBAO_MODEL=doubao-seed-1-6-250615
```

同步更新 `.env.production.example` 模板。

### 2.3 测试更新（`tests/test_v1128_suoke_borrowed.py`）

- `test_chat_fallback_on_no_key`：断言从「返回 mock」改为「抛 `ConnectionError`」
- 新增 `test_chat_all_no_key_returns_mock`：验证全链无 key 时 `_chat` 兜底 mock
- `test_cost_tier_routing.py` 既有断言兼容（49 项测试全通过）

## 3. 生产部署

```bash
bash scripts/deploy-remote.sh backend
```

验证：

```bash
# 服务器配置
ssh root@118.31.223.213 "grep -E 'GLM_API_KEY|DOUBAO_API_KEY|QWEN_API_KEY' /opt/ihome/.env"
# 健康检查
curl -s https://i-home.life/health
# 确认新逻辑已同步
ssh root@118.31.223.213 "grep -n 'API key unset' /opt/ihome/app/agents/base.py"
```

## 4. 验证结果

| 项 | 结果 |
|----|------|
| 本地测试（test_v1128 + test_cost_tier_routing） | 49 passed |
| `/api/agents/chat`（concierge，economy 档） | HTTP 200 真实 LLM 回复（11.7s） |
| qwen-plus 兼容端点直连 | key 有效，正常返回 |
| 生产 `API key 为空` 告警（10 分钟内） | 0 |
| 服务器 base.py 含新逻辑 | 已同步 |

## 5. 待办与回滚

- **GLM 余额不足**：key 有效（智谱 code 1113），充值后自动生效，无需改配置
- **Doubao 未配置**：需在火山方舟控制台创建推理接入点（`ep-` 开头 ID）后填入 `DOUBAO_API_KEY`
- **回滚**：`git checkout app/agents/base.py tests/test_v1128_suoke_borrowed.py`，再重新部署

## 6. 相关文档

- [Qwen 音色修复与生产部署手册](qwen-voice-fix-deploy.md)

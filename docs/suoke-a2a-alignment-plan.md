# 索克生活 A2A 协议对齐改造方案

> 编制日期：2026-09-13 ｜ 适用版本：i-home.life v1.16.0
> 目标：让 i-home.life（空间健康资产运营商）与索克生活（suoke_life）实现双向 A2A 互通，
> 承接「索克生活生态空间供应链 + 引流入口」定位。
>
> **证据纪律**：本文所有对端契约结论均标注 `文件:行号`。标注「主代理已核验」的条目由
> 主代理亲自 Read 源码确认；标注「待核验」的条目来自检索代理，落地前须复核。

---

## 一、结论先行

**可以对接，但不是「协议翻译」问题，而是「身份互信」问题。**

三个真实阻塞点（按严重度排序）：

| # | 阻塞点 | 性质 | 可否单方解决 |
|---|---|---|---|
| B1 | **鉴权令牌不互认**：i-home 令牌缺 `type:"access"` claim + 密钥材料不同 | 硬阻塞（401） | ❌ 需双方协商密钥/签发方 |
| B2 | **协议形状不同**：对端 JSON-RPC 2.0 单 method；本端 REST Task Machine | 中（适配层可解） | ✅ 本端单方可做 |
| B3 | **入站无身份证明**：对端出站不带 Authorization，peer 可任意自报 | 安全风险 | ⚠️ 本端可加固，对端不改则无法互信 |

**建议**：B2 先做（纯本端工作、零依赖、可独立验收）；B1 走「索克签发专用机器令牌」而非共享密钥；B3 本端单方面加固 + 向对端提改进项。

---

## 二、对端契约（实测）

### 2.1 JSON-RPC 层 —— 只有一个 method【主代理已核验】

`AGS/api/v1/a2a_routes.py:481-530`（`AGS` = `suoke_life/functionai_services/node-ai-inference/agents-service`）

```python
@message_router.post("")                      # :481  prefix=/a2a → POST /a2a
async def a2a_message_send(body, user=Depends(get_current_user), eco=Depends(get_eco_context)):
    if str(body.jsonrpc or "") != "2.0":  return _json_rpc_error(req_id, -32600, ...)   # :500
    if str(body.method or "").strip() != "message/send": return _json_rpc_error(-32601) # :505
    ...取 parts[] 中第一个 type=="text" 的 text，空则 -32602                            # :514-520
    agent_id = params.metadata.agent
    if agent_id not in SUOKE_AGENTS: return _json_rpc_error(-32602, ...)                # :523-530
```

- **端点**：`POST /a2a`（单端点）。`/api/v1/agents/a2a` 前缀下**只有 REST，无 JSON-RPC**。
- **method 白名单**：仅 `message/send`。`tasks/get` / `tasks/cancel` 等一律 `-32601`。
- **目标 Agent 白名单**：`SUOKE_AGENTS = ("xiaoai","xiaoke","laoke","soer")`
  （`AGS/core/a2a_protocol.py:82`，`a2a_routes.py:523` 强校验）。
- **不支持** batch（数组 body → FastAPI 422，非 JSON-RPC 错误）；不支持 notification（总回响应）。
- **错误 envelope 也走 HTTP 200**（`a2a_routes.py:474-478`）——不可用 HTTP 状态码判成败。

错误码映射：

| code | 触发 | 行号 |
|---|---|---|
| -32600 | `jsonrpc != "2.0"` | :500-504 |
| -32601 | `method != "message/send"` | :505-509 |
| -32602 | 缺 text part / `metadata.agent` 不在白名单 | :511-530 |
| -32603 | `run_agent_chat` 抛异常 | :569-575【待核验】 |
| -32000 | 回复为空 | :577-584【待核验】 |

成功 result 形状（`:595-607`【待核验】）：

```json
{"id":"task_<hex12>","status":"completed",
 "metadata":{"agent":"xiaoke","model":"<llm_provider>","trace_id":"..."},
 "artifacts":[{"name":"reply","parts":[{"type":"text","text":"..."}]}]}
```

> `status` 是**纯字符串**，非 A2A 官方 `TaskStatus` 对象；**无** `sessionId` / `contextId` /
> `history` / `kind` / `messageId`。官方规范字段大面积未实现——适配层不得假设其存在。

### 2.2 REST 任务层（可选的第二条通道）【待核验】

| 方法 + 路径 | 说明 |
|---|---|
| `POST /api/v1/agents/a2a/tasks` | body `{skill_id*, input{}, assigned_agent?, metadata?}` → **202** `{success,data:{task_id,skill_id,status,assigned_agent,created_at}}` |
| `GET /api/v1/agents/a2a/tasks/{id}` | 200 `to_public_dict()`（**剔除 metadata**）；404 |
| `GET /api/v1/agents/a2a/tasks/{id}/stream` | **SSE**（非 NDJSON），帧 `event:/id:/data:`，60s ping，终态自动断流 |
| `POST /api/v1/agents/a2a/tasks/{id}/cancel` | 终态 → 200 + `already_terminal:true`；非法流转 → **409** |

- 状态机：`submitted / working / completed / failed / canceled`（`AGS/core/a2a_task_machine.py:78-97`）。
- **任务是内存态**，TTL 默认 3600s，**服务重启即丢**——不可作为持久事实源，必须本端落库对账。
- 与 JSON-RPC 通道的关键差异：REST 可**按 `skill_id` 精确下发**；JSON-RPC 只能发自然语言走 LLM。

### 2.3 技能级直连（康养/旅居最实用的一条路）【待核验】

家居/康养/疗愈/旅居能力全部挂在 `xiaoke`，可直接 REST 调用，绕过 A2A：

| 端点 | 入参 | 对应本端场景 |
|---|---|---|
| `POST /api/v1/agents/xiaoke/healing-scene` | `user_id*`, constitution, emotion, modality | 疗愈空间 |
| `POST /api/v1/agents/xiaoke/shared-wellness-lodge` | `user_id*`, constitution, region, lodge_type | 康养小院推荐 |
| `POST /api/v1/agents/xiaoke/scene-recommendation` | `user_id`, scene(enum 6 值) | 场景推荐 |
| `POST /api/v1/agents/xiaoke/wellness-diary` | 见 `@suoke_tool` | 健康日记 |
| `POST /api/v1/agents/xiaoke/lodge-live` | 见 `@suoke_tool` | 民宿直播 |
| `POST /api/v1/agents/xiaoke/lodge-manager-registration` | 见 `@suoke_tool` | 主理人入驻 |

响应统一 `{success, data:{service_type, result, status, processing_time}, message, code}`；
`result` 是**自由 dict，无强 schema**，须按 `service_type` 分支容错解析。

入参 SSOT 是 `AGS/api/v1/routes.py` 的 `@suoke_tool(parameters=...)` 装饰器（`:9183-9199`、
`:9210-9228`、`:8928-8947`、`:9324-9326`、`:9363`、`:9393-9395`）。

### 2.4 鉴权契约【主代理已核验 —— 本节最关键】

对端 `shared/auth_client.py`：

```python
# :826-847  版本分派
parts = raw.split(".")
if parts[0].lower() == "v3": return _fail("Unsupported PASETO version")
if parts[0].lower() == "v2" and os.getenv("PASETO_ALLOW_LEGACY_V2") != "1": return _fail(...)
if purpose == "public":                       # v4.public（Ed25519）＝唯一生产主路径
    public_pem = _resolve_paseto_public_pem() or _resolve_paseto_private_pem()
    payload = _decode_paseto_v4_public_with_pyseto(raw, public_pem) or _standalone(...)
else:                                         # :848-855 legacy v4.local/v2.local 仍被接受
    key = key or _resolve_paseto_key()        # PASETO_LOCAL_KEY_HEX / SUOKE_PASETO_LOCAL_KEY_HEX
    payload = _decode_paseto_with_pyseto(raw, key)

# :880-889  用户身份入口
async def get_current_user(credentials = Depends(_security)):
    payload = verify_paseto_token(credentials.credentials, require_type="access")   # ← 强制
    if payload is None: raise HTTPException(401, "Invalid or expired token")
```

本端 `app/auth/paseto_handler.py:162-176`：

```python
payload = {"sub": user_id, "role": role, "iat": <iso>, "exp": <iso>, "jti": <uuid>}
return paseto.create(key=key, purpose="local", claims=payload)      # ← 无 "type" 字段
```

**逐条比对结论**：

| 项 | 对端要求 | 本端现状 | 是否阻塞 |
|---|---|---|---|
| PASETO 版本 | v4.public 主路径；**v4.local 仍走 legacy 分支被接受** | v4.local | ⚠️ 算法不阻塞 |
| **`type` claim** | `require_type="access"` **强制**，不符即 401 | **完全缺失** | 🔴 **硬阻塞** |
| `exp` 格式 | `_is_expired` 兼容 ISO8601 字符串与数值（`:237-262`） | ISO8601 字符串 | ✅ 不阻塞 |
| 密钥材料 | `PASETO_LOCAL_KEY_HEX` / v4.public Ed25519 公私钥 | 自有 `paseto_secret_key` | 🔴 **硬阻塞** |
| Header | `Authorization: Bearer <token>`（也接受 `paseto ` 前缀，`:819-822`） | 同 | ✅ 不阻塞 |
| 身份字段 | 读 `user.get("user_id") or user.get("sub")`（`a2a_routes.py:532`） | 只有 `sub` | ✅ 可用 |

> **修正一处常见误判**：阻塞原因**不是**「对端只认 v4.public、本端 v4.local 被拒」——
> `:848-855` 的 legacy 分支明确仍接受 v4.local。真正阻塞是
> **① 缺 `type:"access"` claim（必 401）② 两侧密钥材料不同（签名验不过）**。

### 2.5 网关接入【待核验】

- 单一入口：`@app.api_route("/proxy/{service_key}/{path:path}", methods=[GET,POST,PUT,DELETE])`
  （`GW/app.py:754-755`）；目标 URL = `route_config.json` `routes.<service_key>` + `/{path}` + query。
- `route_config.json:36` 真实条目：`"agents-service": "https://agents-service-paepcfnmds.cn-hangzhou.fcapp.run"`；
  未设 env 的键自动变 `PLACEHOLDER_*` → 503 `service_not_deployed`。
- 约束：body ≤ 20MB（超 → 413）；agents-service 超时 120s；`X-Forwarded-*` 被剥离；
  网关注入 `X-Trace-Id` + W3C `traceparent/tracestate`（本端应透传落 `agent_traces`）；
  熔断打开 → 503 `{"error":"circuit_breaker_open"}`，**须与业务 5xx 区分重试策略**。
- **无 IP 白名单、无 mTLS、无请求体签名**（grep `IP_ALLOWLIST|ALLOWED_IPS|ip_whitelist` 零命中）。
- `/.well-known/*` **不在**网关免鉴权白名单（`GW/core/proxy_auth_exempt.py:4-71`）→
  经网关访问 Agent Card 需 token；**直连 FC URL 才公开**。

### 2.6 Agent Card 与签名【主代理已核验：签名未接线】

- 生产端点返回的是 `AGS/core/a2a_agent_card.py:177-188` 的 `AgentCard`
  （字段：`agent_card_version/agent_id/name/description/version/capabilities{streaming,
  push_notifications,stateful_sessions}/skills[]/endpoints{tasks,stream,card}/
  auth{type:"bearer",scopes[]}/created_at/updated_at/metadata`），
  **与 Google A2A 官方 Card 字段名不同**（官方是 `url/provider/supportedInterfaces/
  securitySchemes/defaultInputModes`），需字段映射。
- 发现文档外层是 `{agent_card_version, agents:[...], count, updated_at}`（`:311-322`），
  **不是**官方单 card 结构。
- **签名函数存在但未接入任何端点**：全仓 grep `sign_agent_card|verify_agent_card` 仅命中
  `shared/tests/test_agent_card.py`、`test/unit/protocols/a2a_adapter_test.dart`、`CHANGELOG.md:516`
  ——**无生产调用方**。`A2A_CARD_SIGNING_KEY` 只出现在 docstring/报错文案，无 `os.getenv` 读取。
  ⇒ 对端 `/.well-known/agent.json` 与 `/agent-card.json` 当前返回**未签名卡片**。
- 签名算法（若将来接线）：HMAC-SHA256 over
  `json.dumps({k:v for k,v in card.items() if k!="signature"}, ensure_ascii=False, sort_keys=True, separators=(",",":"))`，
  `sig = base64.urlsafe_b64encode(digest).rstrip(b"=")`，写入 `signature={alg:"HS256",kid,sig}`。
- `A2A_ENABLED` 默认 **false**（`a2a_protocol.py:71`），但作用面**仅限出站** `send_task_request`
  对非 `SUOKE_AGENTS` 目标返回 None（`:575-577`）+ 管理端点 + mcp_a2a_bridge。
  **`POST /a2a` 与 REST tasks 不受该开关约束**——即对端入站始终可用。

### 2.7 生态回流护栏 eco_guard【主代理已核验】

`AGS/core/eco_guard.py:166-173`：

```python
def guard(self, text: str) -> Optional[str]:
    """生态回流护栏：仅 peer=suoke_club 时检查；命中返回拦截回复，否则 None。"""
    self._blocked_reply = None
    if self.peer != "suoke_club":
        return None                      # ← 其他任何 peer 值直接放行
    blocked = _eco_backflow_guard(text)
    ...
```

- `peer` 取自请求体 `params.metadata.peer`，**由调用方自报，无签名、无鉴权绑定 ⇒ 可伪造**。
- 词表：`shared/wellness_claim_compliance.py:36-60`（治疗/治愈/根治/防癌/抗癌/降糖/降压/消炎/控血糖…
  = prohibited；调理/祛湿/降火/清热 = caution），否定语境 8 字窗口跳过（`:100-114`）。
  **与本端 `app/services/health_claim_compliance.py` 语义同源，词表需人工比对合并。**
- 拦截响应（HTTP 200，`:182-203`）：`result.metadata.guarded = true` + 文案含免责语。
  ⇒ **本端解析必须检查 `guarded` 标志，不得把拦截文案当成模型输出**。
- 异常一律 **fail-open**（`:136-140`）；`AUDIT_HMAC_ENABLED` 默认 False（`shared/audit_integrity.py:484-505`）。
- **无白名单机制**：外部系统回流内容不经护栏、不拦截，只按自报 `peer` 记入审计。

### 2.8 出站传输（对端调本端时的行为）【主代理已核验】

`AGS/core/a2a_protocol.py:311-319`：

```python
self._session = httpx.AsyncClient(timeout=self.timeout,
    headers={"Content-Type": "application/json", "X-A2A-Agent": self.agent_id})
```

- **只有 `Content-Type` + `X-A2A-Agent` 两个头，无 Authorization、无 X-Trace-Id、无 peer 签名**。
- 目标 URL 不做拼接，直接取 `message.payload["_target_endpoint"]`（`:327-330`），
  由运行时 `register_remote_agent(endpoint=...)` 注入（`:515-549`）——
  **无持久化 peer 注册表**（grep `A2A_PEER|ECO_PEER|PEER_URL|peer_registry` 在 functionai_services 下零命中），
  全仓调用方只有测试。
- 重试最多 3 次，退避 `min(2**attempt, 8)` = 1s/2s/4s；消息 TTL 300s；心跳 30s / 90s 判 offline。
- 信任分：初值 0.5，成功 +0.05，失败 -0.1，<0.3 仅告警**不阻断**。

⇒ **对端调本端时不提供任何身份证明**。本端入站端点必须自行鉴权，不可信任 `X-A2A-Agent` 头。

---

## 三、差异矩阵

| 维度 | 索克生活 | i-home.life v1.16.0 | 差异处理 |
|---|---|---|---|
| 协议风格 | JSON-RPC 2.0（单 method）+ REST tasks | REST Task Machine（`POST /api/a2a/tasks/send`） | 适配层双向翻译 |
| method 面 | 仅 `message/send` | REST 端点，无 JSON-RPC | 本端**新增** JSON-RPC 入站端点 |
| 目标寻址 | `params.metadata.agent` ∈ 4 值白名单 | `agent_name` ∈ 23 值注册表 | 映射表 + 白名单校验 |
| 任务持久化 | 内存态，TTL 3600s，重启即丢 | `a2a_tasks` 表落库，TTL 24h | 本端为准，对端任务仅做对账 |
| Task 字段 | `task_id/skill_id/input/status/progress/output/error/assigned_agent/metadata` | `task_id/state/result/error/trace_id/evidence` | 字段映射 + `evidence` 降级为 metadata |
| 状态枚举 | `submitted/working/completed/failed/canceled` | `submitted/working/completed/failed` | 本端补 `canceled` |
| 流式 | SSE（`event/id/data`，60s ping） | 无 A2A 流式 | 出站用轮询；入站可选补 SSE |
| 鉴权 | v4.public 主 + v4.local legacy；**强制 `type:"access"`** | v4.local；**无 `type` claim** | 🔴 见 §4 B1 |
| Agent Card | 自有字段名 + 未签名 | Google A2A 风格 + AID/ACDL | 字段映射；签名作为可选增强 |
| 身份传递 | 出站无 Authorization | 入站依赖 PASETO | 🔴 见 §4 B3 |
| 合规护栏 | `eco_guard` 仅查 `peer=="suoke_club"` | `health_claim_compliance` 全量生效 | 本端**出站前自行过滤**，不依赖对端 |
| trace | 网关注入 `X-Trace-Id`/`traceparent` | `agent_traces.workflow_id`/`trace_id` | 透传落库 |

---

## 四、改造方案

### B1 鉴权互信（阻塞项，需双方协商）

**推荐方案：索克侧签发专用机器令牌（machine-to-machine token），而非共享对称密钥。**

理由：共享 `PASETO_LOCAL_KEY_HEX` 等于把索克全平台用户令牌的签发权交给本端，
一旦本端密钥泄漏即可伪造任意索克用户身份——违反最小权限，且与本端 ATH「授权可控」自述冲突。

| 方案 | 说明 | 评价 |
|---|---|---|
| **A（推荐）** 索克签发 M2M 令牌 | 索克 auth-service 为本端签发 `type:"access"` + `roles:["ecosystem_partner"]` + 短 TTL（≤15min）+ 固定 `client_id:"ihome"` 的令牌，本端只持有**刷新凭证**不持有签发密钥 | 最小权限、可撤销、可审计 |
| B 共享 v4.local 对称密钥 | 双方配同一 `PASETO_LOCAL_KEY_HEX` | ❌ 拒绝：等于交出全平台签发权 |
| C 本端改签 v4.public | 本端引入 Ed25519，索克配本端公钥 | 可行但改动大；且 CLAUDE.md 禁 JWT/JWS——PASETO v4.public 不属 JWS，不违规，但需评估 |
| D 网关内部令牌 | 走 `X-Suoke-Internal-Token`（`GW/app.py:242-254`，env `API_GATEWAY_DOWNSTREAM_INTERNAL_TOKEN`） | 仅适用于**经网关**且被当作内部服务；本端是外部生态方，语义不符 |

**无论选哪个方案，本端必须先补 `type` claim**（否则任何令牌都被 `require_type="access"` 拒）：

```python
# app/auth/paseto_handler.py::create_token
payload = {
    "sub": user_id, "role": role,
    "type": "access",          # ← 新增：对齐 suoke_life require_type="access"
    "iat": ..., "exp": ..., "jti": ...,
}
```

> ⚠️ 该改动影响本端**全部**存量令牌校验路径，须同步 `verify_token` 兼容旧令牌
> （无 `type` 字段视为 legacy 通过），并跑全量回归。属独立 PR，勿与适配层混提。

### B2 协议适配层（本端单方可做，零外部依赖）

新增 `app/services/suoke_a2a_adapter.py`（**出站**）+ `app/api/a2a_jsonrpc.py`（**入站**）。

**出站（本端 → 索克）**：

```python
async def send_to_suoke(agent_id: str, text: str, *, trace_id: str) -> SuokeA2AResult:
    # 1. agent_id 必须 ∈ SUOKE_AGENTS，否则本端先拒（省一次 401/−32602 往返）
    # 2. 文本先过 health_claim_compliance（不依赖对端 eco_guard，因其仅查 suoke_club）
    # 3. 构造 JSON-RPC envelope，peer 自报真实值 "ihome"（不伪装 suoke_club）
    body = {"jsonrpc":"2.0","id":<int>,"method":"message/send",
            "params":{"message":{"role":"user","parts":[{"type":"text","text":text}]},
                      "metadata":{"agent":agent_id,"peer":"ihome","trace_id":f"ihome:{uuid}"}}}
    # 4. POST {base}/a2a，Header: Authorization: Bearer <M2M token>
    # 5. HTTP 恒 200 → 必须解析 body：有 "error" 按 code 分支；有 "result" 取
    #    result.artifacts[0].parts[0].text，并检查 result.metadata.guarded
    # 6. 落 a2a_tasks（本端为准）+ agent_traces（透传对端 trace_id 与网关 X-Trace-Id）
```

关键实现约束：
- **HTTP 200 ≠ 成功**：错误 envelope 也返回 200（`:474-478`），必须判 `error` 字段。
- **`guarded:true` 必须识别**：那是合规拦截文案，不是模型输出；本端应标注降级原因，
  不得当成业务结果落库或展示给用户。
- **禁止伪造 peer**：不得为了绕开护栏而自报 `suoke_club`——那会让对端把本端内容
  当俱乐部回流处理，审计链失真。诚实自报 `ihome`，合规责任由本端前置过滤承担。
- 超时/重试对齐对端语义：agents-service 经网关 120s；本端设 ≤30s + 最多 2 次重试，
  熔断 503（`circuit_breaker_open`）**不重试**，与业务 5xx 区分。

**入站（索克 → 本端）**：新增 `POST /api/a2a/jsonrpc`，接受 `message/send`：
- 鉴权用本端 PASETO v4.local（对端不带 Authorization ⇒ **必须另设接入凭证**，见 B3）
- `params.metadata.agent` 映射到本端注册表（`care`/`designer`/`concierge`…），
  未知 agent 回 `-32602`（对齐对端语义）
- 返回 envelope 严格对齐对端形状（`result.artifacts[0].parts[0].text` + `metadata.trace_id`），
  使对端无需为本端写特殊解析
- 附加 `metadata.evidence`（本端证据链）——对端会忽略未知字段，不影响兼容

### B3 入站身份加固（本端单方加固 + 向对端提改进项）

对端出站**不带任何身份证明**（`:311-319` 已核验），`peer` 又可任意自报。
本端若开放入站端点，等于开放匿名调用。

本端加固（复用已落地的 ATH 握手凭证，v1.16.0）：

| 措施 | 实现 |
|---|---|
| 入站强制握手凭证 | 复用 `agent_handshake.verify_handshake_credential`，`app_id="suoke_life"`，`scope="a2a:task"`；无凭证 → 403 |
| 凭证带外分发 | 通过索克侧 `ecosystem-service` partner + API Key 通道交换（`routes.py:349-403`），不走 A2A 自身 |
| peer 不可自报 | 本端从**已验证凭证**取 `app_id` 作为 peer，忽略 body 里的 `metadata.peer` |
| 审计留痕 | 每次入站落 `agent_traces` + `a2a_tasks.evidence`（含 `handshake:"verified"`），可回放 |
| 限流 | 复用现有 per-user/IP 限流，对 `app_id="suoke_life"` 单独配额 |

**向对端提的改进项**（不阻塞本端落地）：
1. `HTTPTransport` 出站补 `Authorization` 头（凭证由 partner 通道下发）
2. `peer` 改为从已验证令牌取，不接受 body 自报
3. `eco_guard` 的 peer 白名单扩展为「所有外部生态方」，而非仅 `suoke_club`
4. `sign_agent_card` 接入 `/.well-known/*` 端点（函数已存在，仅缺接线）
5. peer → URL 注册表持久化（当前只有进程内 dict，重启即失）

---

## 五、实施顺序与验收

| 阶段 | 内容 | 外部依赖 | 验收标准 |
|---|---|---|---|
| **S0** | 本端 `create_token` 补 `type:"access"`（兼容旧令牌） | 无 | 全量 pytest 不回退；旧令牌仍可登录 |
| **S1** | 出站适配层 `suoke_a2a_adapter.py` + 单测（mock 对端） | 无 | envelope 构造/错误码分支/`guarded` 识别/合规前置过滤 全覆盖 |
| **S2** | 入站 `POST /api/a2a/jsonrpc` + 握手凭证强校验 + 单测 | 无 | 无凭证 403；合法凭证 200 且 envelope 对齐对端形状 |
| **S3** | M2M 令牌签发协商 + 联调 | 🔴 索克侧配合 | 真实调通 `POST /a2a` `metadata.agent="xiaoke"` |
| **S4** | 技能级直连（`/api/v1/agents/xiaoke/*`）接入康养/旅居场景 | 🔴 索克侧配合 | `shared-wellness-lodge` 返回真实 POI 并落本端台账 |
| **S5** | 词表合并 + 双向合规对账 | 双方 | 两侧 prohibited/caution 词表 diff 为空或差异已记录 |

S0–S2 **可立即开工，零外部依赖**；S3–S5 须先拿到索克侧配合承诺。

---

## 六、不做的事（防止范围蔓延）

1. **不实现 A2A 官方全字段**（`sessionId`/`contextId`/`history`/`TaskStatus` 对象）——
   对端未实现，本端单方实现只增加维护面，无互通收益。
2. **不引入 JSON-RPC 客户端库**——只用 `httpx` 手搓 envelope，保持模块化单体依赖面。
3. **不把对端内存态任务当事实源**——本端 `a2a_tasks` 表为准，对端 task_id 仅作对账键。
4. **不为了绕护栏伪造 peer**（见 B2 约束）。
5. **不在本端实现 v4.public 签发**，除非 S3 协商结论明确要求（方案 C）。
6. **不改动本端既有 REST A2A 端点语义**——新增 JSON-RPC 端点并存，既有 23 个 Agent 的
   `POST /api/a2a/tasks/send` 路径与字段不变。**注意**：v1.17.x 起该端点改为
   **强制 ATH 握手**（`agent_handshake_required=True` 时缺省凭证 403），既有调用方须先
   `POST /api/agents/handshake/issue` 签发凭证并携带 `app_id` + `handshake_token`；
   回滚开关 `agent_handshake_required=False` 可恢复旧放行行为。

---

## 七、风险登记

| 风险 | 等级 | 缓解 |
|---|---|---|
| 索克侧不愿签发 M2M 令牌 → S3 卡死 | 高 | S0–S2 先落地，形成「本端已就绪」既成事实再谈；同时准备方案 C（本端改 v4.public）作为备选 |
| 对端契约变更无版本协商机制 | 中 | 适配层对 result 全字段 `getattr`/`.get` 防御解析；契约测试用**录制的真实响应**做 fixture，对端变更即测试红 |
| 对端任务是内存态，重启丢任务 | 中 | 本端落库为准；对端 404 视为「任务已过期」而非错误，标注降级原因 |
| `eco_guard` fail-open + peer 可伪造 ⇒ 合规责任实际落在本端 | 高 | 本端出站前**强制**过 `health_claim_compliance`（已落地），不依赖对端；入站内容同样过闸门 |
| 词表两侧漂移 | 中 | S5 建立 diff 脚本，纳入 CI（改任一侧词表须同步） |
| 网关熔断开（503 `circuit_breaker_open`）被误判为业务失败 | 低 | 适配层区分该错误码，不重试、标注 `degraded:"peer_circuit_open"` |
| 3 人团队产能（索克侧） | 高 | S3–S5 全部依赖对端，排期须留缓冲；本端 S0–S2 不占对端工时 |

---

## 八、待核验清单（落地前必须复核）

以下条目来自检索代理，主代理**尚未**亲自 Read 源码确认，S1 开工前逐条复核：

- [ ] `-32603` / `-32000` 错误码触发条件（`a2a_routes.py:569-584`）
- [ ] 成功 result 精确字段（`a2a_routes.py:595-607`）
- [ ] REST tasks 端点状态码与 body schema（`a2a_routes.py:247-465`）
- [ ] SSE 帧格式与 ping 间隔（`a2a_task_machine.py:130-133, 705-726`）
- [ ] 任务 TTL 默认 3600s（`a2a_task_machine.py:57-59`）
- [ ] `shared/wellness_claim_compliance.py:36-60` 完整词表（用于 S5 diff）
- [ ] `GW/route_config.json` 新增外部服务键所需字段
- [ ] `@suoke_tool` 装饰器中 6 个 xiaoke 技能的完整入参 schema

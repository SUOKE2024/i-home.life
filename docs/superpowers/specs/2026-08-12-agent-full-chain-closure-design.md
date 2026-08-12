# 智能体全链路闭环补齐 — 设计文档（Spec）

- 日期：2026-08-12
- 版本目标：v1.13.3
- 状态：已批准（用户确认「全量闭环 + 断点 I 一并修复 + bump v1.13.3」）

## 一、背景与目标

按用户要求对智能体系统做「全景、全量、全链路」系统性打磨。经两个搜索子代理全量审计（主链路 9 断点 A–I + 反馈闭环 5 缺口），本次以「全链路闭环补齐」为切入维度，打通从「用户需求输入 → 智能决策（注入）→ 执行（工具）→ 反馈（沉淀）→ 结果输出」的完整闭环。

**核心目标**：消除所有「think/think_with_tools/think_stream 未传 db/user_id/project_id」导致的自进化注入、Case 沉淀、轨迹落库、Skill 成败回写静默失效点，并激活 P1 Skill 进化数据层（`record_skill_outcome` 生产路径零调用问题）。

**验收标准**（用户确认：完整工程闭环）：每个修复配套回归测试；flake8/mypy 0；全量 pytest 基线 2169 passed/2 skipped/4 xfailed 不回退；文档（CHANGELOG/CLAUDE.md）同步；版本 bump v1.13.3（12 处全链路）。

## 二、现状断点清单（审计结论）

### 主链路断点（think 调用未传 db/user_id → 注入/沉淀/轨迹静默失效）

| # | 断点 | 位置 | 调用点 |
|---|------|------|--------|
| A | `OrchestratorAgent.classify_intent` 裸调 `self.think(message)` | `app/agents/orchestrator.py:126` | `app/api/agents.py:566`（/chat）、`:1217`（/chat/stream）、`app/api/voice_realtime.py:132` |
| B | `generate_content_publish_reply` 裸调 `self.think(prompt)` | `app/agents/content_publisher.py:257` | `app/api/agents.py:676`、`:1247` |
| C | `ConciergeAgent.generate_response` 裸调 `self.think(user_message, context)` | `app/agents/concierge.py:363` | `app/api/agents.py:773`、`:1317`、`:2336` |
| D | `think_stream` 无 db/user_id/project_id 签名 | `app/agents/base.py:658-673` | `app/api/agents.py:1538`（覆盖 settlement/admin/takeoff/kitchen/bathroom/mep/appliance/furniture/door_window/files/products/identity/notifications/ifc_export 共 14 分支） |
| E | 实时语音 `_route_voice_to_agent` 6 处裸调 | `app/api/voice_realtime.py:248,262,275,288,301,313` | `voice_realtime.py:144`（voice/process，有 db）、`:704`（websocket mock，无 db） |
| F | IM 群聊 `harness.run` 无 kwargs | `app/services/chat_service.py:281` | `generate_agent_auto_reply`（`chat_service.py:324`，有 db+room.project_id） |
| G | 产品 AI 文案 3 处裸调 | `app/api/products.py:99`、`app/services/ai_copy_service.py:71`、`app/api/camera_scan.py:137` | 前两者端点有 db/current_user；ai_copy 为后台批量任务（有 db 无 user_id） |
| H | Skill 实例化测试裸调 | `app/api/agent_skills.py:318` | 端点有 db/current_user |
| I | 编排 LLM 分解绕过 think（`agent._chat` 直连，签名收 db/user_id 但未用于注入） | `app/services/agent_orchestration_service.py:237` | `_llm_decompose`（签名 `:199-202`） |

### 反馈闭环缺口

1. **`record_skill_outcome` 生产路径零调用**（`app/services/agent_skill_evolution_service.py:275-297`）：仅被 verify 脚本与测试调用 → `success_count/fail_count` 恒 0 → `evaluate_skill_quality` 恒走 `total==0` 分支（`:322-326`），P1 Skill 进化数据层空转。
2. **`/chat/stream` 端点缺 preference hint 注入**（对比 `/chat` 的 `app/api/agents.py:578-603`）。
3. **`ai_render_service.py:143,214,305` 用非缓存版偏好**（低优先级，本次不改，写遗留）。

### 明确不做（遗留清单，下一轮）

- `agent_feedbacks` 纳入 `detect_agent_drift` / `QUALITY_TARGETS`（属评估体系维度）
- `ai_render_service` 缓存版偏好对齐
- 流式路径 HC 反驳重生成（保持现状，诚实标注）

## 三、设计

### 3.1 Agent 层（`app/agents/`）

**1. `think_stream` 补全签名与注入**（断点 D 核心）

```python
async def think_stream(self, user_message: str, context: str = "",
                       db=None, project_id: str = "", user_id: str = ""):
    messages = []
    if self.system_prompt:
        messages.append({"role": "system", "content": self.system_prompt})
    # AgenticRAG 证据注入（与 think 一致，db 传入时）
    # _inject_evolution_context（与 think 一致）
    if context:
        messages.append({"role": "assistant", "content": context})
    messages.append({"role": "user", "content": user_message})
    chunks: list[str] = []
    async for chunk in self._chat_stream(messages):
        chunks.append(chunk)
        yield chunk
    # 流结束后：Case 沉淀 + Skill outcome 回写（用累积全文，best-effort）
    reply_text = "".join(chunks)
    await self._maybe_persist_execution_case(user_message, reply_text, db, user_id, project_id)
    await self._maybe_record_skill_outcome(reply_text, db)
```

- 流式路径无 rebuttal 重生成（保持现状，诚实标注）。
- mock 模式（无 API key）：`_chat_stream` 产出 `[mock] ...`，Case 提取与 skill outcome 内部判定会正确跳过。

**2. 三处透传（断点 A/B/C）**

- `classify_intent(self, message, db=None, user_id="", project_id="")` → `await self.think(message, db=db, user_id=user_id, project_id=project_id)`
- `generate_response(self, user_message, context="", db=None, user_id="", project_id="")` → `await self.think(user_message, context, db=db, user_id=user_id, project_id=project_id)`
- `generate_content_publish_reply(self, message, user_name, db=None, user_id="", project_id="")` → `await self.think(prompt, db=db, user_id=user_id, project_id=project_id)`

**3. 新增 `_maybe_record_skill_outcome` hook（反馈闭环核心）**

- `_inject_evolution_context` 在函数入口先 `self._injected_skill_id = None` 重置，注入 Skill 成功后记录 `self._injected_skill_id = skill.id`（防陈旧 skill_id 误记）。
- 新 hook（`app/agents/base.py`，与 `_maybe_persist_execution_case` 并列）：

```python
async def _maybe_record_skill_outcome(self, reply: str, db) -> None:
    """v1.13.3: Skill 使用成败回写（best-effort）。
    确定性判定：reply 非空、非 [mock] 前缀、非降级占位 → success=True；
    无法判定（mock/空/降级）→ 跳过不计数，防污染。
    """
    skill_id = getattr(self, "_injected_skill_id", None)
    if not skill_id or db is None:
        return
    if not isinstance(reply, str) or not reply.strip():
        return
    if reply.startswith("[mock]") or reply.startswith("Agent 暂时无法响应"):
        return
    from app.services.agent_skill_evolution_service import record_skill_outcome
    await record_skill_outcome(db, skill_id=skill_id, success=True)
```

- 调用点：`think`（`base.py:601` 后）、`think_with_tools` 三个出口（`base.py:776/844/863` 后）、`think_stream`（流结束后）。
- 效果：Skill 注入后的执行结果回写 → `success/fail_count` 增长 → `evaluate_skill_quality` 进入真实评分分支 → P1 Skill 进化数据层激活。
- 失败判定（success=False）本次不实现——需 LLM 判定或更复杂信号，写遗留（诚实标注：当前只记成功，失败不计数）。

### 3.2 API 层（`app/api/`）

**4. `agents.py` 调用点透传**

- `chat_stream` 的 `stream_agent.think_stream(stream_msg, stream_ctx)`（`:1538`）→ 补 `db=db, user_id=current_user.id, project_id=data.project_id`
- `classify_intent` 两处（`:566`、`:1217`）→ 补三参
- `generate_content_publish_reply` 两处（`:676`、`:1247`）→ 补三参
- concierge `generate_response` 三处（`:773`、`:1317`、`:2336`）→ 补三参

**5. `/chat/stream` 补 preference hint 注入**

- 提取公共 helper（放 `app/api/agents.py`）：

```python
async def _inject_preference_hint(db, user_id: str, intent: str, user_ctx: str) -> str:
    if not settings.agent_learning_enabled:
        return user_ctx
    from app.agents.base import get_pref_hint_cached
    agent_name = INTENT_TO_AGENT.get(intent, "orchestrator")
    hint = await get_pref_hint_cached(user_id, agent_name, db,
                                      max_examples=settings.agent_learning_max_examples)
    return f"{hint}\n{user_ctx}" if hint else user_ctx
```

- `/chat`（`:577-603`）与 `/chat/stream`（intent 分类后、分支前，约 `:1220`）共用该 helper（消除重复，行为不变）。
- `INTENT_TO_AGENT` 复用现有映射（现为 `intent_to_agent` 局部 dict，提升为模块级常量或保持局部——实现时保持 surgical，仅提取逻辑）。

**6. `voice_realtime.py` 透传**

- `_route_voice_to_agent(text, intent, user_name, context="", emotion=None, db=None, user_id="", project_id="")`，内部 6 处 think/think_with_tools 补参。
- 调用点 `:144`（voice/process 端点，有 `db`、`current_user`、`data.project_id`）→ 补传三参；`:132` classify_intent 补传。
- 调用点 `:704`（websocket mock 路径，无 db 依赖）→ 不传（默认 None，安全降级，不 crash）。

**7. 产品文案/测试端点透传**

- `app/api/products.py:99` → `p_agent.think(prompt, db=db, user_id=current_user.id, project_id=data.project_id)`（需确认端点签名有 current_user/db——有，见 read）
- `app/api/agent_skills.py:318` → `agent.think(payload.test_message, db=db, user_id=current_user.id)`
- `app/api/camera_scan.py:137` → `agent.think(prompt, db=db, user_id=current_user.id, project_id=...)`（project_id 视端点可用性；`_maybe_record_skill_outcome` 内部需 try/except 包裹，沿用 best-effort 惯例）

### 3.3 服务层（`app/services/`）

**8. `chat_service.py` IM 群聊透传**

- `_call_agent_auto_reply(agent_name, user_message, db=None, user_id="", project_id="")` → `harness.run(agent, user_message, db=db, user_id=user_id, project_id=project_id)`
- `generate_agent_auto_reply` 调用处（`:324`）：`db=db, project_id=room.project_id`；`user_id` 取 `trigger_msg.sender_id` 且不以 `agent:` 前缀时为该用户 id，否则空串（agent 机器人消息不归属个人，诚实降级）。

**9. `agent_orchestration_service.py` `_llm_decompose` 注入**（断点 I）

- 构建 messages 后、`_chat` 调用前：

```python
if db is not None and user_id:
    await agent._inject_evolution_context(messages, message, user_id, db, project_id)
```

- 保持 `_chat` 直连（decompose 需专用 prompt）；不做 Case 沉淀（子任务执行已由 harness 统一沉淀，避免重复）。诚实标注。

### 3.4 数据流闭环（修复后）

```
用户输入
  → 端点(db, user_id, project_id)                     [全部 21+ 端点]
  → think / think_with_tools / think_stream            [含流式/语音/IM/文案]
    → 注入: RAG证据 + 进化Case/Skill + 偏好hint + 记忆/空间
    → LLM(fallback链) → 工具执行(有db串行) → 回复
  → 沉淀: Case提取(_maybe_persist_execution_case)
         + Skill outcome回写(_maybe_record_skill_outcome)   [P1 数据层激活]
  → agent_traces / agent_cases / agent_skills(进化) → 下次注入
  → 用户反馈(like/dislike) → L4 偏好hint → 下次注入
```

## 四、测试与验证

### 新增/扩展测试（`tests/test_agent_chain.py` 为主，约 8 用例）

1. `test_stream_think_injects_and_persists`：monkeypatch `_chat_stream` 产固定 chunks → `think_stream(..., db, user_id, project_id)` → 断言 `_inject_evolution_context` 注入生效（预置 Case/Skill）+ `_maybe_persist_execution_case` 沉淀新 Case（scope=project）
2. `test_stream_think_skill_outcome`：预置注入 Skill → 正常 reply → 断言 `success_count` 增 1
3. `test_stream_think_skill_outcome_mock_skip`：reply 为 `[mock]...` → 断言不计数
4. `test_classify_intent_passes_context`：monkeypatch orchestrator `think` 断言收到 db/user_id/project_id
5. `test_concierge_generate_response_passes_context`：同法
6. `test_content_publish_passes_context`：同法
7. `test_im_auto_reply_passes_context`：`generate_agent_auto_reply` → mock `harness.run` 断言 kwargs 含 db/user_id/project_id
8. `test_voice_route_passes_context`：`_route_voice_to_agent(..., db, user_id, project_id)` → mock think 断言透传
9. `test_llm_decompose_injects_evolution`：mock `_inject_evolution_context` 断言被调（预置 skill）

### 回归验证

- 全量 pytest：`.venv/bin/python -m pytest`（**2169 passed / 2 skipped / 4 xfailed 不回退**）；受外部会话并发影响时用 `scripts/run_full_tests_with_retry.py --wait-clean`
- `flake8`（max-line-length=120, max-complexity=15）
- `mypy`（`mypy.ini`）
- 相关定向测试先行：test_agent_chain / test_agent_case / test_agent_orchestration / test_voice* / test_chat* / test_products* / test_agent_skills*

## 五、版本号 bump v1.13.3（12 处全链路）

按 `.claude/templates/version-bump.md` 清单：
- `app/config.py` app_version、`.env*`（4 处，本机 .env 存在则改）
- `flutter_app/pubspec.yaml`（+build 递增）、`flutter_app/lib/config.dart`、`flutter_app/lib/pages/settings_page.dart`
- `console-src/package.json`（1.13.3.0）
- `.github/workflows/ci.yml`（3 处 APP_VERSION）
- `scripts/deploy-production.sh`
- `tests/test_v1_3_0_compliance.py` / `tests/test_mcp_2026_07_28.py` / `tests/test_v1128_suoke_borrowed.py`
- 注：`web/version.json` 已随旧 `web/` 废弃（webapp 替代），如文件存在则同步，否则跳过并标注
- 发布前跑模板第 4 步验证命令（grep 新旧版本号残留）

## 六、文档同步

- `CHANGELOG.md` [Unreleased] 追加条目（Edit append，避开外部会话已改动内容）
- `CLAUDE.md` 同步（若涉及 Agent 能力描述变化，如 Skill outcome 回写）
- 本次不生成新报告文档（修复类，随代码 + 测试 + CHANGELOG 闭环）；如需落地报告由用户指示

## 七、风险与约束

1. **工作树外部会话未提交改动**：`app/config.py`、`app/models/__init__.py`、`CHANGELOG.md` 等被外部会话修改 —— bump 版本与 CHANGELOG 用 Edit 定点修改，不覆盖外部内容；若 config.py 版本字段与外部冲突，先 `git diff app/config.py` 确认再改。
2. **`think_stream` 改动影响生产流式路径**：mock 无 key 环境回归必须覆盖；新增 2 次 DB 查询（search_cases + skill）在流开始前，延迟可接受（与 think 一致）。
3. **并发约束（v1.13.1）**：有 db 的工具执行必须串行——本次不新增并行路径，无违反。
4. **`_inject_evolution_context` 在 `_llm_decompose` 的复用**：OrchestratorAgent 为 economy 档，注入检索 2 次 DB 查询，失败仅 log debug，不影响 decompose。
5. **v1.13.2 遗留**（`/chat` Case 提取最小 trace 无 tool_calls/无 token 统计）：保持现状，不在本次范围。

## 八、实施顺序（供计划阶段细化）

1. Agent 层：`think_stream` 签名 + 注入；三处透传；`_maybe_record_skill_outcome` + `_injected_skill_id`
2. API 层：`agents.py` 透传 + preference hint helper 提取 + `/chat/stream` 注入；`voice_realtime.py`；`products.py` / `agent_skills.py` / `camera_scan.py`
3. 服务层：`chat_service.py`；`agent_orchestration_service.py`
4. 测试：新增 9 用例 + 定向回归
5. 版本 bump v1.13.3 + CHANGELOG + CLAUDE.md 同步
6. 全量验证：pytest 基线 + flake8 + mypy

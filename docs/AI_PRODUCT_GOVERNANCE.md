# AI 产品治理（i-home.life）

> 依据《人工智能拟人化互动服务管理暂行办法》（网信办等五部门令第 21 号，2026-07-15 施行）。
> 背景：2026 年腾讯（QClaw 12-24 停运、元器 11-09 停服）、豆包/千问/元宝（7-15 下线用户自建智能体，
> 涉 800 万+ AI 角色）、OpenAI（3-24 关 Sora、7-9 关 Atlas）集中收缩 AI 产品。本文件把治理固化为
> 三张台账，与索克生活 / 索克俱乐部**同口径**（契约 1 合规分级 / 契约 2 provider 生命周期 /
> 契约 3 能力生命周期）。

## 一、AI 能力合规分级台账（契约 1）

**代码**：`app/services/ai_service_compliance.py`（输出闸门 + 工具分级）
**口径**：`assets/legal/ai-service-compliance-notice.md`
**测试**：`tests/test_ai_service_compliance.py`

| 维度 | 处理 | 触发 |
|---|---|---|
| `personification` | **阻断** | 自称真人（「我是真人」「我不是 AI」）、情感陪伴承诺（「我永远不会离开你」） |
| `personification`（软化） | 放行 + 附加 `STANDARD_AI_DISCLOSURE` | 「我一直陪着你」「随时陪你聊天」 |
| `finance` | **阻断** | 收益承诺 / 荐股（「稳赚不赔」「保证年化」「内幕消息」「荐股」） |
| `health` | 由 `health_claim_compliance` 承担 | 疗效词（治疗/降压/降糖/康复率…） |

- **正交串联**：`app/agents/care.py` 输出路径 = 健康闸门 → AI 服务闸门。
- **工具分级与暴露层 fail-closed**：`AgentTool.compliance` 由 `classify_tool(name, category)` 派生；
  未登记 category 的工具可注册但**不出现**于 `_visible_tools()` / `get_admin_openai_schemas()`。
  已登记 category：`budget` / `design` / `procurement` / `construction` / `qa` / `location` /
  `orchestration` / `design_proposal` / `admin` / `general`（均为 SAFE——家居工具属物理空间/装修域，
  无卫生健康或金融边界）。
- **开关**：`settings.ai_service_compliance_enabled`（默认 True），关闭即诚实标注未校验。

## 二、LLM provider 生命周期台账（契约 2）

**代码**：`app/agents/base.py` —— `PROVIDER_STATUS`（active/disabled/retired）+ `validate_provider_config()`
**测试**：`tests/test_llm_provider_config.py`

规则：注册表 provider 必须登记状态；`active` 须具备 `api_base`/`api_key`/`model`/`chat_path`；
降级链（`DEFAULT_FALLBACK_CHAIN`）仅可引用 `active` provider。当前 5 个 provider 均为 `active`：
`deepseek` / `glm` / `qwen` / `doubao` / `local`。

**外部平台下线应对**：外部平台（豆包/千问/元器/扣子/Dify 等）停服时，将 `PROVIDER_STATUS` 中对应
项置 `retired`，**并同步从 `DEFAULT_FALLBACK_CHAIN` 摘除**；`validate_provider_config()` 与单测兜底，
避免"降级链仍引用已下线 provider"。

## 三、能力生命周期台账（契约 3）

状态枚举 `active` / `frozen` / `retired`；`retired` 须附三件套：**数据导出 + 迁移工具 + 过渡截止日**。

| 载体 | 位置 |
|---|---|
| 工具级 | `app/services/agent_tool_registry.py`（`BUILTIN_TOOLS` + `compliance` 分级；MCP 经 `app/mcp/server.py` 暴露） |
| 能力可见性 | `ToolRegistry._visible_tools()`（按 feature flag 与分级过滤） |
| 端点级 | 各 feature flag（关闭即端点 503 诚实降级，如 `space_asset_ledger_enabled`） |

## 四、成本 / ROI 口径

`app/agents/base.py` 的 `_resolve_chain()` 已按 `cost_tier` 与任务复杂度路由（v1.13.1 usage 累计）；
LLM 响应缓存降低重复调用。治理口径：按 agent 维度汇总 token 用量与结果指标，低敏批处理走低档模型。

## 五、价值主张纪律（卖结果，不卖"有 AI"）

对外表述以**结果指标**为准（空间健康评分改善、智能化改造交付率、运营指标提升），不以"接入了
大模型"为卖点。领域数据（空间资产台账、设备/场景运行数据）默认可导出、可迁移。

## 附带：本轮对既有工程缺口的纠正

- `scripts/fc-timer/s.yaml` 已存在（FC 定时器 IaC 并非"缺失"，仅需按 `CLAUDE.md` 运维须知维护）。
- `miniapp/` **已被 git 跟踪（71 文件）**，工作树无未跟踪残留（原评估"整目录未入库"结论已过期）。

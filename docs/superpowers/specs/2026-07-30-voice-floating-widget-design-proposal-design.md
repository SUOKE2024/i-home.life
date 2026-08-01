# 悬浮窗常驻语音交互 + 讨论式方案交互 设计文档

> 日期: 2026-07-30
> 版本: v1.2.8
> 状态: 设计已确认，待实现
> 关联: v1.2.7 Qwen-Audio-3.0-Realtime 协议对齐（WS + 场景画像 + orchestration flag）

## 一、目标

借鉴 Qwen-Audio-3.0-Realtime "能聊天更能办事" 范式，落地两个 Flutter 前端能力：

1. **悬浮窗常驻语音交互** — 全局悬浮入口，任意页面可唤起语音，后台执行 Agent 任务不阻塞当前页面。
2. **讨论式方案交互** — 复杂设计任务先给 2-3 套方案，用户语音补充"方案B但加上中岛"，模型调整续跑。

## 二、关键决策（brainstorming 确认）

| 决策点 | 选择 | 理由 |
|---|---|---|
| 悬浮窗形态 | B 语音+任务融合面板 | 打通 voice_realtime WS 与 VoiceTaskPanel 两套系统，闭环"说→看到任务跑→看结果" |
| 讨论式布局 | B 全屏方案对比页 + 底部语音条 | 方案对比需空间，全屏展示充分；底部语音条保证讨论连续 |
| 与现有设计页关系 | 新建通用 DesignProposalPage | 现有 kitchen_page 等保留单方案深化，新页专注多方案对比 |
| 方案生成方式 | LLM 生成多方案 | 现有 designer.py 是确定性算法返回单方案，讨论式需 LLM 理解自然语言并多方案 |
| 调整指令路径 | WS FunctionCall 工具 | 对齐 Qwen-Audio-3.0 Realtime 模式 FunctionCall，语音与方案调整一步到位 |

## 三、整体架构

```
MaterialApp (main.dart)
├─ Overlay ← VoiceOverlayController 注入（全局，不阻塞当前页）
│  └─ VoiceOverlayWidget
│     ├─ 收起态: FAB（右下角，带 running 任务数角标）
│     └─ 展开态: VoiceFusionPanel
│        ├─ 上半: VoiceConversationArea（波纹动画 + 实时转写，接 voice_realtime WS）
│        └─ 下半: VoiceTaskPanelList（复用现有 VoiceTaskPanel 轮询逻辑）
│
└─ Navigator
   └─ DesignProposalPage（全屏方案对比页，语音指令触发跳转）
      ├─ 2-3 栏方案卡片（布局图/预算/亮点，蓝色边框=选中，✏️=有未确认修改）
      └─ 底部常驻 VoiceProposalBar（语音条，复用同一 WS 会话不断开）
```

**核心数据流（讨论式循环）**：

```
1. 用户语音"设计厨房"
   → voice_realtime WS → Realtime LLM
   → 调用 generate_design_proposals 工具
   → 后端 LLM 生成 2-3 方案 JSON
   → function_call_output 回流 → 前端收到方案
   → 跳转 DesignProposalPage 展示

2. 用户语音"方案B加中岛"
   → 同一 WS 会话 → Realtime LLM
   → 调用 update_design_proposal(proposal_id="B", change="加中岛")
   → 后端 LLM 修订方案 B（保留 A/C 不变）
   → function_call_output 回流 → 方案 B 栏原地刷新
```

## 四、组件清单

### 后端（Python）

| 文件 | 改动 | 说明 |
|---|---|---|
| `app/services/agent_tool_registry.py` | 新增 2 个工具 | `generate_design_proposals` + `update_design_proposal`，注册进 BUILTIN_TOOLS，受 `voice_agent_orchestration_enabled` 门控 |
| `app/services/design_proposal_service.py` | 新建 | 封装 LLM 调用生成/修订方案，复用 LLM fallback 链（DeepSeek→GLM→Qwen），方案数据结构 ProposalSpec |
| `app/api/agents.py` | 新增 2 端点 | `POST /api/agents/design/proposals`（生成）、`POST /api/agents/design/proposals/{id}/revise`（修订，REST 降级路径） |
| `app/services/voice_realtime_service.py` | 小改 | `_qwen_events_to_client` 处理 `function_call` 事件时，将 `update_design_proposal` 的结果通过 `response.function_call_output` 回送，并通过 WS 推送 `proposal_updated` 事件给前端 |

### Flutter（Dart）

| 文件 | 改动 | 说明 |
|---|---|---|
| `lib/widgets/voice_overlay.dart` | 新建 | `VoiceOverlayController` + `VoiceOverlayWidget`，OverlayEntry 注入 MaterialApp，收起/展开状态机 |
| `lib/widgets/voice_fusion_panel.dart` | 新建 | 融合面板，上下分层：VoiceConversationArea + VoiceTaskPanelList |
| `lib/widgets/voice_conversation_area.dart` | 新建 | 波纹动画 + 实时转写展示，订阅 voice_realtime_service 事件流 |
| `lib/pages/design_proposal_page.dart` | 新建 | 全屏方案对比页，2-3 栏卡片 + 底部 VoiceProposalBar |
| `lib/widgets/voice_proposal_bar.dart` | 新建 | 底部语音条，通过 VoiceSessionScope 共享 WS 会话 |
| `lib/services/voice_session_scope.dart` | 新建 | InheritedWidget，跨页面共享 VoiceRealtimeService 单例，避免方案页重连 |
| `lib/services/voice_realtime_service.dart` | 小改 | 新增 `onProposalUpdate` 回调流，处理 `proposal_updated` 事件 |
| `lib/main.dart` | 小改 | MaterialApp 外包 Overlay 注入 VoiceOverlayWidget |

## 五、数据结构

### ProposalSpec（方案）

```python
class ProposalSpec(BaseModel):
    proposal_id: str          # "A" | "B" | "C"
    title: str                # "紧凑型" | "标准型" | "豪华型"
    layout_type: str          # "L型" | "U型" | "岛型"
    area_sqm: float           # 5.2
    budget_cny: int           # 18000
    highlights: list[str]     # ["动线紧凑", "储物充足"]
    layout_data: dict | None  # 可选，给前端画平面图的结构化数据
    change_log: list[str]     # ["加中岛（用户语音）"] 修订历史
```

### WS 事件（前端←后端）

```jsonc
// 方案生成完成
{
  "type": "proposal_generated",
  "proposals": [ProposalSpec, ProposalSpec, ProposalSpec],
  "session_id": "xxx"
}

// 方案修订完成（仅变更项）
{
  "type": "proposal_updated",
  "proposal_id": "B",
  "proposal": ProposalSpec  // 修订后的完整方案
}
```

## 六、关键技术点

1. **Overlay 而非 Navigator push**：悬浮窗用 `Overlay.of(context).insert(OverlayEntry)`，任意页面常驻，不阻塞当前页交互。FAB 位置用 `Positioned` 固定右下角。

2. **WS 会话跨页面共享**：悬浮窗创建的 `VoiceRealtimeService` 实例通过 `VoiceSessionScope`（InheritedWidget）暴露。跳转 DesignProposalPage 时，底部 VoiceProposalBar 从 scope 获取同一实例，不重连。

3. **FunctionCall 工具注册**：`generate_design_proposals` / `update_design_proposal` 注册进 `BUILTIN_TOOLS`，经 `tool_registry.get_qwen_schemas()` 暴露给 Realtime WS 的 `session.update.tools`。LLM 自主决定何时调用。

4. **LLM fallback 链**：方案生成复用项目既有 `call_llm_with_fallback`（DeepSeek→GLM→Qwen），LLM 不可用时降级到 `DesignerAgent.generate_layouts` 确定性算法返回单方案（标注 `source: "fallback"`）。

5. **方案修订上下文**：方案数据存 `agent_sessions` 上下文（复用现有 session 机制），`update_design_proposal` 通过 `proposal_id` 定位历史方案，LLM 基于完整上下文修订。

## 七、Feature Flag

新增 `voice_floating_widget_enabled`（默认 false，灰度开启）+ `design_proposal_llm_enabled`（默认 false）。挂载到 `/config/feature-flags` 端点。

## 八、测试策略

- **后端**：`tests/test_design_proposal.py` 覆盖 LLM 生成/修订端点 + FunctionCall 工具执行 + fallback 降级
- **Flutter**：`voice_overlay_test.dart` 覆盖收起/展开状态机 + 任务角标更新
- **集成**：扩展 `test_voice_realtime.py` 覆盖 `proposal_updated` 事件推送

## 九、不在本次范围

- 悬浮窗拖拽/吸附边缘（后续优化）
- 方案页平面图 Canvas 渲染（先用占位图，复用 floor_plan_canvas.dart 是独立任务）
- 语音条 TTS 播放（依赖 voice_realtime WS 的 output_audio.delta，本次仅做转写展示）

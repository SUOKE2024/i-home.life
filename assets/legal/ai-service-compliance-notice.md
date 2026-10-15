# AI 服务合规声明（i-home.life）

**版本**: V1.0 (2026-10-15)
**适用范围**: i-home.life 全部 AI 智能体与 MCP 工具输出
**法规依据**: 《人工智能拟人化互动服务管理暂行办法》（国家网信办等五部门令第 21 号，2026-07-15 施行）；《广告法》；证券投资顾问相关资质要求
**技术口径**: `app/services/ai_service_compliance.py`
**关联文档**: [健康声明免责声明](health-claim-disclaimer.md)、[AI 产品治理](../docs/AI_PRODUCT_GOVERNANCE.md)

## 一、拟人化互动边界

本平台提供的是**空间（家居/康养/适老）领域的任务型 AI 智能体**，不提供拟人化互动服务：

1. **非真人身份**：AI 输出不得自称真人（「我是真人」「我不是 AI」等），不得诱导用户误认为在与真人交谈。
2. **非情感陪伴承诺**：不得承诺开放式情感陪伴（「我永远不会离开你」「我只属于你」等）；软化型表达
   （「我一直陪着你」）放行但由系统附加标准 AI 身份声明 `STANDARD_AI_DISCLOSURE`。
3. **实时告知**：语音/对话链路须保持 AI 身份可见（`is_ai_generated` / 身份披露徽章）。

> 复核触发条件：若后续新增「数字分身 / 角色扮演 / 情感陪伴」类能力，必须先在
> `app/services/ai_service_compliance.py` 登记其分级并补齐本声明与运行时告知，否则视为未登记能力。

## 二、卫生健康边界

健康功效宣称由既有闸门 `app/services/health_claim_compliance.py` 承担：prohibited 疗效词
（治疗/降压/降糖/康复率…）命中即阻断，caution 词（调理/祛湿/助眠…）放行并附加标准健康免责声明。
管理端输出路径在 `app/agents/care.py` 串联 **健康闸门 → AI 服务闸门**，两类边界各司其职。

## 三、金融边界

本平台不提供投资建议。输出不得含收益承诺或荐股（「稳赚不赔」「保证年化」「内幕消息」「荐股」等），
命中即阻断；涉及装修预算/结算等业务口径的内容不属于投资建议，但不得表述为收益承诺。

## 四、兜底与开关

- `settings.ai_service_compliance_enabled`（默认 True）：关闭即放行并由返回值诚实标注
  `gate_enabled=False`，**不伪装已校验**。
- 工具侧：`AgentTool.compliance` 按 `category` 派生；未登记 category 的工具不出现在
  可见/可调用工具列表（暴露层 fail-closed）。

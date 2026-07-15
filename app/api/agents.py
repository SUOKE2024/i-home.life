import asyncio
import json

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.models.project import Project
from app.auth import get_current_user
from app.database import get_db
from app.rbac import verify_project_access
from app.agents.orchestrator import OrchestratorAgent
from app.agents.designer import DesignerAgent
from app.agents.budget import BudgetAgent
from app.agents.procurement import ProcurementAgent
from app.agents.construction import ConstructionAgent
from app.agents.settlement import SettlementAgent
from app.agents.qa_inspector import QAInspectorAgent
from app.agents.concierge import ConciergeAgent
from app.config import get_settings
from app.ws import ws_manager

router = APIRouter(prefix="/agents", tags=["AI Agent"])


class AgentMessage(BaseModel):
    message: str = Field(min_length=1, max_length=2000)
    agent_type: str = Field(default="orchestrator")
    project_id: str | None = None
    history: list[dict] = Field(
        default_factory=list, max_length=20,
        description="最近 N 轮对话历史，每项含 role/content/agent_type",
    )


class DesignRequest(BaseModel):
    message: str = Field(min_length=1, max_length=2000)
    project_id: str | None = None
    room_info: str | None = Field(None, description="房间信息（户型、面积等）")


class CirculationAnalysisRequest(BaseModel):
    rooms: list[dict] = Field(..., description="房间布局列表，含 name/type/x/y/w/h")


class AgentResponse(BaseModel):
    agent_type: str
    reply: str
    suggestions: list[str] = []


class DesignPlanResponse(BaseModel):
    agent_type: str = "designer"
    space_planning: str = ""
    style_suggestion: str = ""
    circulation_analysis: str = ""
    material_plan: str = ""
    full_reply: str = ""


class BudgetAnalysisResponse(BaseModel):
    agent_type: str = "budget"
    summary: str = ""
    category_breakdown: str = ""
    cost_saving_tips: str = ""
    full_reply: str = ""


class ProcurementAnalysisResponse(BaseModel):
    agent_type: str = "procurement"
    purchase_plan: str = ""
    supplier_recommendation: str = ""
    timeline: str = ""
    full_reply: str = ""


class ConstructionPlanResponse(BaseModel):
    agent_type: str = "construction"
    phases: str = ""
    schedule: str = ""
    quality_checklist: str = ""
    full_reply: str = ""


class AcceptanceReportRequest(BaseModel):
    project_id: str = ""
    project_name: str = ""
    inspector: str = ""
    acceptance_date: str = ""
    phases: list[str] = []
    inspection_results: dict = {}


class CompareDesignRequest(BaseModel):
    project_id: str = ""
    phase: str = ""
    images: list[dict] = []
    design_reference: dict = {}
    expected_dimensions: dict = {}


class DefectDetectionRequest(BaseModel):
    project_id: str = ""
    phase: str = ""
    images: list[dict] = []
    check_categories: list[str] = []


class FAQRequest(BaseModel):
    question: str = Field(min_length=1, max_length=2000)


class ClassifyInquiryRequest(BaseModel):
    message: str = Field(min_length=1, max_length=2000)


class ConciergeChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=2000)
    context: str = ""


settings = get_settings()

MOCK_MODE = not settings.deepseek_api_key and not settings.glm_api_key


@router.post("/chat", response_model=AgentResponse)
async def chat_with_agent(  # noqa: C901
    data: AgentMessage,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    # 校验项目归属（若指定了 project_id）
    if data.project_id:
        result = await db.execute(select(Project).where(Project.id == data.project_id))
        project = result.scalar_one_or_none()
        if not project:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="项目不存在")
        if current_user.role != "admin" and project.owner_id != current_user.id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无权访问该项目")
    # 构建 history 上下文（多轮对话支持）
    history_ctx = ""
    if data.history:
        recent = data.history[-10:]  # 仅取最近 10 轮，防止 token 超限
        lines = []
        for h in recent:
            role = h.get("role", "user")
            content = h.get("content", "")[:500]  # 截断超长消息
            agent_t = h.get("agent_type", "")
            prefix = f"[{agent_t}] " if agent_t and role == "assistant" else ""
            lines.append(f"{prefix}{role}: {content}")
        history_ctx = "\n".join(lines)
    user_ctx = f"用户: {current_user.name}"
    if history_ctx:
        user_ctx = f"{history_ctx}\n{user_ctx}"
    # Hybrid routing: LLM classify (with API key) or rule-based (mock mode)
    agent = OrchestratorAgent()
    try:
        if MOCK_MODE:
            classification = OrchestratorAgent.fallback_classify(data.message)
        else:
            classification = await agent.classify_intent(data.message)

        intent = classification.get("intent", "general")

        # Route to specialized agent based on intent
        suggestions_map = {
            "designer": ["调整方案", "查看材料清单", "不同风格对比"],
            "budget": ["查看明细", "调整预算", "导出报表"],
            "procurement": ["查看供应商", "发起询价", "生成订单"],
            "construction": ["查看进度", "上传日志", "发起验收"],
            "qa_inspector": ["生成验收报告", "图纸比对", "缺陷检测"],
            "concierge": ["查看常见问题", "转人工客服", "提交报修"],
            "content_publisher": ["生成产品文案", "发布产品", "编辑产品信息"],
            "orchestrator": ["开始设计", "查看预算", "浏览材料", "施工进度"],
        }

        if intent in ("content_publish",):
            # 内容发布：复用 ProcurementAgent 的内容发布能力
            proc_agent = ProcurementAgent()
            try:
                if MOCK_MODE:
                    reply = (
                        "**产品发布助手**\n\n"
                        "检测到您要发布产品，请提供以下信息：\n\n"
                        "1. **产品名称**：如「800×800灰色防滑地砖」\n"
                        "2. **产品类别**：瓷砖/地板/涂料/橱柜/卫浴/灯具/家电/窗帘/定制家具/其他\n"
                        "3. **价格区间**：如「50-80元/㎡」\n"
                        "4. **产品描述**：材质、规格、产地、卖点等\n"
                        "5. **标签**：如「#防滑 #灰色 #客厅 #地砖」\n\n"
                        "示例：我要上架一款800×800的灰色防滑地砖，广东佛山产，50元/㎡起"
                    )
                else:
                    # 使用 ProcurementAgent 生成内容发布引导
                    reply = await proc_agent.generate_content_publish_reply(data.message, current_user.name)
                return AgentResponse(
                    agent_type="content_publisher", reply=reply,
                    suggestions=suggestions_map["content_publisher"],
                )
            finally:
                await proc_agent.close()

        if intent in ("design",):
            des_agent = DesignerAgent()
            try:
                if MOCK_MODE:
                    layouts = await des_agent.generate_layouts(data.message)
                    reply = layouts["reply"]
                else:
                    reply = await des_agent.think(data.message, user_ctx)
                return AgentResponse(agent_type="designer", reply=reply, suggestions=suggestions_map["designer"])
            finally:
                await des_agent.close()

        elif intent in ("budget",):
            bud_agent = BudgetAgent()
            try:
                if MOCK_MODE:
                    reply = (
                        _mock_budget_summary(data.message)
                        + "\n\n"
                        + _mock_budget_breakdown()
                        + "\n\n"
                        + _mock_cost_saving()
                    )
                else:
                    reply = await bud_agent.think(data.message, user_ctx)
                return AgentResponse(agent_type="budget", reply=reply, suggestions=suggestions_map["budget"])
            finally:
                await bud_agent.close()

        elif intent in ("procurement",):
            proc_agent = ProcurementAgent()
            try:
                if MOCK_MODE:
                    reply = (
                        _mock_purchase_plan()
                        + "\n\n"
                        + _mock_supplier_rec()
                        + "\n\n"
                        + _mock_procurement_timeline()
                    )
                else:
                    reply = await proc_agent.think(data.message, user_ctx)
                return AgentResponse(agent_type="procurement", reply=reply, suggestions=suggestions_map["procurement"])
            finally:
                await proc_agent.close()

        elif intent in ("construction",):
            cons_agent = ConstructionAgent()
            try:
                if MOCK_MODE:
                    reply = _mock_phases() + "\n\n" + _mock_schedule() + "\n\n" + _mock_quality()
                else:
                    reply = await cons_agent.think(data.message, user_ctx)
                return AgentResponse(
                    agent_type="construction", reply=reply,
                    suggestions=suggestions_map["construction"],
                )
            finally:
                await cons_agent.close()

        elif intent in ("settlement",):
            sett_agent = SettlementAgent()
            try:
                if MOCK_MODE:
                    reply = _mock_settlement()
                else:
                    reply = await sett_agent.think(data.message, user_ctx)
                return AgentResponse(agent_type="settlement", reply=reply, suggestions=["查看结算明细", "确认结算", "导出报表"])
            finally:
                await sett_agent.close()

        elif intent in ("qa_inspector",):
            qa_agent = QAInspectorAgent()
            try:
                if MOCK_MODE:
                    reply = _mock_qa_inspection()
                else:
                    reply = await qa_agent.think(data.message, user_ctx)
                return AgentResponse(
                    agent_type="qa_inspector", reply=reply,
                    suggestions=suggestions_map["qa_inspector"],
                )
            finally:
                await qa_agent.close()

        elif intent in ("concierge",):
            conc_agent = ConciergeAgent()
            try:
                if MOCK_MODE:
                    faq_result = conc_agent.answer_faq(data.message)
                    reply = faq_result["answer"]
                else:
                    reply = await conc_agent.generate_response(data.message, f"业主: {current_user.name}")
                return AgentResponse(agent_type="concierge", reply=reply, suggestions=suggestions_map["concierge"])
            finally:
                await conc_agent.close()

        else:
            reply, suggestions = _mock_agent_reply(data.message, "orchestrator")
            return AgentResponse(agent_type="orchestrator", reply=reply, suggestions=suggestions)
    finally:
        await agent.close()


@router.post("/chat/stream")
async def chat_stream(  # noqa: C901
    data: AgentMessage,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Agent 聊天 SSE 流式响应 — 逐句/逐词推送回复"""
    # 校验项目归属
    if data.project_id:
        result = await db.execute(select(Project).where(Project.id == data.project_id))
        project = result.scalar_one_or_none()
        if not project:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="项目不存在")
        if current_user.role != "admin" and project.owner_id != current_user.id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无权访问该项目")

    # 构建 history 上下文（复用 /chat 逻辑）
    history_ctx = ""
    if data.history:
        recent = data.history[-10:]
        lines = []
        for h in recent:
            role = h.get("role", "user")
            content = h.get("content", "")[:500]
            agent_t = h.get("agent_type", "")
            prefix = f"[{agent_t}] " if agent_t and role == "assistant" else ""
            lines.append(f"{prefix}{role}: {content}")
        history_ctx = "\n".join(lines)
    user_ctx = f"用户: {current_user.name}"
    if history_ctx:
        user_ctx = f"{history_ctx}\n{user_ctx}"

    # Hybrid routing
    agent = OrchestratorAgent()
    try:
        if MOCK_MODE:
            classification = OrchestratorAgent.fallback_classify(data.message)
        else:
            classification = await agent.classify_intent(data.message)
        intent = classification.get("intent", "general")

        # 获取回复文本（与 /chat 相同逻辑）
        if intent in ("content_publish",):
            proc_agent = ProcurementAgent()
            try:
                if MOCK_MODE:
                    reply = (
                        "**产品发布助手**\n\n"
                        "检测到您要发布产品，请提供以下信息：\n\n"
                        "1. **产品名称**：如「800×800灰色防滑地砖」\n"
                        "2. **产品类别**：瓷砖/地板/涂料/橱柜/卫浴/灯具/家电/窗帘/定制家具/其他\n"
                        "3. **价格区间**：如「50-80元/㎡」\n"
                        "4. **产品描述**：材质、规格、产地、卖点等\n"
                        "5. **标签**：如「#防滑 #灰色 #客厅 #地砖」\n\n"
                        "示例：我要上架一款800×800的灰色防滑地砖，广东佛山产，50元/㎡起"
                    )
                else:
                    reply = await proc_agent.generate_content_publish_reply(data.message, current_user.name)
            finally:
                await proc_agent.close()
        elif intent in ("design",):
            des_agent = DesignerAgent()
            try:
                if MOCK_MODE:
                    layouts = await des_agent.generate_layouts(data.message)
                    reply = layouts["reply"]
                else:
                    reply = await des_agent.think(data.message, user_ctx)
            finally:
                await des_agent.close()
        elif intent in ("budget",):
            bud_agent = BudgetAgent()
            try:
                if MOCK_MODE:
                    reply = (
                        _mock_budget_summary(data.message)
                        + "\n\n"
                        + _mock_budget_breakdown()
                        + "\n\n"
                        + _mock_cost_saving()
                    )
                else:
                    reply = await bud_agent.think(data.message, user_ctx)
            finally:
                await bud_agent.close()
        elif intent in ("procurement",):
            proc_agent = ProcurementAgent()
            try:
                if MOCK_MODE:
                    reply = (
                        _mock_purchase_plan()
                        + "\n\n"
                        + _mock_supplier_rec()
                        + "\n\n"
                        + _mock_procurement_timeline()
                    )
                else:
                    reply = await proc_agent.think(data.message, user_ctx)
            finally:
                await proc_agent.close()
        elif intent in ("construction",):
            cons_agent = ConstructionAgent()
            try:
                if MOCK_MODE:
                    reply = _mock_phases() + "\n\n" + _mock_schedule() + "\n\n" + _mock_quality()
                else:
                    reply = await cons_agent.think(data.message, user_ctx)
            finally:
                await cons_agent.close()
        elif intent in ("settlement",):
            sett_agent = SettlementAgent()
            try:
                if MOCK_MODE:
                    reply = _mock_settlement()
                else:
                    reply = await sett_agent.think(data.message, user_ctx)
            finally:
                await sett_agent.close()
        elif intent in ("qa_inspector",):
            qa_agent = QAInspectorAgent()
            try:
                if MOCK_MODE:
                    reply = _mock_qa_inspection()
                else:
                    reply = await qa_agent.think(data.message, user_ctx)
            finally:
                await qa_agent.close()
        elif intent in ("concierge",):
            conc_agent = ConciergeAgent()
            try:
                if MOCK_MODE:
                    faq_result = conc_agent.answer_faq(data.message)
                    reply = faq_result["answer"]
                else:
                    reply = await conc_agent.generate_response(data.message, f"业主: {current_user.name}")
            finally:
                await conc_agent.close()
        else:
            reply, _ = _mock_agent_reply(data.message, "orchestrator")

        # SSE 流式推送：按句子分割，每句间隔 80ms
        async def generate_sse():
            # 先发送 agent_type 元信息
            yield f"data: {json.dumps({'event': 'meta', 'agent_type': intent})}\n\n"
            await asyncio.sleep(0.05)

            # 按段落分割，再按句号分割
            paragraphs = reply.split("\n\n")
            for para in paragraphs:
                # 按句号、问号、感叹号分割
                sentences = para.replace("？", "?\n").replace("！", "!\n").replace("。", ".\n").split("\n")
                for sent in sentences:
                    sent = sent.strip()
                    if not sent:
                        continue
                    # 以词为单位（每 3-5 个字符为一组）
                    i = 0
                    while i < len(sent):
                        chunk = sent[i:i + 4]
                        i += len(chunk)
                        yield f"data: {json.dumps({'event': 'token', 'content': chunk})}\n\n"
                        await asyncio.sleep(0.03)
                # 段落间增加停顿
                _newlines = '\n\n'
                yield f"data: {json.dumps({'event': 'token', 'content': _newlines})}\n\n"
                await asyncio.sleep(0.1)

            # 发送结束信号
            yield f"data: {json.dumps({'event': 'done'})}\n\n"

        return StreamingResponse(
            generate_sse(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
            },
        )
    finally:
        await agent.close()


@router.post("/design", response_model=DesignPlanResponse)
async def request_design(
    data: DesignRequest,
    current_user: User = Depends(get_current_user),
):
    agent = DesignerAgent()
    try:
        msg = data.message
        if data.room_info:
            msg = f"户型信息: {data.room_info}\n\n用户需求: {data.message}"

        layouts = await agent.generate_layouts(msg)

        return DesignPlanResponse(
            space_planning=layouts["reply"],
            style_suggestion=layouts["recommendation"],
            circulation_analysis=" | ".join(layouts["materials"][:2]),
            material_plan="\n".join(layouts["materials"]),
            full_reply=json.dumps(layouts, ensure_ascii=False, indent=2),
        )
    finally:
        await agent.close()


@router.post("/design/circulation")
async def analyze_circulation(
    data: CirculationAnalysisRequest,
    current_user: User = Depends(get_current_user),
):
    """F28 智能布局动线分析：访客/家务/居住三条动线评分 + 冲突检测 + 优化建议"""
    agent = DesignerAgent()
    try:
        return agent.analyze_circulation(data.rooms)
    finally:
        await agent.close()


@router.post("/budget", response_model=BudgetAnalysisResponse)
async def analyze_budget(
    data: AgentMessage,
    current_user: User = Depends(get_current_user),
):
    if MOCK_MODE:
        return BudgetAnalysisResponse(
            summary=_mock_budget_summary(data.message),
            category_breakdown=_mock_budget_breakdown(),
            cost_saving_tips=_mock_cost_saving(),
            full_reply="预算分析完成，请注意查看各项明细。",
        )

    agent = BudgetAgent()
    try:
        try:
            reply = await agent.think(data.message, f"业主: {current_user.name}")
        except Exception:
            return BudgetAnalysisResponse(
                summary=_mock_budget_summary(data.message),
                category_breakdown=_mock_budget_breakdown(),
                cost_saving_tips=_mock_cost_saving(),
                full_reply="预算分析完成（LLM 不可用，使用预置模板）。",
            )
        return BudgetAnalysisResponse(
            summary=reply,
            category_breakdown=reply,
            cost_saving_tips=reply,
            full_reply=reply,
        )
    finally:
        await agent.close()


@router.post("/procurement", response_model=ProcurementAnalysisResponse)
async def analyze_procurement(
    data: AgentMessage,
    current_user: User = Depends(get_current_user),
):
    if MOCK_MODE:
        return ProcurementAnalysisResponse(
            purchase_plan=_mock_purchase_plan(),
            supplier_recommendation=_mock_supplier_rec(),
            timeline=_mock_procurement_timeline(),
            full_reply="采购分析完成，请查看推荐方案。",
        )

    agent = ProcurementAgent()
    try:
        try:
            reply = await agent.think(data.message, f"采购经理: {current_user.name}")
        except Exception:
            return ProcurementAnalysisResponse(
                purchase_plan=_mock_purchase_plan(),
                supplier_recommendation=_mock_supplier_rec(),
                timeline=_mock_procurement_timeline(),
                full_reply="采购分析完成（LLM 不可用，使用预置模板）。",
            )
        return ProcurementAnalysisResponse(
            purchase_plan=reply,
            supplier_recommendation=reply,
            timeline=reply,
            full_reply=reply,
        )
    finally:
        await agent.close()


@router.post("/construction", response_model=ConstructionPlanResponse)
async def plan_construction(
    data: AgentMessage,
    current_user: User = Depends(get_current_user),
):
    if MOCK_MODE:
        return ConstructionPlanResponse(
            phases=_mock_phases(),
            schedule=_mock_schedule(),
            quality_checklist=_mock_quality(),
            full_reply="施工计划已生成，请查看各阶段详情。",
        )

    agent = ConstructionAgent()
    try:
        try:
            reply = await agent.think(data.message, f"工长: {current_user.name}")
        except Exception:
            return ConstructionPlanResponse(
                phases=_mock_phases(),
                schedule=_mock_schedule(),
                quality_checklist=_mock_quality(),
                full_reply="施工计划已生成（LLM 不可用，使用预置模板）。",
            )
        return ConstructionPlanResponse(
            phases=reply,
            schedule=reply,
            quality_checklist=reply,
            full_reply=reply,
        )
    finally:
        await agent.close()


@router.post("/construction/publish-tasks")
async def construction_publish_tasks(
    project_id: str,
    sub_roles: list[str] | None = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """施工 Agent 根据位置和项目信息发布工种任务到任务池"""
    from sqlalchemy import select as sql_select
    from app.models.orchestrator_task import OrchestratorTask
    from app.services import points_service

    # 校验项目归属
    await verify_project_access(project_id=project_id, current_user=current_user, db=db)

    # 获取项目信息
    result = await db.execute(sql_select(Project).where(Project.id == project_id))
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")

    project_info = {
        "project_id": project.id,
        "project_name": project.name,
        "address": project.address or "",
        "project_type": project.project_type,
        "total_area": project.total_area or 0,
    }

    agent = ConstructionAgent()
    try:
        sub_task_data = agent.generate_sub_task_cards(
            project_info=project_info,
            sub_roles=sub_roles,
            location=project.address or None,
        )
    finally:
        await agent.close()

    # 将子任务写入任务池
    created_tasks = []
    for task_data in sub_task_data["tasks"]:
        task = OrchestratorTask(
            project_id=project_id,
            task_type=task_data["task_type"],
            title=task_data["title"],
            description=task_data["description"],
            assigned_agent="construction",
            claimable=True,
            claim_role="contractor",
            priority=7,
            created_by=current_user.id,
            status="pending",
        )
        db.add(task)
        created_tasks.append(task)

    await db.commit()

    # WebSocket 推送任务
    for task in created_tasks:
        await ws_manager.broadcast_to_project(project_id, "task.created", {
            "task_id": task.id,
            "title": task.title,
            "task_type": task.task_type,
            "claim_role": task.claim_role,
            "priority": task.priority,
        })

    # 奖励积分
    await points_service.earn_points(
        db, current_user.id, "product_publish",
        reference_id=project_id,
        description=f"发布工种施工任务: {project.name}",
    )

    return {
        "agent_type": "construction",
        "reply": sub_task_data["reply"],
        "sub_roles": sub_task_data["sub_roles"],
        "tasks_created": len(created_tasks),
        "task_ids": [t.id for t in created_tasks],
    }


# === QA Inspector Agent 端点 ===


@router.post("/qa-inspector/acceptance-report")
async def generate_acceptance_report(
    data: AcceptanceReportRequest,
    current_user: User = Depends(get_current_user),
):
    """生成验收报告（分项验收 + 总体验收结论）"""
    agent = QAInspectorAgent()
    try:
        return agent.generate_acceptance_report(data.model_dump())
    finally:
        await agent.close()


@router.post("/qa-inspector/compare-design")
async def compare_with_design(
    data: CompareDesignRequest,
    current_user: User = Depends(get_current_user),
):
    """照片与设计图纸比对"""
    agent = QAInspectorAgent()
    try:
        return agent.compare_with_design(data.model_dump())
    finally:
        await agent.close()


@router.post("/qa-inspector/defects")
async def detect_defects(
    data: DefectDetectionRequest,
    current_user: User = Depends(get_current_user),
):
    """工艺缺陷识别（mock CV 检测）"""
    agent = QAInspectorAgent()
    try:
        return agent.detect_defects(data.model_dump())
    finally:
        await agent.close()


# === Concierge Agent 端点 ===


@router.post("/concierge/faq")
async def answer_faq(
    data: FAQRequest,
    current_user: User = Depends(get_current_user),
):
    """FAQ 知识问答（基于预置知识库匹配）"""
    agent = ConciergeAgent()
    try:
        return agent.answer_faq(data.question)
    finally:
        await agent.close()


@router.post("/concierge/classify")
async def classify_inquiry(
    data: ClassifyInquiryRequest,
    current_user: User = Depends(get_current_user),
):
    """分类用户咨询（类型 + 紧急度 + 是否需人工）"""
    agent = ConciergeAgent()
    try:
        return agent.classify_inquiry(data.message)
    finally:
        await agent.close()


@router.post("/concierge/chat")
async def concierge_chat(
    data: ConciergeChatRequest,
    current_user: User = Depends(get_current_user),
):
    """生成客服回复（调用 think，LLM 不可用时 FAQ 兜底）"""
    agent = ConciergeAgent()
    try:
        if MOCK_MODE:
            faq_result = agent.answer_faq(data.message)
            if faq_result["found"]:
                reply = faq_result["answer"]
            else:
                classify = agent.classify_inquiry(data.message)
                if classify["need_human"]:
                    reply = "您好，您的问题需要人工客服协助处理，正在为您转接人工客服，请稍候。"
                else:
                    reply = "您好，我是索克家居 AI 客服。您的问题我已记录，可以尝试换一种方式提问，或转接人工客服获取帮助。"
        else:
            reply = await agent.generate_response(data.message, data.context)
        return {"agent_type": "concierge", "reply": reply}
    finally:
        await agent.close()


def _mock_agent_reply(message: str, agent_type: str) -> tuple[str, list[str]]:
    kw_map = {
        "设计": "orchestrator",
        "布局": "orchestrator",
        "方案": "orchestrator",
        "户型": "orchestrator",
        "预算": "budget",
        "价格": "budget",
        "费用": "budget",
        "成本": "budget",
        "采购": "procurement",
        "材料": "procurement",
        "建材": "procurement",
        "供应商": "procurement",
        "施工": "construction",
        "进度": "construction",
        "验收": "construction",
        "质检": "construction",
    }
    matched = agent_type
    for kw, at in kw_map.items():
        if kw in message:
            matched = at
            break

    replies = {
        "budget": (
            "💰 **预算分析**\n\n"
            "根据您提供的项目信息，我来帮您做个预算框架：\n\n"
            "**装修等级估算**\n"
            "- 经济型（800-1200/㎡）：适合出租/简装\n"
            "- 舒适型（1200-2000/㎡）：推荐自住选择\n"
            "- 品质型（2000-3500/㎡）：品牌材料、定制化\n\n"
            "**分项预算参考**\n"
            "- 硬装（水电+墙面+地面）：约 40-50%\n"
            "- 定制柜体：约 15-20%\n"
            "- 软装+家电：约 30-40%\n\n"
            "建议您先确定装修等级，我可以帮您细化每个分项。"
        ),
        "procurement": (
            "🛒 **采购分析**\n\n"
            "根据项目物料清单，为您规划采购方案：\n\n"
            "**第一阶段（开工前）**\n"
            "- 水电材料：电线、水管、开关暗盒\n"
            "- 防水材料：防水涂料\n\n"
            "**第二阶段（水电后）**\n"
            "- 瓷砖/地板：确认花色和用量\n"
            "- 橱柜方案：复尺后下单\n\n"
            "**第三阶段（油漆后）**\n"
            "- 卫浴洁具安装\n"
            "- 灯具/开关面板安装\n\n"
            "建议按施工进度分批采购，避免过早采购占用资金和空间。"
        ),
        "construction": (
            "🔨 **施工计划**\n\n"
            "标准施工流程共 8 个阶段：\n\n"
            "1. **准备阶段**（2-5天）：办理许可、材料进场\n"
            "2. **拆改阶段**（3-7天）：墙体拆改\n"
            "3. **水电阶段**（5-10天）：管线敷设\n"
            "4. **泥瓦阶段**（7-15天）：防水、贴砖\n"
            "5. **木工阶段**（5-10天）：吊顶、柜体\n"
            "6. **油漆阶段**（7-10天）：墙面处理\n"
            "7. **安装阶段**（5-7天）：灯具、卫浴\n"
            "8. **验收阶段**（2-3天）：全面验收\n\n"
            "预计总工期约 40-60 天。需要我为您的项目生成详细排期吗？"
        ),
        "orchestrator": (
            "您好！我是索克家居的 AI 总控 Agent。\n\n"
            "我可以帮您：\n"
            "🏠 **设计规划** - 智能生成平面布局和效果图\n"
            "💰 **预算管理** - 成本估算和预算跟踪\n"
            "🛒 **物料采购** - BOM 生成、供应商匹配\n"
            "🔨 **施工管理** - 进度跟踪、质检报告\n\n"
            "请告诉我您需要什么帮助？"
        ),
    }

    suggestions = {
        "budget": ["查看明细", "调整预算", "导出报表"],
        "procurement": ["查看供应商", "发起询价", "生成订单"],
        "construction": ["查看进度", "上传日志", "发起验收"],
        "orchestrator": ["开始设计", "查看预算", "浏览材料", "施工进度"],
    }
    return replies.get(matched, replies["orchestrator"]), suggestions.get(matched, suggestions["orchestrator"])


def _mock_budget_summary(message: str) -> str:
    return "根据您的项目信息，预估总预算约 18-25 万元（舒适型装修）。详细分项如下："


def _mock_budget_breakdown() -> str:
    return (
        "**分项预算明细**\n\n"
        "| 项目 | 预估金额 |\n"
        "|------|---------|\n"
        "| 硬装（水电+墙面+地面） | 90,000-110,000 |\n"
        "| 定制柜体（橱柜+衣柜） | 35,000-45,000 |\n"
        "| 软装（家具+窗帘+灯具） | 40,000-50,000 |\n"
        "| 家电设备 | 25,000-35,000 |\n"
        "| 管理费+其他 | 10,000-15,000 |"
    )


def _mock_cost_saving() -> str:
    return (
        "**省钱技巧**\n"
        "1. 瓷砖/地板：工厂直购省 15-20%\n"
        "2. 灯具：线上采购省 30%+\n"
        "3. 窗帘：辅材配件费用容易忽视，注意对比\n"
        "4. 家电：618/双11 批量采购，一套省 3000-5000"
    )


def _mock_purchase_plan() -> str:
    return (
        "**采购计划**\n\n"
        "按施工阶段分批采购，避免资金积压和材料损耗。\n"
        "第一阶段（开工）→ 水电材料\n"
        "第二阶段（水电后）→ 瓷砖、防水\n"
        "第三阶段（泥瓦后）→ 定制柜、门\n"
        "第四阶段（油漆后）→ 卫浴、灯具、家电"
    )


def _mock_supplier_rec() -> str:
    return (
        "**推荐供应商**\n\n"
        "- 瓷砖：东鹏、马可波罗（工厂直发）\n"
        "- 地板：圣象、大自然\n"
        "- 橱柜：欧派、索菲亚\n"
        "- 卫浴：科勒、TOTO\n"
        "- 家电：京东自营/天猫旗舰"
    )


def _mock_procurement_timeline() -> str:
    return "采购周期预计 30-45 天，关键节点：开工前 7 天确认水电材料，开工后 10 天确认瓷砖花色，开工后 20 天橱柜复尺下单。"


def _mock_phases() -> str:
    return (
        "**施工阶段**（总工期约 45 天）\n\n"
        "1. 准备阶段：Day 1-3\n"
        "2. 拆改阶段：Day 4-8\n"
        "3. 水电阶段：Day 9-18\n"
        "4. 泥瓦阶段：Day 19-32\n"
        "5. 木工阶段：Day 26-35（可与泥瓦交叉）\n"
        "6. 油漆阶段：Day 33-40\n"
        "7. 安装阶段：Day 40-43\n"
        "8. 验收阶段：Day 44-45"
    )


def _mock_schedule() -> str:
    return (
        "**关键里程碑**\n\n"
        "✅ Day 3：装修许可 & 材料进场\n"
        "✅ Day 8：拆改完成，垃圾清运\n"
        "✅ Day 18：水电验收（打压测试+线路测试）\n"
        "✅ Day 32：防水闭水试验 & 瓷砖铺贴完成\n"
        "✅ Day 40：油漆完成，等待安装\n"
        "✅ Day 45：竣工验收"
    )


def _mock_settlement() -> str:
    return (
        "⏣ **结算分析**\n\n"
        "根据项目进度，为您梳理结算情况：\n\n"
        "**结算公式**\n"
        "应付金额 = 合同金额 + 变更金额 - 扣款金额 - 已付金额\n\n"
        "**结算里程碑**\n"
        "1. 交房节点：支付 30%（约 50,000-75,000 元）\n"
        "2. 水电验收：支付 20%（约 35,000-50,000 元）\n"
        "3. 泥瓦验收：支付 25%（约 45,000-65,000 元）\n"
        "4. 竣工验收：支付 20%（约 35,000-50,000 元）\n"
        "5. 保修期满：支付 5%（约 8,000-12,500 元）\n\n"
        "建议每阶段验收合格后再付款，保留尾款作为质量保障。"
    )


def _mock_quality() -> str:
    return (
        "**质检检查清单**\n\n"
        "- 水电：水管打压 0.8MPa 半小时不掉压\n"
        "- 防水：闭水试验 48h 无渗漏\n"
        "- 瓷砖：空鼓率 < 5%\n"
        "- 墙面：平整度 2m 靠尺 ≤ 3mm\n"
        "- 木工：柜体对角线偏差 ≤ 2mm\n"
        "- 油漆：无色差、无流坠、无漏刷"
    )


def _mock_qa_inspection() -> str:
    return (
        "🔍 **质检报告**\n\n"
        "**分项验收结果**\n"
        "- 水电工程：合格（5/5 项通过）\n"
        "- 泥瓦工程：有条件合格（4/5 项通过，地漏坡度需调整）\n"
        "- 木工工程：合格（4/4 项通过）\n"
        "- 油漆工程：合格（4/4 项通过）\n"
        "- 安装工程：合格（4/4 项通过）\n\n"
        "**总体验收结论**：合格（合格率 95.5%）\n\n"
        "**整改建议**：\n"
        "1. 卫生间地漏坡度不足，建议重新找坡\n"
        "2. 瓷砖空鼓率检测需复检\n\n"
        "建议整改后复验，确认全部合格后签署验收报告。"
    )

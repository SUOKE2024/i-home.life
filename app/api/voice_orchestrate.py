"""语音智能体编排 API — 语音作为 Agent 调度入口

借鉴 GPT Voice / Claude Voice (2026-07) 的语音调度范式：
- POST /api/voice/orchestrate  一句话启动/编排后台 Agent 任务
- GET  /api/voice/orchestrate/tasks  任务列表（供 UI 轮询进度）

受 settings.voice_agent_orchestration_enabled feature flag 控制（默认关闭）。
"""

import logging

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.orchestrator import OrchestratorAgent
from app.api.voice_realtime import _get_enhanced_reply, _route_voice_to_agent
from app.auth import get_current_user
from app.config import get_settings
from app.database import get_db
from app.models.project import Project
from app.models.user import User
from app.services.voice_orchestrator import (
    VoiceTask,
    parse_task_command,
    split_multi_intent,
    voice_task_registry,
)

router = APIRouter(prefix="/voice/orchestrate", tags=["语音编排"])

settings = get_settings()
logger = logging.getLogger(__name__)

_INTENT_LABELS = {
    "design": "设计方案",
    "budget": "预算分析",
    "procurement": "物料采购",
    "construction": "施工进度",
    "qa_inspector": "质量检查",
    "settlement": "结算对账",
    "concierge": "客服咨询",
    "ar_measurement": "AR 测量",
}


class OrchestrateRequest(BaseModel):
    text: str = Field(min_length=1, max_length=2000)
    project_id: str | None = None


class LaunchedTask(BaseModel):
    task_id: str
    seq: int
    intent: str
    command: str


class OrchestrateResponse(BaseModel):
    transcript: str
    action: str  # launch | status | cancel | list
    launched: list[LaunchedTask] = []
    tasks: list[dict] = []
    reply: str


def _check_enabled() -> None:
    if not settings.voice_agent_orchestration_enabled:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="语音智能体编排功能未启用",
        )


async def _verify_project_ownership(
    project_id: str, current_user: User, db: AsyncSession
) -> None:
    result = await db.execute(select(Project).where(Project.id == project_id))
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="项目不存在")
    if current_user.role != "admin" and project.owner_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无权访问该项目")


def _task_brief(task: VoiceTask) -> str:
    label = _INTENT_LABELS.get(task.intent, task.intent)
    status_text = {
        "running": "进行中",
        "done": "已完成",
        "failed": "失败",
        "cancelled": "已取消",
    }.get(task.status, task.status)
    return f"任务 {task.seq}（{label}）：{status_text}"


async def _handle_task_control(
    action: str, task_ref: str | None, user_id: str, transcript: str
) -> OrchestrateResponse:
    if action == "list":
        tasks = await voice_task_registry.list(user_id)
        if not tasks:
            reply = "当前没有语音任务。您可以对我说「帮我设计客厅，同时做一份预算」来启动任务。"
        else:
            lines = [_task_brief(t) for t in tasks[-5:]]
            reply = "最近的语音任务：\n" + "\n".join(lines)
        return OrchestrateResponse(
            transcript=transcript, action="list",
            tasks=[t.to_dict() for t in tasks], reply=reply,
        )

    if action == "status":
        task = await voice_task_registry.resolve(user_id, task_ref)
        if task is None:
            return OrchestrateResponse(
                transcript=transcript, action="status",
                reply="没有找到对应的任务。对我说「任务列表」可以查看全部任务。",
            )
        brief = _task_brief(task)
        if task.status == "done" and task.reply:
            reply = f"{brief}\n\n{task.reply}"
        elif task.status == "failed":
            reply = f"{brief}，原因：{task.error or '未知错误'}。可以再说一次重新启动。"
        else:
            reply = f"{brief}。完成后我会第一时间告诉您。"
        return OrchestrateResponse(
            transcript=transcript, action="status", tasks=[task.to_dict()], reply=reply,
        )

    # cancel
    task = await voice_task_registry.cancel(user_id, task_ref)
    if task is None:
        return OrchestrateResponse(
            transcript=transcript, action="cancel",
            reply="没有找到对应的任务。对我说「任务列表」可以查看全部任务。",
        )
    if task.status == "cancelled":
        reply = f"已取消：{_task_brief(task)}。"
    else:
        brief = _task_brief(task)
        reply = f"{brief}，无需取消。"
    return OrchestrateResponse(
        transcript=transcript, action="cancel", tasks=[task.to_dict()], reply=reply,
    )


async def _launch_segment_tasks(
    user_id: str, user_name: str, segments: list[str], db=None,
) -> tuple[list[LaunchedTask], list[str]]:
    """多意图切分后的指令段 → 意图分类 → 并行启动后台 Agent 任务。

    general 意图段不启动任务，转为内联回复。供 REST 端点与
    realtime WebSocket 编排钩子复用。

    v1.13.x P2-2: 新增 db 透传，使后台 Agent 任务享有 RAG/自进化注入
    与 Case 沉淀（与文本/语音主链路 v1.13.3 闭环对齐）。
    """
    launched: list[LaunchedTask] = []
    inline_replies: list[str] = []
    for segment in segments:
        intent = OrchestratorAgent.fallback_classify(segment).get("intent", "general")
        if intent == "general":
            inline_replies.append(_get_enhanced_reply(segment, intent, None))
            continue
        task = await voice_task_registry.launch(
            user_id, intent, segment,
            _route_voice_to_agent(segment, intent, user_name, db=db, user_id=user_id),
        )
        launched.append(LaunchedTask(
            task_id=task.task_id, seq=task.seq, intent=intent, command=segment,
        ))
    return launched, inline_replies


def _format_launch_reply(
    launched: list[LaunchedTask], inline_replies: list[str]
) -> str:
    """生成调度回执文案。"""
    parts: list[str] = []
    if launched:
        if len(launched) == 1:
            t = launched[0]
            parts.append(
                f"好的，已启动{_INTENT_LABELS.get(t.intent, t.intent)}（任务 {t.seq}），"
                "我在后台处理，您可以继续忙别的。"
            )
        else:
            items = "、".join(
                f"{_INTENT_LABELS.get(t.intent, t.intent)}（任务 {t.seq}）" for t in launched
            )
            parts.append(f"好的，已并行启动 {len(launched)} 个任务：{items}。")
        parts.append("随时对我说「任务进度」查看进展，或说「取消任务」叫停。")
    parts.extend(inline_replies)
    if not parts:
        parts.append("抱歉，我没有理解您的指令。可以说「帮我设计客厅，同时做一份预算」试试。")
    return "\n".join(parts)


@router.post("", response_model=OrchestrateResponse)
async def orchestrate_voice(
    data: OrchestrateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """语音智能体编排：一句话启动 / 查询 / 取消后台 Agent 任务。

    - 任务控制指令（"任务进度"/"取消任务 1"/"任务列表"）→ 直接操作注册表
    - 业务指令 → 多意图切分 + 意图分类 + 后台并行执行 Agent 管道
    """
    _check_enabled()
    if data.project_id:
        await _verify_project_ownership(data.project_id, current_user, db)

    text = data.text

    # 1. 任务控制指令优先（生命周期语音控制）
    control = parse_task_command(text)
    if control:
        return await _handle_task_control(
            control["action"], control["task_ref"], current_user.id, text,
        )

    # 2. 多意图切分 → 并行启动后台 Agent 任务
    segments = split_multi_intent(text)
    launched, inline_replies = await _launch_segment_tasks(
        current_user.id, current_user.name, segments, db=db,
    )

    # 3. 生成调度回执
    reply = _format_launch_reply(launched, inline_replies)

    logger.info(
        "voice_orchestrate: user=%s launched=%d inline=%d",
        current_user.id, len(launched), len(inline_replies),
    )
    return OrchestrateResponse(
        transcript=text, action="launch" if launched else "reply",
        launched=launched, reply=reply,
    )


@router.get("/tasks")
async def list_voice_tasks(current_user: User = Depends(get_current_user)):
    """语音任务列表（供 UI 轮询任务进度）。"""
    _check_enabled()
    tasks = await voice_task_registry.list(current_user.id)
    return {"tasks": [t.to_dict() for t in tasks]}

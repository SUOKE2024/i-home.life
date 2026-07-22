"""A2A (Agent-to-Agent) 协议 API（借鉴索克生活 A2A v1.0 实现）

基于 Google A2A v1.0 规范，暴露 Agent Card + Task Machine：
- GET  /.well-known/agent-card  公开发现端点（无 /api 前缀，A2A 规范要求）
- GET  /api/a2a/agents          列出已注册 Agent
- POST /api/a2a/tasks/send      下发任务到指定 Agent
- GET  /api/a2a/tasks/{id}      查询任务详情
- GET  /api/a2a/tasks/{id}/status  查询任务状态

所有非公开端点需 PASETO 鉴权；任务下发/查询受 settings.a2a_enabled feature flag 控制。
"""
import logging
import uuid
from enum import Enum
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from app.agents.harness import AgentRunStatus, get_harness
from app.auth import get_current_user
from app.config import get_settings
from app.models.user import User

router = APIRouter(prefix="/a2a", tags=["A2A 协议"])
# A2A v1.0 规范要求 Agent Card 暴露在 /.well-known/agent-card（无 /api 前缀）
public_router = APIRouter(tags=["A2A 协议"])

settings = get_settings()
logger = logging.getLogger(__name__)

# 22 个已注册 Agent 的类名（覆盖全平台 Agent 能力）
REGISTERED_AGENT_NAMES: list[str] = [
    "OrchestratorAgent", "DesignerAgent", "BudgetAgent", "ProcurementAgent",
    "ConstructionAgent", "SettlementAgent", "QAInspectorAgent", "ConciergeAgent",
    "ContentPublisherAgent", "AdminAgent", "KitchenAgent", "BathroomAgent",
    "MepAgent", "ApplianceAgent", "FurnitureAgent", "DoorWindowAgent",
    "FilesAgent", "ProductsAgent", "IdentityAgent", "NotificationsAgent",
    "TakeoffAgent", "IfcExportAgent",
]

_AGENT_DESCRIPTIONS: dict[str, str] = {
    "OrchestratorAgent": "全流程编排，跨 Agent 协同调度",
    "DesignerAgent": "室内设计方案生成，3套平面布局",
    "BudgetAgent": "工程报价，含税/质保金/漏项检查",
    "ProcurementAgent": "材料采购，供应商对接",
    "ConstructionAgent": "施工管理，进度/工序/工种调度",
    "SettlementAgent": "工程结算，对账/尾款",
    "QAInspectorAgent": "质量验收，整改/返工",
    "ConciergeAgent": "售后客服，投诉/保修",
    "ContentPublisherAgent": "产品发布，供应商上架",
    "AdminAgent": "平台管理，用户/权限/统计",
    "KitchenAgent": "厨房空间设计",
    "BathroomAgent": "卫浴空间设计，干湿分离/防水",
    "MepAgent": "水电方案，强弱电/给排水",
    "ApplianceAgent": "家电选型，中央空调/厨电",
    "FurnitureAgent": "家具选择与尺寸适配",
    "DoorWindowAgent": "门窗方案与防水工程",
    "FilesAgent": "文件管理，图纸/合同上传",
    "ProductsAgent": "建材/家居产品管理",
    "IdentityAgent": "实名认证，身份证/企业资质",
    "NotificationsAgent": "通知推送，多渠道消息",
    "TakeoffAgent": "工程量计算，算量",
    "IfcExportAgent": "BIM/IFC 模型导出",
}

# 内存任务存储（简化实现；生产环境可换 Redis）
_tasks: dict[str, dict] = {}


# ════════════════════════════════════════════════════════════════
# Pydantic 模型
# ════════════════════════════════════════════════════════════════


class A2ATaskState(str, Enum):
    """A2A 任务状态机"""
    SUBMITTED = "submitted"
    WORKING = "working"
    COMPLETED = "completed"
    FAILED = "failed"


class A2ASkill(BaseModel):
    """Agent 技能描述"""
    name: str
    description: str = ""


class A2AAgentCard(BaseModel):
    """A2A Agent Card — 描述本节点暴露的 Agent 能力"""
    name: str
    version: str
    description: str
    capabilities: dict[str, Any] = {}
    skills: list[A2ASkill] = []
    registered_agents: list[str] = []


class A2ATaskRequest(BaseModel):
    """A2A 任务请求"""
    agent_name: str
    message: str
    project_id: str | None = None


class A2ATaskResponse(BaseModel):
    """A2A 任务响应"""
    task_id: str
    state: A2ATaskState
    result: Any = None
    error: str | None = None


# ════════════════════════════════════════════════════════════════
# 端点
# ════════════════════════════════════════════════════════════════


@router.get("/.well-known/agent-card", response_model=A2AAgentCard)
@public_router.get("/.well-known/agent-card", response_model=A2AAgentCard)
async def get_agent_card() -> A2AAgentCard:
    """获取 Agent Card（公开端点，无需认证）。

    按 A2A v1.0 规范，Agent Card 描述本节点暴露的 Agent 能力，
    供外部系统发现并决定是否下发任务。
    """
    skills = [
        A2ASkill(name=name, description=_AGENT_DESCRIPTIONS.get(name, ""))
        for name in REGISTERED_AGENT_NAMES
    ]
    return A2AAgentCard(
        name=settings.app_name,
        version=settings.app_version,
        description="i-home.life 智能家居/室内设计平台 A2A 节点 — 22 个专业 Agent 协同",
        capabilities={
            "streaming": False,
            "pushNotifications": False,
            "stateTransition": True,
        },
        skills=skills,
        registered_agents=REGISTERED_AGENT_NAMES,
    )


@router.get("/agents")
async def list_agents(
    current_user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """列出已注册的 Agent（来自 Harness 注册表）。"""
    harness = get_harness()
    return {
        "agents": harness._agent_registry,
        "count": len(harness._agent_registry),
    }


@router.post("/tasks/send", response_model=A2ATaskResponse)
async def send_task(
    request: A2ATaskRequest,
    current_user: User = Depends(get_current_user),
) -> A2ATaskResponse:
    """下发任务到指定 Agent。

    通过 Harness 运行 Agent 并返回结果。受 settings.a2a_enabled feature flag 控制。
    """
    if not settings.a2a_enabled:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="A2A 协议未启用",
        )

    task_id = f"a2a_{uuid.uuid4().hex[:12]}"
    _tasks[task_id] = {"task_id": task_id, "state": A2ATaskState.WORKING, "result": None}

    harness = get_harness()
    agent_cls = harness._agent_registry.get(request.agent_name)
    if not agent_cls:
        _tasks[task_id]["state"] = A2ATaskState.FAILED
        _tasks[task_id]["error"] = f"Agent '{request.agent_name}' 未注册"
        return A2ATaskResponse(
            task_id=task_id, state=A2ATaskState.FAILED,
            error=f"Agent '{request.agent_name}' 未注册",
        )

    trace = None
    try:
        agent = agent_cls()
        trace = harness.start_trace(
            request.agent_name, request.message,
            user_id=current_user.id, project_id=request.project_id or "",
        )
        result = await harness.run(
            agent=agent,
            user_message=request.message,
            trace=trace,
        )
        harness.finish_trace(trace, AgentRunStatus.SUCCESS)
        _tasks[task_id]["state"] = A2ATaskState.COMPLETED
        _tasks[task_id]["result"] = result.get("reply", "")
        return A2ATaskResponse(
            task_id=task_id,
            state=A2ATaskState.COMPLETED,
            result=result.get("reply", ""),
        )
    except Exception as e:
        logger.error("a2a_task_failed: agent=%s error=%s", request.agent_name, e)
        if trace:
            harness.finish_trace(trace, AgentRunStatus.FAILED)
        _tasks[task_id]["state"] = A2ATaskState.FAILED
        _tasks[task_id]["error"] = str(e)
        return A2ATaskResponse(
            task_id=task_id, state=A2ATaskState.FAILED, error=str(e),
        )


@router.get("/tasks/{task_id}")
async def get_task(
    task_id: str,
    current_user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """查询任务详情。"""
    if not settings.a2a_enabled:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="A2A 协议未启用",
        )
    task = _tasks.get(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")
    return task


@router.get("/tasks/{task_id}/status")
async def get_task_status(
    task_id: str,
    current_user: User = Depends(get_current_user),
) -> dict[str, str]:
    """查询任务状态。"""
    if not settings.a2a_enabled:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="A2A 协议未启用",
        )
    task = _tasks.get(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")
    return {"task_id": task_id, "state": task["state"]}

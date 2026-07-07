"""水电点位规划路由 — F22 + F20"""

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from app.models.user import User
from app.auth import get_current_user
from app.services import mep_service

router = APIRouter(prefix="/mep", tags=["水电点位"])


class RoomRequest(BaseModel):
    name: str
    room_type: str = "bedroom"
    area: float | None = None


class MepPlanRequest(BaseModel):
    rooms: list[RoomRequest]


class ComplianceRequest(BaseModel):
    points: list[dict]


@router.post("/plan")
async def generate_mep_plan(
    data: MepPlanRequest,
    current_user: User = Depends(get_current_user),
):
    """根据房间清单生成水电点位规划（F22）"""
    return mep_service.generate_mep_plan([r.model_dump() for r in data.rooms])


@router.post("/appliances")
async def generate_appliance_plan(
    data: MepPlanRequest,
    current_user: User = Depends(get_current_user),
):
    """电器点位规划（F20）"""
    return mep_service.generate_appliance_plan([r.model_dump() for r in data.rooms])


@router.post("/compliance-check")
async def check_compliance(
    data: ComplianceRequest,
    current_user: User = Depends(get_current_user),
):
    """水电点位合规性检查"""
    return mep_service.check_mep_compliance(data.points)


@router.get("/room-standards/{room_type}")
async def get_room_standards(
    room_type: str,
    current_user: User = Depends(get_current_user),
):
    """查询指定房型的标准水电配置"""
    from app.services.mep_service import ROOM_MEP_STANDARDS
    standard = ROOM_MEP_STANDARDS.get(room_type)
    if not standard:
        return {"error": f"未知房型: {room_type}", "available": list(ROOM_MEP_STANDARDS.keys())}
    return standard

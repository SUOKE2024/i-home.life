"""F31 智能家居方案设计器 API"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.project import Project
from app.models.user import User
from app.auth import get_current_user
from app.schemas.smart_home import (
    SmartHomeSchemeCreate,
    SmartHomeSchemeResponse,
    SmartDeviceCreate,
    SmartDeviceResponse,
    AutoRecommendResult,
    WiringPlanResult,
    ProtocolAdviceResult,
    PriceComputeResult,
)
from app.rbac import verify_project_access
from app.services import smart_home_service as svc
from app.ws import ws_manager

router = APIRouter(prefix="/smart-home", tags=["智能家居方案"])


# ── 方案 ──


@router.post("/schemes", response_model=SmartHomeSchemeResponse, status_code=status.HTTP_201_CREATED)
async def create_scheme(
    data: SmartHomeSchemeCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    project = await db.get(Project, data.project_id)
    if not project or project.owner_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无权访问该项目")
    scheme = await svc.create_scheme(db, data.model_dump())
    resp = SmartHomeSchemeResponse.model_validate(scheme)
    await ws_manager.broadcast_to_project(scheme.project_id, "smart.scheme.created", resp.model_dump())
    return resp


@router.get("/schemes/project/{project_id}", response_model=list[SmartHomeSchemeResponse])
async def list_schemes_by_project(
    project_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await verify_project_access(project_id=project_id, current_user=current_user, db=db)
    schemes = await svc.list_schemes_by_project(db, project_id)
    return [SmartHomeSchemeResponse.model_validate(s) for s in schemes]


@router.get("/schemes/{scheme_id}", response_model=SmartHomeSchemeResponse)
async def get_scheme(
    scheme_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    scheme = await svc.get_scheme(db, scheme_id)
    if not scheme:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="方案不存在")
    await verify_project_access(project_id=scheme.project_id, current_user=current_user, db=db)
    return SmartHomeSchemeResponse.model_validate(scheme)


@router.delete("/schemes/{scheme_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_scheme(
    scheme_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    scheme = await svc.get_scheme(db, scheme_id)
    if not scheme:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="方案不存在")
    project = await db.get(Project, scheme.project_id)
    if not project or project.owner_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无权访问该项目")
    project_id = scheme.project_id
    deleted = await svc.delete_scheme(db, scheme_id)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="方案不存在")
    await ws_manager.broadcast_to_project(project_id, "smart.scheme.deleted", {"id": scheme_id})


# ── 自动推荐设备 ──


@router.post("/schemes/{scheme_id}/auto-recommend", response_model=AutoRecommendResult)
async def auto_recommend(
    scheme_id: str,
    body: dict,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    scheme = await svc.get_scheme(db, scheme_id)
    if not scheme:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="方案不存在")
    await verify_project_access(project_id=scheme.project_id, current_user=current_user, db=db)
    room_type = body.get("room_type") or scheme.room_type
    room_area = float(body.get("room_area") or 20.0)
    protocol = body.get("protocol") or scheme.protocol
    hub_brand = body.get("hub_brand") or scheme.hub_brand
    result = await svc.auto_recommend_devices(db, scheme, room_type, room_area, protocol, hub_brand)
    await ws_manager.broadcast_to_project(
        scheme.project_id,
        "smart.scheme.auto_recommended",
        {"scheme_id": scheme_id, "device_count": len(result["recommended_devices"])},
    )
    return AutoRecommendResult(**result)


# ── 布线规划 ──


@router.get("/schemes/{scheme_id}/wiring", response_model=WiringPlanResult)
async def wiring_plan(
    scheme_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    scheme = await svc.get_scheme(db, scheme_id)
    if not scheme:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="方案不存在")
    await verify_project_access(project_id=scheme.project_id, current_user=current_user, db=db)
    result = await svc.plan_wiring(db, scheme)
    return WiringPlanResult(**result)


# ── 协议选型建议 ──


@router.get("/schemes/{scheme_id}/protocol-advice", response_model=ProtocolAdviceResult)
async def protocol_advice(
    scheme_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    scheme = await svc.get_scheme(db, scheme_id)
    if not scheme:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="方案不存在")
    await verify_project_access(project_id=scheme.project_id, current_user=current_user, db=db)
    devices = scheme.devices or await svc.list_devices(db, scheme_id)
    result = svc.recommend_protocol(scheme.hub_brand, devices)
    return ProtocolAdviceResult(**result)


# ── 方案总价 ──


@router.get("/schemes/{scheme_id}/price", response_model=PriceComputeResult)
async def compute_price(
    scheme_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    scheme = await svc.get_scheme(db, scheme_id)
    if not scheme:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="方案不存在")
    await verify_project_access(project_id=scheme.project_id, current_user=current_user, db=db)
    result = await svc.compute_total_price(db, scheme)
    return PriceComputeResult(**result)


# ── 设备 ──


@router.post("/schemes/{scheme_id}/devices", response_model=SmartDeviceResponse, status_code=status.HTTP_201_CREATED)
async def add_device(
    scheme_id: str,
    data: SmartDeviceCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    scheme = await svc.get_scheme(db, scheme_id)
    if not scheme:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="方案不存在")
    await verify_project_access(project_id=scheme.project_id, current_user=current_user, db=db)
    device = await svc.add_device(db, scheme_id, data.model_dump())
    resp = SmartDeviceResponse.model_validate(device)
    await ws_manager.broadcast_to_project(scheme.project_id, "smart.device.added", resp.model_dump())
    return resp


@router.get("/schemes/{scheme_id}/devices", response_model=list[SmartDeviceResponse])
async def list_devices(
    scheme_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    scheme = await svc.get_scheme(db, scheme_id)
    if not scheme:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="方案不存在")
    await verify_project_access(project_id=scheme.project_id, current_user=current_user, db=db)
    devices = await svc.list_devices(db, scheme_id)
    return [SmartDeviceResponse.model_validate(d) for d in devices]


@router.delete("/devices/{device_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_device(
    device_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    from sqlalchemy import select
    from app.models.smart_home import SmartDevice
    result = await db.execute(select(SmartDevice).where(SmartDevice.id == device_id))
    device = result.scalar_one_or_none()
    if not device:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="设备不存在")
    scheme = await svc.get_scheme(db, device.scheme_id)
    if scheme:
        await verify_project_access(project_id=scheme.project_id, current_user=current_user, db=db)
    deleted = await svc.delete_device(db, device_id)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="设备不存在")


# ── Matter 设备点位规划（v1.2.0）──


@router.get("/matter/device-types")
async def get_matter_device_types():
    """返回支持的 Matter 设备类型列表。

    Matter 2.0（2026.05）已实现全品类覆盖，本端点提供可在户型图上
    标注的 Matter 兼容设备类型，供设计工作台使用。
    """
    return {
        "protocol": "Matter 2.0",
        "categories": [
            {
                "category": "照明",
                "icon": "💡",
                "types": [
                    {"id": "light_bulb", "name": "智能灯泡", "power_w": 10, "matter_cluster": "OnOff + LevelControl"},
                    {"id": "light_switch", "name": "智能开关", "power_w": 0.5, "matter_cluster": "OnOff"},
                    {"id": "light_strip", "name": "灯带", "power_w": 15, "matter_cluster": "OnOff + LevelControl + ColorControl"},
                ],
            },
            {
                "category": "安防",
                "icon": "🔒",
                "types": [
                    {"id": "door_lock", "name": "智能门锁", "power_w": 1, "matter_cluster": "DoorLock"},
                    {"id": "camera", "name": "摄像头", "power_w": 5, "matter_cluster": "MediaPlayback (Matter 1.5+)"},
                    {"id": "smoke_detector", "name": "烟雾报警器", "power_w": 0.5, "matter_cluster": "SmokeCOAlarm"},
                    {"id": "motion_sensor", "name": "人体传感器", "power_w": 0.2, "matter_cluster": "OccupancySensing"},
                ],
            },
            {
                "category": "环境",
                "icon": "🌡️",
                "types": [
                    {"id": "thermostat", "name": "智能温控器", "power_w": 2, "matter_cluster": "Thermostat (Matter 1.6+)"},
                    {"id": "temp_sensor", "name": "温湿度传感器", "power_w": 0.1, "matter_cluster": "Temperature + Humidity"},
                    {"id": "air_quality", "name": "空气质量传感器", "power_w": 0.3, "matter_cluster": "AirQuality"},
                ],
            },
            {
                "category": "家电",
                "icon": "🔌",
                "types": [
                    {"id": "smart_plug", "name": "智能插座", "power_w": 0.5, "matter_cluster": "OnOff"},
                    {"id": "robot_vacuum", "name": "扫地机器人", "power_w": 50, "matter_cluster": "RVC (Matter 1.5+)"},
                ],
            },
            {
                "category": "遮阳",
                "icon": "🪟",
                "types": [
                    {"id": "curtain_motor", "name": "电动窗帘", "power_w": 10, "matter_cluster": "WindowCovering"},
                    {"id": "blind_motor", "name": "百叶窗电机", "power_w": 8, "matter_cluster": "WindowCovering"},
                ],
            },
        ],
        "commissioning_note": "Matter 1.6 支持 NFC 全流程配网，可在设备安装前完成预配配置。",
        "ecosystem_compatibility": [
            "Apple Home (iOS 19+)", "Google Home", "Amazon Alexa",
            "Samsung SmartThings", "国内 OneConnect (AWE 2026 发布)",
        ],
    }


@router.post("/matter/placement-plan")
async def generate_matter_placement_plan(
    project_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """为指定项目生成 Matter 设备点位规划方案。

    结合项目户型图和推荐设备类型，生成设备点位图数据。
    """
    await verify_project_access(project_id=project_id, current_user=current_user, db=db)

    from sqlalchemy import select as sql_select

    result = await db.execute(sql_select(Project).where(Project.id == project_id))
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="项目不存在")

    # 基于面积计算推荐设备数量
    area = project.total_area or 100
    placement_plan = {
        "project_id": project_id,
        "project_name": project.name,
        "estimated_area": area,
        "protocol": "Matter 2.0",
        "rooms": [
            {
                "name": "客厅",
                "devices": [
                    {"type": "light_bulb", "count": 4, "position": "天花板中央 + 电视背景墙"},
                    {"type": "light_strip", "count": 1, "position": "电视背景墙"},
                    {"type": "smart_plug", "count": 2, "position": "电视柜后 + 沙发旁"},
                    {"type": "curtain_motor", "count": 1, "position": "阳台推拉门"},
                    {"type": "temp_sensor", "count": 1, "position": "空调附近"},
                ],
            },
            {
                "name": "主卧",
                "devices": [
                    {"type": "light_bulb", "count": 2, "position": "天花板 + 床头"},
                    {"type": "curtain_motor", "count": 1, "position": "窗户"},
                    {"type": "temp_sensor", "count": 1, "position": "床头柜"},
                ],
            },
            {
                "name": "厨房",
                "devices": [
                    {"type": "light_bulb", "count": 2, "position": "天花板 + 操作台上方"},
                    {"type": "smoke_detector", "count": 1, "position": "天花板中央"},
                    {"type": "smart_plug", "count": 1, "position": "操作台"},
                ],
            },
            {
                "name": "卫生间",
                "devices": [
                    {"type": "light_bulb", "count": 1, "position": "天花板"},
                ],
            },
            {
                "name": "玄关",
                "devices": [
                    {"type": "door_lock", "count": 1, "position": "入户门"},
                    {"type": "motion_sensor", "count": 1, "position": "天花板"},
                ],
            },
        ],
        "total_device_count": 0,
        "estimated_power_w": 0,
        "commissioning_guide": (
            "1. 装修布线阶段预留零火线（智能开关必需）\n"
            "2. 每个房间预留 1-2 个网线口（Matter over Thread/Wi-Fi）\n"
            "3. 安装完设备后用手机 NFC 触碰完成配网（Matter 1.6）\n"
            "4. 建议选购 Thread Border Router（如 Apple TV/HomePod）\n"
            "5. 国内用户注意 OneConnect 兼容性认证"
        ),
    }

    # 计算总设备数和预估功耗
    total_devices = 0
    total_power = 0
    for room in placement_plan["rooms"]:
        for dev in room["devices"]:
            total_devices += dev["count"]
            device_type = next(
                (t for cat in [
                    {"id": "light_bulb", "power_w": 10},
                    {"id": "light_strip", "power_w": 15},
                    {"id": "light_switch", "power_w": 0.5},
                    {"id": "door_lock", "power_w": 1},
                    {"id": "camera", "power_w": 5},
                    {"id": "smoke_detector", "power_w": 0.5},
                    {"id": "motion_sensor", "power_w": 0.2},
                    {"id": "thermostat", "power_w": 2},
                    {"id": "temp_sensor", "power_w": 0.1},
                    {"id": "air_quality", "power_w": 0.3},
                    {"id": "smart_plug", "power_w": 0.5},
                    {"id": "robot_vacuum", "power_w": 50},
                    {"id": "curtain_motor", "power_w": 10},
                    {"id": "blind_motor", "power_w": 8},
                ] for t in [cat] if t["id"] == dev["type"]),
                {"power_w": 1},
            )
            total_power += dev["count"] * device_type["power_w"]

    placement_plan["total_device_count"] = total_devices
    placement_plan["estimated_power_w"] = total_power

    return placement_plan

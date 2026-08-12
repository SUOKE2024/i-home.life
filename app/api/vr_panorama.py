"""视觉表现层 VR 全景 API — 全景图渲染 + 热点管理 + VR 场景漫游"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.auth import get_current_user
from app.rbac import verify_project_access
from app.models.user import User
from app.schemas.vr_panorama import (
    VRPanoramaCreate,
    VRPanoramaUpdate,
    VRPanoramaResponse,
    VRPanoramaListItem,
    EffectRenderPublishRequest,
    HotspotCreate,
    RenderPanoramaRequest,
    VRSceneCreate,
    VRSceneUpdate,
    VRSceneResponse,
)
from app.services import vr_panorama_service
from app.ws import ws_manager

router = APIRouter(prefix="/vr", tags=["VR 全景"])


# ── 全景图 ──


@router.post("/panoramas", response_model=VRPanoramaResponse, status_code=status.HTTP_201_CREATED)
async def create_panorama(
    body: VRPanoramaCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """创建全景图记录。"""
    await verify_project_access(project_id=body.project_id, current_user=user, db=db)
    data = body.model_dump()
    if data.get("initial_view") and hasattr(data["initial_view"], "model_dump"):
        data["initial_view"] = data["initial_view"].model_dump()
    panorama = await vr_panorama_service.create_panorama(db, data)
    resp = VRPanoramaResponse.model_validate(panorama)
    await ws_manager.broadcast_to_project(
        panorama.project_id, "vr.panorama.created", resp.model_dump()
    )
    return resp


@router.post(
    "/panoramas/from-effect-render",
    response_model=VRPanoramaResponse,
    status_code=status.HTTP_201_CREATED,
)
async def publish_effect_render(
    body: EffectRenderPublishRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """把 AI 效果图发布为效果图漫游全景（设计 4.1「先看后装」）。

    image_url 为 ai_render 2D 效果图产物（普通 2D 图，非等距柱状）；
    落库 content_source=effect，前端 2D 平面预览并诚实标注「效果图预览 · 非实景」，
    不伪造 360° 沉浸感（2D→3D .spz 内容管线待 GPU 立项，M3 余项）。
    """
    await verify_project_access(project_id=body.project_id, current_user=user, db=db)
    panorama = await vr_panorama_service.publish_effect_render(
        db,
        project_id=body.project_id,
        room_name=body.room_name,
        image_url=body.image_url,
    )
    resp = VRPanoramaResponse.model_validate(panorama)
    await ws_manager.broadcast_to_project(
        panorama.project_id, "vr.panorama.created", resp.model_dump()
    )
    return resp


@router.get("/panoramas/project/{project_id}", response_model=list[VRPanoramaListItem])
async def list_panoramas(
    project_id: str,
    status_filter: str | None = None,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    await verify_project_access(project_id=project_id, current_user=user, db=db)
    panoramas = await vr_panorama_service.list_panoramas(db, project_id, status_filter)
    # ORM 的 initial_view / hotspots 是 JSON 字符串,这里透传为解析后的 dict/list
    return [
        VRPanoramaListItem(
            id=p.id,
            project_id=p.project_id,
            room_name=p.room_name,
            panorama_type=p.panorama_type,
            content_source=p.content_source,
            image_url=p.image_url,
            splat_url=p.splat_url,
            thumbnail_url=p.thumbnail_url,
            resolution=p.resolution,
            initial_view=p.initial_view_dict or None,
            hotspots=p.hotspot_list or [],
            status=p.status,
            created_at=p.created_at,
        )
        for p in panoramas
    ]


@router.get("/panoramas/{panorama_id}", response_model=VRPanoramaResponse)
async def get_panorama(
    panorama_id: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    panorama = await vr_panorama_service.get_panorama(db, panorama_id)
    if not panorama:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="全景图不存在")
    await verify_project_access(project_id=panorama.project_id, current_user=user, db=db)
    return panorama


@router.post("/panoramas/{panorama_id}/render", response_model=VRPanoramaResponse)
async def render_panorama(
    panorama_id: str,
    body: RenderPanoramaRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """触发全景图渲染 (mock 实现)。"""
    panorama = await vr_panorama_service.get_panorama(db, panorama_id)
    if not panorama:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="全景图不存在")
    await verify_project_access(project_id=panorama.project_id, current_user=user, db=db)
    rendered = await vr_panorama_service.render_panorama(
        db, panorama_id, body.floorplan_data, body.quality
    )
    if not rendered:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="渲染失败")
    resp = VRPanoramaResponse.model_validate(rendered)
    await ws_manager.broadcast_to_project(
        panorama.project_id, "vr.panorama.rendered", resp.model_dump()
    )
    return resp


@router.patch("/panoramas/{panorama_id}", response_model=VRPanoramaResponse)
async def update_panorama(
    panorama_id: str,
    body: VRPanoramaUpdate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """更新全景图元数据 (image_url/thumbnail_url/status)。"""
    panorama = await vr_panorama_service.get_panorama(db, panorama_id)
    if not panorama:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="全景图不存在")
    await verify_project_access(project_id=panorama.project_id, current_user=user, db=db)
    updated = await vr_panorama_service.update_panorama(db, panorama_id, body.model_dump(exclude_none=True))
    if not updated:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="全景图不存在")
    resp = VRPanoramaResponse.model_validate(updated)
    await ws_manager.broadcast_to_project(
        panorama.project_id, "vr.panorama.updated", resp.model_dump()
    )
    return resp


# ── 热点 ──


@router.post("/panoramas/{panorama_id}/hotspots", response_model=VRPanoramaResponse)
async def add_hotspot(
    panorama_id: str,
    body: HotspotCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """添加热点 (跳转其他房间/户型/外部链接)。"""
    panorama = await vr_panorama_service.get_panorama(db, panorama_id)
    if not panorama:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="全景图不存在")
    await verify_project_access(project_id=panorama.project_id, current_user=user, db=db)
    hotspot_data = body.model_dump()
    updated = await vr_panorama_service.add_hotspot(db, panorama_id, hotspot_data)
    resp = VRPanoramaResponse.model_validate(updated)
    await ws_manager.broadcast_to_project(
        panorama.project_id, "vr.hotspot.added", {"panorama_id": panorama_id, "hotspot": hotspot_data}
    )
    return resp


@router.get("/panoramas/{panorama_id}/hotspots", response_model=list[dict])
async def list_hotspots(
    panorama_id: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    panorama = await vr_panorama_service.get_panorama(db, panorama_id)
    if not panorama:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="全景图不存在")
    await verify_project_access(project_id=panorama.project_id, current_user=user, db=db)
    return await vr_panorama_service.list_hotspots(db, panorama_id)


@router.delete("/hotspots/{panorama_id}/{hotspot_index}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_hotspot(
    panorama_id: str,
    hotspot_index: int,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """通过索引删除热点 (hotspot 是 panorama.hotspots JSON 字段中的元素)。"""
    panorama = await vr_panorama_service.get_panorama(db, panorama_id)
    if not panorama:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="全景图不存在")
    await verify_project_access(project_id=panorama.project_id, current_user=user, db=db)
    updated = await vr_panorama_service.delete_hotspot(db, panorama_id, hotspot_index)
    if not updated:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="热点不存在")
    await ws_manager.broadcast_to_project(
        panorama.project_id,
        "vr.hotspot.deleted",
        {"panorama_id": panorama_id, "hotspot_index": hotspot_index},
    )


# ── 全景图删除 ──


@router.delete("/panoramas/{panorama_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_panorama(
    panorama_id: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    panorama = await vr_panorama_service.get_panorama(db, panorama_id)
    if not panorama:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="全景图不存在")
    await verify_project_access(project_id=panorama.project_id, current_user=user, db=db)
    project_id = panorama.project_id
    deleted = await vr_panorama_service.delete_panorama(db, panorama_id)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="全景图不存在")
    await ws_manager.broadcast_to_project(
        project_id, "vr.panorama.deleted", {"id": panorama_id}
    )


# ── VR 场景 ──


@router.post("/scenes", response_model=VRSceneResponse, status_code=status.HTTP_201_CREATED)
async def create_scene(
    body: VRSceneCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """创建 VR 场景 (多个全景图按顺序组合,支持漫游)。"""
    await verify_project_access(project_id=body.project_id, current_user=user, db=db)
    data = body.model_dump()
    scene = await vr_panorama_service.create_scene(db, data)
    resp = VRSceneResponse.model_validate(scene)
    await ws_manager.broadcast_to_project(
        scene.project_id, "vr.scene.created", resp.model_dump()
    )
    return resp


@router.get("/scenes/project/{project_id}", response_model=list[VRSceneResponse])
async def list_scenes(
    project_id: str,
    status_filter: str | None = None,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    await verify_project_access(project_id=project_id, current_user=user, db=db)
    return await vr_panorama_service.list_scenes(db, project_id, status_filter)


@router.get("/scenes/{scene_id}", response_model=VRSceneResponse)
async def get_scene(
    scene_id: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    scene = await vr_panorama_service.get_scene(db, scene_id)
    if not scene:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="VR 场景不存在")
    await verify_project_access(project_id=scene.project_id, current_user=user, db=db)
    return scene


@router.patch("/scenes/{scene_id}", response_model=VRSceneResponse)
async def update_scene(
    scene_id: str,
    body: VRSceneUpdate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """更新场景 (添加/删除 panorama)。"""
    scene = await vr_panorama_service.get_scene(db, scene_id)
    if not scene:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="VR 场景不存在")
    await verify_project_access(project_id=scene.project_id, current_user=user, db=db)
    data = body.model_dump(exclude_none=True)
    updated = await vr_panorama_service.update_scene(db, scene_id, data)
    resp = VRSceneResponse.model_validate(updated)
    await ws_manager.broadcast_to_project(
        scene.project_id, "vr.scene.updated", resp.model_dump()
    )
    return resp


@router.delete("/scenes/{scene_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_scene(
    scene_id: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    scene = await vr_panorama_service.get_scene(db, scene_id)
    if not scene:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="VR 场景不存在")
    await verify_project_access(project_id=scene.project_id, current_user=user, db=db)
    project_id = scene.project_id
    deleted = await vr_panorama_service.delete_scene(db, scene_id)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="VR 场景不存在")
    await ws_manager.broadcast_to_project(
        project_id, "vr.scene.deleted", {"id": scene_id}
    )


# ── 3D 设备图层（P0 漫游 × 设备热点联动，2026-08-12）──


@router.get("/projects/{project_id}/device-overlay")
async def device_overlay(
    project_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """3D 场景设备图层聚合：设备锚点 + 实时状态 + 关联场景 + 最近传感器快照。

    供 PanoramaViewer 渲染设备热点：
    - yaw/pitch 由 SmartDevice.position（x: 东西向, y: 高度, z: 南北向）球坐标换算
    - 关联可触发的 SceneAutomation（scene_ids）
    - latest_sensor 为最近真实 SensorSnapshot（诚实数据，供联动上下文）
    """
    import math

    from sqlalchemy import select

    from app.models.scene_automation import SceneAutomation
    from app.models.sensor_snapshot import SensorSnapshot
    from app.models.smart_home import SmartDevice, SmartHomeScheme

    await verify_project_access(project_id=project_id, current_user=current_user, db=db)

    # 项目下全部设备（join scheme 过滤 project_id，排除已删除）
    result = await db.execute(
        select(SmartDevice, SmartHomeScheme)
        .join(SmartHomeScheme, SmartDevice.scheme_id == SmartHomeScheme.id)
        .where(
            SmartHomeScheme.project_id == project_id,
            SmartDevice.deleted_at.is_(None),
        )
    )
    rows = result.all()
    devices = [row[0] for row in rows]

    # 项目下启用中的场景（按 scheme 关联，供设备热点一键触发）
    result = await db.execute(
        select(SceneAutomation).where(
            SceneAutomation.project_id == project_id,
            SceneAutomation.enabled.is_(True),
        )
    )
    scenes = list(result.scalars().all())
    scene_by_scheme: dict[str, list[str]] = {}
    for s in scenes:
        scene_by_scheme.setdefault(s.scheme_id or "", []).append(s.id)

    # 最近真实传感器快照（联动上下文，诚实数据）
    latest_sensor: dict | None = None
    snap_result = await db.execute(
        select(SensorSnapshot)
        .where(SensorSnapshot.user_id == current_user.id)
        .order_by(SensorSnapshot.sampled_at.desc())
        .limit(1)
    )
    snap = snap_result.scalar_one_or_none()
    if snap:
        latest_sensor = {
            "snapshot_id": snap.id,
            "temperature": snap.temperature,
            "humidity": snap.humidity,
            "light_lux": snap.light_lux,
            "sampled_at": snap.sampled_at.isoformat() if snap.sampled_at else None,
        }

    overlay_devices = []
    for d in devices:
        yaw, pitch = 0.0, 0.0
        if d.position_x is not None and d.position_z is not None:
            # position_x: 东西向(+东), position_z: 南北向(+南), yaw 0=正北顺时针
            yaw = (math.degrees(math.atan2(d.position_x, d.position_z)) + 360) % 360
            pitch = -math.degrees(math.atan2(d.position_y or 0, max(
                math.hypot(d.position_x, d.position_z), 0.1
            )))
        overlay_devices.append({
            "device_id": d.id,
            "name": d.device_name,
            "type": d.device_type,
            "room_name": d.room_name,
            "status": d.status,
            "yaw": round(yaw, 1),
            "pitch": round(pitch, 1),
            "state": d.state,
            "scene_ids": scene_by_scheme.get(d.scheme_id, []),
        })

    return {
        "project_id": project_id,
        "device_count": len(overlay_devices),
        "devices": overlay_devices,
        "latest_sensor": latest_sensor,
    }

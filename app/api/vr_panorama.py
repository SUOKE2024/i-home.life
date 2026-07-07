"""视觉表现层 VR 全景 API — 全景图渲染 + 热点管理 + VR 场景漫游"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.auth import get_current_user
from app.models.user import User
from app.schemas.vr_panorama import (
    VRPanoramaCreate,
    VRPanoramaResponse,
    VRPanoramaListItem,
    VRPanoramaUpdate,
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
    data = body.model_dump()
    if data.get("initial_view") and hasattr(data["initial_view"], "model_dump"):
        data["initial_view"] = data["initial_view"].model_dump()
    panorama = await vr_panorama_service.create_panorama(db, data)
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
    return await vr_panorama_service.list_panoramas(db, project_id, status_filter)


@router.get("/panoramas/{panorama_id}", response_model=VRPanoramaResponse)
async def get_panorama(
    panorama_id: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    panorama = await vr_panorama_service.get_panorama(db, panorama_id)
    if not panorama:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="全景图不存在")
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
    project_id = scene.project_id
    deleted = await vr_panorama_service.delete_scene(db, scene_id)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="VR 场景不存在")
    await ws_manager.broadcast_to_project(
        project_id, "vr.scene.deleted", {"id": scene_id}
    )

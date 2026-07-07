"""F32 场景编辑 API"""

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.project import Project
from app.models.user import User
from app.auth import get_current_user
from app.schemas.scene_automation import (
    SceneAutomationCreate,
    SceneAutomationUpdate,
    SceneAutomationResponse,
    EcosystemIntegrationCreate,
    EcosystemIntegrationResponse,
    SceneSimulateResult,
    SceneRecommendResult,
    SceneParseResult,
    SceneSyncResult,
)
from app.services import scene_automation_service as svc
from app.ws import ws_manager

router = APIRouter(prefix="/scene-automation", tags=["场景编辑"])


# ── 场景 ──


@router.post("/scenes", response_model=SceneAutomationResponse, status_code=status.HTTP_201_CREATED)
async def create_scene(
    data: SceneAutomationCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    project = await db.get(Project, data.project_id)
    if not project or project.owner_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无权访问该项目")
    scene = await svc.create_scene(db, data.model_dump())
    resp = SceneAutomationResponse.model_validate(scene)
    await ws_manager.broadcast_to_project(scene.project_id, "scene.created", resp.model_dump())
    return resp


@router.get("/scenes/project/{project_id}", response_model=list[SceneAutomationResponse])
async def list_scenes_by_project(
    project_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    scenes = await svc.list_scenes_by_project(db, project_id)
    return [SceneAutomationResponse.model_validate(s) for s in scenes]


# 固定路径必须优先于 /scenes/{scene_id},否则会被当作 scene_id 匹配
@router.get("/scenes/recommend", response_model=SceneRecommendResult)
async def recommend_scenes(
    room_type: str = Query(..., description="房间类型"),
    lifestyle: str = Query("", description="生活方式偏好"),
    current_user: User = Depends(get_current_user),
):
    result = svc.recommend_scenes(room_type, lifestyle)
    return SceneRecommendResult(**result)


@router.post("/scenes/parse", response_model=SceneParseResult)
async def parse_scene(body: dict):
    """自然语言解析场景 (body: text)"""
    text = body.get("text") or ""
    result = svc.parse_natural_language_scene(text)
    return SceneParseResult(**result)


@router.get("/scenes/{scene_id}", response_model=SceneAutomationResponse)
async def get_scene(
    scene_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    scene = await svc.get_scene(db, scene_id)
    if not scene:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="场景不存在")
    return SceneAutomationResponse.model_validate(scene)


@router.patch("/scenes/{scene_id}", response_model=SceneAutomationResponse)
async def update_scene(
    scene_id: str,
    data: SceneAutomationUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    existing = await svc.get_scene(db, scene_id)
    if not existing:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="场景不存在")
    project = await db.get(Project, existing.project_id)
    if not project or project.owner_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无权访问该项目")
    scene = await svc.update_scene(db, scene_id, data.model_dump(exclude_unset=True))
    if not scene:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="场景不存在")
    resp = SceneAutomationResponse.model_validate(scene)
    await ws_manager.broadcast_to_project(scene.project_id, "scene.updated", resp.model_dump())
    return resp


@router.delete("/scenes/{scene_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_scene(
    scene_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    scene = await svc.get_scene(db, scene_id)
    if not scene:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="场景不存在")
    project = await db.get(Project, scene.project_id)
    if not project or project.owner_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无权访问该项目")
    project_id = scene.project_id
    deleted = await svc.delete_scene(db, scene_id)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="场景不存在")
    await ws_manager.broadcast_to_project(project_id, "scene.deleted", {"id": scene_id})


@router.post("/scenes/{scene_id}/simulate", response_model=SceneSimulateResult)
async def simulate_scene(scene_id: str, db: AsyncSession = Depends(get_db)):
    scene = await svc.get_scene(db, scene_id)
    if not scene:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="场景不存在")
    result = await svc.simulate_scene(db, scene)
    return SceneSimulateResult(**result)


@router.post("/scenes/{scene_id}/sync", response_model=SceneSyncResult)
async def sync_scene(
    scene_id: str,
    body: dict,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    scene = await svc.get_scene(db, scene_id)
    if not scene:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="场景不存在")
    ecosystem = body.get("ecosystem")
    if not ecosystem:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="缺少 ecosystem 参数")
    result = await svc.sync_to_ecosystem(db, scene, ecosystem)
    resp = SceneSyncResult(**result)
    await ws_manager.broadcast_to_project(
        scene.project_id,
        "scene.synced",
        {"scene_id": scene_id, "ecosystem": ecosystem, "synced": resp.synced},
    )
    return resp


# ── 生态对接 ──


@router.post("/ecosystems", response_model=EcosystemIntegrationResponse, status_code=status.HTTP_201_CREATED)
async def create_ecosystem(
    data: EcosystemIntegrationCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    eco = await svc.create_ecosystem(db, data.model_dump())
    resp = EcosystemIntegrationResponse.model_validate(eco)
    await ws_manager.broadcast_to_project(eco.project_id, "scene.ecosystem.added", resp.model_dump())
    return resp


@router.get("/ecosystems/project/{project_id}", response_model=list[EcosystemIntegrationResponse])
async def list_ecosystems_by_project(
    project_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    ecos = await svc.list_ecosystems_by_project(db, project_id)
    return [EcosystemIntegrationResponse.model_validate(e) for e in ecos]


@router.delete("/ecosystems/{ecosystem_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_ecosystem(
    ecosystem_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    deleted = await svc.delete_ecosystem(db, ecosystem_id)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="生态对接不存在")

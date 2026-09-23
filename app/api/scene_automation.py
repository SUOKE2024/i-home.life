"""F32 场景编辑 API + A4 预测式智能场景推荐"""

from datetime import datetime, timezone

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.user import User
from app.auth import get_current_user
from app.schemas.scene_automation import (
    SceneAutomationCreate,
    SceneAutomationUpdate,
    SceneAutomationResponse,
    EcosystemIntegrationCreate,
    EcosystemIntegrationResponse,
    SceneSimulateResult,
    SceneValidateResult,
    SceneRecommendResult,
    SceneParseResult,
    SceneSyncResult,
    SceneExecuteRequest,
    SceneExecuteResult,
)
from app.schemas.scene_behavior import (
    SceneBehaviorLogCreate,
    SceneBehaviorLogResponse,
    PredictedSceneResponse,
    PredictedSceneAcceptResult,
)
from app.rbac import verify_project_access
from app.services import scene_automation_service as svc
from app.services import predictive_scene_service as ps
from app.ws import ws_manager

router = APIRouter(prefix="/scene-automation", tags=["场景编辑"])


# ── 场景 ──


@router.post("/scenes", response_model=SceneAutomationResponse, status_code=status.HTTP_201_CREATED)
async def create_scene(
    data: SceneAutomationCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await verify_project_access(project_id=data.project_id, current_user=current_user, db=db)
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
    await verify_project_access(project_id=project_id, current_user=current_user, db=db)
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
async def parse_scene(
    body: dict,
    current_user: User = Depends(get_current_user),
):
    """自然语言解析场景 (body: text)

    2026-09-23：补 PASETO 鉴权（此前为匿名可调的计算端点，违反「所有端点必须鉴权」约束）。
    """
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
    await verify_project_access(project_id=scene.project_id, current_user=current_user, db=db)
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
    await verify_project_access(project_id=existing.project_id, current_user=current_user, db=db)
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
    await verify_project_access(project_id=scene.project_id, current_user=current_user, db=db)
    project_id = scene.project_id
    deleted = await svc.delete_scene(db, scene_id)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="场景不存在")
    await ws_manager.broadcast_to_project(project_id, "scene.deleted", {"id": scene_id})


@router.post("/scenes/{scene_id}/simulate", response_model=SceneSimulateResult)
async def simulate_scene(
    scene_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    scene = await svc.get_scene(db, scene_id)
    if not scene:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="场景不存在")
    await verify_project_access(project_id=scene.project_id, current_user=current_user, db=db)
    result = await svc.simulate_scene(db, scene)
    return SceneSimulateResult(**result)


# ── 场景执行（P0 3D 场景/语音触发入口，2026-08-12）──


async def _run_scene_bg(scene_id: str, user_id: str, trigger_source: str) -> None:
    """异步执行场景（2026-08-27 P2 遗留修复）：独立 session 执行 + WS 回填结果。

    场景动作为真实第三方桥 I/O，异步化避免 HTTP 请求被桥响应拖慢；
    结果经 WS scene.triggered 推送（多 worker 下仅同进程连接可达，best-effort）。
    """
    import logging

    from datetime import datetime, timezone

    from app.database import async_session
    from app.ws import ws_manager

    log = logging.getLogger("ihome.scene_automation")
    async with async_session() as db:
        scene = await svc.get_scene(db, scene_id)
        if not scene:
            log.warning("scene_execute_async_skipped: scene=%s 不存在", scene_id)
            return
        result = await svc.execute_scene_actions(db, scene, user_id, trigger_source)
        result["async_queued"] = True
        result["triggered_at"] = datetime.now(timezone.utc).isoformat()
        await ws_manager.broadcast_to_project(
            scene.project_id, "scene.triggered",
            {"scene_id": scene.id, "scene_name": scene.scene_name, "result": result, "async": True},
        )
        log.info("scene_execute_async_done: scene=%s source=%s", scene_id, trigger_source)


@router.post("/scenes/{scene_id}/execute", response_model=SceneExecuteResult)
async def execute_scene(
    scene_id: str,
    body: SceneExecuteRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    background_tasks: BackgroundTasks = BackgroundTasks(),
):
    """执行场景（P0 3D 场景/语音触发入口，2026-08-12）。

    - 与传感器自动触发（check_sensor_triggers）共用执行语义
    - 每个动作写 SceneBehaviorLog(action_type=manual_trigger)
    - 生态桥逐个执行，未接真机 action_status=pending 诚实标注
    - execute_async=True：请求立即返回，后台执行 + WS 推送结果（2026-08-27）
    """
    scene = await svc.get_scene(db, scene_id)
    if not scene:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="场景不存在")
    await verify_project_access(project_id=scene.project_id, current_user=current_user, db=db)

    # ── 异步模式：请求立即返回，后台执行 + WS 回填（防桥慢拖垮请求）──
    if body.execute_async:
        background_tasks.add_task(_run_scene_bg, scene.id, current_user.id, body.trigger_source)
        return SceneExecuteResult(
            scene_id=scene.id,
            scene_name=scene.scene_name,
            executed=True,
            actions=[],
            triggered_at=datetime.now(timezone.utc).isoformat(),
            async_queued=True,
        )

    result = await svc.execute_scene_actions(
        db, scene, current_user.id, trigger_source=body.trigger_source,
    )
    resp = SceneExecuteResult(**result)
    await ws_manager.broadcast_to_project(
        scene.project_id, "scene.triggered",
        {"scene_id": scene.id, "scene_name": scene.scene_name, "result": resp.model_dump()},
    )
    return resp


@router.post("/scenes/{scene_id}/validate", response_model=SceneValidateResult)
async def validate_scene(
    scene_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    scene = await svc.get_scene(db, scene_id)
    if not scene:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="场景不存在")
    await verify_project_access(project_id=scene.project_id, current_user=current_user, db=db)
    result = await svc.validate_scene(db, scene)
    return SceneValidateResult(**result)


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
    await verify_project_access(project_id=scene.project_id, current_user=current_user, db=db)
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


def _redacted_ecosystem_response(eco) -> EcosystemIntegrationResponse:
    """生态对接响应构造：config 脱敏（只回露字段名，绝不回露凭据值）。

    2026-09-22：此前直接 model_validate 会把明文凭据（米家账号密码等）原样回露给前端。
    """
    resp = EcosystemIntegrationResponse.model_validate(eco)
    resp.config = svc.redact_ecosystem_config(eco.config)
    return resp


@router.post("/ecosystems", response_model=EcosystemIntegrationResponse, status_code=status.HTTP_201_CREATED)
async def create_ecosystem(
    data: EcosystemIntegrationCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await verify_project_access(project_id=data.project_id, current_user=current_user, db=db)
    try:
        eco = await svc.create_ecosystem(db, data.model_dump())
    except ValueError as e:
        # 凭据加密失败（密钥不可用）→ fail-closed，拒绝明文落库
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e)) from e
    resp = _redacted_ecosystem_response(eco)
    await ws_manager.broadcast_to_project(eco.project_id, "scene.ecosystem.added", resp.model_dump())
    return resp


@router.get("/ecosystems/project/{project_id}", response_model=list[EcosystemIntegrationResponse])
async def list_ecosystems_by_project(
    project_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await verify_project_access(project_id=project_id, current_user=current_user, db=db)
    ecos = await svc.list_ecosystems_by_project(db, project_id)
    return [_redacted_ecosystem_response(e) for e in ecos]


@router.delete("/ecosystems/{ecosystem_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_ecosystem(
    ecosystem_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    from sqlalchemy import select
    from app.models.scene_automation import EcosystemIntegration
    result = await db.execute(
        select(EcosystemIntegration).where(EcosystemIntegration.id == ecosystem_id)
    )
    eco = result.scalar_one_or_none()
    if not eco:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="生态对接不存在")
    await verify_project_access(project_id=eco.project_id, current_user=current_user, db=db)
    deleted = await svc.delete_ecosystem(db, ecosystem_id)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="生态对接不存在")


# ── A4 预测式智能场景推荐 ──


@router.post(
    "/scenes/behaviors",
    response_model=SceneBehaviorLogResponse,
    status_code=status.HTTP_201_CREATED,
)
async def log_scene_behavior(
    data: SceneBehaviorLogCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """记录用户场景行为（供前端在场景激活/手动触发等时机调用）"""
    from app.config import get_settings
    settings = get_settings()
    if not settings.predictive_scene_enabled:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="预测式场景推荐功能未启用",
        )

    await verify_project_access(
        project_id=data.project_id, current_user=current_user, db=db
    )
    entry = await ps.log_behavior(
        db=db,
        project_id=data.project_id,
        user_id=current_user.id,
        action_type=data.action_type,
        scene_id=data.scene_id,
        room_type=data.room_type,
        time_of_day=data.time_of_day,
        day_of_week=data.day_of_week,
        duration_seconds=data.duration_seconds,
        device_states_before=data.device_states_before,
        device_states_after=data.device_states_after,
        ambient_data=data.ambient_data,
    )
    await ws_manager.broadcast_to_project(
        data.project_id,
        "scene.behavior.logged",
        {"action_type": data.action_type, "scene_id": data.scene_id},
    )
    return SceneBehaviorLogResponse.model_validate(entry)


@router.get(
    "/scenes/predictions/{project_id}",
    response_model=list[PredictedSceneResponse],
)
async def get_predictions(
    project_id: str,
    status_filter: str | None = Query(None, alias="status"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """获取项目的预测场景列表"""
    from app.config import get_settings
    settings = get_settings()
    if not settings.predictive_scene_enabled:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="预测式场景推荐功能未启用",
        )

    await verify_project_access(
        project_id=project_id, current_user=current_user, db=db
    )
    predictions = await ps.get_predictions_by_project(db, project_id, status_filter)
    return [PredictedSceneResponse.model_validate(p) for p in predictions]


@router.post(
    "/scenes/predictions/{project_id}/generate",
    status_code=status.HTTP_200_OK,
)
async def generate_predictions_for_project(
    project_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """触发生成预测场景（基于行为日志分析）"""
    from app.config import get_settings
    settings = get_settings()
    if not settings.predictive_scene_enabled:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="预测式场景推荐功能未启用",
        )

    await verify_project_access(
        project_id=project_id, current_user=current_user, db=db
    )
    predictions = await ps.predict_scenes(project_id, db)
    return {
        "project_id": project_id,
        "generated": len(predictions),
        "predictions": [
            PredictedSceneResponse.model_validate(p).model_dump() for p in predictions
        ],
    }


@router.patch(
    "/scenes/predictions/{prediction_id}/accept",
    response_model=PredictedSceneAcceptResult,
)
async def accept_prediction(
    prediction_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """接受预测并创建为真实场景"""
    from app.config import get_settings
    settings = get_settings()
    if not settings.predictive_scene_enabled:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="预测式场景推荐功能未启用",
        )

    from sqlalchemy import select
    from app.models.scene_behavior import PredictedScene
    result = await db.execute(
        select(PredictedScene).where(PredictedScene.id == prediction_id)
    )
    pred = result.scalar_one_or_none()
    if not pred:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="预测场景不存在"
        )
    await verify_project_access(
        project_id=pred.project_id, current_user=current_user, db=db
    )

    outcome = await ps.accept_prediction(db, prediction_id, current_user.id)
    if not outcome:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="预测场景不存在"
        )
    resp = PredictedSceneAcceptResult(**outcome)
    await ws_manager.broadcast_to_project(
        pred.project_id,
        "scene.prediction.accepted",
        {"prediction_id": prediction_id, "scene_id": outcome["scene_id"]},
    )
    return resp


@router.patch(
    "/scenes/predictions/{prediction_id}/dismiss",
    status_code=status.HTTP_200_OK,
)
async def dismiss_prediction(
    prediction_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """忽略预测"""
    from app.config import get_settings
    settings = get_settings()
    if not settings.predictive_scene_enabled:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="预测式场景推荐功能未启用",
        )

    from sqlalchemy import select
    from app.models.scene_behavior import PredictedScene
    result = await db.execute(
        select(PredictedScene).where(PredictedScene.id == prediction_id)
    )
    pred = result.scalar_one_or_none()
    if not pred:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="预测场景不存在"
        )
    await verify_project_access(
        project_id=pred.project_id, current_user=current_user, db=db
    )

    success = await ps.dismiss_prediction(db, prediction_id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="预测场景不存在"
        )
    await ws_manager.broadcast_to_project(
        pred.project_id,
        "scene.prediction.dismissed",
        {"prediction_id": prediction_id},
    )
    return {"status": "ok", "prediction_id": prediction_id, "message": "预测已忽略"}

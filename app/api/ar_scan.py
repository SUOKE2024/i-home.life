"""F1 AR 空间测量 API — 扫描会话生命周期 + 墙面特征 + 测量校准点 + 精度报告

独立模块（v1.14.x 自 surveys.py 拆分），保持原路径前缀 /surveys/ar/* 兼容既有客户端。
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.auth import get_current_user
from app.rbac import verify_project_access
from app.models.ar_scan import WallFeature
from app.schemas.ar_scan import (
    ScanSessionCreate,
    ScanSessionUpdate,
    ScanSessionResponse,
    ScanSessionListItem,
    WallFeatureCreate,
    WallFeatureResponse,
    MeasurementPointCreate,
    MeasurementPointResponse,
    DeviceCapabilityRequest,
    ProcessScanRequest,
    AccuracyReportResponse,
    ARDeviceCapabilityResponse,
)
from app.services import ar_scan_service
from app.ws import ws_manager

router = APIRouter(prefix="/surveys/ar", tags=["AR 空间测量"])


def _current_user(user=Depends(get_current_user)):
    return user


@router.post("/device-capability", response_model=ARDeviceCapabilityResponse)
async def ar_device_capability(body: DeviceCapabilityRequest, user=Depends(_current_user)):
    """检测设备 AR 能力并返回推荐扫描方法与降级链。

    返回的 fallback_chain 是从推荐方法到 manual 的完整降级路径,
    客户端据此设计 UI 引导和提示文案。
    """
    cap = body.model_dump()
    result = ar_scan_service.detect_device_capability(cap)
    return ARDeviceCapabilityResponse(**result)


@router.post("/sessions", response_model=ScanSessionResponse, status_code=status.HTTP_201_CREATED)
async def create_ar_session(body: ScanSessionCreate, db: AsyncSession = Depends(get_db), user=Depends(_current_user)):
    """创建 AR 扫描会话 — 自动检测设备能力并确定扫描方法。"""
    await verify_project_access(project_id=body.project_id, current_user=user, db=db)
    data = body.model_dump()
    if data.get("device_capability"):
        data["device_capability"] = dict(data["device_capability"])
    session = await ar_scan_service.create_session(db, data)
    await ws_manager.broadcast_to_project(
        session.project_id,
        "ar.session.created",
        {"session_id": session.id, "scan_method": session.scan_method},
    )
    return session


@router.get("/sessions/project/{project_id}", response_model=list[ScanSessionListItem])
async def list_ar_sessions(
    project_id: str,
    status_filter: str | None = None,
    db: AsyncSession = Depends(get_db),
    user=Depends(_current_user),
):
    await verify_project_access(project_id=project_id, current_user=user, db=db)
    sessions = await ar_scan_service.list_sessions(db, project_id, status_filter)
    return sessions


@router.get("/sessions/{session_id}", response_model=ScanSessionResponse)
async def get_ar_session(session_id: str, db: AsyncSession = Depends(get_db), user=Depends(_current_user)):
    session = await ar_scan_service.get_session(db, session_id)
    if not session:
        raise HTTPException(status_code=404, detail="扫描会话不存在")
    await verify_project_access(project_id=session.project_id, current_user=user, db=db)
    return session


@router.patch("/sessions/{session_id}", response_model=ScanSessionResponse)
async def update_ar_session(
    session_id: str, body: ScanSessionUpdate, db: AsyncSession = Depends(get_db), user=Depends(_current_user)
):
    session = await ar_scan_service.get_session(db, session_id)
    if not session:
        raise HTTPException(status_code=404, detail="扫描会话不存在")
    await verify_project_access(project_id=session.project_id, current_user=user, db=db)
    data = body.model_dump(exclude_none=True)
    if "panoramas" in data and data["panoramas"] is not None:
        data["panoramas"] = list(data["panoramas"])
    return await ar_scan_service.update_session(db, session, data)


@router.post("/sessions/{session_id}/start", response_model=ScanSessionResponse)
async def start_ar_scan(session_id: str, db: AsyncSession = Depends(get_db), user=Depends(_current_user)):
    """开始扫描 — 状态从 created 流转到 scanning。"""
    session = await ar_scan_service.get_session(db, session_id)
    if not session:
        raise HTTPException(status_code=404, detail="扫描会话不存在")
    await verify_project_access(project_id=session.project_id, current_user=user, db=db)
    if session.status not in ("created", "failed"):
        raise HTTPException(status_code=400, detail=f"当前状态 {session.status} 不允许开始扫描")
    session = await ar_scan_service.start_scan(db, session)
    await ws_manager.broadcast_to_project(
        session.project_id, "ar.scan.started", {"session_id": session.id}
    )
    return session


@router.post("/sessions/{session_id}/process", response_model=dict)
async def process_ar_scan(
    session_id: str, body: ProcessScanRequest, db: AsyncSession = Depends(get_db), user=Depends(_current_user)
):
    """处理扫描数据 — 解析 USDZ/GLB 模型、提取房间结构、识别墙面特征、生成精度报告。"""
    session = await ar_scan_service.get_session(db, session_id)
    if not session:
        raise HTTPException(status_code=404, detail="扫描会话不存在")
    await verify_project_access(project_id=session.project_id, current_user=user, db=db)
    if session.status not in ("scanning", "uploaded", "processing", "failed"):
        raise HTTPException(status_code=400, detail=f"当前状态 {session.status} 不允许处理")
    data = body.model_dump(exclude_none=True)
    result = await ar_scan_service.process_scan(
        db,
        session,
        model_url=data.get("model_url"),
        model_format=data.get("model_format", "usdz"),
        raw_data_url=data.get("raw_data_url"),
        panoramas=data.get("panoramas"),
        scan_points_count=data.get("scan_points_count", 0),
        scan_duration_sec=data.get("scan_duration_sec", 0),
    )
    # 序列化返回 (session 对象已包含最新字段)
    session_obj = result["session"]
    await ws_manager.broadcast_to_project(
        session.project_id,
        "ar.scan.completed",
        {
            "session_id": session.id,
            "room_count": session_obj.room_count,
            "total_area": session_obj.total_area,
            "accuracy_level": session_obj.accuracy_level,
            "rms_error_cm": session_obj.accuracy_rms_error,
        },
    )
    return {
        "session_id": session.id,
        "status": session_obj.status,
        "room_count": session_obj.room_count,
        "total_area": session_obj.total_area,
        "wall_features_added": result["wall_features_added"],
        "point_cloud": result["point_cloud_info"],
        "parsed_model": {
            "rooms": result["parsed_model"]["rooms"],
            "wall_count": result["parsed_model"]["wall_count"],
            "door_count": result["parsed_model"]["door_count"],
            "window_count": result["parsed_model"]["window_count"],
        },
        # 诚实标注：真实解析降级到 mock 时给出警告，前端据此标注「模拟数据」
        "parse_warnings": result["parsed_model"]["parse_warnings"],
        "accuracy_report": result["accuracy_report"],
    }


@router.get("/sessions/{session_id}/accuracy", response_model=AccuracyReportResponse)
async def get_accuracy_report(session_id: str, db: AsyncSession = Depends(get_db), user=Depends(_current_user)):
    """获取精度校验报告 — 包含 RMS 误差、等级、通过率、建议。"""
    session = await ar_scan_service.get_session(db, session_id)
    if not session:
        raise HTTPException(status_code=404, detail="扫描会话不存在")
    await verify_project_access(project_id=session.project_id, current_user=user, db=db)
    report = await ar_scan_service.get_accuracy_report(db, session_id)
    if not report:
        raise HTTPException(status_code=404, detail="扫描会话不存在")
    # 序列化 points 为 response model
    points_data = []
    for p in report["points"]:
        points_data.append(MeasurementPointResponse.model_validate(p, from_attributes=True))
    report["points"] = points_data
    return AccuracyReportResponse(**report)


@router.post("/sessions/{session_id}/apply", response_model=dict)
async def apply_ar_session(session_id: str, db: AsyncSession = Depends(get_db), user=Depends(_current_user)):
    """将 AR 扫描结果应用到测量记录(Survey),自动生成户型数据。"""
    session = await ar_scan_service.get_session(db, session_id)
    if not session:
        raise HTTPException(status_code=404, detail="扫描会话不存在")
    await verify_project_access(project_id=session.project_id, current_user=user, db=db)
    if session.status != "completed":
        raise HTTPException(status_code=400, detail="扫描会话未完成,无法应用")
    result = await ar_scan_service.apply_session_to_survey(db, session)
    await ws_manager.broadcast_to_project(
        session.project_id,
        "ar.session.applied",
        {"session_id": session.id, "survey_id": session.survey_id},
    )
    return result


@router.delete("/sessions/{session_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_ar_session(session_id: str, db: AsyncSession = Depends(get_db), user=Depends(_current_user)):
    session = await ar_scan_service.get_session(db, session_id)
    if not session:
        raise HTTPException(status_code=404, detail="扫描会话不存在")
    await verify_project_access(project_id=session.project_id, current_user=user, db=db)
    await ar_scan_service.delete_session(db, session)


# ── 墙面特征 (WallFeature) ──


@router.post("/features", response_model=WallFeatureResponse, status_code=status.HTTP_201_CREATED)
async def add_wall_feature(body: WallFeatureCreate, db: AsyncSession = Depends(get_db), user=Depends(_current_user)):
    """添加墙面特征 — 门/窗/洞口/梁/柱/管道/开关插座。"""
    # 先鉴权再写库：session 不存在即 404，防止悬空 session 绕过鉴权越权写库
    session = await ar_scan_service.get_session(db, body.session_id)
    if not session:
        raise HTTPException(status_code=404, detail="扫描会话不存在")
    await verify_project_access(project_id=session.project_id, current_user=user, db=db)

    data = body.model_dump()
    if "extra" in data and data["extra"] is not None:
        data["extra"] = dict(data["extra"])
    feature = await ar_scan_service.add_wall_feature(db, data)
    # 校验规范并发送 WS 通知
    warnings = ar_scan_service.validate_wall_feature(feature)
    await ws_manager.broadcast_to_project(
        session.project_id,
        "ar.feature.added",
        {
            "feature_id": feature.id,
            "feature_type": feature.feature_type,
            "room_name": feature.room_name,
            "compliance_warnings": warnings,
        },
    )
    return feature


@router.get("/features/{session_id}", response_model=list[WallFeatureResponse])
async def list_wall_features(
    session_id: str, room_name: str | None = None, db: AsyncSession = Depends(get_db),
    user=Depends(_current_user),
):
    session = await ar_scan_service.get_session(db, session_id)
    if not session:
        raise HTTPException(status_code=404, detail="扫描会话不存在")
    await verify_project_access(project_id=session.project_id, current_user=user, db=db)
    return await ar_scan_service.list_wall_features(db, session_id, room_name)


@router.delete("/features/{feature_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_wall_feature(feature_id: str, db: AsyncSession = Depends(get_db), user=Depends(_current_user)):
    feat_result = await db.execute(select(WallFeature).where(WallFeature.id == feature_id))
    feat = feat_result.scalar_one_or_none()
    if not feat:
        raise HTTPException(status_code=404, detail="墙面特征不存在")
    session = await ar_scan_service.get_session(db, feat.session_id)
    if not session:
        raise HTTPException(status_code=404, detail="扫描会话不存在")
    await verify_project_access(project_id=session.project_id, current_user=user, db=db)
    ok = await ar_scan_service.delete_wall_feature(db, feature_id)
    if not ok:
        raise HTTPException(status_code=404, detail="墙面特征不存在")


# ── 测量校准点 (MeasurementPoint) ──


@router.post("/points", response_model=MeasurementPointResponse, status_code=status.HTTP_201_CREATED)
async def add_measurement_point(
    body: MeasurementPointCreate, db: AsyncSession = Depends(get_db), user=Depends(_current_user)
):
    """添加测量校准点 — 用于 AR 精度校验 (同时记录 AR 测量值和人工参考值)。"""
    # 先鉴权再写库：session 不存在即 404，防止悬空 session 绕过鉴权越权写库
    session = await ar_scan_service.get_session(db, body.session_id)
    if not session:
        raise HTTPException(status_code=404, detail="扫描会话不存在")
    await verify_project_access(project_id=session.project_id, current_user=user, db=db)

    data = body.model_dump()
    point = await ar_scan_service.add_measurement_point(db, data)
    await ws_manager.broadcast_to_project(
        session.project_id,
        "ar.point.added",
        {
            "point_id": point.id,
            "label": point.label,
            "deviation": point.deviation,
            "rms_error_cm": session.accuracy_rms_error,
        },
    )
    return point


@router.get("/points/{session_id}", response_model=list[MeasurementPointResponse])
async def list_measurement_points(session_id: str, db: AsyncSession = Depends(get_db), user=Depends(_current_user)):
    session = await ar_scan_service.get_session(db, session_id)
    if not session:
        raise HTTPException(status_code=404, detail="扫描会话不存在")
    await verify_project_access(project_id=session.project_id, current_user=user, db=db)
    return await ar_scan_service.list_measurement_points(db, session_id)

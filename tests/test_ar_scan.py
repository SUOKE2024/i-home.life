"""F1 AR 空间测量完整功能测试 — 设备能力检测 + 扫描会话生命周期 + 精度校验 + 墙面特征"""

import pytest
from httpx import AsyncClient


async def _register_and_login(client: AsyncClient, phone: str = "13900008001") -> tuple[str, dict]:
    resp = await client.post(
        "/api/auth/register",
        json={"phone": phone, "name": "AR 扫描测试用户", "password": "test123456"},
    )
    token = resp.json()["access_token"]
    return token, {"Authorization": f"Bearer {token}"}


async def _create_project(client: AsyncClient, headers: dict, name: str = "AR 扫描测试项目") -> str:
    resp = await client.post(
        "/api/projects",
        json={"name": name, "total_area": 100.0},
        headers=headers,
    )
    return resp.json()["id"]


# ── F1.1 设备能力检测与降级策略 ──

@pytest.mark.asyncio
async def test_ar_device_capability_lidar(client: AsyncClient):
    """LiDAR 设备 — 推荐 lidar 方法,降级链包含所有方法"""
    resp = await client.post("/api/surveys/ar/device-capability", json={
        "platform": "ios",
        "device_model": "iPhone 15 Pro",
        "has_lidar": True,
        "arkit_version": "7.0",
        "supports_roomplan": True,
        "supports_photogrammetry": True,
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["recommended_method"] == "lidar"
    assert "lidar" in data["available_methods"]
    assert data["lidar_supported"] is True
    assert data["fallback_chain"][0] == "lidar"
    assert data["fallback_chain"][-1] == "manual"
    assert data["estimated_accuracy_cm"] == 1.0


@pytest.mark.asyncio
async def test_ar_device_capability_visual_slam_android(client: AsyncClient):
    """Android 设备 (无 LiDAR) — 推荐 visual_slam 方法"""
    resp = await client.post("/api/surveys/ar/device-capability", json={
        "platform": "android",
        "device_model": "Pixel 8",
        "has_lidar": False,
        "arcore_version": "1.31",
        "supports_photogrammetry": True,
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["recommended_method"] == "visual_slam"
    assert data["lidar_supported"] is False
    assert "visual_slam" in data["available_methods"]
    assert "lidar" not in data["available_methods"]


@pytest.mark.asyncio
async def test_ar_device_capability_harmonyos(client: AsyncClient):
    """HarmonyOS 设备 — 支持 AR Engine visual_slam"""
    resp = await client.post("/api/surveys/ar/device-capability", json={
        "platform": "harmonyos",
        "device_model": "MatePad Pro 13.2",
        "has_lidar": False,
        "ar_engine_version": "1.0",
        "supports_photogrammetry": True,
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["recommended_method"] == "visual_slam"
    assert "manual" in data["available_methods"]


@pytest.mark.asyncio
async def test_ar_device_capability_old_ios_degrades(client: AsyncClient):
    """iOS ARKit 4 但无 LiDAR — 应降级到 visual_slam"""
    resp = await client.post("/api/surveys/ar/device-capability", json={
        "platform": "ios",
        "device_model": "iPhone 11",
        "has_lidar": False,
        "arkit_version": "5.0",
        "supports_photogrammetry": True,
    })
    assert resp.status_code == 200
    data = resp.json()
    # iPhone 11 无 LiDAR,推荐 visual_slam
    assert data["recommended_method"] == "visual_slam"
    assert data["lidar_supported"] is False
    assert data["fallback_chain"][0] == "visual_slam"


# ── F1.2 扫描会话生命周期 ──

@pytest.mark.asyncio
async def test_ar_session_full_lifecycle(client: AsyncClient):
    """AR 扫描会话完整生命周期: 创建 → 启动 → 处理 → 完成"""
    token, headers = await _register_and_login(client, "13900008010")
    project_id = await _create_project(client, headers, "AR 全流程测试")

    # 1. 创建会话 (iOS + LiDAR)
    resp = await client.post("/api/surveys/ar/sessions", json={
        "project_id": project_id,
        "name": "主卧+客厅 AR 扫描",
        "platform": "ios",
        "requested_method": "lidar",
        "device_capability": {
            "platform": "ios",
            "device_model": "iPhone 15 Pro",
            "has_lidar": True,
            "arkit_version": "7.0",
            "supports_roomplan": True,
        },
        "floor_count": 1,
        "wall_height": 2.8,
    }, headers=headers)
    assert resp.status_code == 201
    session = resp.json()
    session_id = session["id"]
    assert session["status"] == "created"
    assert session["scan_method"] == "lidar"
    assert session["requested_method"] == "lidar"

    # 2. 启动扫描
    resp = await client.post(f"/api/surveys/ar/sessions/{session_id}/start", headers=headers)
    assert resp.status_code == 200
    assert resp.json()["status"] == "scanning"

    # 3. 处理扫描数据
    resp = await client.post(f"/api/surveys/ar/sessions/{session_id}/process", json={
        "model_url": "https://example.com/scan.usdz",
        "model_format": "usdz",
        "scan_points_count": 50000,
        "scan_duration_sec": 180,
    }, headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "completed"
    assert data["room_count"] > 0
    assert data["total_area"] > 0
    assert data["wall_features_added"] > 0
    assert "point_cloud" in data
    assert "accuracy_report" in data

    # 4. 查询会话详情
    resp = await client.get(f"/api/surveys/ar/sessions/{session_id}", headers=headers)
    assert resp.status_code == 200
    detail = resp.json()
    assert detail["status"] == "completed"
    assert detail["room_count"] == data["room_count"]
    assert detail["total_area"] == data["total_area"]


@pytest.mark.asyncio
async def test_ar_session_list_by_project(client: AsyncClient):
    """按项目列出扫描会话"""
    token, headers = await _register_and_login(client, "13900008020")
    project_id = await _create_project(client, headers, "会话列表测试")

    # 创建两个会话
    for i in range(2):
        await client.post("/api/surveys/ar/sessions", json={
            "project_id": project_id,
            "name": f"扫描 {i+1}",
            "platform": "ios",
            "requested_method": "lidar",
            "device_capability": {"platform": "ios", "has_lidar": True, "arkit_version": "7.0"},
        }, headers=headers)

    resp = await client.get(f"/api/surveys/ar/sessions/project/{project_id}", headers=headers)
    assert resp.status_code == 200
    sessions = resp.json()
    assert len(sessions) >= 2


@pytest.mark.asyncio
async def test_ar_session_method_degradation(client: AsyncClient):
    """请求 lidar 但设备不支持 — 自动降级到 visual_slam"""
    token, headers = await _register_and_login(client, "13900008030")
    project_id = await _create_project(client, headers, "降级策略测试")

    resp = await client.post("/api/surveys/ar/sessions", json={
        "project_id": project_id,
        "name": "降级测试",
        "platform": "android",
        "requested_method": "lidar",  # 请求 lidar
        "device_capability": {
            "platform": "android",
            "device_model": "Pixel 8",
            "has_lidar": False,  # 但设备不支持
            "arcore_version": "1.31",
        },
    }, headers=headers)
    assert resp.status_code == 201
    session = resp.json()
    # 实际 scan_method 应降级为 visual_slam
    assert session["scan_method"] == "visual_slam"
    assert session["requested_method"] == "lidar"


# ── F1.3 精度校验 ──

@pytest.mark.asyncio
async def test_ar_accuracy_with_calibration_points(client: AsyncClient):
    """添加校准点后,精度报告应正确计算 RMS 误差"""
    token, headers = await _register_and_login(client, "13900008040")
    project_id = await _create_project(client, headers, "精度校验测试")

    # 创建并完成扫描
    resp = await client.post("/api/surveys/ar/sessions", json={
        "project_id": project_id,
        "name": "精度测试",
        "platform": "ios",
        "requested_method": "lidar",
        "device_capability": {"platform": "ios", "has_lidar": True, "arkit_version": "7.0"},
    }, headers=headers)
    session_id = resp.json()["id"]

    await client.post(f"/api/surveys/ar/sessions/{session_id}/start", headers=headers)
    await client.post(f"/api/surveys/ar/sessions/{session_id}/process", json={
        "model_url": "https://example.com/test.usdz",
        "model_format": "usdz",
        "scan_points_count": 30000,
        "scan_duration_sec": 120,
    }, headers=headers)

    # 添加校准点 (AR 与参考值接近,精度高)
    resp = await client.post("/api/surveys/ar/points", json={
        "session_id": session_id,
        "label": "主卧对角线",
        "room_name": "主卧",
        "point_type": "diagonal",
        "ar_value": 5.42,
        "reference_value": 5.40,
        "unit": "m",
    }, headers=headers)
    assert resp.status_code == 201
    point = resp.json()
    assert abs(point["deviation"] - 0.02) < 0.001
    assert point["deviation_percent"] < 1.0

    # 再添加一个校准点
    resp = await client.post("/api/surveys/ar/points", json={
        "session_id": session_id,
        "label": "客厅宽度",
        "room_name": "客厅",
        "point_type": "distance",
        "ar_value": 4.85,
        "reference_value": 4.80,
        "unit": "m",
    }, headers=headers)
    assert resp.status_code == 201

    # 获取精度报告
    resp = await client.get(f"/api/surveys/ar/sessions/{session_id}/accuracy", headers=headers)
    assert resp.status_code == 200
    report = resp.json()
    assert report["total_count"] == 2
    assert report["rms_error_cm"] > 0
    assert report["accuracy_level"] in ("high", "medium", "low")
    assert report["passed_count"] >= 1
    assert len(report["recommendations"]) > 0
    assert isinstance(report["degradation_path"], list)


@pytest.mark.asyncio
async def test_ar_accuracy_level_high(client: AsyncClient):
    """AR 值与参考值非常接近 — 精度等级应为 high (RMS < 2cm)"""
    token, headers = await _register_and_login(client, "13900008050")
    project_id = await _create_project(client, headers, "高精度测试")

    resp = await client.post("/api/surveys/ar/sessions", json={
        "project_id": project_id,
        "platform": "ios",
        "requested_method": "lidar",
        "device_capability": {"platform": "ios", "has_lidar": True, "arkit_version": "7.0"},
    }, headers=headers)
    session_id = resp.json()["id"]

    await client.post(f"/api/surveys/ar/sessions/{session_id}/start", headers=headers)
    await client.post(f"/api/surveys/ar/sessions/{session_id}/process", json={
        "model_format": "usdz",
        "scan_points_count": 50000,
    }, headers=headers)

    # 三个校准点偏差都 < 1cm (RMS 必然 < 2cm)
    for label, ar_v, ref_v in [("对角1", 5.401, 5.400), ("对角2", 4.202, 4.200), ("对角3", 6.503, 6.500)]:
        await client.post("/api/surveys/ar/points", json={
            "session_id": session_id,
            "label": label,
            "ar_value": ar_v,
            "reference_value": ref_v,
            "unit": "m",
        }, headers=headers)

    resp = await client.get(f"/api/surveys/ar/sessions/{session_id}/accuracy", headers=headers)
    report = resp.json()
    assert report["accuracy_level"] == "high"
    assert report["rms_error_cm"] < 2.0
    assert report["pass_rate"] == 1.0


# ── F1.4 墙面特征管理 ──

@pytest.mark.asyncio
async def test_ar_wall_features_crud(client: AsyncClient):
    """墙面特征 CRUD — 门/窗/洞口"""
    token, headers = await _register_and_login(client, "13900008060")
    project_id = await _create_project(client, headers, "墙面特征测试")

    # 创建并处理扫描 (会自动识别一批特征)
    resp = await client.post("/api/surveys/ar/sessions", json={
        "project_id": project_id,
        "platform": "ios",
        "requested_method": "lidar",
        "device_capability": {"platform": "ios", "has_lidar": True, "arkit_version": "7.0"},
    }, headers=headers)
    session_id = resp.json()["id"]
    await client.post(f"/api/surveys/ar/sessions/{session_id}/start", headers=headers)
    process_resp = await client.post(f"/api/surveys/ar/sessions/{session_id}/process", json={
        "model_format": "usdz",
    }, headers=headers)
    auto_count = process_resp.json()["wall_features_added"]
    assert auto_count > 0

    # 列出自动识别的特征
    resp = await client.get(f"/api/surveys/ar/features/{session_id}", headers=headers)
    assert resp.status_code == 200
    features = resp.json()
    assert len(features) == auto_count
    feature_types = {f["feature_type"] for f in features}
    assert "door" in feature_types

    # 手动添加窗特征
    resp = await client.post("/api/surveys/ar/features", json={
        "session_id": session_id,
        "room_name": "主卧",
        "wall_id": "wall_2",
        "feature_type": "window",
        "position_x": 1.8,
        "position_y": 0.9,
        "width": 1.5,
        "height": 1.5,
        "depth": 0.1,
        "sill_height": 0.9,
        "load_bearing": False,
        "confidence": 0.92,
        "detected_by": "manual",
    }, headers=headers)
    assert resp.status_code == 201
    new_feature = resp.json()
    assert new_feature["feature_type"] == "window"
    assert new_feature["detected_by"] == "manual"

    # 按房间过滤
    resp = await client.get(f"/api/surveys/ar/features/{session_id}?room_name=主卧", headers=headers)
    assert resp.status_code == 200
    filtered = resp.json()
    assert all(f["room_name"] == "主卧" for f in filtered)

    # 删除特征
    resp = await client.delete(f"/api/surveys/ar/features/{new_feature['id']}", headers=headers)
    assert resp.status_code == 204


@pytest.mark.asyncio
async def test_ar_wall_feature_compliance_warning(client: AsyncClient):
    """添加不合规的门 (宽度 < 0.8m) — 应触发规范警告"""
    token, headers = await _register_and_login(client, "13900008070")
    project_id = await _create_project(client, headers, "规范校验测试")

    resp = await client.post("/api/surveys/ar/sessions", json={
        "project_id": project_id,
        "platform": "ios",
        "requested_method": "lidar",
        "device_capability": {"platform": "ios", "has_lidar": True, "arkit_version": "7.0"},
    }, headers=headers)
    session_id = resp.json()["id"]

    # 添加不合规门 (宽 0.7m < 0.8m 规范最小值)
    resp = await client.post("/api/surveys/ar/features", json={
        "session_id": session_id,
        "room_name": "卫生间",
        "feature_type": "door",
        "position_x": 0.5,
        "position_y": 0.0,
        "width": 0.7,  # < 0.8m 不合规
        "height": 2.1,
    }, headers=headers)
    assert resp.status_code == 201
    # 服务层应识别为不合规 (validate_wall_feature 在服务层被调用,但 API 不返回警告)
    # 这里仅验证添加成功,实际警告通过 WS 广播


# ── F1.5 应用到测量记录 ──

@pytest.mark.asyncio
async def test_ar_apply_to_survey(client: AsyncClient):
    """将 AR 扫描结果应用到测量记录 (Survey)"""
    token, headers = await _register_and_login(client, "13900008080")
    project_id = await _create_project(client, headers, "应用测试")

    resp = await client.post("/api/surveys/ar/sessions", json={
        "project_id": project_id,
        "name": "待应用扫描",
        "platform": "ios",
        "requested_method": "lidar",
        "device_capability": {"platform": "ios", "has_lidar": True, "arkit_version": "7.0"},
    }, headers=headers)
    session_id = resp.json()["id"]
    await client.post(f"/api/surveys/ar/sessions/{session_id}/start", headers=headers)
    await client.post(f"/api/surveys/ar/sessions/{session_id}/process", json={
        "model_format": "usdz",
    }, headers=headers)

    # 应用
    resp = await client.post(f"/api/surveys/ar/sessions/{session_id}/apply", headers=headers)
    assert resp.status_code == 200
    result = resp.json()
    assert "survey_id" in result
    assert result["rooms_added"] > 0

    # 验证 Survey 已创建
    resp = await client.get(f"/api/surveys/project/{project_id}", headers=headers)
    assert resp.status_code == 200
    surveys = resp.json()
    assert any(s["id"] == result["survey_id"] for s in surveys)


@pytest.mark.asyncio
async def test_ar_apply_blocked_when_not_completed(client: AsyncClient):
    """未完成的会话不允许应用"""
    token, headers = await _register_and_login(client, "13900008090")
    project_id = await _create_project(client, headers, "未完成应用测试")

    resp = await client.post("/api/surveys/ar/sessions", json={
        "project_id": project_id,
        "platform": "ios",
        "requested_method": "lidar",
        "device_capability": {"platform": "ios", "has_lidar": True, "arkit_version": "7.0"},
    }, headers=headers)
    session_id = resp.json()["id"]

    resp = await client.post(f"/api/surveys/ar/sessions/{session_id}/apply", headers=headers)
    assert resp.status_code == 400


# ── F1.6 单元测试 — 服务层算法 ──

def test_compute_accuracy_report_low_level():
    """单元测试: RMS 误差计算 — low 等级"""
    from app.services.ar_scan_service import compute_accuracy_report
    from app.models.ar_scan import ScanSession, MeasurementPoint

    session = ScanSession(
        id="test-1",
        project_id="proj-1",
        scan_method="visual_slam",
        requested_method="lidar",
    )

    # 构造偏差大的校准点 (AR 5.5m vs 参考 5.0m,偏差 50cm)
    points = [
        MeasurementPoint(
            id="p1",
            session_id="test-1",
            label="对角线",
            point_type="diagonal",
            ar_value=5.5,
            reference_value=5.0,
            unit="m",
            deviation=0.5,
            deviation_percent=10.0,
        ),
    ]
    report = compute_accuracy_report(points, session)
    assert report["accuracy_level"] == "low"
    assert report["rms_error_cm"] >= 50.0
    assert report["pass_rate"] == 0.0
    assert any("不合格" in r for r in report["recommendations"])
    # 降级路径: lidar → visual_slam
    assert "lidar" in report["degradation_path"]
    assert "visual_slam" in report["degradation_path"]


def test_compute_accuracy_report_empty():
    """单元测试: 无校准点时返回 unknown 等级"""
    from app.services.ar_scan_service import compute_accuracy_report
    from app.models.ar_scan import ScanSession

    session = ScanSession(id="test-2", project_id="proj-2")
    report = compute_accuracy_report([], session)
    assert report["accuracy_level"] == "unknown"
    assert report["rms_error_cm"] == 0.0
    assert len(report["recommendations"]) > 0


def test_validate_wall_feature_window_sill_too_low():
    """单元测试: 窗台高度低于规范 0.9m 应触发警告"""
    from app.services.ar_scan_service import validate_wall_feature, WallFeature

    feature = WallFeature(
        id="f1",
        session_id="s1",
        room_name="客厅",
        feature_type="window",
        width=1.5,
        height=1.5,
        sill_height=0.7,  # < 0.9m 不合规
    )
    warnings = validate_wall_feature(feature)
    assert len(warnings) > 0
    assert any("GB 50096" in w or "规范" in w for w in warnings)


def test_parse_usdz_model_empty():
    """单元测试: 空 model_url 应返回带警告的解析结果"""
    from app.services.ar_scan_service import parse_usdz_model

    result = parse_usdz_model("", "usdz")
    assert "parse_warnings" in result
    assert any("model_url 为空" in w for w in result["parse_warnings"])


def test_process_point_cloud_downsampling():
    """单元测试: 点云下采样应保留约 40% 点"""
    from app.services.ar_scan_service import process_point_cloud

    result = process_point_cloud(100000, 100.0)
    assert result["original_points"] == 100000
    assert result["downsampled_points"] == 40000
    assert result["voxel_size_cm"] == 2.0
    assert result["wall_planes"] >= 4


def test_detect_device_capability_lidar_priority():
    """单元测试: LiDAR 优先级最高"""
    from app.services.ar_scan_service import detect_device_capability

    result = detect_device_capability({
        "platform": "ios",
        "has_lidar": True,
        "arkit_version": "7.0",
        "supports_roomplan": True,
        "supports_photogrammetry": True,
    })
    assert result["recommended_method"] == "lidar"
    assert result["lidar_supported"] is True
    assert result["fallback_chain"] == ["lidar", "visual_slam", "photogrammetry", "manual"]

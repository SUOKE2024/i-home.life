"""F37 进度管理 / F38 质量管理 / F35 服务者匹配 新功能测试"""

from datetime import datetime, timezone, timedelta

import pytest
from httpx import AsyncClient


async def _register_and_login(client: AsyncClient, phone: str = "13900007001") -> tuple[str, dict]:
    resp = await client.post(
        "/api/auth/register",
        json={"phone": phone, "name": "高阶功能测试用户", "password": "test123456"},
    )
    token = resp.json()["access_token"]
    return token, {"Authorization": f"Bearer {token}"}


async def _create_project(client: AsyncClient, headers: dict, name: str = "高阶测试项目") -> str:
    resp = await client.post(
        "/api/projects",
        json={"name": name, "total_area": 100.0},
        headers=headers,
    )
    return resp.json()["id"]


# ── F37 AI 进度管理 ──

@pytest.mark.asyncio
async def test_progress_analysis_with_delay(client: AsyncClient):
    """F37 进度分析 — 延期任务预警"""
    token, headers = await _register_and_login(client, "13900007001")
    project_id = await _create_project(client, headers, "进度分析测试")

    # 构造延期任务：end_date 已过且未完成
    now = datetime.now(timezone.utc)
    tasks = [
        {
            "id": "task-1",
            "name": "水电布线",
            "phase": "mep",
            "status": "in_progress",
            "start_date": (now - timedelta(days=20)).isoformat(),
            "end_date": (now - timedelta(days=5)).isoformat(),  # 已延期 5 天
        },
        {
            "id": "task-2",
            "name": "瓷砖铺贴",
            "phase": "masonry",
            "status": "pending",
            "start_date": (now + timedelta(days=1)).isoformat(),
            "end_date": (now + timedelta(days=15)).isoformat(),
        },
        {
            "id": "task-3",
            "name": "材料进场",
            "phase": "preparation",
            "status": "completed",
            "start_date": (now - timedelta(days=30)).isoformat(),
            "end_date": (now - timedelta(days=28)).isoformat(),
        },
    ]

    resp = await client.post(
        "/api/construction/progress-analysis",
        json={"project_id": project_id, "tasks": tasks, "current_date": now.isoformat()},
        headers=headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["project_id"] == project_id
    assert "overall_progress" in data
    assert "expected_progress" in data
    assert "progress_deviation" in data
    assert len(data["phase_status"]) >= 2  # mep + masonry + preparation
    # 应有延期预警
    alerts = data["alerts"]
    assert len(alerts) >= 1
    delay_alerts = [a for a in alerts if a["alert_type"] == "delay"]
    assert len(delay_alerts) >= 1
    assert delay_alerts[0]["delay_days"] >= 5
    assert "suggestion" in delay_alerts[0]
    # 里程碑跟踪
    assert len(data["milestones"]) == 5
    assert data["risk_level"] in ("low", "medium", "high", "critical")
    assert len(data["suggestions"]) >= 1


@pytest.mark.asyncio
async def test_progress_analysis_empty_tasks(client: AsyncClient):
    """F37 进度分析 — 空任务列表"""
    token, headers = await _register_and_login(client, "13900007002")
    project_id = await _create_project(client, headers, "空进度测试")

    resp = await client.post(
        "/api/construction/progress-analysis",
        json={"project_id": project_id, "tasks": []},
        headers=headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["overall_progress"] == 0.0
    assert data["risk_level"] == "low"
    assert "暂无施工任务" in data["summary"]


@pytest.mark.asyncio
async def test_progress_alert_crud(client: AsyncClient):
    """F37 预警 CRUD"""
    token, headers = await _register_and_login(client, "13900007003")
    project_id = await _create_project(client, headers, "预警 CRUD 测试")

    # 创建预警
    resp = await client.post(
        "/api/construction/progress-alerts",
        json={
            "project_id": project_id,
            "phase": "mep",
            "alert_type": "delay",
            "severity": "high",
            "message": "水电阶段延期 7 天",
            "delay_days": 7,
            "progress_percent": 50.0,
            "suggestion": "建议增派人手",
        },
        headers=headers,
    )
    assert resp.status_code == 201
    alert_id = resp.json()["id"]
    assert resp.json()["status"] == "active"

    # 查询列表
    resp = await client.get(f"/api/construction/progress-alerts/{project_id}", headers=headers)
    assert resp.status_code == 200
    assert len(resp.json()) == 1

    # 解决预警
    resp = await client.patch(
        f"/api/construction/progress-alerts/{alert_id}/resolve",
        json={"note": "已增派人手赶工"},
        headers=headers,
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "resolved"
    assert resp.json()["resolved_by"] is not None


@pytest.mark.asyncio
async def test_milestone_tracking(client: AsyncClient):
    """F37 里程碑跟踪"""
    token, headers = await _register_and_login(client, "13900007004")
    project_id = await _create_project(client, headers, "里程碑测试")

    # 创建里程碑
    resp = await client.post(
        "/api/construction/milestones",
        json={
            "project_id": project_id,
            "milestone_code": "delivery",
            "name": "交房验收",
            "planned_percent": 5.0,
            "payment_ratio": 30.0,
        },
        headers=headers,
    )
    assert resp.status_code == 200
    milestone_id = resp.json()["id"]
    assert resp.json()["status"] == "pending"

    # 查询列表
    resp = await client.get(f"/api/construction/milestones/{project_id}", headers=headers)
    assert resp.status_code == 200
    assert len(resp.json()) == 1

    # 标记进行中（pending → in_progress）
    resp = await client.patch(
        f"/api/construction/milestones/{milestone_id}/status?new_status=in_progress",
        headers=headers,
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "in_progress"

    # 标记完成
    resp = await client.patch(
        f"/api/construction/milestones/{milestone_id}/complete",
        json={"actual_percent": 5.0, "note": "交房完成"},
        headers=headers,
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "completed"
    assert resp.json()["actual_date"] is not None


# ── F38 AI 质量管理 ──

@pytest.mark.asyncio
async def test_quality_detect_with_results(client: AsyncClient):
    """F38 质量检测 — 基于质检结果"""
    token, headers = await _register_and_login(client, "13900007005")
    project_id = await _create_project(client, headers, "质量检测测试")

    inspection_results = [
        {
            "check_item": "水管打压测试",
            "standard": "0.8MPa 保压 30 分钟不掉压",
            "ai_result": "fail",
            "confidence": 0.92,
            "issues": ["检测到压力下降 0.05MPa"],
        },
        {
            "check_item": "电路绝缘测试",
            "standard": "绝缘电阻 ≥ 0.5MΩ",
            "ai_result": "pass",
            "confidence": 0.95,
            "issues": [],
        },
        {
            "check_item": "瓷砖空鼓率",
            "standard": "单砖空鼓 < 5%",
            "ai_result": "fail",
            "confidence": 0.88,
            "issues": ["检测到 3 处空鼓"],
        },
    ]

    resp = await client.post(
        "/api/construction/quality-detect",
        json={
            "project_id": project_id,
            "phase": "mep",
            "inspection_results": inspection_results,
        },
        headers=headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["project_id"] == project_id
    assert len(data["detected_issues"]) == 2  # 2 项 fail
    # 防水问题应为 critical
    critical_issues = [i for i in data["detected_issues"] if i["severity"] == "critical"]
    assert len(critical_issues) >= 1
    # 应有建议整改单
    assert data["suggested_order"] is not None
    assert data["suggested_order"]["priority"] == "urgent"
    assert data["suggested_order"]["cost"] > 0


@pytest.mark.asyncio
async def test_quality_issue_and_rectification(client: AsyncClient):
    """F38 质量问题 + 整改单全链路"""
    token, headers = await _register_and_login(client, "13900007006")
    project_id = await _create_project(client, headers, "整改单测试")

    # 1. 创建质量问题
    resp = await client.post(
        "/api/construction/quality-issues",
        json={
            "project_id": project_id,
            "phase": "masonry",
            "category": "空鼓",
            "description": "客厅瓷砖空鼓 3 处",
            "severity": "high",
            "standard": "单砖空鼓 < 5%",
            "location": "客厅墙面",
        },
        headers=headers,
    )
    assert resp.status_code == 201
    issue_id = resp.json()["id"]
    assert resp.json()["status"] == "open"

    # 2. 创建整改单（关联 issue）
    resp = await client.post(
        "/api/construction/rectification-orders",
        json={
            "project_id": project_id,
            "title": "泥瓦阶段空鼓整改",
            "phase": "masonry",
            "issue_ids": [issue_id],
            "responsible_party": "张工长",
            "priority": "high",
            "cost": 800.0,
        },
        headers=headers,
    )
    assert resp.status_code == 201
    order_id = resp.json()["id"]
    order_no = resp.json()["order_no"]
    assert order_no.startswith("RO-")
    # 整改单创建后，关联 issue 应自动变为 in_progress
    resp = await client.get(f"/api/construction/quality-issues/{project_id}", headers=headers)
    assert resp.status_code == 200
    assert resp.json()[0]["status"] == "in_progress"

    # 3. 查询整改单列表
    resp = await client.get(f"/api/construction/rectification-orders/{project_id}", headers=headers)
    assert resp.status_code == 200
    assert len(resp.json()) == 1

    # 4. 完成整改单 (需先转为 in_progress, 再 completed)
    resp = await client.patch(
        f"/api/construction/rectification-orders/{order_id}/status?new_status=in_progress",
        headers=headers,
    )
    assert resp.status_code == 200
    resp = await client.patch(
        f"/api/construction/rectification-orders/{order_id}/status?new_status=completed",
        headers=headers,
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "completed"
    assert resp.json()["completed_at"] is not None

    # 5. 验收整改单（关联 issue 应变为 verified）
    resp = await client.patch(
        f"/api/construction/rectification-orders/{order_id}/status?new_status=verified",
        headers=headers,
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "verified"

    resp = await client.get(f"/api/construction/quality-issues/{project_id}", headers=headers)
    assert resp.json()[0]["status"] == "verified"


@pytest.mark.asyncio
async def test_quality_assessment(client: AsyncClient):
    """F38 质量评估"""
    token, headers = await _register_and_login(client, "13900007007")
    project_id = await _create_project(client, headers, "质量评估测试")

    resp = await client.post(
        "/api/construction/quality-assessments",
        json={
            "project_id": project_id,
            "phase": "masonry",
            "total_items": 5,
            "passed": 4,
            "failed": 1,
            "score": 80.0,
            "verdict": "conditional_pass",
            "assessor": "AI 质检",
            "summary": "泥瓦阶段质检：4/5 合格，需整改 1 项",
        },
        headers=headers,
    )
    assert resp.status_code == 201
    assert resp.json()["verdict"] == "conditional_pass"

    # 查询列表
    resp = await client.get(f"/api/construction/quality-assessments/{project_id}", headers=headers)
    assert resp.status_code == 200
    assert len(resp.json()) == 1


# ── F35 服务者匹配 ──

@pytest.mark.asyncio
async def test_worker_create_and_list(client: AsyncClient):
    """F35 服务者档案 CRUD"""
    token, headers = await _register_and_login(client, "13900007008")

    # 创建设计师
    resp = await client.post(
        "/api/workers",
        json={
            "name": "李设计师",
            "phone": "13900000001",
            "city": "北京",
            "district": "朝阳区",
            "role": "designer",
            "role_attributes": {
                "design_styles": ["modern", "minimal"],
                "software": ["AutoCAD", "SketchUp"],
                "portfolio_count": 60,
                "awards": 2,
            },
            "qualification": "A",
            "rating": 4.8,
            "completed_projects": 60,
            "years_of_experience": 8,
            "hourly_rate": 300,
            "daily_rate": 1200,
        },
        headers=headers,
    )
    assert resp.status_code == 201
    worker_id = resp.json()["id"]
    assert resp.json()["role_attributes"]["design_styles"] == ["modern", "minimal"]

    # 查询
    resp = await client.get(f"/api/workers/{worker_id}", headers=headers)
    assert resp.status_code == 200
    assert resp.json()["name"] == "李设计师"

    # 列表（按 role 过滤）
    resp = await client.get("/api/workers?role=designer", headers=headers)
    assert resp.status_code == 200
    assert len(resp.json()) >= 1


@pytest.mark.asyncio
async def test_designer_match(client: AsyncClient):
    """F35 设计师匹配"""
    token, headers = await _register_and_login(client, "13900007009")
    project_id = await _create_project(client, headers, "设计师匹配测试")

    # 创建 2 个设计师
    await client.post(
        "/api/workers",
        json={
            "name": "高分设计师", "city": "北京", "district": "朝阳区",
            "role": "designer",
            "role_attributes": {"design_styles": ["modern", "minimal"], "portfolio_count": 80, "awards": 3},
            "qualification": "A", "rating": 4.9, "completed_projects": 80,
            "years_of_experience": 12, "hourly_rate": 280,
        },
        headers=headers,
    )
    await client.post(
        "/api/workers",
        json={
            "name": "普通设计师", "city": "天津",
            "role": "designer",
            "role_attributes": {"design_styles": ["chinese"], "portfolio_count": 15, "awards": 0},
            "qualification": "C", "rating": 3.8, "completed_projects": 15,
            "years_of_experience": 2, "hourly_rate": 500,
        },
        headers=headers,
    )

    # 匹配
    resp = await client.post(
        "/api/workers/match",
        json={
            "project_id": project_id,
            "role": "designer",
            "city": "北京",
            "district": "朝阳区",
            "required_styles": ["modern", "minimal"],
            "budget_hourly_rate_max": 300,
            "top_n": 5,
        },
        headers=headers,
    )
    assert resp.status_code == 200
    matches = resp.json()
    assert len(matches) >= 1
    # 第一名应为高分设计师
    top = matches[0]
    assert top["worker"]["name"] == "高分设计师"
    assert top["match_score"] > 80
    assert "score_breakdown" in top
    assert top["score_breakdown"]["style"] == 30  # 风格完全匹配


@pytest.mark.asyncio
async def test_supervisor_and_estimator_match(client: AsyncClient):
    """F35 监理 + 预算师匹配"""
    token, headers = await _register_and_login(client, "13900007010")
    project_id = await _create_project(client, headers, "多角色匹配测试")

    # 创建监理
    await client.post(
        "/api/workers",
        json={
            "name": "王监理", "city": "北京",
            "role": "supervisor",
            "role_attributes": {
                "phases": ["mep", "masonry", "carpentry"],
                "certificate": "注册监理工程师", "supervised_projects": 100,
            },
            "qualification": "A", "rating": 4.7, "completed_projects": 100,
            "years_of_experience": 10, "daily_rate": 800,
        },
        headers=headers,
    )

    # 创建预算师
    await client.post(
        "/api/workers",
        json={
            "name": "赵预算师", "city": "北京",
            "role": "estimator",
            "role_attributes": {"budget_types": ["main", "soft"], "accuracy_rate": 0.96, "estimated_projects": 150},
            "qualification": "A", "rating": 4.8, "completed_projects": 150,
            "years_of_experience": 8, "hourly_rate": 250,
        },
        headers=headers,
    )

    # 监理匹配
    resp = await client.post(
        "/api/workers/match",
        json={
            "project_id": project_id,
            "role": "supervisor",
            "city": "北京",
            "required_phases": ["mep", "masonry"],
            "budget_daily_rate_max": 1000,
            "top_n": 3,
        },
        headers=headers,
    )
    assert resp.status_code == 200
    sup_matches = resp.json()
    assert len(sup_matches) >= 1
    assert sup_matches[0]["worker"]["name"] == "王监理"
    assert sup_matches[0]["score_breakdown"]["phase"] == 30  # 阶段全覆盖

    # 预算师匹配
    resp = await client.post(
        "/api/workers/match",
        json={
            "project_id": project_id,
            "role": "estimator",
            "city": "北京",
            "required_budget_types": ["main", "soft"],
            "budget_hourly_rate_max": 300,
            "top_n": 3,
        },
        headers=headers,
    )
    assert resp.status_code == 200
    est_matches = resp.json()
    assert len(est_matches) >= 1
    assert est_matches[0]["worker"]["name"] == "赵预算师"
    assert est_matches[0]["score_breakdown"]["accuracy"] >= 23.0  # 0.96 × 25 = 24.0

    # 更新匹配状态
    match_id = sup_matches[0]["id"]
    resp = await client.patch(
        f"/api/workers/matches/{match_id}/status?new_status=shortlisted",
        headers=headers,
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "shortlisted"

    # 查询项目匹配记录
    resp = await client.get(f"/api/workers/matches/{project_id}", headers=headers)
    assert resp.status_code == 200
    # 应包含监理和预算师两类匹配
    roles = {m["role"] for m in resp.json()}
    assert "supervisor" in roles
    assert "estimator" in roles

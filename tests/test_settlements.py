import pytest
from httpx import AsyncClient

from app.agents.settlement import SettlementAgent


async def _register_and_login(client: AsyncClient) -> str:
    resp = await client.post(
        "/api/auth/register",
        json={"phone": "13900004001", "name": "结算测试用户", "password": "test123456"},
    )
    return resp.json()["access_token"]


async def _create_project(client: AsyncClient, headers: dict) -> str:
    resp = await client.post(
        "/api/projects",
        json={"name": "结算测试项目", "total_area": 100.0},
        headers=headers,
    )
    return resp.json()["id"]


async def _create_settlement(client: AsyncClient, headers: dict, project_id: str) -> dict:
    """创建一份结算单，含两行：基础工程 + 主材"""
    resp = await client.post(
        "/api/settlements",
        json={
            "project_id": project_id,
            "milestone": "completion",
            "lines": [
                {
                    "category": "main",
                    "name": "基础工程",
                    "contract_amount": 50000.0,
                    "change_amount": 0.0,
                },
                {
                    "category": "main",
                    "name": "主材",
                    "contract_amount": 80000.0,
                    "change_amount": 5000.0,
                },
            ],
        },
        headers=headers,
    )
    return resp.json()


@pytest.mark.asyncio
async def test_get_settlement_not_found(client: AsyncClient):
    token = await _register_and_login(client)
    headers = {"Authorization": f"Bearer {token}"}
    project_id = await _create_project(client, headers)

    response = await client.get(f"/api/settlements/project/{project_id}", headers=headers)
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_create_settlement(client: AsyncClient):
    token = await _register_and_login(client)
    headers = {"Authorization": f"Bearer {token}"}
    project_id = await _create_project(client, headers)

    response = await client.post(
        "/api/settlements",
        json={
            "project_id": project_id,
            "milestone": "completion",
            "lines": [
                {
                    "category": "main",
                    "name": "基础工程",
                    "contract_amount": 50000.0,
                    "change_amount": 0.0,
                },
                {
                    "category": "main",
                    "name": "主材",
                    "contract_amount": 80000.0,
                    "change_amount": 5000.0,
                },
            ],
        },
        headers=headers,
    )
    assert response.status_code == 201
    data = response.json()
    assert data["project_id"] == project_id
    assert data["milestone"] == "completion"
    assert len(data["lines"]) == 2
    # contract_amount = (50000 + 0) + (80000 + 5000)
    assert data["contract_amount"] == 135000.0


@pytest.mark.asyncio
async def test_get_settlement(client: AsyncClient):
    token = await _register_and_login(client)
    headers = {"Authorization": f"Bearer {token}"}
    project_id = await _create_project(client, headers)

    await client.post(
        "/api/settlements",
        json={
            "project_id": project_id,
            "lines": [
                {"category": "main", "name": "测试行", "contract_amount": 10000.0},
            ],
        },
        headers=headers,
    )

    response = await client.get(f"/api/settlements/project/{project_id}", headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert data["project_id"] == project_id
    assert len(data["lines"]) == 1


@pytest.mark.asyncio
async def test_create_settlement_conflict(client: AsyncClient):
    token = await _register_and_login(client)
    headers = {"Authorization": f"Bearer {token}"}
    project_id = await _create_project(client, headers)

    payload = {
        "project_id": project_id,
        "lines": [
            {"category": "main", "name": "重复测试", "contract_amount": 1000.0},
        ],
    }
    first = await client.post("/api/settlements", json=payload, headers=headers)
    assert first.status_code == 201

    second = await client.post("/api/settlements", json=payload, headers=headers)
    assert second.status_code == 409


@pytest.mark.asyncio
async def test_generate_settlement_from_budget(client: AsyncClient):
    token = await _register_and_login(client)
    headers = {"Authorization": f"Bearer {token}"}
    project_id = await _create_project(client, headers)

    # 先创建预算
    budget_resp = await client.post(
        "/api/budgets",
        json={
            "project_id": project_id,
            "lines": [
                {
                    "category": "main",
                    "name": "基础工程",
                    "estimated_amount": 50000.0,
                    "unit": "项",
                    "quantity": 1.0,
                    "unit_price": 50000.0,
                },
                {
                    "category": "main",
                    "name": "主材",
                    "estimated_amount": 80000.0,
                    "unit": "项",
                    "quantity": 1.0,
                    "unit_price": 80000.0,
                },
            ],
        },
        headers=headers,
    )
    assert budget_resp.status_code == 201

    response = await client.post(
        f"/api/settlements/generate-from-budget/{project_id}",
        headers=headers,
    )
    assert response.status_code == 201
    data = response.json()
    assert data["project_id"] == project_id
    assert len(data["lines"]) == 2
    # contract_amount 由预算 estimated_amount 汇总
    assert data["contract_amount"] == 130000.0


@pytest.mark.asyncio
async def test_generate_settlement_from_budget_no_budget(client: AsyncClient):
    token = await _register_and_login(client)
    headers = {"Authorization": f"Bearer {token}"}
    project_id = await _create_project(client, headers)

    response = await client.post(
        f"/api/settlements/generate-from-budget/{project_id}",
        headers=headers,
    )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_confirm_settlement(client: AsyncClient):
    token = await _register_and_login(client)
    headers = {"Authorization": f"Bearer {token}"}
    project_id = await _create_project(client, headers)

    await client.post(
        "/api/settlements",
        json={
            "project_id": project_id,
            "lines": [
                {"category": "main", "name": "确认测试", "contract_amount": 20000.0},
            ],
        },
        headers=headers,
    )

    response = await client.post(
        f"/api/settlements/confirm/{project_id}",
        headers=headers,
    )
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "confirmed"
    assert data["settled_at"] is not None


@pytest.mark.asyncio
async def test_confirm_settlement_not_found(client: AsyncClient):
    token = await _register_and_login(client)
    headers = {"Authorization": f"Bearer {token}"}
    project_id = await _create_project(client, headers)

    response = await client.post(
        f"/api/settlements/confirm/{project_id}",
        headers=headers,
    )
    assert response.status_code == 404


# ── F14 新增测试用例 ─────────────────────────────────────────


@pytest.mark.asyncio
async def test_list_milestones(client: AsyncClient):
    """测试列出结算里程碑"""
    token = await _register_and_login(client)
    headers = {"Authorization": f"Bearer {token}"}

    response = await client.get("/api/settlements/milestones", headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert "milestones" in data
    assert data["total"] == 5  # handover/plumbing/tiling/completion/warranty
    codes = [m["code"] for m in data["milestones"]]
    assert "handover" in codes
    assert "completion" in codes
    assert "warranty" in codes
    # 验证里程碑比例合计 = 100%
    total_ratio = sum(m["payment_ratio"] for m in data["milestones"])
    assert abs(total_ratio - 1.0) < 0.001


@pytest.mark.asyncio
async def test_generate_milestone_settlement(client: AsyncClient):
    """测试生成里程碑结算单（竣工结算 20%）"""
    token = await _register_and_login(client)
    headers = {"Authorization": f"Bearer {token}"}

    response = await client.post(
        "/api/settlements/milestone",
        json={
            "contract_amount": 200000.0,
            "milestone_code": "completion",
            "change_amount": 10000.0,
            "deduction_amount": 5000.0,
            "paid_amount": 80000.0,
        },
        headers=headers,
    )
    assert response.status_code == 200
    data = response.json()
    assert data["milestone_code"] == "completion"
    assert data["milestone_name"] == "竣工结算"
    assert data["payment_ratio"] == 0.20
    # base_payable = 200000 * 0.20 = 40000
    assert data["base_payable"] == 40000.0
    # total_payable = 40000 + 10000 - 5000 - 80000 = -35000 → max(0) = 0
    assert data["total_payable"] == 0.0


@pytest.mark.asyncio
async def test_generate_milestone_settlement_unknown(client: AsyncClient):
    """测试未知里程碑返回 error"""
    token = await _register_and_login(client)
    headers = {"Authorization": f"Bearer {token}"}

    response = await client.post(
        "/api/settlements/milestone",
        json={
            "contract_amount": 200000.0,
            "milestone_code": "unknown_milestone",
        },
        headers=headers,
    )
    # Agent 返回 error 字典，FastAPI 默认 200
    assert response.status_code == 200
    data = response.json()
    assert "error" in data
    assert "available" in data


@pytest.mark.asyncio
async def test_anomaly_check(client: AsyncClient):
    """测试异常费用检测：超预算 + 未授权变更"""
    token = await _register_and_login(client)
    headers = {"Authorization": f"Bearer {token}"}

    response = await client.post(
        "/api/settlements/anomaly-check",
        json={
            "contract_amount": 200000.0,
            "actual_amount": 218000.0,  # 超出 9% → 触发 over_budget
            "change_orders": [
                {"name": "瓷砖升级", "amount": 8000.0, "authorized": True},
                {"name": "隐形门加项", "amount": 5000.0, "authorized": False},  # 未授权
            ],
            "unaccepted_items": [
                {"name": "防水验收", "amount": 3000.0},
            ],
            "line_items": [],
        },
        headers=headers,
    )
    assert response.status_code == 200
    data = response.json()
    assert data["total_anomalies"] >= 2  # 至少超预算 + 未授权 + 验收未通过
    assert data["critical_count"] >= 2  # 未授权 + 验收未通过 都是 critical
    assert data["suggested_deduction"] > 0
    assert "reply" in data


@pytest.mark.asyncio
async def test_anomaly_check_no_anomaly(client: AsyncClient):
    """测试异常费用检测：无异常场景"""
    token = await _register_and_login(client)
    headers = {"Authorization": f"Bearer {token}"}

    response = await client.post(
        "/api/settlements/anomaly-check",
        json={
            "contract_amount": 200000.0,
            "actual_amount": 200000.0,
            "change_orders": [],
            "unaccepted_items": [],
            "line_items": [],
        },
        headers=headers,
    )
    assert response.status_code == 200
    data = response.json()
    assert data["total_anomalies"] == 0
    assert data["critical_count"] == 0
    assert data["suggested_deduction"] == 0


@pytest.mark.asyncio
async def test_generate_reconciliation(client: AsyncClient):
    """测试对账单生成"""
    token = await _register_and_login(client)
    headers = {"Authorization": f"Bearer {token}"}

    response = await client.post(
        "/api/settlements/reconciliation",
        json={
            "contract_amount": 200000.0,
            "change_orders": [
                {"name": "瓷砖升级", "amount": 8000.0, "authorized": True},
                {"name": "隐形门加项", "amount": 5000.0, "authorized": False},
            ],
            "procurement_actual": 100000.0,
            "labor_actual": 80000.0,
            "unaccepted_items": [],
        },
        headers=headers,
    )
    assert response.status_code == 200
    data = response.json()
    assert data["contract_amount"] == 200000.0
    assert data["authorized_changes"] == 8000.0
    assert data["unauthorized_changes"] == 5000.0
    # payable = 200000 + 8000 - deduction - 5000
    assert data["total_payable"] == 203000.0 - data["deduction"]
    assert "reply" in data


@pytest.mark.asyncio
async def test_attach_anomalies_to_settlement(client: AsyncClient):
    """测试 F14 异常标记附加到结算行（按名称匹配）"""
    token = await _register_and_login(client)
    headers = {"Authorization": f"Bearer {token}"}
    project_id = await _create_project(client, headers)

    # 创建结算单，包含 "基础工程" 行
    await _create_settlement(client, headers, project_id)

    # 调用异常标记接口
    response = await client.post(
        f"/api/settlements/anomaly-attach/{project_id}",
        json={
            "anomalies": [
                {
                    "type": "over_budget",
                    "name": "基础工程",
                    "severity": "warning",
                    "detail": "基础工程超预算 8%",
                    "amount": 4000.0,
                },
                {
                    "type": "unaccepted",
                    "name": "主材",
                    "severity": "critical",
                    "detail": "主材验收未通过",
                    "amount": 5000.0,
                },
            ],
            "auto_mark_lines": True,
        },
        headers=headers,
    )
    assert response.status_code == 200
    data = response.json()
    assert data["anomaly_count"] == 2
    assert data["critical_anomaly_count"] == 1
    assert data["suggested_deduction"] == 5000.0
    assert data["review_required"] is True  # critical > 0 触发复核
    # 找到 "基础工程" 行，验证 is_anomaly=True
    base_line = next(line for line in data["lines"] if line["name"] == "基础工程")
    assert base_line["is_anomaly"] is True
    assert base_line["anomaly_type"] == "over_budget"
    assert base_line["anomaly_severity"] == "warning"
    # 找到 "主材" 行，验证 critical 标记
    main_line = next(line for line in data["lines"] if line["name"] == "主材")
    assert main_line["is_anomaly"] is True
    assert main_line["anomaly_severity"] == "critical"
    assert main_line["status"] == "flagged"


@pytest.mark.asyncio
async def test_attach_anomalies_not_found(client: AsyncClient):
    """测试异常标记附加到不存在的结算单"""
    token = await _register_and_login(client)
    headers = {"Authorization": f"Bearer {token}"}
    project_id = await _create_project(client, headers)

    response = await client.post(
        f"/api/settlements/anomaly-attach/{project_id}",
        json={"anomalies": [], "auto_mark_lines": True},
        headers=headers,
    )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_request_and_approve_review(client: AsyncClient):
    """测试 F14 人工复核：请求 → 通过 → 状态变化"""
    token = await _register_and_login(client)
    headers = {"Authorization": f"Bearer {token}"}
    project_id = await _create_project(client, headers)
    await _create_settlement(client, headers, project_id)

    # 1. 请求人工复核
    req_resp = await client.post(
        f"/api/settlements/request-review/{project_id}",
        json={"reason": "需复核瓷砖升级变更"},
        headers=headers,
    )
    assert req_resp.status_code == 200
    req_data = req_resp.json()
    assert req_data["review_required"] is True
    assert req_data["status"] == "review"
    assert req_data["review_reason"] == "需复核瓷砖升级变更"
    assert req_data["reviewed_by"] is not None

    # 2. 通过复核
    approve_resp = await client.post(
        f"/api/settlements/approve-review/{project_id}",
        headers=headers,
    )
    assert approve_resp.status_code == 200
    approve_data = approve_resp.json()
    assert approve_data["review_required"] is False
    assert approve_data["status"] == "draft"
    assert approve_data["reviewed_by"] is not None


@pytest.mark.asyncio
async def test_confirm_blocked_by_critical_anomaly(client: AsyncClient):
    """测试 F14：存在严重异常时，确认结算被 409 阻止"""
    token = await _register_and_login(client)
    headers = {"Authorization": f"Bearer {token}"}
    project_id = await _create_project(client, headers)
    await _create_settlement(client, headers, project_id)

    # 附加 critical 异常
    await client.post(
        f"/api/settlements/anomaly-attach/{project_id}",
        json={
            "anomalies": [
                {
                    "type": "unaccepted",
                    "name": "主材",
                    "severity": "critical",
                    "detail": "主材验收未通过",
                    "amount": 5000.0,
                },
            ],
            "auto_mark_lines": True,
        },
        headers=headers,
    )

    # 尝试确认 → 应被阻止
    response = await client.post(
        f"/api/settlements/confirm/{project_id}",
        headers=headers,
    )
    assert response.status_code == 409
    detail = response.json()["detail"]
    assert "message" in detail
    assert detail["critical_anomaly_count"] == 1


@pytest.mark.asyncio
async def test_export_reconciliation(client: AsyncClient):
    """测试 F14 对账单导出"""
    token = await _register_and_login(client)
    headers = {"Authorization": f"Bearer {token}"}
    project_id = await _create_project(client, headers)
    await _create_settlement(client, headers, project_id)

    response = await client.get(
        f"/api/settlements/export/{project_id}",
        headers=headers,
    )
    assert response.status_code == 200
    data = response.json()
    assert data["project_id"] == project_id
    assert "settlement_id" in data
    assert data["milestone"] == "completion"
    assert data["contract_amount"] == 135000.0
    assert len(data["lines"]) == 2
    assert "variance" in data["lines"][0]
    assert "exported_at" in data


@pytest.mark.asyncio
async def test_export_reconciliation_not_found(client: AsyncClient):
    """测试导出不存在的结算单"""
    token = await _register_and_login(client)
    headers = {"Authorization": f"Bearer {token}"}
    project_id = await _create_project(client, headers)

    response = await client.get(
        f"/api/settlements/export/{project_id}",
        headers=headers,
    )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_auto_settlement_no_anomaly(client: AsyncClient):
    """测试 F14 一键自动结算（无异常场景）"""
    token = await _register_and_login(client)
    headers = {"Authorization": f"Bearer {token}"}

    response = await client.post(
        "/api/settlements/auto-settlement",
        json={
            "contract_amount": 200000.0,
            "actual_amount": 200000.0,
            "change_orders": [],
            "unaccepted_items": [],
            "line_items": [],
        },
        headers=headers,
    )
    assert response.status_code == 200
    data = response.json()
    assert "anomalies" in data
    assert "reconciliation" in data
    assert data["review_required"] is False
    assert data["anomalies"]["total_anomalies"] == 0


@pytest.mark.asyncio
async def test_auto_settlement_with_critical(client: AsyncClient):
    """测试 F14 一键自动结算（含严重异常 → 触发复核）"""
    token = await _register_and_login(client)
    headers = {"Authorization": f"Bearer {token}"}

    response = await client.post(
        "/api/settlements/auto-settlement",
        json={
            "contract_amount": 200000.0,
            "actual_amount": 250000.0,  # 超支 25%
            "change_orders": [
                {"name": "瓷砖升级", "amount": 8000.0, "authorized": False},  # 未授权
            ],
            "unaccepted_items": [
                {"name": "防水验收", "amount": 3000.0},
            ],
            "line_items": [],
        },
        headers=headers,
    )
    assert response.status_code == 200
    data = response.json()
    assert data["review_required"] is True
    assert data["anomalies"]["critical_count"] >= 2


def test_agent_milestone_settlement_unit():
    """单元测试：直接验证 SettlementAgent 里程碑计算公式"""
    agent = SettlementAgent()
    # 竣工结算 20%：200000 * 0.20 = 40000
    result = agent.generate_milestone_settlement(
        contract_amount=200000.0,
        milestone_code="completion",
        change_amount=10000.0,
        deduction_amount=5000.0,
        paid_amount=20000.0,
    )
    assert result["base_payable"] == 40000.0
    # total = 40000 + 10000 - 5000 - 20000 = 25000
    assert result["total_payable"] == 25000.0
    assert "reply" in result


def test_agent_anomaly_detection_unit():
    """单元测试：直接验证异常检测规则"""
    agent = SettlementAgent()
    # 严重超预算 25% + 未授权变更 + 验收未通过
    result = agent.detect_anomalies({
        "contract_amount": 200000.0,
        "actual_amount": 250000.0,
        "change_orders": [{"name": "未授权加项", "amount": 5000.0, "authorized": False}],
        "unaccepted_items": [{"name": "防水", "amount": 3000.0}],
        "line_items": [],
    })
    assert result["critical_count"] >= 2  # 严重超支 + 未授权 + 验收未通过
    assert result["suggested_deduction"] > 0


def test_agent_reconciliation_unit():
    """单元测试：直接验证对账单生成"""
    agent = SettlementAgent()
    result = agent.generate_reconciliation({
        "contract_amount": 100000.0,
        "change_orders": [
            {"name": "瓷砖升级", "amount": 5000.0, "authorized": True},
            {"name": "隐形门", "amount": 3000.0, "authorized": False},
        ],
        "procurement_actual": 60000.0,
        "labor_actual": 40000.0,
        "unaccepted_items": [],
    })
    assert result["contract_amount"] == 100000.0
    assert result["authorized_changes"] == 5000.0
    assert result["unauthorized_changes"] == 3000.0
    # payable = 100000 + 5000 - deduction - 3000
    expected = 102000.0 - result["deduction"]
    assert result["total_payable"] == round(expected, 2)

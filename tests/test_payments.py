"""F15 支付管理测试 — 发起 / 确认 / 退款 / 标记失败 / 里程碑聚合 / 状态机校验 / 电子发票 / 分阶段支付节点 / 最终结算报告"""

import pytest
from httpx import AsyncClient


async def _register_and_login(client: AsyncClient, phone: str = "13900005001") -> tuple[str, dict]:
    resp = await client.post(
        "/api/auth/register",
        json={"phone": phone, "name": "支付测试用户", "password": "test123456"},
    )
    token = resp.json()["access_token"]
    return token, {"Authorization": f"Bearer {token}"}


async def _create_project(client: AsyncClient, headers: dict, name: str = "支付测试项目") -> str:
    resp = await client.post(
        "/api/projects",
        json={"name": name, "total_area": 100.0},
        headers=headers,
    )
    return resp.json()["id"]


async def _create_payment(
    client: AsyncClient,
    headers: dict,
    project_id: str,
    amount: float = 10000.0,
    milestone_code: str = "completion",
    stage_code: str | None = None,
    stage_order: int = 0,
) -> str:
    payload = {
        "project_id": project_id,
        "milestone_code": milestone_code,
        "amount": amount,
        "payment_method": "bank_transfer",
        "payer": "张三",
        "payee": "索克家居",
    }
    if stage_code:
        payload["stage_code"] = stage_code
        payload["stage_order"] = stage_order
    resp = await client.post("/api/payments", json=payload, headers=headers)
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


# ── 1. 创建支付 ──


@pytest.mark.asyncio
async def test_create_payment(client: AsyncClient):
    """测试发起支付：默认状态 pending，字段正确写入"""
    token, headers = await _register_and_login(client)
    project_id = await _create_project(client, headers)

    resp = await client.post(
        "/api/payments",
        json={
            "project_id": project_id,
            "milestone_code": "completion",
            "stage_code": "final",
            "stage_order": 3,
            "amount": 50000.0,
            "payment_method": "alipay",
            "payer": "李四",
            "payee": "索克家居",
            "note": "尾款支付",
        },
        headers=headers,
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["project_id"] == project_id
    assert data["status"] == "pending"
    assert data["amount"] == 50000.0
    assert data["milestone_code"] == "completion"
    assert data["stage_code"] == "final"
    assert data["stage_order"] == 3
    assert data["payer"] == "李四"
    assert data["payee"] == "索克家居"
    assert data["payment_method"] == "alipay"


# ── 2. 确认支付 ──


@pytest.mark.asyncio
async def test_confirm_payment(client: AsyncClient):
    """测试确认支付：pending → paid，记录流水号和凭证"""
    token, headers = await _register_and_login(client, "13900005002")
    project_id = await _create_project(client, headers, "确认支付项目")
    payment_id = await _create_payment(client, headers, project_id, amount=20000.0)

    resp = await client.post(
        f"/api/payments/{payment_id}/confirm",
        json={
            "transaction_id": "TXN-20260712-001",
            "evidence_url": "https://example.com/evidence/001.pdf",
            "payer": "王五",
            "note": "银行转账确认",
        },
        headers=headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "paid"
    assert data["transaction_id"] == "TXN-20260712-001"
    assert data["evidence_url"] == "https://example.com/evidence/001.pdf"
    assert data["payer"] == "王五"
    assert data["paid_at"] is not None


# ── 3. 退款 ──


@pytest.mark.asyncio
async def test_refund_payment(client: AsyncClient):
    """测试退款：paid → refunded，退款金额不超过原金额"""
    token, headers = await _register_and_login(client, "13900005003")
    project_id = await _create_project(client, headers, "退款测试项目")
    payment_id = await _create_payment(client, headers, project_id, amount=15000.0)

    # 先确认支付
    await client.post(
        f"/api/payments/{payment_id}/confirm",
        json={"transaction_id": "TXN-REFUND-001"},
        headers=headers,
    )

    # 退款
    resp = await client.post(
        f"/api/payments/{payment_id}/refund",
        json={
            "refund_amount": 10000.0,
            "refund_reason": "部分退款-施工范围调整",
        },
        headers=headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "refunded"
    assert data["refund_amount"] == 10000.0
    assert data["refund_reason"] == "部分退款-施工范围调整"
    assert data["refunded_at"] is not None


# ── 4. 标记失败 ──


@pytest.mark.asyncio
async def test_fail_payment(client: AsyncClient):
    """测试标记失败：pending → failed，记录失败原因"""
    token, headers = await _register_and_login(client, "13900005004")
    project_id = await _create_project(client, headers, "标记失败项目")
    payment_id = await _create_payment(client, headers, project_id, amount=8000.0)

    resp = await client.post(
        f"/api/payments/{payment_id}/fail",
        json={"reason": "银行通道异常，支付超时"},
        headers=headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "failed"
    assert "银行通道异常" in data["note"]

    # failed → paid（重试确认）
    resp2 = await client.post(
        f"/api/payments/{payment_id}/confirm",
        json={"transaction_id": "TXN-RETRY-001"},
        headers=headers,
    )
    assert resp2.status_code == 200
    assert resp2.json()["status"] == "paid"


# ── 5. 里程碑聚合 ──


@pytest.mark.asyncio
async def test_milestone_summary(client: AsyncClient):
    """测试里程碑聚合：按 milestone_code 分组统计支付金额"""
    token, headers = await _register_and_login(client, "13900005005")
    project_id = await _create_project(client, headers, "里程碑聚合项目")

    # 创建 3 笔支付，分属 2 个里程碑
    p1 = await _create_payment(client, headers, project_id, amount=30000.0, milestone_code="handover")
    p2 = await _create_payment(client, headers, project_id, amount=50000.0, milestone_code="completion")
    p3 = await _create_payment(client, headers, project_id, amount=20000.0, milestone_code="completion")

    # 确认 p1 和 p2
    await client.post(f"/api/payments/{p1}/confirm", json={"transaction_id": "T1"}, headers=headers)
    await client.post(f"/api/payments/{p2}/confirm", json={"transaction_id": "T2"}, headers=headers)

    resp = await client.get(f"/api/payments/milestones/{project_id}", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["project_id"] == project_id

    milestone_map = {m["milestone_code"]: m for m in data["milestones"]}
    assert "handover" in milestone_map
    assert "completion" in milestone_map

    # handover: 1 笔，总额 30000，已付 30000
    assert milestone_map["handover"]["total_payments"] == 1
    assert milestone_map["handover"]["total_amount"] == 30000.0
    assert milestone_map["handover"]["paid_amount"] == 30000.0

    # completion: 2 笔，总额 70000，已付 50000，待付 20000
    assert milestone_map["completion"]["total_payments"] == 2
    assert milestone_map["completion"]["total_amount"] == 70000.0
    assert milestone_map["completion"]["paid_amount"] == 50000.0
    assert milestone_map["completion"]["pending_amount"] == 20000.0

    # 汇总
    assert data["total_paid"] == 80000.0
    assert data["total_pending"] == 20000.0


# ── 6. 状态机校验：确认已支付记录应返回 400 ──


@pytest.mark.asyncio
async def test_state_machine_confirm_paid_returns_400(client: AsyncClient):
    """状态机校验：对已 paid 的支付再次 confirm 应返回 400"""
    token, headers = await _register_and_login(client, "13900005006")
    project_id = await _create_project(client, headers, "状态机-重复确认项目")
    payment_id = await _create_payment(client, headers, project_id, amount=10000.0)

    # 第一次确认成功
    resp1 = await client.post(
        f"/api/payments/{payment_id}/confirm",
        json={"transaction_id": "TXN-OK"},
        headers=headers,
    )
    assert resp1.status_code == 200

    # 第二次确认应失败
    resp2 = await client.post(
        f"/api/payments/{payment_id}/confirm",
        json={"transaction_id": "TXN-DUP"},
        headers=headers,
    )
    assert resp2.status_code == 400
    assert "paid" in resp2.json()["detail"]


# ── 7. 状态机校验：退款未支付记录应返回 400 ──


@pytest.mark.asyncio
async def test_state_machine_refund_pending_returns_400(client: AsyncClient):
    """状态机校验：对 pending 的支付退款应返回 400"""
    token, headers = await _register_and_login(client, "13900005007")
    project_id = await _create_project(client, headers, "状态机-退款未付项目")
    payment_id = await _create_payment(client, headers, project_id, amount=10000.0)

    resp = await client.post(
        f"/api/payments/{payment_id}/refund",
        json={"refund_amount": 5000.0},
        headers=headers,
    )
    assert resp.status_code == 400
    assert "pending" in resp.json()["detail"]


# ── 8. 状态机校验：标记已支付记录失败应返回 400 ──


@pytest.mark.asyncio
async def test_state_machine_fail_paid_returns_400(client: AsyncClient):
    """状态机校验：对 paid 的支付标记失败应返回 400"""
    token, headers = await _register_and_login(client, "13900005008")
    project_id = await _create_project(client, headers, "状态机-已付标记失败项目")
    payment_id = await _create_payment(client, headers, project_id, amount=10000.0)

    await client.post(
        f"/api/payments/{payment_id}/confirm",
        json={"transaction_id": "TXN-OK"},
        headers=headers,
    )

    resp = await client.post(
        f"/api/payments/{payment_id}/fail",
        json={"reason": "尝试标记失败"},
        headers=headers,
    )
    assert resp.status_code == 400


# ── 9. 电子发票 ──


@pytest.mark.asyncio
async def test_generate_invoice(client: AsyncClient):
    """F15 电子发票：仅已支付记录可开票，生成发票号"""
    token, headers = await _register_and_login(client, "13900005009")
    project_id = await _create_project(client, headers, "电子发票项目")
    payment_id = await _create_payment(client, headers, project_id, amount=30000.0)

    # 未支付时开票应失败
    resp1 = await client.post(
        f"/api/payments/{payment_id}/invoice",
        json={"payer": "测试公司", "invoice_url": "https://example.com/inv/001.pdf"},
        headers=headers,
    )
    assert resp1.status_code == 400

    # 确认支付
    await client.post(
        f"/api/payments/{payment_id}/confirm",
        json={"transaction_id": "TXN-INV-001"},
        headers=headers,
    )

    # 开票
    resp2 = await client.post(
        f"/api/payments/{payment_id}/invoice",
        json={
            "payer": "上海测试科技有限公司",
            "payee": "索克家居",
            "invoice_url": "https://example.com/inv/001.pdf",
        },
        headers=headers,
    )
    assert resp2.status_code == 200
    data = resp2.json()
    assert data["invoice_no"] is not None
    assert data["invoice_no"].startswith("INV-")
    assert data["invoice_url"] == "https://example.com/inv/001.pdf"
    assert data["invoiced_at"] is not None
    assert data["payer"] == "上海测试科技有限公司"

    # 重复开票：更新发票 URL，不生成新发票号
    resp3 = await client.post(
        f"/api/payments/{payment_id}/invoice",
        json={"invoice_url": "https://example.com/inv/001-v2.pdf"},
        headers=headers,
    )
    assert resp3.status_code == 200
    assert resp3.json()["invoice_no"] == data["invoice_no"]
    assert resp3.json()["invoice_url"] == "https://example.com/inv/001-v2.pdf"


# ── 10. 分阶段支付节点 ──


@pytest.mark.asyncio
async def test_payment_schedule(client: AsyncClient):
    """F15 分阶段支付节点：按 stage_code 聚合，返回各阶段进度"""
    token, headers = await _register_and_login(client, "13900005010")
    project_id = await _create_project(client, headers, "分阶段支付项目")

    # 创建 4 个阶段的支付节点
    p1 = await _create_payment(client, headers, project_id, amount=30000.0,
                               milestone_code="handover", stage_code="deposit", stage_order=1)
    p2 = await _create_payment(client, headers, project_id, amount=40000.0,
                               milestone_code="mep", stage_code="progress", stage_order=2)
    p3 = await _create_payment(client, headers, project_id, amount=20000.0,
                               milestone_code="completion", stage_code="final", stage_order=3)
    p4 = await _create_payment(client, headers, project_id, amount=10000.0,
                               milestone_code="warranty", stage_code="warranty", stage_order=4)

    # 确认首付和进度款
    await client.post(f"/api/payments/{p1}/confirm", json={"transaction_id": "T-S1"}, headers=headers)
    await client.post(f"/api/payments/{p2}/confirm", json={"transaction_id": "T-S2"}, headers=headers)

    resp = await client.get(f"/api/payments/schedule/{project_id}", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 4

    # 按 stage_order 排序
    data.sort(key=lambda n: n["stage_order"])
    assert data[0]["stage_code"] == "deposit"
    assert data[0]["status"] == "paid"
    assert data[0]["paid_amount"] == 30000.0

    assert data[1]["stage_code"] == "progress"
    assert data[1]["status"] == "paid"
    assert data[1]["paid_amount"] == 40000.0

    assert data[2]["stage_code"] == "final"
    assert data[2]["status"] == "pending"
    assert data[2]["paid_amount"] == 0.0
    assert data[2]["pending_amount"] == 20000.0

    assert data[3]["stage_code"] == "warranty"
    assert data[3]["status"] == "pending"


# ── 11. 最终结算报告 ──


@pytest.mark.asyncio
async def test_final_settlement_report(client: AsyncClient):
    """F15 最终结算报告：聚合支付/发票/结算单数据"""
    token, headers = await _register_and_login(client, "13900005011")
    project_id = await _create_project(client, headers, "最终结算报告项目")

    # 创建 2 笔支付
    p1 = await _create_payment(client, headers, project_id, amount=50000.0,
                               milestone_code="handover", stage_code="deposit", stage_order=1)
    p2 = await _create_payment(client, headers, project_id, amount=30000.0,
                               milestone_code="completion", stage_code="final", stage_order=2)

    # 确认 p1
    await client.post(f"/api/payments/{p1}/confirm", json={"transaction_id": "T-FS-1"}, headers=headers)

    # 对 p1 开票
    await client.post(
        f"/api/payments/{p1}/invoice",
        json={"payer": "测试公司", "invoice_url": "https://example.com/inv/fs.pdf"},
        headers=headers,
    )

    resp = await client.get(f"/api/payments/final-settlement/{project_id}", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["project_id"] == project_id
    assert data["total_paid"] == 50000.0
    assert data["total_pending"] == 30000.0
    assert data["total_refunded"] == 0.0
    assert data["payment_count"] == 2
    assert data["invoice_count"] == 1
    assert data["invoiced_amount"] == 50000.0
    assert 0 < data["paid_ratio"] < 1
    assert data["milestone_summary"] is not None
    assert data["generated_at"] is not None


# ── 12. 获取支付列表 + 单条详情 ──


@pytest.mark.asyncio
async def test_list_and_get_payment(client: AsyncClient):
    """测试支付列表按 stage_order 排序，单条详情正确返回"""
    token, headers = await _register_and_login(client, "13900005012")
    project_id = await _create_project(client, headers, "列表详情项目")

    p1 = await _create_payment(client, headers, project_id, amount=10000.0,
                               stage_code="final", stage_order=3)
    p2 = await _create_payment(client, headers, project_id, amount=20000.0,
                               stage_code="deposit", stage_order=1)

    # 列表
    resp = await client.get(f"/api/payments/project/{project_id}", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 2
    # 按 stage_order 升序
    assert data[0]["stage_code"] == "deposit"
    assert data[0]["stage_order"] == 1
    assert data[1]["stage_code"] == "final"
    assert data[1]["stage_order"] == 3

    # 单条详情
    resp2 = await client.get(f"/api/payments/{p2}", headers=headers)
    assert resp2.status_code == 200
    assert resp2.json()["id"] == p2
    assert resp2.json()["amount"] == 20000.0


# ── 13. 404 不存在 ──


@pytest.mark.asyncio
async def test_get_payment_not_found(client: AsyncClient):
    """测试获取不存在的支付记录返回 404"""
    token, headers = await _register_and_login(client, "13900005013")
    resp = await client.get("/api/payments/nonexistent-id", headers=headers)
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_confirm_payment_not_found(client: AsyncClient):
    """测试确认不存在的支付记录返回 404"""
    token, headers = await _register_and_login(client, "13900005014")
    resp = await client.post(
        "/api/payments/nonexistent-id/confirm",
        json={"transaction_id": "T"},
        headers=headers,
    )
    assert resp.status_code == 404

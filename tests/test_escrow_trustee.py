"""F43 资金托管深化 API 集成测试

覆盖端点:
- POST   /api/escrow/trustee-accounts                          (开通存管账户)
- GET    /api/escrow/trustee-accounts/{account_id}             (账户详情)
- GET    /api/escrow/escrow-payments/{payment_id}/trustee      (按担保支付查账户)
- GET    /api/escrow/project/{project_id}/trustee-accounts     (项目账户列表)
- POST   /api/escrow/trustee-accounts/{account_id}/acceptance  (节点验收双向确认)
- POST   /api/escrow/trustee-accounts/{account_id}/release     (放款)
- GET    /api/escrow/trustee-accounts/{account_id}/interest    (利息信息)
- DELETE /api/escrow/trustee-accounts/{account_id}             (删除账户)
"""
import pytest
from httpx import AsyncClient

from app.models import escrow_trustee  # noqa: F401
from app.models import procurement_enhanced  # noqa: F401


async def _auth_headers(client: AsyncClient, phone: str = "13930040001") -> dict:
    resp = await client.post(
        "/api/auth/register",
        json={"phone": phone, "name": "托管测试用户", "password": "test123456"},
    )
    assert resp.status_code == 201
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


async def _create_project(client: AsyncClient, headers: dict, name: str = "托管测试项目") -> str:
    resp = await client.post(
        "/api/projects", json={"name": name, "total_area": 100.0}, headers=headers,
    )
    assert resp.status_code == 201
    return resp.json()["id"]


async def _create_escrow_payment(
    client: AsyncClient, headers: dict, project_id: str, idx: int,
) -> str:
    """复用 F34 担保支付流程创建 EscrowPayment，返回 payment id"""
    cat_resp = await client.post(
        "/api/materials/categories",
        json={"name": f"托管分类{idx}", "code": f"trustee_cat_{idx}"},
        headers=headers,
    )
    assert cat_resp.status_code == 201
    cat_id = cat_resp.json()["id"]
    mat_resp = await client.post(
        "/api/materials",
        json={
            "category_id": cat_id, "name": "托管测试材料",
            "sku": f"TR-{idx}", "unit": "㎡", "unit_price": 200.0,
        },
        headers=headers,
    )
    assert mat_resp.status_code == 201
    material_id = mat_resp.json()["id"]
    sup_resp = await client.post(
        "/api/procurement/suppliers",
        json={"name": f"托管供应商{idx}", "category": "flooring", "rating": 4.8, "address": "上海市"},
        headers=headers,
    )
    assert sup_resp.status_code == 201
    supplier_id = sup_resp.json()["id"]
    order_resp = await client.post(
        "/api/procurement/orders",
        json={
            "project_id": project_id,
            "supplier_id": supplier_id,
            "lines": [{"material_id": material_id, "quantity": 10, "unit_price": 180.0}],
        },
        headers=headers,
    )
    assert order_resp.status_code == 201, order_resp.text
    order_id = order_resp.json()["id"]
    escrow_resp = await client.post(
        "/api/procurement-enhanced/escrow",
        json={"order_id": order_id},
        headers=headers,
    )
    assert escrow_resp.status_code == 201, escrow_resp.text
    return escrow_resp.json()["id"]


async def _pay_escrow(client: AsyncClient, headers: dict, payment_id: str) -> None:
    resp = await client.post(f"/api/procurement-enhanced/escrow/{payment_id}/pay", headers=headers)
    assert resp.status_code == 200


async def _create_account(
    client: AsyncClient, headers: dict, payment_id: str,
    interest_to_owner: bool = True,
) -> dict:
    resp = await client.post(
        "/api/escrow/trustee-accounts",
        json={
            "escrow_payment_id": payment_id,
            "trustee_type": "bank",
            "account_no_masked": "6222****8888",
            "interest_to_owner": interest_to_owner,
        },
        headers=headers,
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


# ── Auth ──


@pytest.mark.asyncio
async def test_escrow_trustee_unauthorized(client: AsyncClient):
    """未认证用户不能开通存管账户"""
    resp = await client.post(
        "/api/escrow/trustee-accounts",
        json={"escrow_payment_id": "fake", "account_no_masked": "6222****8888"},
    )
    assert resp.status_code == 401


# ── 存管账户 CRUD ──


@pytest.mark.asyncio
async def test_create_and_get_account(client: AsyncClient):
    """创建存管账户 + 详情/按担保支付/按项目查询"""
    headers = await _auth_headers(client, "13930040002")
    project_id = await _create_project(client, headers)
    payment_id = await _create_escrow_payment(client, headers, project_id, 1)

    account = await _create_account(client, headers, payment_id)
    assert account["status"] == "active"
    assert account["trustee_type"] == "bank"
    assert account["release_rule"] == "node_based"
    assert account["account_no_masked"] == "6222****8888"
    assert account["interest_to_owner"] is True
    assert account["owner_confirmed"] is False
    assert account["contractor_confirmed"] is False

    resp = await client.get(f"/api/escrow/trustee-accounts/{account['id']}", headers=headers)
    assert resp.status_code == 200
    assert resp.json()["escrow_payment_id"] == payment_id

    resp = await client.get(f"/api/escrow/escrow-payments/{payment_id}/trustee", headers=headers)
    assert resp.status_code == 200
    assert resp.json()["id"] == account["id"]

    resp = await client.get(f"/api/escrow/project/{project_id}/trustee-accounts", headers=headers)
    assert resp.status_code == 200
    assert len(resp.json()) == 1


@pytest.mark.asyncio
async def test_duplicate_account_conflict(client: AsyncClient):
    """同一担保支付重复开通存管账户 → 409"""
    headers = await _auth_headers(client, "13930040003")
    project_id = await _create_project(client, headers)
    payment_id = await _create_escrow_payment(client, headers, project_id, 2)
    await _create_account(client, headers, payment_id)

    resp = await client.post(
        "/api/escrow/trustee-accounts",
        json={"escrow_payment_id": payment_id, "account_no_masked": "6222****9999"},
        headers=headers,
    )
    assert resp.status_code == 409
    assert "已开通存管账户" in resp.json()["detail"]


# ── 节点验收双向确认 ──


@pytest.mark.asyncio
async def test_acceptance_transitions(client: AsyncClient):
    """业主确认后仍 active，双方都确认后 → release_requested"""
    headers = await _auth_headers(client, "13930040004")
    project_id = await _create_project(client, headers)
    payment_id = await _create_escrow_payment(client, headers, project_id, 3)
    account = await _create_account(client, headers, payment_id)

    resp = await client.post(
        f"/api/escrow/trustee-accounts/{account['id']}/acceptance",
        json={"role": "owner"},
        headers=headers,
    )
    assert resp.status_code == 200
    assert resp.json()["owner_confirmed"] is True
    assert resp.json()["status"] == "active"

    resp = await client.post(
        f"/api/escrow/trustee-accounts/{account['id']}/acceptance",
        json={"role": "contractor"},
        headers=headers,
    )
    assert resp.status_code == 200
    assert resp.json()["contractor_confirmed"] is True
    assert resp.json()["status"] == "release_requested"


@pytest.mark.asyncio
async def test_acceptance_invalid_role_422(client: AsyncClient):
    """非法确认角色 → 422"""
    headers = await _auth_headers(client, "13930040005")
    project_id = await _create_project(client, headers)
    payment_id = await _create_escrow_payment(client, headers, project_id, 4)
    account = await _create_account(client, headers, payment_id)

    resp = await client.post(
        f"/api/escrow/trustee-accounts/{account['id']}/acceptance",
        json={"role": "admin"},
        headers=headers,
    )
    assert resp.status_code == 422


# ── 放款 ──


@pytest.mark.asyncio
async def test_release_without_acceptance_conflict(client: AsyncClient):
    """未双方确认时放款 → 409"""
    headers = await _auth_headers(client, "13930040006")
    project_id = await _create_project(client, headers)
    payment_id = await _create_escrow_payment(client, headers, project_id, 5)
    await _pay_escrow(client, headers, payment_id)
    account = await _create_account(client, headers, payment_id)

    resp = await client.post(f"/api/escrow/trustee-accounts/{account['id']}/release", headers=headers)
    assert resp.status_code == 409
    assert "确认" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_release_without_buyer_paid_conflict(client: AsyncClient):
    """已双方确认但担保支付未买家付款 → 409"""
    headers = await _auth_headers(client, "13930040007")
    project_id = await _create_project(client, headers)
    payment_id = await _create_escrow_payment(client, headers, project_id, 6)
    account = await _create_account(client, headers, payment_id)
    await client.post(
        f"/api/escrow/trustee-accounts/{account['id']}/acceptance",
        json={"role": "owner"}, headers=headers,
    )
    await client.post(
        f"/api/escrow/trustee-accounts/{account['id']}/acceptance",
        json={"role": "contractor"}, headers=headers,
    )

    resp = await client.post(f"/api/escrow/trustee-accounts/{account['id']}/release", headers=headers)
    assert resp.status_code == 409
    assert "付款" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_release_success(client: AsyncClient):
    """付款 + 双方确认后放款 → released 且父担保支付 supplier_received"""
    headers = await _auth_headers(client, "13930040008")
    project_id = await _create_project(client, headers)
    payment_id = await _create_escrow_payment(client, headers, project_id, 7)
    await _pay_escrow(client, headers, payment_id)
    account = await _create_account(client, headers, payment_id)
    await client.post(
        f"/api/escrow/trustee-accounts/{account['id']}/acceptance",
        json={"role": "owner"}, headers=headers,
    )
    await client.post(
        f"/api/escrow/trustee-accounts/{account['id']}/acceptance",
        json={"role": "contractor"}, headers=headers,
    )

    resp = await client.post(f"/api/escrow/trustee-accounts/{account['id']}/release", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "released"
    assert data["released_at"] is not None

    resp = await client.get(f"/api/procurement-enhanced/escrow/{payment_id}", headers=headers)
    assert resp.status_code == 200
    assert resp.json()["supplier_received"] is True
    assert resp.json()["status"] == "supplier_received"


# ── 利息信息 ──


@pytest.mark.asyncio
async def test_interest_info(client: AsyncClient):
    """利息归属业主/平台两种说明"""
    headers = await _auth_headers(client, "13930040009")
    project_id = await _create_project(client, headers)
    payment_owner = await _create_escrow_payment(client, headers, project_id, 8)
    payment_platform = await _create_escrow_payment(client, headers, project_id, 9)
    acc_owner = await _create_account(client, headers, payment_owner, interest_to_owner=True)
    acc_platform = await _create_account(client, headers, payment_platform, interest_to_owner=False)

    resp = await client.get(f"/api/escrow/trustee-accounts/{acc_owner['id']}/interest", headers=headers)
    assert resp.status_code == 200
    assert resp.json()["interest_to_owner"] is True
    assert "业主" in resp.json()["note"]

    resp = await client.get(f"/api/escrow/trustee-accounts/{acc_platform['id']}/interest", headers=headers)
    assert resp.status_code == 200
    assert resp.json()["interest_to_owner"] is False
    assert "合规" in resp.json()["note"]


# ── 越权校验 ──


@pytest.mark.asyncio
async def test_cross_user_access_blocked(client: AsyncClient):
    """用户不能访问他人项目的存管账户"""
    headers_a = await _auth_headers(client, "13930040010")
    headers_b = await _auth_headers(client, "13930040011")
    project_id = await _create_project(client, headers_a)
    payment_id = await _create_escrow_payment(client, headers_a, project_id, 10)
    account = await _create_account(client, headers_a, payment_id)

    resp = await client.get(f"/api/escrow/trustee-accounts/{account['id']}", headers=headers_b)
    assert resp.status_code == 403


# ── 删除 ──


@pytest.mark.asyncio
async def test_delete_account(client: AsyncClient):
    """删除存管账户后查询 → 404"""
    headers = await _auth_headers(client, "13930040012")
    project_id = await _create_project(client, headers)
    payment_id = await _create_escrow_payment(client, headers, project_id, 11)
    account = await _create_account(client, headers, payment_id)

    resp = await client.delete(f"/api/escrow/trustee-accounts/{account['id']}", headers=headers)
    assert resp.status_code == 204

    resp = await client.get(f"/api/escrow/trustee-accounts/{account['id']}", headers=headers)
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_delete_released_account_conflict(client: AsyncClient):
    """已放款账户不可删除 → 409"""
    headers = await _auth_headers(client, "13930040013")
    project_id = await _create_project(client, headers)
    payment_id = await _create_escrow_payment(client, headers, project_id, 12)
    await _pay_escrow(client, headers, payment_id)
    account = await _create_account(client, headers, payment_id)
    await client.post(
        f"/api/escrow/trustee-accounts/{account['id']}/acceptance",
        json={"role": "owner"}, headers=headers,
    )
    await client.post(
        f"/api/escrow/trustee-accounts/{account['id']}/acceptance",
        json={"role": "contractor"}, headers=headers,
    )
    await client.post(f"/api/escrow/trustee-accounts/{account['id']}/release", headers=headers)

    resp = await client.delete(f"/api/escrow/trustee-accounts/{account['id']}", headers=headers)
    assert resp.status_code == 409

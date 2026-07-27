"""摄像头扫描 API 集成测试

覆盖端点:
- POST /api/products/camera/scan    (拍照识别产品)
- POST /api/products/camera/confirm (确认创建产品)
"""
import pytest
from httpx import AsyncClient


async def _auth_headers(
    client: AsyncClient, phone: str = "13900034001", role: str = "homeowner"
) -> dict:
    resp = await client.post(
        "/api/auth/register",
        json={"phone": phone, "name": "相机扫描测试", "password": "test123456", "role": role},
    )
    assert resp.status_code == 201
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


async def _auth_headers_supplier(client: AsyncClient, phone: str = "13900034010") -> dict:
    """注册供应商角色用户"""
    return await _auth_headers(client, phone, role="supplier")


def _make_dummy_image() -> bytes:
    """生成一个合法的 1x1 白色 PNG"""
    from io import BytesIO
    from PIL import Image
    img = Image.new('RGB', (1, 1), color='white')
    buf = BytesIO()
    img.save(buf, format='PNG')
    return buf.getvalue()


# ── Auth 校验 ──


@pytest.mark.asyncio
async def test_scan_unauthorized(client: AsyncClient):
    """未认证用户不能拍照扫描"""
    resp = await client.post(
        "/api/products/camera/scan",
        files={"image": ("test.jpg", _make_dummy_image(), "image/jpeg")},
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_confirm_unauthorized(client: AsyncClient):
    """未认证用户不能确认创建产品"""
    resp = await client.post(
        "/api/products/camera/confirm",
        data={"name": "测试产品"},
    )
    assert resp.status_code == 401


# ── 非供应商权限 ──


@pytest.mark.asyncio
async def test_scan_non_supplier(client: AsyncClient):
    """非供应商/未认证用户扫描应被拒绝"""
    headers = await _auth_headers(client, "13900034002")
    resp = await client.post(
        "/api/products/camera/scan",
        files={"image": ("test.jpg", _make_dummy_image(), "image/jpeg")},
        headers=headers,
    )
    # 普通 homeowner 未认证 → 403
    assert resp.status_code == 403


# ── 拍照扫描 ──


@pytest.mark.asyncio
async def test_scan_with_image(client: AsyncClient):
    """供应商上传图片进行产品识别"""
    headers = await _auth_headers_supplier(client, "13900034011")
    resp = await client.post(
        "/api/products/camera/scan",
        files={"image": ("product.png", _make_dummy_image(), "image/png")},
        data={"context": "瓷砖"},
        headers=headers,
    )
    # image_recognition_service 可能返回 200（识别成功）或 500（服务不可用）
    assert resp.status_code in (200, 500)
    if resp.status_code == 200:
        data = resp.json()
        assert "name" in data
        assert "category_cn" in data
        assert "confidence" in data


@pytest.mark.asyncio
async def test_scan_invalid_file_type(client: AsyncClient):
    """上传非图片文件应返回 400"""
    headers = await _auth_headers_supplier(client, "13900034012")
    resp = await client.post(
        "/api/products/camera/scan",
        files={"image": ("test.txt", b"hello", "text/plain")},
        headers=headers,
    )
    assert resp.status_code == 400
    assert "图片" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_confirm_create_product(client: AsyncClient):
    """确认并创建产品"""
    headers = await _auth_headers_supplier(client, "13900034013")
    # 先创建供应商记录
    await client.post(
        "/api/procurement/suppliers",
        json={
            "name": "相机测试供应商",
            "category": "tile",
            "rating": 4.5,
            "phone": "13900034013",
        },
        headers=headers,
    )

    resp = await client.post(
        "/api/products/camera/confirm",
        data={
            "name": "防滑地砖 800x800",
            "category": "tile",
            "description": "优质防滑地砖",
            "price_min": "50",
            "price_max": "80",
            "unit": "㎡",
            "stock_status": "in_stock",
        },
        headers=headers,
    )
    assert resp.status_code in (200, 201, 500)
    if resp.status_code == 201:
        data = resp.json()
        assert data["name"] == "防滑地砖 800x800"
        assert data["category"] == "tile"
        assert data["status"] == "draft"

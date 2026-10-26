"""structural API HTTP 层测试 —— 鉴权 / 项目归属 / 入参校验 / 序列化 / CRUD 闭环

为什么单独一个文件：`tests/test_structural.py` 的 38 个用例全部直接调
`structural_service`，一行 HTTP 都没走。`app/api/structural.py` 是最大的单个
API 模块（42 个端点），它的鉴权、跨用户越权、404/403 语义、422 校验、
响应序列化此前**完全没有覆盖**——service 层测试全绿也说明不了这些。

端点清单不手写，直接读 `app.main.app` 的路由表，新增端点会自动进入鉴权扫描。
"""
import re

import pytest
from httpx import AsyncClient

from app.main import app

PREFIX = "/api/structural"


def _collect_endpoints() -> list[tuple[str, str]]:
    """从真实路由表里取 structural 的全部 (method, path)。"""
    items: set[tuple[str, str]] = set()
    for route in app.routes:
        path = getattr(route, "path", "")
        if not path.startswith(PREFIX):
            continue
        for method in getattr(route, "methods", ()):
            if method in {"HEAD", "OPTIONS"}:
                continue
            items.add((method, path))
    return sorted(items)


ENDPOINTS = _collect_endpoints()
ENDPOINT_IDS = [f"{m} {p}" for m, p in ENDPOINTS]

# 以项目为作用域的集合端点：项目不存在时必须 404（不能 403 泄露存在性）
COLLECTION_PATHS = sorted(
    {p.replace("{project_id}", "missing-project") for _, p in ENDPOINTS if "{project_id}" in p}
)


def _concrete(path: str) -> str:
    """把 {wall_id} 这类占位符替换成不存在的 id，用于 404 场景。"""
    return re.sub(r"\{[^}]+\}", "missing-id", path)


async def _headers(client: AsyncClient, phone: str) -> dict:
    resp = await client.post(
        "/api/auth/register",
        json={"phone": phone, "name": "土建 HTTP 测试", "password": "test123456"},
    )
    assert resp.status_code == 201, resp.text
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


async def _new_project(client: AsyncClient, headers: dict, name: str = "土建 HTTP 项目") -> str:
    resp = await client.post("/api/projects", json={"name": name}, headers=headers)
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


# ════════════════════════════════════════════════════════════════
# 端点清单自检 + 全量鉴权扫描
# ════════════════════════════════════════════════════════════════


def test_endpoint_inventory_not_empty():
    """路由表能扫到 structural 端点（防前缀改名后本文件静默全跳过）。"""
    assert len(ENDPOINTS) >= 42, f"只扫到 {len(ENDPOINTS)} 个端点，路由前缀可能变了：{ENDPOINTS}"
    methods = {m for m, _ in ENDPOINTS}
    assert {"GET", "POST", "PUT", "DELETE"} <= methods


@pytest.mark.parametrize("method,path", ENDPOINTS, ids=ENDPOINT_IDS)
async def test_every_endpoint_requires_auth(client: AsyncClient, method: str, path: str):
    """42 个端点每一个都必须 401——土建数据不能裸奔。

    这条扫描是"新增端点忘记加 Depends(get_current_user)"的唯一防线：
    逐个手写用例一定会漏，从路由表生成就不会。
    """
    kwargs = {"json": {}} if method in {"POST", "PUT", "PATCH"} else {}
    resp = await client.request(method, _concrete(path), **kwargs)
    assert resp.status_code == 401, f"{method} {path} 未鉴权却返回 {resp.status_code}"


# ════════════════════════════════════════════════════════════════
# 项目归属：404 与 403 的语义不能混
# ════════════════════════════════════════════════════════════════


@pytest.mark.parametrize("path", COLLECTION_PATHS)
async def test_collection_404_when_project_missing(client: AsyncClient, path: str):
    """项目不存在 → 404「项目不存在」，不能退化成 403 或空列表。

    空列表是最坏结果：前端会显示「该项目还没有承重墙」，用户以为数据丢了。
    """
    headers = await _headers(client, "13900009101")
    resp = await client.get(path, headers=headers)
    assert resp.status_code == 404, f"{path} 返回 {resp.status_code}: {resp.text}"
    assert resp.json()["detail"] == "项目不存在"


async def test_cross_user_cannot_read_others_wall(client: AsyncClient):
    """别人的项目数据一律 403，不能靠猜到 id 读到。"""
    owner = await _headers(client, "13900009102")
    intruder = await _headers(client, "13900009103")
    project_id = await _new_project(client, owner)

    created = await client.post(
        "/api/structural/walls",
        json={"project_id": project_id, "wall_name": "业主的承重墙", "thickness_mm": 240},
        headers=owner,
    )
    assert created.status_code == 201, created.text
    wall_id = created.json()["id"]

    assert (await client.get(f"/api/structural/walls/{wall_id}", headers=intruder)).status_code == 403
    assert (
        await client.get(f"/api/structural/projects/{project_id}/walls", headers=intruder)
    ).status_code == 403
    assert (
        await client.put(f"/api/structural/walls/{wall_id}", json={"thickness_mm": 120}, headers=intruder)
    ).status_code == 403
    assert (await client.delete(f"/api/structural/walls/{wall_id}", headers=intruder)).status_code == 403

    # 越权请求全部被拒后，原数据必须完好
    still_there = await client.get(f"/api/structural/walls/{wall_id}", headers=owner)
    assert still_there.status_code == 200
    assert still_there.json()["thickness_mm"] == 240


async def test_cross_user_cannot_create_into_others_project(client: AsyncClient):
    """往别人项目里塞数据的请求必须被拒。"""
    owner = await _headers(client, "13900009104")
    intruder = await _headers(client, "13900009105")
    project_id = await _new_project(client, owner)

    resp = await client.post(
        "/api/structural/walls",
        json={"project_id": project_id, "wall_name": "偷塞的墙"},
        headers=intruder,
    )
    assert resp.status_code == 403


# ════════════════════════════════════════════════════════════════
# 入参校验
# ════════════════════════════════════════════════════════════════


async def test_create_wall_requires_required_fields(client: AsyncClient):
    """缺必填字段 → 422，且错误定位到具体字段（不能 500）。"""
    headers = await _headers(client, "13900009106")
    resp = await client.post("/api/structural/walls", json={}, headers=headers)
    assert resp.status_code == 422
    fields = {err["loc"][-1] for err in resp.json()["detail"]}
    assert {"project_id", "wall_name"} <= fields


async def test_create_wall_rejects_wrong_type(client: AsyncClient):
    """字段类型错误 → 422（thickness_mm 传字符串）。"""
    headers = await _headers(client, "13900009107")
    project_id = await _new_project(client, headers)
    resp = await client.post(
        "/api/structural/walls",
        json={"project_id": project_id, "wall_name": "墙", "thickness_mm": "很厚"},
        headers=headers,
    )
    assert resp.status_code == 422


# ════════════════════════════════════════════════════════════════
# 404 语义
# ════════════════════════════════════════════════════════════════


@pytest.mark.parametrize(
    "method,path",
    [
        ("GET", "/api/structural/walls/missing-id"),
        ("PUT", "/api/structural/walls/missing-id"),
        ("DELETE", "/api/structural/walls/missing-id"),
        ("GET", "/api/structural/beams/missing-id"),
        ("GET", "/api/structural/columns/missing-id"),
        ("GET", "/api/structural/slabs/missing-id"),
        ("GET", "/api/structural/foundations/missing-id"),
        ("GET", "/api/structural/load-estimates/missing-id"),
        ("GET", "/api/structural/compliance/missing-id"),
        ("GET", "/api/structural/quantity-calcs/missing-id"),
    ],
)
async def test_detail_endpoints_404_on_unknown_id(client: AsyncClient, method: str, path: str):
    """不存在的实体 id → 404，不能 500 或返回空对象。"""
    headers = await _headers(client, "13900009108")
    kwargs = {"json": {"thickness_mm": 200}} if method == "PUT" else {}
    resp = await client.request(method, path, headers=headers, **kwargs)
    assert resp.status_code == 404, f"{method} {path} 返回 {resp.status_code}: {resp.text}"


# ════════════════════════════════════════════════════════════════
# 承重墙 CRUD 全链路（HTTP 层）
# ════════════════════════════════════════════════════════════════


async def test_wall_crud_roundtrip(client: AsyncClient):
    """建 → 查 → 列 → 改 → 删 → 再查 404，全程走 HTTP，顺带验序列化字段。"""
    headers = await _headers(client, "13900009109")
    project_id = await _new_project(client, headers)

    created = await client.post(
        "/api/structural/walls",
        json={
            "project_id": project_id,
            "wall_name": "北侧承重墙",
            "thickness_mm": 240,
            "length_m": 5.5,
            "is_load_bearing": True,
        },
        headers=headers,
    )
    assert created.status_code == 201, created.text
    body = created.json()
    wall_id = body["id"]

    # 序列化：前端依赖这些字段名，改一个就是接口破坏
    for key in ("id", "project_id", "wall_name", "thickness_mm", "length_m"):
        assert key in body, f"响应缺字段 {key}: {body}"
    assert body["project_id"] == project_id
    assert body["wall_name"] == "北侧承重墙"
    assert body["thickness_mm"] == 240
    assert float(body["length_m"]) == pytest.approx(5.5)

    got = await client.get(f"/api/structural/walls/{wall_id}", headers=headers)
    assert got.status_code == 200
    assert got.json()["id"] == wall_id

    listed = await client.get(f"/api/structural/projects/{project_id}/walls", headers=headers)
    assert listed.status_code == 200
    ids = [item["id"] for item in listed.json()]
    assert ids == [wall_id], "列表必须包含刚建的墙且不串项目"

    updated = await client.put(
        f"/api/structural/walls/{wall_id}",
        json={"thickness_mm": 370, "wall_name": "北侧承重墙（加固）"},
        headers=headers,
    )
    assert updated.status_code == 200, updated.text
    assert updated.json()["thickness_mm"] == 370
    assert updated.json()["wall_name"] == "北侧承重墙（加固）"

    deleted = await client.delete(f"/api/structural/walls/{wall_id}", headers=headers)
    assert deleted.status_code == 204
    assert deleted.content == b"", "204 必须无响应体"

    gone = await client.get(f"/api/structural/walls/{wall_id}", headers=headers)
    assert gone.status_code == 404


async def test_quantity_calc_line_items_roundtrip(client: AsyncClient):
    """工程量计算 + 明细增删：明细写在 calc 上，删除后 calc 本身仍在。

    明细的 project_id 来自所属 calc（请求体里的 calculation_id 会被路径覆盖），
    这条链最容易写错归属校验，所以单独验一遍。
    """
    headers = await _headers(client, "13900009110")
    project_id = await _new_project(client, headers)

    calc = await client.post(
        "/api/structural/quantity-calcs",
        json={"project_id": project_id, "calc_name": "一层工程量", "calc_type": "concrete"},
        headers=headers,
    )
    assert calc.status_code == 201, calc.text
    calc_id = calc.json()["id"]

    item = await client.post(
        f"/api/structural/quantity-calcs/{calc_id}/line-items",
        json={"calculation_id": calc_id, "material_type": "concrete", "material_name": "C30 混凝土"},
        headers=headers,
    )
    assert item.status_code == 201, item.text
    item_id = item.json()["id"]

    removed = await client.delete(f"/api/structural/quantity-calcs/line-items/{item_id}", headers=headers)
    assert removed.status_code == 204

    calc_still_there = await client.get(f"/api/structural/quantity-calcs/{calc_id}", headers=headers)
    assert calc_still_there.status_code == 200

    # 已删除的明细再删一次 → 404（不能静默成功，否则前端会以为撤销了）
    again = await client.delete(f"/api/structural/quantity-calcs/line-items/{item_id}", headers=headers)
    assert again.status_code == 404


# ════════════════════════════════════════════════════════════════
# 计算型端点（不落库，但同样要鉴权 + 返回结构稳定）
# ════════════════════════════════════════════════════════════════


async def test_recommend_foundation_returns_reasoned_result(client: AsyncClient):
    """基础推荐必须给出推荐项与依据，不能只回一个空壳。"""
    headers = await _headers(client, "13900009111")
    resp = await client.post(
        "/api/structural/foundations/recommend",
        params={"soil_type": "粘土", "building_floors": 3},
        headers=headers,
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["soil_type"] == "粘土"
    assert body["building_floors"] == 3
    assert body["recommended"], "必须给出推荐的基础类型"
    assert body["reason"], "推荐必须带依据，否则前端只能瞎显示"


async def test_compute_load_estimates_returns_breakdown(client: AsyncClient):
    """荷载估算要返回分项清单 + 合计 + 依据规范，而不是只给一个总数。

    实测契约（2026-10-26）：顶层是 load_items[]（每项 load_type/load_name/
    load_value_kn_m2/total_load_kn），恒载与活载以分项形式给出，
    外加 total_load_kn 与 reference_standard。
    """
    headers = await _headers(client, "13900009112")
    resp = await client.post(
        "/api/structural/load-estimates/compute",
        json={"usage": "residential", "area_m2": 100.0, "floor_level": 1},
        headers=headers,
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()

    items = body["load_items"]
    assert items, "必须给出分项，否则业主看不懂这个总数是怎么来的"
    for item in items:
        for key in ("load_type", "load_name", "load_value_kn_m2", "total_load_kn"):
            assert key in item, f"分项缺字段 {key}: {item}"

    types = {item["load_type"] for item in items}
    assert {"dead_load", "live_load"} <= types, f"恒载与活载都要有分项：{types}"

    # 合计必须等于分项之和（否则前端两处数字对不上）
    assert float(body["total_load_kn"]) == pytest.approx(
        sum(float(i["total_load_kn"]) for i in items), rel=1e-6
    )
    assert body["reference_standard"], "必须标注依据规范，不能无来源地报数"


async def test_auto_calc_quantities_returns_result(client: AsyncClient):
    """自动算量：给参数就要给出结果对象（哪怕参数不全都算 0，也不能 500）。"""
    headers = await _headers(client, "13900009113")
    resp = await client.post(
        "/api/structural/quantity-calcs/auto-calc",
        json={"calc_type": "concrete", "wall_length_m": 10.0, "wall_height_m": 3.0, "wall_thickness_m": 0.24},
        headers=headers,
    )
    assert resp.status_code == 200, resp.text
    assert isinstance(resp.json(), dict) and resp.json()

"""空间语义理解层 + 渲染一致性校验测试（v1.14.0 P0-1/P0-2）

覆盖：
- infer_room_type 中文/英文名推断
- analyze_spatial_semantics 家具面积门槛 / 区域聚合 / 空数据诚实降级
- validate_floorplan_consistency 通过 / 无房间 / 面积不一致 / 洞口孤儿墙
- /api/floorplans/{id}/semantics 端点（200 / flag 关闭 503 / 未认证 401）
"""

import pytest
from httpx import AsyncClient

from app.config import get_settings
from app.services.spatial_semantics_service import (
    analyze_spatial_semantics,
    build_spatial_foundation,
    infer_room_type,
    validate_floorplan_consistency,
)


# ── 房间类型推断 ──


def test_infer_room_type_chinese():
    assert infer_room_type("客厅") == "living_room"
    assert infer_room_type("主卧") == "bedroom"
    assert infer_room_type("厨房") == "kitchen"
    assert infer_room_type("卫生间") == "bathroom"
    assert infer_room_type("书房") == "study"
    assert infer_room_type("餐厅") == "dining_room"


def test_infer_room_type_english_and_unknown():
    assert infer_room_type("living_room") == "living_room"
    assert infer_room_type("bedroom") == "bedroom"
    assert infer_room_type("bathroom") == "bathroom"
    assert infer_room_type("未知空间") == "other"
    assert infer_room_type(None) == "other"


# ── 语义空间理解 ──


def test_analyze_semantics_furniture_area_gate():
    data = {
        "rooms": [
            {"name": "客厅", "room_type": "living_room", "area": 10.0},
            {"name": "小客厅", "room_type": "living_room", "area": 6.0},
        ],
    }
    result = analyze_spatial_semantics(data)
    assert result["source"] == "rule_estimated"
    assert result["room_count"] == 2
    big = result["rooms"][0]
    small = result["rooms"][1]
    big_names = {f["name"] for f in big["furniture"]}
    assert "沙发" in big_names
    assert "茶几" in big_names
    assert "电视柜" not in big_names  # min_area 12 > 10
    assert small["furniture"] == []  # 6 < 9 全部不入


def test_analyze_semantics_zones():
    data = {
        "rooms": [
            {"name": "客厅", "type": "living_room", "area": 30.0},
            {"name": "主卧", "type": "bedroom", "area": 18.0},
            {"name": "厨房", "type": "kitchen", "area": 8.0},
            {"name": "卫生间", "type": "bathroom", "area": 5.0},
        ],
    }
    result = analyze_spatial_semantics(data)
    zones = result["zones"]
    assert zones["wet_zones"] == 2  # 厨房 + 卫生间
    assert zones["sleeping_zones"] == 1  # 主卧
    assert zones["public_zones"] == 1  # 客厅


def test_analyze_semantics_empty_honest():
    result = analyze_spatial_semantics('{"walls":[]}')
    assert result["source"] == "rule_estimated"
    assert result["room_count"] == 0
    assert result["rooms"] == []
    assert result["zones"] == {"wet_zones": 0, "sleeping_zones": 0, "public_zones": 0}


# ── 几何一致性校验 ──


def test_validate_consistency_valid():
    data = {
        "walls": [{"name": "墙A", "length": 4.0}],
        "doors": [{"name": "入户门", "width": 0.9, "height": 2.1, "wall_id": "墙A"}],
        "windows": [{"name": "客厅窗", "width": 1.2, "height": 1.5, "wall_id": "墙A"}],
        "rooms": [{"name": "客厅", "room_type": "living_room", "area": 30.0}],
        "total_area": 80.0,
    }
    result = validate_floorplan_consistency(data)
    assert result["source"] == "deterministic_rules"
    assert result["passed"] is True
    assert result["error_count"] == 0
    assert result["warning_count"] == 0
    assert result["checks"]["room_count"] == 1
    assert result["checks"]["wall_count"] == 1


def test_validate_consistency_no_rooms_error():
    result = validate_floorplan_consistency({"walls": [{"name": "墙A", "length": 4.0}]})
    assert result["passed"] is False
    assert result["error_count"] == 1
    assert result["issues"][0]["code"] == "no_rooms"


def test_validate_consistency_area_mismatch_warning():
    data = {
        "rooms": [{"name": "客厅", "room_type": "living_room", "area": 120.0}],
        "total_area": 80.0,
    }
    result = validate_floorplan_consistency(data)
    assert result["passed"] is True  # 仅告警，不阻断
    assert any(i["code"] == "area_mismatch" for i in result["issues"])


def test_validate_consistency_opening_orphan_wall():
    data = {
        "walls": [{"name": "墙A", "length": 4.0}],
        "doors": [{"name": "入户门", "width": 0.9, "height": 2.1, "wall_id": "不存在的墙"}],
        "rooms": [{"name": "客厅", "room_type": "living_room", "area": 30.0}],
    }
    result = validate_floorplan_consistency(data)
    assert any(i["code"] == "opening_orphan_wall" for i in result["issues"])


# ── 端点 ──


async def _create_project_and_plan(client: AsyncClient, headers: dict) -> str:
    proj = await client.post(
        "/api/projects", json={"name": "语义测试项目", "total_area": 80.0}, headers=headers,
    )
    assert proj.status_code in (200, 201), proj.text
    project_id = proj.json()["id"]
    plan = await client.post(
        "/api/floorplans",
        json={
            "project_id": project_id,
            "name": "语义测试方案",
            "data": (
                '{"walls":[{"name":"墙A","length":4.0}],'
                '"rooms":[{"name":"客厅","room_type":"living_room","area":30.0},'
                '{"name":"主卧","room_type":"bedroom","area":18.0}],'
                '"total_area":80.0}'
            ),
            "wall_height": 2.8,
            "total_area": 80.0,
            "room_count": 2,
        },
        headers=headers,
    )
    assert plan.status_code == 201, plan.text
    return plan.json()["id"]


@pytest.mark.asyncio
async def test_get_semantics_endpoint(client: AsyncClient, auth_headers: dict):
    plan_id = await _create_project_and_plan(client, auth_headers)
    resp = await client.get(f"/api/floorplans/{plan_id}/semantics", headers=auth_headers)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["plan_id"] == plan_id
    assert body["semantics"]["room_count"] == 2
    assert body["semantics"]["source"] == "rule_estimated"
    assert body["consistency"]["passed"] is True
    assert body["consistency"]["source"] == "deterministic_rules"


@pytest.mark.asyncio
async def test_get_semantics_flag_disabled_503(client: AsyncClient, auth_headers: dict, monkeypatch):
    plan_id = await _create_project_and_plan(client, auth_headers)
    monkeypatch.setattr(get_settings(), "spatial_semantics_enabled", False)
    resp = await client.get(f"/api/floorplans/{plan_id}/semantics", headers=auth_headers)
    assert resp.status_code == 503


@pytest.mark.asyncio
async def test_get_semantics_requires_auth(client: AsyncClient):
    resp = await client.get("/api/floorplans/some-id/semantics")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_get_semantics_not_found(client: AsyncClient, auth_headers: dict):
    resp = await client.get("/api/floorplans/nonexistent-id/semantics", headers=auth_headers)
    assert resp.status_code == 404


# ── 空间数字底座（Robot-Ready Home）──


def test_build_foundation_with_geometry():
    data = {
        "rooms": [
            {"name": "玄关", "type": "hallway", "x": 0, "y": 0, "w": 2, "h": 2},
            {"name": "客厅", "type": "living_room", "x": 2, "y": 0, "w": 5, "h": 4},
            {"name": "厨房", "type": "kitchen", "x": 7, "y": 0, "w": 3, "h": 3},
            {"name": "卫生间", "type": "bathroom", "x": 7, "y": 3, "w": 3, "h": 2},
        ],
    }
    result = build_spatial_foundation(data)
    assert result["source"] == "rule_derived"
    assert result["room_count"] == 4
    assert result["scale_unit"] == "mm"

    # 玄关中心 + 毫米尺度（非估算）
    hallway = result["rooms"][0]
    assert hallway["room_type"] == "hallway"
    assert hallway["center"] == {"x": 1.0, "y": 1.0}
    assert hallway["dimensions_mm"] == {"width": 2000, "depth": 2000, "estimated": False}

    # 邻接图：玄关-客厅 / 客厅-厨房 / 厨房-卫生间 / 客厅-卫生间
    edge_pairs = {(e["a"], e["b"]) for e in result["adjacency"]}
    assert len(result["adjacency"]) >= 3
    assert ("玄关", "客厅") in edge_pairs

    # 关键动线导航：客厅 1 跳 / 厨房 2 跳 / 卫生间 2 跳
    nav_by_to = {n["to"]: n for n in result["navigation"]}
    assert nav_by_to["客厅"]["hops"] == 1
    assert nav_by_to["厨房"]["hops"] == 2
    assert nav_by_to["卫生间"]["hops"] == 2
    assert "缺几何" not in result["note"]


def test_build_foundation_no_geometry_honest():
    data = {"rooms": [{"name": "客厅", "room_type": "living_room", "area": 30.0}]}
    result = build_spatial_foundation(data)
    assert result["room_count"] == 1
    assert result["rooms"][0]["center"] is None
    assert result["rooms"][0]["dimensions_mm"]["estimated"] is True
    assert result["adjacency"] == []
    assert result["navigation"] == []
    assert "缺几何" in result["note"]


@pytest.mark.asyncio
async def test_get_spatial_foundation_endpoint(client: AsyncClient, auth_headers: dict):
    proj = await client.post(
        "/api/projects", json={"name": "底座测试项目", "total_area": 80.0}, headers=auth_headers,
    )
    project_id = proj.json()["id"]
    plan = await client.post(
        "/api/floorplans",
        json={
            "project_id": project_id,
            "name": "底座测试方案",
            "data": (
                '{"rooms":['
                '{"name":"玄关","type":"hallway","x":0,"y":0,"w":2,"h":2},'
                '{"name":"客厅","type":"living_room","x":2,"y":0,"w":5,"h":4},'
                '{"name":"厨房","type":"kitchen","x":7,"y":0,"w":3,"h":3}]}'
            ),
            "wall_height": 2.8,
            "total_area": 80.0,
            "room_count": 3,
        },
        headers=auth_headers,
    )
    plan_id = plan.json()["id"]
    resp = await client.get(f"/api/floorplans/{plan_id}/spatial-foundation", headers=auth_headers)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["source"] == "rule_derived"
    assert body["room_count"] == 3
    assert len(body["adjacency"]) >= 1
    assert any(n["to"] == "客厅" for n in body["navigation"])

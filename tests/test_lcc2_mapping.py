"""LCC2 语义映射 sidecar 导出测试（评估报告 2026-09-12 P3 余项）

覆盖端点:
- GET /api/construction/projects/{project_id}/lcc2-mapping

契约要点:
- schema_version = lcc2-semantic-mapping/0.1（平台先行定义，行业无标准）
- 复用空间语义 + 3DGS 资产清单 + 确定性映射（施工阶段/房间名/项目兜底）
- 诚实边界：平台不产出 LCC2 二进制，仅语义映射 sidecar
"""
import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy import select


async def _latest_user(db_session):
    from app.models.user import User

    return (
        await db_session.execute(select(User).order_by(User.created_at.desc()).limit(1))
    ).scalars().first()


async def _make_project(db_session, user_id):
    from app.models.project import Project

    project = Project(id=str(uuid.uuid4()), name="LCC2 映射测试项目", total_area=100.0, owner_id=user_id)
    db_session.add(project)
    await db_session.flush()
    return project


@pytest.mark.asyncio
async def test_lcc2_mapping_export_schema(client: AsyncClient, auth_headers, db_session):
    """无数据项目 → 200 + schema v0.1 + 空资产清单 + 空映射"""
    user = await _latest_user(db_session)
    project = await _make_project(db_session, user.id)

    resp = await client.get(
        f"/api/construction/projects/{project.id}/lcc2-mapping", headers=auth_headers,
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["schema_version"] == "lcc2-semantic-mapping/0.1"
    assert body["project_id"] == project.id
    assert "spatial_semantics" in body
    assert body["gaussian_assets"] == []
    assert body["mapping"] == []
    assert "LCC2" in body["note"] and "不产出" in body["note"]


@pytest.mark.asyncio
async def test_lcc2_mapping_with_snapshot(client: AsyncClient, auth_headers, db_session):
    """施工快照 → construction_stage 映射"""
    from app.models.construction_snapshot import ConstructionSnapshot

    user = await _latest_user(db_session)
    project = await _make_project(db_session, user.id)
    snap = ConstructionSnapshot(
        id=str(uuid.uuid4()),
        project_id=project.id,
        stage="masonry",
        room_name="客厅",
        splat_url="/api/files/download/snap-1",
    )
    db_session.add(snap)
    await db_session.flush()

    resp = await client.get(
        f"/api/construction/projects/{project.id}/lcc2-mapping", headers=auth_headers,
    )
    assert resp.status_code == 200
    body = resp.json()
    assert len(body["gaussian_assets"]) == 1
    assert body["gaussian_assets"][0]["kind"] == "construction_snapshot"
    assert body["gaussian_assets"][0]["stage"] == "masonry"
    assert body["gaussian_assets"][0]["splat_url"] == "/api/files/download/snap-1"
    assert len(body["mapping"]) == 1
    entity = body["mapping"][0]["semantic_entity"]
    assert entity["type"] == "construction_stage"
    assert entity["stage"] == "masonry"


@pytest.mark.asyncio
async def test_lcc2_mapping_with_gaussian_panorama(client: AsyncClient, auth_headers, db_session):
    """高斯全景（无房间匹配）→ project 兜底映射"""
    from app.models.vr_panorama import VRPanorama

    user = await _latest_user(db_session)
    project = await _make_project(db_session, user.id)
    db_session.add(VRPanorama(
        id=str(uuid.uuid4()),
        project_id=project.id,
        room_name="主卧",
        panorama_type="gaussian",
        content_source="actual",
        splat_url="/api/files/download/pano-1",
        status="completed",
    ))
    await db_session.flush()

    resp = await client.get(
        f"/api/construction/projects/{project.id}/lcc2-mapping", headers=auth_headers,
    )
    assert resp.status_code == 200
    body = resp.json()
    assert len(body["gaussian_assets"]) == 1
    assert body["gaussian_assets"][0]["kind"] == "vr_panorama"
    # 无 room 语义匹配 → 项目级兜底（诚实标注，不伪造房间映射）
    entity = body["mapping"][0]["semantic_entity"]
    assert entity["type"] == "project"
    assert "未匹配" in entity.get("note", "")


@pytest.mark.asyncio
async def test_lcc2_mapping_non_owner_403(client: AsyncClient, auth_headers, db_session):
    """越权访问他人项目 → 403"""
    project = await _make_project(db_session, "other_user_999")
    resp = await client.get(
        f"/api/construction/projects/{project.id}/lcc2-mapping", headers=auth_headers,
    )
    assert resp.status_code == 403

"""structural_service 测试 — 承重墙/梁/柱/楼板/工程量计算 CRUD

覆盖 5 类 CRUD:
- 承重墙 (wall): create/get/list/update/delete (8 用例)
- 梁 (beam): create/get/list/update/delete (8 用例)
- 柱 (column): create/get/list/update/delete (8 用例)
- 楼板 (slab): create/get/list/update/delete (8 用例)
- 工程量计算 (quantity_calc): create/get/list/delete (6 用例,无 update 函数)
"""

import pytest

from app.models.user import User
from app.models.project import Project
from app.services.structural_service import (
    # 承重墙
    create_wall, get_wall, list_walls, update_wall, delete_wall,
    # 梁
    create_beam, get_beam, list_beams, update_beam, delete_beam,
    # 柱
    create_column, get_column, list_columns, update_column, delete_column,
    # 楼板
    create_slab, get_slab, list_slabs, update_slab, delete_slab,
    # 工程量计算
    create_quantity_calc, get_quantity_calc, list_quantity_calcs, delete_quantity_calc,
)


async def _create_user_and_project(db_session):
    user = User(phone="13900008001", name="土建测试", role="homeowner", hashed_password="x")
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    project = Project(name="土建项目", owner_id=user.id, total_area=80.0)
    db_session.add(project)
    await db_session.commit()
    await db_session.refresh(project)
    return user, project


# ════════════════════════════════════════════════════════════════
# 承重墙 CRUD
# ════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_create_wall(db_session):
    _, project = await _create_user_and_project(db_session)
    wall = await create_wall(db_session, {
        "project_id": project.id,
        "wall_name": "承重墙1",
        "thickness_mm": 240,
        "length_m": 5.0,
    })
    assert wall.id is not None
    assert wall.wall_name == "承重墙1"


@pytest.mark.asyncio
async def test_get_wall_not_found(db_session):
    result = await get_wall(db_session, "nonexistent-id")
    assert result is None


@pytest.mark.asyncio
async def test_list_walls_empty(db_session):
    _, project = await _create_user_and_project(db_session)
    result = await list_walls(db_session, project.id)
    assert result == []


@pytest.mark.asyncio
async def test_list_walls_with_data(db_session):
    _, project = await _create_user_and_project(db_session)
    await create_wall(db_session, {"project_id": project.id, "wall_name": "墙1"})
    await create_wall(db_session, {"project_id": project.id, "wall_name": "墙2"})
    result = await list_walls(db_session, project.id)
    assert len(result) == 2


@pytest.mark.asyncio
async def test_update_wall(db_session):
    _, project = await _create_user_and_project(db_session)
    wall = await create_wall(db_session, {"project_id": project.id, "wall_name": "墙1"})
    updated = await update_wall(db_session, wall.id, {"thickness_mm": 370})
    assert updated is not None
    assert updated.thickness_mm == 370


@pytest.mark.asyncio
async def test_update_wall_not_found(db_session):
    result = await update_wall(db_session, "nonexistent-id", {"thickness_mm": 370})
    assert result is None


@pytest.mark.asyncio
async def test_delete_wall(db_session):
    _, project = await _create_user_and_project(db_session)
    wall = await create_wall(db_session, {"project_id": project.id, "wall_name": "墙1"})
    result = await delete_wall(db_session, wall.id)
    assert result is True
    assert await get_wall(db_session, wall.id) is None


@pytest.mark.asyncio
async def test_delete_wall_not_found(db_session):
    result = await delete_wall(db_session, "nonexistent-id")
    assert result is False


# ════════════════════════════════════════════════════════════════
# 梁 CRUD
# ════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_create_beam(db_session):
    _, project = await _create_user_and_project(db_session)
    beam = await create_beam(db_session, {
        "project_id": project.id,
        "beam_name": "主梁1",
        "width_mm": 200,
        "height_mm": 400,
    })
    assert beam.id is not None
    assert beam.beam_name == "主梁1"


@pytest.mark.asyncio
async def test_get_beam_not_found(db_session):
    result = await get_beam(db_session, "nonexistent-id")
    assert result is None


@pytest.mark.asyncio
async def test_list_beams_empty(db_session):
    _, project = await _create_user_and_project(db_session)
    result = await list_beams(db_session, project.id)
    assert result == []


@pytest.mark.asyncio
async def test_list_beams_with_data(db_session):
    _, project = await _create_user_and_project(db_session)
    await create_beam(db_session, {"project_id": project.id, "beam_name": "梁1"})
    await create_beam(db_session, {"project_id": project.id, "beam_name": "梁2"})
    result = await list_beams(db_session, project.id)
    assert len(result) == 2


@pytest.mark.asyncio
async def test_update_beam(db_session):
    _, project = await _create_user_and_project(db_session)
    beam = await create_beam(db_session, {"project_id": project.id, "beam_name": "梁1"})
    updated = await update_beam(db_session, beam.id, {"height_mm": 500})
    assert updated is not None
    assert updated.height_mm == 500


@pytest.mark.asyncio
async def test_update_beam_not_found(db_session):
    result = await update_beam(db_session, "nonexistent-id", {"height_mm": 500})
    assert result is None


@pytest.mark.asyncio
async def test_delete_beam(db_session):
    _, project = await _create_user_and_project(db_session)
    beam = await create_beam(db_session, {"project_id": project.id, "beam_name": "梁1"})
    result = await delete_beam(db_session, beam.id)
    assert result is True
    assert await get_beam(db_session, beam.id) is None


@pytest.mark.asyncio
async def test_delete_beam_not_found(db_session):
    result = await delete_beam(db_session, "nonexistent-id")
    assert result is False


# ════════════════════════════════════════════════════════════════
# 柱 CRUD
# ════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_create_column(db_session):
    _, project = await _create_user_and_project(db_session)
    col = await create_column(db_session, {
        "project_id": project.id,
        "column_name": "柱1",
        "width_mm": 300,
        "depth_mm": 300,
    })
    assert col.id is not None
    assert col.column_name == "柱1"


@pytest.mark.asyncio
async def test_get_column_not_found(db_session):
    result = await get_column(db_session, "nonexistent-id")
    assert result is None


@pytest.mark.asyncio
async def test_list_columns_empty(db_session):
    _, project = await _create_user_and_project(db_session)
    result = await list_columns(db_session, project.id)
    assert result == []


@pytest.mark.asyncio
async def test_list_columns_with_data(db_session):
    _, project = await _create_user_and_project(db_session)
    await create_column(db_session, {"project_id": project.id, "column_name": "柱1"})
    await create_column(db_session, {"project_id": project.id, "column_name": "柱2"})
    result = await list_columns(db_session, project.id)
    assert len(result) == 2


@pytest.mark.asyncio
async def test_update_column(db_session):
    _, project = await _create_user_and_project(db_session)
    col = await create_column(db_session, {"project_id": project.id, "column_name": "柱1"})
    updated = await update_column(db_session, col.id, {"width_mm": 400})
    assert updated is not None
    assert updated.width_mm == 400


@pytest.mark.asyncio
async def test_update_column_not_found(db_session):
    result = await update_column(db_session, "nonexistent-id", {"width_mm": 400})
    assert result is None


@pytest.mark.asyncio
async def test_delete_column(db_session):
    _, project = await _create_user_and_project(db_session)
    col = await create_column(db_session, {"project_id": project.id, "column_name": "柱1"})
    result = await delete_column(db_session, col.id)
    assert result is True
    assert await get_column(db_session, col.id) is None


@pytest.mark.asyncio
async def test_delete_column_not_found(db_session):
    result = await delete_column(db_session, "nonexistent-id")
    assert result is False


# ════════════════════════════════════════════════════════════════
# 楼板 CRUD
# ════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_create_slab(db_session):
    _, project = await _create_user_and_project(db_session)
    slab = await create_slab(db_session, {
        "project_id": project.id,
        "slab_name": "楼板1",
        "thickness_mm": 120,
        "area_m2": 25.0,
    })
    assert slab.id is not None
    assert slab.slab_name == "楼板1"


@pytest.mark.asyncio
async def test_get_slab_not_found(db_session):
    result = await get_slab(db_session, "nonexistent-id")
    assert result is None


@pytest.mark.asyncio
async def test_list_slabs_empty(db_session):
    _, project = await _create_user_and_project(db_session)
    result = await list_slabs(db_session, project.id)
    assert result == []


@pytest.mark.asyncio
async def test_list_slabs_with_data(db_session):
    _, project = await _create_user_and_project(db_session)
    await create_slab(db_session, {"project_id": project.id, "slab_name": "板1"})
    await create_slab(db_session, {"project_id": project.id, "slab_name": "板2"})
    result = await list_slabs(db_session, project.id)
    assert len(result) == 2


@pytest.mark.asyncio
async def test_update_slab(db_session):
    _, project = await _create_user_and_project(db_session)
    slab = await create_slab(db_session, {"project_id": project.id, "slab_name": "板1"})
    updated = await update_slab(db_session, slab.id, {"thickness_mm": 150})
    assert updated is not None
    assert updated.thickness_mm == 150


@pytest.mark.asyncio
async def test_update_slab_not_found(db_session):
    result = await update_slab(db_session, "nonexistent-id", {"thickness_mm": 150})
    assert result is None


@pytest.mark.asyncio
async def test_delete_slab(db_session):
    _, project = await _create_user_and_project(db_session)
    slab = await create_slab(db_session, {"project_id": project.id, "slab_name": "板1"})
    result = await delete_slab(db_session, slab.id)
    assert result is True
    assert await get_slab(db_session, slab.id) is None


@pytest.mark.asyncio
async def test_delete_slab_not_found(db_session):
    result = await delete_slab(db_session, "nonexistent-id")
    assert result is False


# ════════════════════════════════════════════════════════════════
# 工程量计算 CRUD (无 update 函数,测 6 个用例)
# ════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_create_quantity_calc(db_session):
    _, project = await _create_user_and_project(db_session)
    calc = await create_quantity_calc(db_session, {
        "project_id": project.id,
        "calc_name": "工程量1",
        "calc_type": "brickwork",
        "brick_count": 1000,
        "mortar_m3": 0.5,
    })
    assert calc.id is not None
    assert calc.calc_name == "工程量1"


@pytest.mark.asyncio
async def test_get_quantity_calc_not_found(db_session):
    result = await get_quantity_calc(db_session, "nonexistent-id")
    assert result is None


@pytest.mark.asyncio
async def test_list_quantity_calcs_empty(db_session):
    _, project = await _create_user_and_project(db_session)
    result = await list_quantity_calcs(db_session, project.id)
    assert result == []


@pytest.mark.asyncio
async def test_list_quantity_calcs_with_data(db_session):
    _, project = await _create_user_and_project(db_session)
    await create_quantity_calc(db_session, {
        "project_id": project.id, "calc_name": "量1", "calc_type": "brickwork",
    })
    await create_quantity_calc(db_session, {
        "project_id": project.id, "calc_name": "量2", "calc_type": "concrete",
    })
    result = await list_quantity_calcs(db_session, project.id)
    assert len(result) == 2


@pytest.mark.asyncio
async def test_delete_quantity_calc(db_session):
    _, project = await _create_user_and_project(db_session)
    calc = await create_quantity_calc(db_session, {
        "project_id": project.id, "calc_name": "量1", "calc_type": "brickwork",
    })
    result = await delete_quantity_calc(db_session, calc.id)
    assert result is True
    assert await get_quantity_calc(db_session, calc.id) is None


@pytest.mark.asyncio
async def test_delete_quantity_calc_not_found(db_session):
    result = await delete_quantity_calc(db_session, "nonexistent-id")
    assert result is False

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.models.project import Project, Floor, Room
from app.schemas.project import ProjectCreate, ProjectUpdate


# ── 状态机定义 ──
# draft     → active (激活项目) | cancelled (取消)
# active    → completed (完工) | cancelled (中止)
# completed → 终态，不可再变
# cancelled → 终态，不可再变
VALID_TRANSITIONS: dict[str, set[str]] = {
    "draft": {"active", "cancelled"},
    "active": {"completed", "cancelled"},
    "completed": set(),
    "cancelled": set(),
}


# ── 全链路 7 阶段状态机（phase 列）──
# initiation → design → budget → procurement → construction → quality → settlement → completed
# 任意阶段可 → cancelled（终态）；仅允许前进，禁止后退/跳跃
PHASE_ORDER: list[str] = [
    "initiation", "design", "budget", "procurement",
    "construction", "quality", "settlement", "completed",
]
# phase→status 联动：进入 completed 时 status 同步 completed；离开 initiation 时 status 同步 active
_PHASE_TO_STATUS: dict[str, str] = {
    "initiation": "draft",
    "design": "active",
    "budget": "active",
    "procurement": "active",
    "construction": "active",
    "quality": "active",
    "settlement": "active",
    "completed": "completed",
}


class ProjectStateError(Exception):
    """项目状态机校验失败"""

    def __init__(self, current_status: str, action: str, allowed: set[str]):
        self.current_status = current_status
        self.action = action
        self.allowed = allowed
        super().__init__(
            f"项目状态「{current_status}」不支持操作「{action}」，"
            f"允许的目标状态: {sorted(allowed) or '无（终态）'}"
        )


class ProjectPhaseError(Exception):
    """项目阶段状态机校验失败"""

    def __init__(self, current_phase: str, target_phase: str, reason: str = ""):
        self.current_phase = current_phase
        self.target_phase = target_phase
        self.reason = reason
        super().__init__(
            f"项目阶段「{current_phase}」不允许转换到「{target_phase}」"
            f"{f'：{reason}' if reason else '，仅允许前进至下一阶段或 cancelled'}"
        )


def _assert_transition(project: Project, action: str, target: str) -> None:
    """校验状态机：当前状态是否允许转换到 target"""
    allowed = VALID_TRANSITIONS.get(project.status, set())
    if target not in allowed:
        raise ProjectStateError(project.status, action, allowed)


def _assert_phase_transition(project: Project, target: str) -> None:
    """校验 phase 状态机：
    - cancelled：任意阶段可进入（终态）
    - completed：仅允许从 quality 或 settlement 进入（验收阶段完工）
    - 其他：仅允许前进到相邻下一阶段（禁止后退或跳跃）
    """
    if target == project.phase:
        return  # 幂等，允许同状态
    if target == "cancelled":
        return  # 任意阶段可取消
    if target not in PHASE_ORDER:
        raise ProjectPhaseError(project.phase, target, "未知阶段码")
    cur = project.phase
    cur_idx = PHASE_ORDER.index(cur) if cur in PHASE_ORDER else -1
    target_idx = PHASE_ORDER.index(target)
    if target == "completed":
        # 完工闸门：仅允许从 quality 或 settlement 进入
        if cur not in ("quality", "settlement"):
            raise ProjectPhaseError(
                cur, target, "completed 仅允许从 quality 或 settlement 阶段进入"
            )
        return
    # 普通阶段：只允许前进到相邻下一阶段（target_idx == cur_idx + 1）
    if target_idx != cur_idx + 1:
        raise ProjectPhaseError(
            cur, target,
            f"仅允许前进到相邻下一阶段（{PHASE_ORDER[cur_idx+1] if cur_idx+1 < len(PHASE_ORDER) else '无'}），"
            f"禁止后退或跳跃",
        )


async def get_project(db: AsyncSession, project_id: str) -> Project | None:
    result = await db.execute(
        select(Project)
        .where(Project.id == project_id)
        .options(
            selectinload(Project.floors).selectinload(Floor.rooms),
            selectinload(Project.bom_items),
        )
    )
    return result.scalar_one_or_none()


async def get_user_projects(db: AsyncSession, user_id: str) -> list[Project]:
    result = await db.execute(
        select(Project)
        .where(Project.owner_id == user_id)
        .options(selectinload(Project.floors))
        .order_by(Project.created_at.desc())
    )
    return list(result.scalars().all())


async def create_project(db: AsyncSession, user_id: str, data: ProjectCreate) -> Project:
    project = Project(
        name=data.name,
        description=data.description,
        address=data.address,
        total_area=data.total_area,
        project_type=data.project_type,
        source=data.source,
        house_type=data.house_type,
        latitude=data.latitude,
        longitude=data.longitude,
        contact_name=data.contact_name,
        contact_phone=data.contact_phone,
        owner_id=user_id,
    )
    db.add(project)
    await db.flush()

    for floor_data in data.floors:
        floor = Floor(
            project_id=project.id,
            name=floor_data.name,
            floor_number=floor_data.floor_number,
            area=floor_data.area,
        )
        db.add(floor)
        await db.flush()

        for room_data in floor_data.rooms:
            room = Room(
                floor_id=floor.id,
                name=room_data.name,
                room_type=room_data.room_type,
                area=room_data.area,
                width=room_data.width,
                height=room_data.height,
                length=room_data.length,
            )
            db.add(room)

    await db.commit()
    project = await get_project(db, project.id)

    # 全链路编排：项目创建 → 自动建预算（受 lifecycle_orchestration_enabled flag 控制）
    from app.services.lifecycle_events import emit_project_created
    await emit_project_created(project.id, owner_id=user_id)

    return project


async def update_project(db: AsyncSession, project_id: str, data: ProjectUpdate) -> Project | None:
    result = await db.execute(select(Project).where(Project.id == project_id))
    project = result.scalar_one_or_none()
    if not project:
        return None

    update_data = data.model_dump(exclude_unset=True)

    # status 变更走状态机校验（修复断裂 2：原 setattr 直绕校验）
    if "status" in update_data:
        new_status = update_data.pop("status")
        if new_status != project.status:
            _assert_transition(project, "update_status", new_status)
            project.status = new_status
            # status→completed 联动 phase→completed（兜底，正常路径走 update_project_phase/accept）
            if new_status == "completed" and project.phase != "completed":
                # 仅当当前 phase 在 settlement/completed 附近时才联动，避免 phase 跳跃
                if project.phase in ("settlement", "completed"):
                    project.phase = "completed"
                # 否则保留当前 phase，由 accept 端点统一推进

    # phase 变更走阶段状态机校验
    if "phase" in update_data:
        new_phase = update_data.pop("phase")
        if new_phase != project.phase:
            _assert_phase_transition(project, new_phase)
            project.phase = new_phase
            # phase→status 联动
            linked_status = _PHASE_TO_STATUS.get(new_phase)
            if linked_status and linked_status != project.status:
                # 走状态机校验（cancelled 不在 _PHASE_TO_STATUS，单独处理）
                if linked_status in VALID_TRANSITIONS.get(project.status, set()):
                    project.status = linked_status

    # 其余字段直接 setattr
    for key, value in update_data.items():
        setattr(project, key, value)

    await db.commit()
    # 重新通过 get_project 加载，确保 floors/rooms 等关系在异步上下文中可用
    return await get_project(db, project_id)


async def update_project_status(
    db: AsyncSession, project_id: str, status: str, action: str = "update_status",
) -> Project | None:
    """更新项目状态（带状态机校验）"""
    result = await db.execute(
        select(Project)
        .where(Project.id == project_id)
        .options(
            selectinload(Project.floors).selectinload(Floor.rooms),
            selectinload(Project.bom_items),
        )
    )
    project = result.scalar_one_or_none()
    if not project:
        return None
    _assert_transition(project, action, status)
    project.status = status
    # status→completed 联动 phase→completed
    if status == "completed":
        project.phase = "completed"
    await db.commit()
    await db.refresh(project)
    return project


async def update_project_phase(
    db: AsyncSession, project_id: str, phase: str,
) -> Project | None:
    """更新项目阶段（带阶段状态机校验 + status 联动）

    用于 accept 端点或显式阶段推进。phase→completed 时同步 status→completed。
    """
    result = await db.execute(
        select(Project)
        .where(Project.id == project_id)
        .options(
            selectinload(Project.floors).selectinload(Floor.rooms),
            selectinload(Project.bom_items),
        )
    )
    project = result.scalar_one_or_none()
    if not project:
        return None
    _assert_phase_transition(project, phase)
    project.phase = phase
    # phase→status 联动
    linked_status = _PHASE_TO_STATUS.get(phase)
    if linked_status and linked_status != project.status:
        if linked_status in VALID_TRANSITIONS.get(project.status, set()):
            project.status = linked_status
    await db.commit()
    await db.refresh(project)
    return project


async def delete_project(db: AsyncSession, project_id: str) -> bool:
    result = await db.execute(select(Project).where(Project.id == project_id))
    project = result.scalar_one_or_none()
    if not project:
        return False
    # 生产 PostgreSQL 严格 FK 约束：先按 FK 依赖逆序级联删除全部关联数据
    # （含二级子表如 budget_lines→budgets→projects、agent_messages→agent_sessions→projects），
    # 否则 DELETE 违反外键报 500（SQLite 测试默认不强制 FK 未暴露此问题）。
    await _cascade_delete_related(db, project_id)
    await db.delete(project)
    await db.commit()
    return True


async def _cascade_delete_related(db: AsyncSession, project_id: str) -> None:
    """递归删除项目全部关联数据。

    从 projects 出发，沿 FK 依赖链（子表 → 父表）逆序删除：
    1. 收集所有直接引用 projects.id 的表（如 budgets/floor_plans/settlements/...）
    2. 对每张关联表再收集引用它的子表（如 budget_lines→budgets、agent_messages→agent_sessions）
    3. 按依赖深度从最深子表开始删除，避免 FK 违反。
    不删除 projects 自身（由调用方处理）。
    """
    from sqlalchemy import delete
    from app.database import Base

    # 表名 → 该表的所有 FK 引用（child_table, child_fk_col, parent_pk_col）
    fk_index: dict[str, list[tuple[str, str, str]]] = {}
    for table in Base.metadata.sorted_tables:
        for fk in table.foreign_keys:
            parent_name = fk.column.table.name
            fk_index.setdefault(parent_name, []).append(
                (table.name, fk.parent.name, fk.column.name)
            )

    async def _delete_children(table_name: str, parent_ids: list[str]) -> None:
        """删除引用指定父表行的全部子表行（先递归孙表，再删本子表）。"""
        if not parent_ids:
            return
        for child_name, child_fk_col, _parent_pk in fk_index.get(table_name, []):
            child_table = Base.metadata.tables.get(child_name)
            if child_table is None or child_fk_col not in child_table.c:
                continue
            child_pk = next(iter(child_table.primary_key.columns)).name
            child_ids = (
                await db.execute(
                    select(child_table.c[child_pk]).where(
                        child_table.c[child_fk_col].in_(parent_ids)
                    )
                )
            ).scalars().all()
            child_id_list = list(child_ids)
            # 先递归删除孙表行，避免子表删除时孙表 FK 违反
            await _delete_children(child_name, child_id_list)
            await db.execute(
                delete(child_table).where(child_table.c[child_pk].in_(child_id_list))
            )

    await _delete_children("projects", [project_id])

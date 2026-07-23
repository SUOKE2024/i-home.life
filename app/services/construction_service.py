from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from sqlalchemy.orm import selectinload

from app.models.construction import ConstructionTask, ConstructionLog, Inspection
from app.models.project import Project, Floor, Room


# ── 施工任务状态机 ──
# pending      → in_progress (开始) | cancelled (取消)
# in_progress  → paused (暂停) | completed (完成) | cancelled (取消)
# paused       → in_progress (恢复) | cancelled (取消)
# completed    → 终态，不可再变
# cancelled    → 终态，不可再变
TASK_TRANSITIONS: dict[str, set[str]] = {
    "pending": {"in_progress", "cancelled"},
    "in_progress": {"paused", "completed", "cancelled"},
    "paused": {"in_progress", "cancelled"},
    "completed": set(),
    "cancelled": set(),
}

# ── 验收状态机 ──
# pending  → passed (通过) | failed (不通过)
# failed   → rework (整改) | passed (复验通过)
# rework   → pending (重新提交) | passed (通过)
# passed   → 终态，不可再变
INSPECTION_TRANSITIONS: dict[str, set[str]] = {
    "pending": {"passed", "failed"},
    "failed": {"rework", "passed"},
    "rework": {"pending", "passed"},
    "passed": set(),
}


class ConstructionStateError(Exception):
    """施工状态机校验失败"""

    def __init__(self, current_status: str, action: str, allowed: set[str]):
        self.current_status = current_status
        self.action = action
        self.allowed = allowed
        super().__init__(
            f"施工状态「{current_status}」不支持操作「{action}」，"
            f"允许的目标状态: {sorted(allowed) or '无（终态）'}"
        )


class InspectionStateError(Exception):
    """验收状态机校验失败"""

    def __init__(self, current_status: str, action: str, allowed: set[str]):
        self.current_status = current_status
        self.action = action
        self.allowed = allowed
        super().__init__(
            f"验收状态「{current_status}」不支持操作「{action}」，"
            f"允许的目标状态: {sorted(allowed) or '无（终态）'}"
        )


def _assert_task_transition(task: ConstructionTask, action: str, target: str) -> None:
    """校验施工任务状态机"""
    allowed = TASK_TRANSITIONS.get(task.status, set())
    if target not in allowed:
        raise ConstructionStateError(task.status, action, allowed)


def _assert_inspection_transition(inspection: Inspection, action: str, target: str) -> None:
    """校验验收状态机"""
    allowed = INSPECTION_TRANSITIONS.get(inspection.status, set())
    if target not in allowed:
        raise InspectionStateError(inspection.status, action, allowed)


async def get_tasks(db: AsyncSession, project_id: str) -> list[ConstructionTask]:
    result = await db.execute(
        select(ConstructionTask)
        .where(ConstructionTask.project_id == project_id)
        .order_by(ConstructionTask.phase, ConstructionTask.priority)
    )
    return list(result.scalars().all())


async def create_task(db: AsyncSession, data: dict) -> ConstructionTask:
    task = ConstructionTask(**data)
    db.add(task)
    await db.commit()
    await db.refresh(task)
    return task


async def update_task_status(db: AsyncSession, task_id: str, status: str) -> ConstructionTask | None:
    result = await db.execute(select(ConstructionTask).where(ConstructionTask.id == task_id))
    task = result.scalar_one_or_none()
    if not task:
        return None
    _assert_task_transition(task, "update_status", status)
    task.status = status
    await db.commit()
    await db.refresh(task)
    return task


async def add_log(db: AsyncSession, data: dict) -> ConstructionLog:
    log = ConstructionLog(**data)
    db.add(log)
    await db.commit()
    await db.refresh(log)
    return log


async def get_logs(db: AsyncSession, task_id: str) -> list[ConstructionLog]:
    result = await db.execute(
        select(ConstructionLog)
        .where(ConstructionLog.task_id == task_id)
        .order_by(ConstructionLog.created_at.desc())
    )
    return list(result.scalars().all())


async def create_inspection(db: AsyncSession, data: dict) -> Inspection:
    inspection = Inspection(**data)
    db.add(inspection)
    await db.commit()
    await db.refresh(inspection)
    return inspection


async def get_inspections(db: AsyncSession, task_id: str) -> list[Inspection]:
    result = await db.execute(
        select(Inspection)
        .where(Inspection.task_id == task_id)
        .order_by(Inspection.created_at.desc())
    )
    return list(result.scalars().all())


# ── 验收状态变更 ──

async def update_inspection_status(
    db: AsyncSession, inspection_id: str, status: str, action: str = "update_status",
) -> Inspection | None:
    """更新验收状态（带状态机校验）"""
    result = await db.execute(select(Inspection).where(Inspection.id == inspection_id))
    inspection = result.scalar_one_or_none()
    if not inspection:
        return None
    _assert_inspection_transition(inspection, action, status)
    inspection.status = status
    await db.commit()
    await db.refresh(inspection)
    return inspection


# ── 任务依赖管理 ──


async def add_task_dependency(db: AsyncSession, parent_task_id: str, child_task_id: str) -> ConstructionTask | None:
    """添加前置依赖：子任务不可在前置任务完成前开始"""
    result = await db.execute(select(ConstructionTask).where(ConstructionTask.id == child_task_id))
    child_task = result.scalar_one_or_none()
    if not child_task:
        return None

    # 校验父任务存在
    parent_result = await db.execute(select(ConstructionTask).where(ConstructionTask.id == parent_task_id))
    parent_task = parent_result.scalar_one_or_none()
    if not parent_task:
        raise ValueError(f"前置任务不存在: {parent_task_id}")

    # 校验不形成循环依赖
    if parent_task_id == child_task_id:
        raise ValueError("任务不能依赖自身")

    # 检查 child 已经是 parent 的前置（反向检查）
    if parent_task.predecessor_id == child_task_id:
        raise ValueError("不能形成循环依赖：子任务已经是父任务的前置")

    child_task.predecessor_id = parent_task_id
    await db.commit()
    await db.refresh(child_task)
    return child_task


async def get_task_chain(db: AsyncSession, task_id: str) -> dict:
    """获取任务的完整依赖链（所有前置和后续任务）"""
    all_predecessors: list[dict] = []
    all_successors: list[dict] = []

    # 递归获取所有前置任务
    visited_ids: set[str] = set()

    async def _collect_predecessors(tid: str) -> None:
        if tid in visited_ids:
            return
        visited_ids.add(tid)
        result = await db.execute(
            select(ConstructionTask)
            .where(ConstructionTask.id == tid)
            .options(selectinload(ConstructionTask.predecessor))
        )
        task = result.scalar_one_or_none()
        if task and task.predecessor:
            pred = task.predecessor
            all_predecessors.append({
                "id": pred.id,
                "name": pred.name,
                "phase": pred.phase,
                "status": pred.status,
            })
            await _collect_predecessors(pred.id)

    async def _collect_successors(tid: str) -> None:
        if tid in visited_ids:
            return
        visited_ids.add(tid)
        result = await db.execute(
            select(ConstructionTask)
            .where(ConstructionTask.id == tid)
            .options(selectinload(ConstructionTask.successors))
        )
        task = result.scalar_one_or_none()
        if task and task.successors:
            for succ in task.successors:
                all_successors.append({
                    "id": succ.id,
                    "name": succ.name,
                    "phase": succ.phase,
                    "status": succ.status,
                })
                await _collect_successors(succ.id)

    await _collect_predecessors(task_id)

    # 获取当前任务信息
    visited_ids.discard(task_id)  # 允许重新访问自身以收集后继
    task_result = await db.execute(
        select(ConstructionTask).where(ConstructionTask.id == task_id)
    )
    current = task_result.scalar_one_or_none()
    if not current:
        raise ValueError(f"任务不存在: {task_id}")

    visited_ids = {task_id}
    await _collect_successors(task_id)

    return {
        "task_id": task_id,
        "task_name": current.name,
        "phase": current.phase,
        "status": current.status,
        "predecessors": all_predecessors,
        "successors": all_successors,
    }


# ── 工期估算 ──

# 各施工阶段标准工期（每100㎡，单位：天）
PHASE_DURATION_DAYS: dict[str, tuple[int, int]] = {
    "demolition": (1, 2),      # 拆除
    "electrical": (3, 5),      # 水电改造
    "waterproof": (2, 3),      # 防水
    "masonry": (5, 7),         # 瓦工
    "carpentry": (5, 7),       # 木工
    "painting": (3, 5),        # 油漆
    "installation": (2, 3),    # 安装
    "inspection": (1, 1),      # 竣工验收
    "preparation": (1, 2),     # 准备
}

# 阶段中文名映射
PHASE_ALIASES: dict[str, str] = {
    "demolition": "拆除",
    "electrical": "水电改造",
    "waterproof": "防水",
    "masonry": "瓦工",
    "carpentry": "木工",
    "painting": "油漆",
    "installation": "安装",
    "inspection": "竣工验收",
    "preparation": "准备阶段",
}


async def _get_project_area(db: AsyncSession, project_id: str) -> float:
    """获取项目总面积（平米）"""
    # 先尝试从 project.total_area 获取
    proj_result = await db.execute(select(Project).where(Project.id == project_id))
    project = proj_result.scalar_one_or_none()
    if project and project.total_area:
        return project.total_area

    # 否则汇总所有房间面积
    area_result = await db.execute(
        select(func.coalesce(func.sum(Room.area), 0))
        .select_from(Room)
        .join(Floor, Floor.id == Room.floor_id)
        .where(Floor.project_id == project_id)
    )
    total = area_result.scalar()
    return float(total) if total and total > 0 else 100.0  # 默认 100㎡


async def estimate_duration(db: AsyncSession, task_id: str) -> dict:
    """根据任务类型和项目面积估算施工工期

    返回预估的最小/最大工期（天），基于 100㎡ 标准工期按面积比例缩放。
    """
    result = await db.execute(select(ConstructionTask).where(ConstructionTask.id == task_id))
    task = result.scalar_one_or_none()
    if not task:
        raise ValueError(f"任务不存在: {task_id}")

    project_area = await _get_project_area(db, task.project_id)
    area_ratio = project_area / 100.0

    # 获取对应阶段的工期范围
    phase = task.phase.lower() if task.phase else "preparation"
    min_days, max_days = PHASE_DURATION_DAYS.get(phase, (1, 2))

    # 按面积比例缩放（最小不低于 0.5 天）
    estimated_min = max(0.5, round(min_days * area_ratio, 1))
    estimated_max = max(0.5, round(max_days * area_ratio, 1))

    return {
        "task_id": task_id,
        "task_name": task.name,
        "phase": task.phase,
        "phase_name": PHASE_ALIASES.get(phase, task.phase),
        "project_area_sqm": project_area,
        "standard_min_days": min_days,
        "standard_max_days": max_days,
        "estimated_min_days": estimated_min,
        "estimated_max_days": estimated_max,
        "recommended_days": estimated_max,
    }


# ── WBS 生成 ──

# 标准 WBS 阶段定义
WBS_PHASES = [
    {"phase": "demolition", "name": "拆除", "min_days": 1, "max_days": 2, "depends_on": None},
    {"phase": "electrical", "name": "水电改造", "min_days": 3, "max_days": 5, "depends_on": "demolition"},
    {"phase": "waterproof", "name": "防水", "min_days": 2, "max_days": 3, "depends_on": "electrical"},
    {"phase": "masonry", "name": "瓦工", "min_days": 5, "max_days": 7, "depends_on": "waterproof"},
    {"phase": "carpentry", "name": "木工", "min_days": 5, "max_days": 7, "depends_on": "masonry"},
    {"phase": "painting", "name": "油漆", "min_days": 3, "max_days": 5, "depends_on": "carpentry"},
    {"phase": "installation", "name": "安装", "min_days": 2, "max_days": 3, "depends_on": "painting"},
    {"phase": "inspection", "name": "竣工验收", "min_days": 1, "max_days": 1, "depends_on": "installation"},
]


async def generate_wbs(db: AsyncSession, project_id: str) -> dict:
    """生成项目标准 WBS（Work Breakdown Structure）

    自动创建 8 个阶段任务并建立依赖关系：
    拆除 → 水电改造 → 防水 → 瓦工 → 木工 → 油漆 → 安装 → 竣工验收

    如项目已有任务则跳过，不会重复创建。
    """
    # 检查项目是否存在
    proj_result = await db.execute(select(Project).where(Project.id == project_id))
    project = proj_result.scalar_one_or_none()
    if not project:
        raise ValueError(f"项目不存在: {project_id}")

    # 检查是否已有 WBS 任务
    existing_result = await db.execute(
        select(func.count(ConstructionTask.id)).where(ConstructionTask.project_id == project_id)
    )
    existing_count = existing_result.scalar() or 0
    if existing_count > 0:
        # 返回现有 WBS 概览
        tasks_result = await db.execute(
            select(ConstructionTask)
            .where(ConstructionTask.project_id == project_id)
            .order_by(ConstructionTask.priority)
        )
        tasks = list(tasks_result.scalars().all())
        return {
            "project_id": project_id,
            "message": "WBS 已存在，返回当前任务列表",
            "total_phases": len(tasks),
            "phases": [
                {
                    "id": t.id,
                    "name": t.name,
                    "phase": t.phase,
                    "status": t.status,
                    "priority": t.priority,
                    "predecessor_id": t.predecessor_id,
                }
                for t in tasks
            ],
        }

    # 按面积缩放工期
    project_area = await _get_project_area(db, project_id)
    area_ratio = project_area / 100.0

    created_tasks: list[ConstructionTask] = []
    phase_id_map: dict[str, str] = {}  # phase_key → task_id

    for idx, phase_def in enumerate(WBS_PHASES):
        min_d = max(0.5, round(phase_def["min_days"] * area_ratio, 1))
        max_d = max(0.5, round(phase_def["max_days"] * area_ratio, 1))

        predecessor_id = None
        if phase_def["depends_on"]:
            predecessor_id = phase_id_map.get(phase_def["depends_on"])

        task = ConstructionTask(
            project_id=project_id,
            name=phase_def["name"],
            phase=phase_def["phase"],
            status="pending",
            priority=idx + 1,
            description=f"标准 WBS 阶段：{phase_def['name']}（预估 {min_d}-{max_d} 天）",
            predecessor_id=predecessor_id,
        )
        db.add(task)
        await db.flush()
        phase_id_map[phase_def["phase"]] = task.id
        created_tasks.append(task)

    await db.commit()
    for t in created_tasks:
        await db.refresh(t)

    return {
        "project_id": project_id,
        "total_phases": len(created_tasks),
        "project_area_sqm": project_area,
        "phases": [
            {
                "id": t.id,
                "name": t.name,
                "phase": t.phase,
                "status": t.status,
                "priority": t.priority,
                "predecessor_id": t.predecessor_id,
            }
            for t in created_tasks
        ],
    }


# ── 关键路径计算 ──


async def calculate_critical_path(db: AsyncSession, project_id: str) -> dict:
    """计算项目关键路径

    基于任务依赖关系和预估工期，找出最长路径（瓶颈路径）。
    返回关键路径任务列表和总工期。
    """
    # 获取项目所有任务，加载依赖关系
    result = await db.execute(
        select(ConstructionTask)
        .where(ConstructionTask.project_id == project_id)
        .options(
            selectinload(ConstructionTask.predecessor),
            selectinload(ConstructionTask.successors),
        )
        .order_by(ConstructionTask.priority)
    )
    tasks = list(result.scalars().all())

    if not tasks:
        raise ValueError(f"项目 {project_id} 没有施工任务")

    project_area = await _get_project_area(db, project_id)
    area_ratio = project_area / 100.0

    # 为每个任务计算预估工期
    task_duration: dict[str, float] = {}
    task_map: dict[str, ConstructionTask] = {}

    for task in tasks:
        phase = task.phase.lower() if task.phase else "preparation"
        _, max_days = PHASE_DURATION_DAYS.get(phase, (1, 2))
        task_duration[task.id] = max(0.5, round(max_days * area_ratio, 1))
        task_map[task.id] = task

    # 找起点任务（无前置依赖的）
    start_tasks = [t for t in tasks if t.predecessor_id is None]

    # 拓扑排序 + 计算最早开始时间（EST）
    in_degree: dict[str, int] = {}
    for t in tasks:
        in_degree[t.id] = 0
    for t in tasks:
        if t.predecessor_id:
            in_degree[t.id] = in_degree.get(t.id, 0) + 1

    # BFS 拓扑排序
    queue: list[str] = [t.id for t in start_tasks]
    topo_order: list[str] = []
    while queue:
        tid = queue.pop(0)
        topo_order.append(tid)
        task = task_map[tid]
        if task.successors:
            for succ in task.successors:
                in_degree[succ.id] -= 1
                if in_degree[succ.id] == 0:
                    queue.append(succ.id)

    # 计算最早完成时间（EFT）
    eft: dict[str, float] = {}
    for tid in topo_order:
        task = task_map[tid]
        pred_eft = 0.0
        if task.predecessor:
            pred_eft = eft.get(task.predecessor.id, 0.0)
        eft[tid] = pred_eft + task_duration[tid]

    # 找最晚完成的终端任务
    end_tasks = [t for t in tasks if not t.successors]
    if not end_tasks:
        end_tasks = tasks

    max_eft = max(eft.get(t.id, 0.0) for t in end_tasks)

    # 反向计算最晚开始时间（LST）
    lst: dict[str, float] = {}
    for t in end_tasks:
        lst[t.id] = max_eft - task_duration.get(t.id, 0.0)

    for tid in reversed(topo_order):
        task = task_map[tid]
        if task.successors:
            min_succ_lst = min(
                lst.get(succ.id, max_eft) for succ in task.successors
            )
            lst[tid] = min_succ_lst - task_duration[tid]

    # 找出关键路径（EFT == LST + duration，即没有浮动时间的任务）
    critical_tasks: list[dict] = []
    for task in tasks:
        slack = lst.get(task.id, 0.0) - (eft.get(task.id, 0.0) - task_duration.get(task.id, 0.0))
        is_critical = abs(slack) < 0.01
        critical_tasks.append({
            "id": task.id,
            "name": task.name,
            "phase": task.phase,
            "status": task.status,
            "duration_days": task_duration[task.id],
            "earliest_finish": eft.get(task.id, 0.0),
            "latest_start": lst.get(task.id, 0.0),
            "slack_days": round(slack, 1),
            "is_critical": is_critical,
            "predecessor_id": task.predecessor_id,
        })

    # 按 EFT 排序关键路径
    critical_path = sorted(
        [t for t in critical_tasks if t["is_critical"]],
        key=lambda x: x["earliest_finish"],
    )

    return {
        "project_id": project_id,
        "project_area_sqm": project_area,
        "total_duration_days": round(max_eft, 1),
        "critical_path_length": len(critical_path),
        "critical_path": critical_path,
        "all_tasks": critical_tasks,
    }


async def ai_predict_duration(
    db: AsyncSession,
    project_id: str,
) -> dict:
    """基于历史同类型项目数据，AI 辅助预测工期并给出置信区间

    通过查询已完成项目的历史工期数据，计算各阶段工期的统计分布，
    给出乐观/悲观/最可能三种估计（PERT 三点估算法）。

    Args:
        db: 数据库会话
        project_id: 项目 ID

    Returns:
        {
            "project_id": str,
            "predicted_total_days": float,     # 推荐工期（加权平均）
            "optimistic_days": float,           # 乐观估计
            "pessimistic_days": float,          # 悲观估计
            "confidence": float,                # 置信度 0-1
            "phase_predictions": [              # 各阶段预测
                {
                    "phase": str,
                    "historical_avg": float,
                    "historical_std": float,
                    "predicted": float,
                    "range": [float, float],
                }
            ],
            "sample_size": int,                 # 历史样本数
            "risk_factors": list[str],          # 识别的风险因素
        }
    """
    from collections import defaultdict
    import statistics

    # 获取当前项目信息
    project = await db.get(Project, project_id)
    if not project:
        return {"error": "Project not found"}

    # 计算项目面积
    floors = (await db.execute(select(Floor).where(Floor.project_id == project_id))).scalars().all()
    project_area = sum(f.area or 0 for f in floors)

    # 获取当前项目已生成的 WBS 任务
    current_tasks = (await db.execute(
        select(ConstructionTask).where(ConstructionTask.project_id == project_id)
    )).scalars().all()

    if not current_tasks:
        return {"error": "No WBS tasks found. Run generate_wbs() first."}

    # 查询历史已完成项目的工期数据
    # 筛选条件：status=completed, 面积在 50%-200% 范围的相似项目
    min_area = project_area * 0.5
    max_area = project_area * 2.0

    subq = (
        select(Project.id)
        .join(Floor, Floor.project_id == Project.id)
        .where(Floor.area.isnot(None))
        .group_by(Project.id)
        .having(
            func.sum(Floor.area).between(min_area, max_area)
        )
    ).subquery()

    historical_tasks = (await db.execute(
        select(ConstructionTask)
        .where(
            ConstructionTask.project_id.in_(select(subq.c.id)),
            ConstructionTask.status == "completed",
            ConstructionTask.actual_duration_days.isnot(None),
        )
    )).scalars().all()

    # 按 phase 聚合历史数据
    phase_data: dict[str, list[float]] = defaultdict(list)
    for t in historical_tasks:
        if t.phase and t.actual_duration_days:
            phase_data[t.phase].append(t.actual_duration_days)

    sample_size = len(historical_tasks)

    # PERT 三点估算法：乐观(最优10%) / 最可能(中位数) / 悲观(最差90%)
    phase_predictions: list[dict] = []
    total_weighted = 0.0
    total_optimistic = 0.0
    total_pessimistic = 0.0

    phase_order = [
        "foundation", "demolition", "mep", "waterproof",
        "masonry", "carpentry", "painting", "installation", "inspection",
    ]

    for phase in phase_order:
        durations = phase_data.get(phase, [])
        if not durations:
            # 无历史数据时使用标准工期作为 fallback
            phase_tasks = [t for t in current_tasks if t.phase == phase]
            if not phase_tasks:
                continue

            # 使用 WBS 定义的标准工期
            std_phase_days = {
                "demolition": 2.0, "mep": 4.0, "waterproof": 2.5,
                "masonry": 6.0, "carpentry": 6.0, "painting": 4.0,
                "installation": 2.5, "inspection": 1.0,
                "foundation": 3.0, "electrical": 4.0,
            }
            area_ratio = project_area / 100.0
            pred = std_phase_days.get(phase, 3.0) * area_ratio
            phase_predictions.append({
                "phase": phase,
                "predicted": round(pred, 1),
                "range": [round(pred * 0.8, 1), round(pred * 1.5, 1)],
                "confidence": 0.3,  # 低置信度（无历史数据）
                "sample_size": 0,
            })
            total_weighted += pred
            total_optimistic += pred * 0.8
            total_pessimistic += pred * 1.5
            continue

        sorted_d = sorted(durations)
        n = len(sorted_d)
        pessimistic = sorted_d[int(n * 0.9)] if n > 5 else max(sorted_d)
        optimistic = sorted_d[int(n * 0.1)] if n > 5 else min(sorted_d)
        most_likely = sorted_d[n // 2]  # 中位数
        avg = statistics.mean(durations)
        std = statistics.stdev(durations) if n > 1 else 0.0

        # PERT 加权: (乐观 + 4*最可能 + 悲观) / 6
        pert_weighted = (optimistic + 4 * most_likely + pessimistic) / 6

        phase_predictions.append({
            "phase": phase,
            "historical_avg": round(avg, 1),
            "historical_std": round(std, 1),
            "predicted": round(pert_weighted, 1),
            "range": [round(optimistic, 1), round(pessimistic, 1)],
            "confidence": min(0.9, 0.4 + 0.1 * n),  # 样本越多置信度越高
            "sample_size": n,
        })
        total_weighted += pert_weighted
        total_optimistic += optimistic
        total_pessimistic += pessimistic

    # 识别风险因素
    risk_factors: list[str] = []
    if project_area > 200:
        risk_factors.append("大面积项目(>200㎡)，协调复杂度高，建议预留 10% buffer")
    if sample_size < 10:
        risk_factors.append(f"历史样本不足(仅 {sample_size} 条)，预测仅供参考")
    if total_pessimistic - total_optimistic > 30:
        risk_factors.append("工期估算范围波动大(>30天)，建议细化施工方案后重新评估")

    return {
        "project_id": project_id,
        "project_area_sqm": round(project_area, 1),
        "predicted_total_days": round(total_weighted, 1),
        "optimistic_days": round(total_optimistic, 1),
        "pessimistic_days": round(total_pessimistic, 1),
        "confidence": round(min(0.9, 0.4 + 0.05 * min(sample_size, 10)), 2),
        "phase_predictions": phase_predictions,
        "sample_size": sample_size,
        "risk_factors": risk_factors,
    }

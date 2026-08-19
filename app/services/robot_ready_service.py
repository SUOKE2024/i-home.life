"""机器人友好（Robot-Ready）校验与空间语义导出 — v1.15.7

背景（2026-08 具身智能 C 端拐点，国盛证券《2026 家用机器人行业报告》）：
- 人形机器人走进家庭首站落地「栖息地」（标准化居家场景，2026-08-18）；
  海尔 AI 家庭机器人体验中心落地青岛；尚品宅配×启元机器人推 Robot-Ready 生态
- 国盛证券：仿真与真实场景落差 77pct，「居家数据采集闭环」是 C 端规模化关键
- 平台差异化：装修交付链天然是居家数据入口（户型语义 + 材料 + 施工 QA），
  在行业无标准前先行定义「空间语义导出 schema」+ 交付 QA 机器人友好校验项

设计约束（对齐 CLAUDE.md 诚实降级红线）：
- 全部确定性规则（零 LLM 成本）；数据缺失逐项标 insufficient_data，禁止伪装
- schema 为 v0.1 先行定义（行业无标准，随标准明朗迭代）
- feature flag robot_ready_export_enabled 门控
"""
from __future__ import annotations

import json
import logging
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)

# 空间语义导出 schema 版本（v0.1 先行定义，行业标准明朗后迭代）
SPATIAL_SCHEMA_VERSION = "spatial-semantics/0.1"

# 机器人友好校验项（确定性阈值，居家机器人通行/操作基础参数；
# 阈值参考公开报道的人形机器人通行宽度与家用设备通用可及性，数据缺失即 insufficient_data）
ROBOT_READY_CHECKS: list[dict] = [
    {
        "id": "RR1", "name": "门洞通行宽度",
        "desc": "主要门洞/通道净宽 ≥ 0.85m（人形机器人直行通行下限）",
        "field": "door_width", "min_value": 0.85,
    },
    {
        "id": "RR2", "name": "无门槛通行",
        "desc": "主要动线无高差门槛（轮式/双足通行；门槛 ≤ 2cm）",
        "field": "threshold_free", "expect": True,
    },
    {
        "id": "RR3", "name": "插座可操作高度",
        "desc": "主要插座/开关高度 0.3–1.2m（机器人机械臂可及区）",
        "field": "outlet_height_ok", "expect": True,
    },
    {
        "id": "RR4", "name": "主要动线宽度",
        "desc": "客厅/走廊主要动线宽度 ≥ 1.0m（双臂展开作业）",
        "field": "pathway_width", "min_value": 1.0,
    },
    {
        "id": "RR5", "name": "地面材质连续性",
        "desc": "主要动线地面材质连续（无大面积地毯/高差拼缝）",
        "field": "floor_continuity", "expect": True,
    },
]


def _load_floorplan_semantics(floorplan) -> dict:
    """从 FloorPlan.data / room_status JSON 提取语义字段（best-effort）。

    返回可判定的字段子集；缺字段一律缺失（insufficient_data），不伪造。
    v1.15.8 起支持 data.robot_ready 嵌套字典展开（QA 采集字段入库后自动消费）。
    """
    out: dict = {}
    for src in (floorplan.room_status, floorplan.data):
        if not src:
            continue
        try:
            data = json.loads(src) if isinstance(src, str) else src
            if isinstance(data, dict):
                for k, v in data.items():
                    if v is None:
                        continue
                    if k == "robot_ready" and isinstance(v, dict):
                        for kk, vv in v.items():
                            if kk not in out and vv is not None:
                                out[kk] = vv
                    elif k not in out:
                        out[k] = v
        except (json.JSONDecodeError, TypeError):
            continue
    return out


async def assess_robot_ready(db: AsyncSession, project_id: str) -> dict:
    """项目机器人友好度评估（确定性，零 LLM 成本）。

    Returns:
        {"project_id", "schema_version", "assessed_at",
         "checks": [{id, name, desc, status: pass/fail/insufficient_data,
                     evidence, note}],
         "summary": {total, pass, fail, insufficient_data, readiness_note}}
    """
    from app.models.floorplan import FloorPlan
    from app.models.project import Room, Floor

    _bj_tz = timezone(__import__("datetime").timedelta(hours=8), name="Asia/Shanghai")
    report: dict = {
        "project_id": project_id,
        "schema_version": SPATIAL_SCHEMA_VERSION,
        "assessed_at": datetime.now(_bj_tz).isoformat(),
        "checks": [],
    }

    floorplans = (
        await db.execute(
            select(FloorPlan).where(FloorPlan.project_id == project_id).order_by(FloorPlan.updated_at.desc())
        )
    ).scalars().all()

    rooms = []
    if floorplans:
        floor_ids = [f.id for f in floorplans]
        floors = (await db.execute(select(Floor).where(Floor.project_id == project_id))).scalars().all()
        floor_ids += [f.id for f in floors]
        if floor_ids:
            rooms = list(
                (await db.execute(select(Room).where(Room.floor_id.in_(floor_ids)))).scalars().all()
            )

    semantics: dict = {}
    for fp in floorplans:
        semantics.update(_load_floorplan_semantics(fp))

    # 房间维度兜底：最大 room.width 作为动线宽度参考（诚实标注推导来源）
    room_widths = [r.width for r in rooms if r.width]
    max_room_width = max(room_widths) if room_widths else None

    def _emit(check: dict, status: str, evidence: str, note: str = "") -> None:
        report["checks"].append({
            "id": check["id"], "name": check["name"], "desc": check["desc"],
            "status": status, "evidence": evidence, "note": note,
        })

    for check in ROBOT_READY_CHECKS:
        if check["field"] in semantics:
            value = semantics[check["field"]]
            if "min_value" in check:
                try:
                    ok = float(value) >= check["min_value"]
                except (TypeError, ValueError):
                    _emit(check, "insufficient_data", f"字段 {check['field']}={value!r} 无法数值判定")
                    continue
                _emit(check, "pass" if ok else "fail",
                      f"{check['field']}={value}（阈值 {check['min_value']}）")
            else:
                _emit(check, "pass" if bool(value) else "fail",
                      f"{check['field']}={bool(value)}")
        elif check["id"] == "RR4" and max_room_width is not None:
            # 动线宽度降级推导：最大房间宽度（诚实标注推导来源）
            ok = max_room_width >= check["min_value"]
            _emit(check, "pass" if ok else "fail",
                  f"由 rooms.width 最大房间宽度推导={max_room_width}（阈值 {check['min_value']}）",
                  note="动线实测数据缺失，由房间宽度推导（诚实标注）")
        else:
            _emit(check, "insufficient_data",
                  f"项目空间语义数据未包含 {check['field']}（floorplan.data/room_status 无该字段）",
                  note="交付 QA 采集该字段后即可判定（数据采集闭环是 C 端规模化关键，国盛证券 2026）")

    n_pass = sum(1 for c in report["checks"] if c["status"] == "pass")
    n_fail = sum(1 for c in report["checks"] if c["status"] == "fail")
    n_insuf = sum(1 for c in report["checks"] if c["status"] == "insufficient_data")
    if n_insuf == len(ROBOT_READY_CHECKS):
        readiness_note = "项目空间语义数据不足，暂无法评估机器人友好度（诚实标注，非不合格）"
    elif n_fail == 0:
        readiness_note = f"全部 {n_pass} 项可判定项通过（另有 {n_insuf} 项数据不足待采集）"
    else:
        readiness_note = f"{n_fail} 项未达标，建议整改后复评（{n_insuf} 项数据不足待采集）"
    report["summary"] = {
        "total": len(ROBOT_READY_CHECKS), "pass": n_pass, "fail": n_fail,
        "insufficient_data": n_insuf, "readiness_note": readiness_note,
    }
    return report


async def export_spatial_semantics(db: AsyncSession, project_id: str) -> dict:
    """空间语义 JSON 导出（schema v0.1 先行定义）。

    导出户型/房间语义 + 机器人友好评估结果 + gaps 诚实标注（缺失维度）。
    供具身智能数据对接（尚品宅配×启元 Robot-Ready 生态同赛道差异化卡位）。
    """
    from app.models.floorplan import FloorPlan
    from app.models.project import Room, Floor, Project

    _bj_tz = timezone(__import__("datetime").timedelta(hours=8), name="Asia/Shanghai")
    project = (await db.execute(select(Project).where(Project.id == project_id))).scalars().first()
    floorplans = (
        await db.execute(
            select(FloorPlan).where(FloorPlan.project_id == project_id).order_by(FloorPlan.updated_at.desc())
        )
    ).scalars().all()
    floors = (await db.execute(select(Floor).where(Floor.project_id == project_id))).scalars().all()
    floor_ids = [f.id for f in floors] + [f.id for f in floorplans]
    rooms = (
        list((await db.execute(select(Room).where(Room.floor_id.in_(floor_ids)))).scalars().all())
        if floor_ids else []
    )

    robot = await assess_robot_ready(db, project_id)

    gaps: list[str] = []
    if not floorplans:
        gaps.append("floorplans：无户型方案数据")
    if not rooms:
        gaps.append("rooms：无房间级语义数据（面积/宽度/高度）")
    gaps.append("door_width/threshold_free/outlet_height_ok/floor_continuity 等机器人友好字段"
                "未在空间语义中（v0.1 schema 预留，待交付 QA 采集）")

    return {
        "schema_version": SPATIAL_SCHEMA_VERSION,
        "project_id": project_id,
        "generated_at": datetime.now(_bj_tz).isoformat(),
        "project": {
            "name": project.name if project else None,
            "total_area": getattr(project, "total_area", None) if project else None,
        },
        "floorplans": [
            {
                "id": fp.id, "name": fp.name, "total_area": fp.total_area,
                "wall_height": fp.wall_height, "room_count": fp.room_count,
                "is_active": fp.is_active,
            }
            for fp in floorplans
        ],
        "rooms": [
            {
                "id": r.id, "name": r.name, "room_type": r.room_type,
                "area": r.area, "width": r.width, "length": r.length, "height": r.height,
            }
            for r in rooms
        ],
        "robot_ready": robot["summary"],
        "gaps": gaps,
        "note": "spatial-semantics/0.1 为平台先行定义的导出格式（行业标准尚未统一）；"
                "数据缺口已逐项诚实标注，未伪造任何实测值",
    }


# ── v1.15.8 P2-4：交付 QA 机器人友好字段采集 ──

# 采集允许字段：ROBOT_READY_CHECKS 定义的可判定字段 + QA 元信息
CHECKLIST_ALLOWED_FIELDS = {c["field"] for c in ROBOT_READY_CHECKS} | {
    "note", "collected_at", "created_by",
}


def _latest_floorplan_query():
    """按 is_active 优先 + 最近更新排序取项目最新户型方案。"""
    from app.models.floorplan import FloorPlan

    return (
        select(FloorPlan)
        .order_by(FloorPlan.is_active.desc(), FloorPlan.updated_at.desc())
        .limit(1)
    )


async def save_robot_ready_checklist(
    db: AsyncSession, project_id: str, fields: dict, created_by: str,
) -> dict:
    """保存施工 QA 机器人友好字段采集（v1.15.8 P2-4，存入 floorplans.data.robot_ready）。

    只接受 CHECKLIST_ALLOWED_FIELDS 白名单字段，写入项目最新户型方案的
    data.robot_ready 嵌套 JSON——assess_robot_ready 的 _load_floorplan_semantics
    自动消费（采集闭环：QA 巡检 → 落库 → 评估可判定）。

    Returns:
        {"saved": bool, "project_id", "fields", "source", "error"?}
    """
    from app.models.floorplan import FloorPlan

    fp = (
        await db.execute(_latest_floorplan_query().where(FloorPlan.project_id == project_id))
    ).scalars().first()
    if not fp:
        return {
            "saved": False,
            "project_id": project_id,
            "error": "项目无户型方案（floorplan），无法存储机器人友好字段——请先创建户型",
        }

    try:
        data = json.loads(fp.data) if fp.data else {}
        if not isinstance(data, dict):
            data = {}
    except json.JSONDecodeError:
        data = {}

    robot: dict = dict(data.get("robot_ready") or {})
    for k, v in fields.items():
        if k in CHECKLIST_ALLOWED_FIELDS and v is not None:
            robot[k] = v
    robot["collected_at"] = datetime.now(timezone.utc).isoformat()
    robot["created_by"] = created_by
    data["robot_ready"] = robot
    fp.data = json.dumps(data, ensure_ascii=False)
    await db.commit()
    return {
        "saved": True,
        "project_id": project_id,
        "fields": robot,
        "source": "floorplans.data.robot_ready",
    }


async def get_robot_ready_checklist(db: AsyncSession, project_id: str) -> dict:
    """读取项目已采集的机器人友好字段（未采集字段为 null，诚实标注）。"""
    from app.models.floorplan import FloorPlan

    fp = (
        await db.execute(_latest_floorplan_query().where(FloorPlan.project_id == project_id))
    ).scalars().first()
    if not fp:
        return {
            "collected": False,
            "project_id": project_id,
            "fields": {c["field"]: None for c in ROBOT_READY_CHECKS},
            "note": "项目无户型方案，未采集任何字段",
        }
    semantics = _load_floorplan_semantics(fp)
    fields = {c["field"]: semantics.get(c["field"]) for c in ROBOT_READY_CHECKS}
    return {
        "collected": any(v is not None for v in fields.values()),
        "project_id": project_id,
        "fields": fields,
        "source": "floorplans.data.robot_ready",
        "note": "未采集字段为 null（诚实标注，不伪造实测值）",
    }

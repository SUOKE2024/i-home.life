"""公开内容新鲜度（「长草」）监测（v1.18.0）

借鉴来源：数智前线《万小智，让AI从网站生成走向企业经营》（2026-09-24）——
「一忙起来内容就有点顾不上，网站很容易长草」；Ahrefs 对 7.5 万个品牌的研究显示
品牌全网被提及度与 AI 可见度相关性约为外链的三倍，「内容停下来，企业就会在不断
膨胀的信息里被慢慢稀释」。

因此本模块按**确定性时间衰减**（半衰期口径复用 `memory_decay_half_life_days`
的同一参数，不另造一套）给出「哪些对外内容该更新了」的清单与优先级。

诚实红线：
- 陈旧度是对**平台内记录更新时间**（`updated_at`）的确定性衰减计算，
  是「对外内容是否需要更新」的**代理指标**，不等于对外页面实际发布状态
  （平台无对外内容发布记录表，故不声称已发布/未发布）。
- 只出**待更新清单**，不代写内容：更新对外表述涉及企业事实与品牌承诺，
  与 `remediation_plan_service` 的 human_only 同纪律，AI 不得自动改写。
- 无数据的类型记 `insufficient_data` 并如实标注，**不因无数据判为不合格**。
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

MODULE_PATH = "app/services/content_freshness_service.py"

METHOD = "deterministic_exponential_decay_on_updated_at"

# 衰减阈值：新鲜度 = 0.5 ** (年龄天数 / 半衰期)
FRESH_THRESHOLD = 0.5    # ≥ 0.5 视为新鲜
AGING_THRESHOLD = 0.25   # [0.25, 0.5) 视为老化；< 0.25 视为陈旧（「长草」）

# 监测对象（类型 → 高价值权重，用于优先级排序；权重为确定性常量，非 AI 判断）
SOURCE_TYPES: tuple[dict, ...] = (
    {"key": "projects", "name": "项目（案例/交付记录）", "priority_weight": 3,
     "note": "项目记录更新滞后会直接影响对外案例的可引用性"},
    {"key": "space_assets", "name": "空间资产台账（运营状态）", "priority_weight": 3,
     "note": "资产运营状态不更新，对外呈现的「在运营」事实即失真"},
    {"key": "products", "name": "已发布产品/服务", "priority_weight": 2,
     "note": "仅统计 status=published 的产品（草稿与归档不计入对外内容）"},
)

_PRIORITY_BY_STATE = {"stale": "high", "aging": "medium", "fresh": "low"}

DISCLAIMER = (
    "本清单为内容维护提示（确定性时间衰减计算），**不代表对外页面已发布或已过期**；"
    "平台只提示更新，不代写、不自动改写任何对外表述（涉及企业事实与品牌承诺）。"
)

LIMITATIONS = [
    "陈旧度以平台内记录 updated_at 为代理指标，非对外内容实际发布时间",
    "未接入对外内容发布记录表，因此不声称某条内容「已发布」或「已下线」",
    "只出清单不代写：对外表述更新须由经营者本人确认（human_only 同纪律）",
    "无数据的类型如实记 insufficient_data，不因无数据判为不合格",
]


def _now() -> datetime:
    from datetime import timedelta, timezone
    return datetime.now(timezone(timedelta(hours=8), name="Asia/Shanghai"))


def decay_factor(age_days: float, half_life_days: float) -> float:
    """确定性指数衰减：0.5 ** (年龄 / 半衰期)。age=0 → 1.0；age=半衰期 → 0.5。"""
    if half_life_days <= 0:
        return 1.0
    return float(0.5 ** (max(0.0, age_days) / half_life_days))


def _state_for(freshness: float) -> str:
    if freshness >= FRESH_THRESHOLD:
        return "fresh"
    if freshness >= AGING_THRESHOLD:
        return "aging"
    return "stale"


async def _load_rows(db: AsyncSession, key: str, limit: int) -> list[tuple[str, str, datetime | None]]:
    """按类型加载 (id, name, updated_at)；仅取用于统计的必要字段。"""
    from app.models.product import Product
    from app.models.project import Project
    from app.models.space_asset import SpaceAsset

    if key == "projects":
        stmt = select(Project.id, Project.name, Project.updated_at).limit(limit)
    elif key == "space_assets":
        stmt = select(SpaceAsset.id, SpaceAsset.name, SpaceAsset.updated_at).limit(limit)
    elif key == "products":
        stmt = (
            select(Product.id, Product.name, Product.updated_at)
            .where(Product.status == "published", Product.deleted_at.is_(None))
            .limit(limit)
        )
    else:
        raise ValueError(f"未知内容类型：{key}")
    return [(r[0], r[1], r[2]) for r in (await db.execute(stmt)).all()]


async def compute_content_freshness(
    db: AsyncSession,
    half_life_days: float | None = None,
    now: datetime | None = None,
    limit: int = 500,
    top_stale: int = 5,
) -> dict:
    """计算对外内容的陈旧度清单（确定性，只读）。"""
    from app.config import get_settings

    settings = get_settings()
    half_life = float(half_life_days if half_life_days is not None else settings.memory_decay_half_life_days)
    now = now or _now()

    sources: list[dict] = []
    totals = {"total": 0, "fresh": 0, "aging": 0, "stale": 0}
    priority_items: list[dict] = []

    for spec in SOURCE_TYPES:
        rows = await _load_rows(db, spec["key"], limit)
        if not rows:
            sources.append({
                "key": spec["key"], "name": spec["name"], "table_note": spec["note"],
                "status": "insufficient_data",
                "note": "无数据可评估——如实标注，不据此判为内容不合格（非「全部新鲜」）",
                "total": 0, "fresh": 0, "aging": 0, "stale": 0,
                "oldest": None, "items": [],
            })
            continue

        entries = []
        for rid, name, updated in rows:
            age_days = None
            freshness = None
            if updated is not None:
                if updated.tzinfo is None:  # SQLite/PG 混合场景：naive 视为北京时间
                    updated = updated.replace(tzinfo=now.tzinfo)
                age_days = max(0.0, (now - updated).total_seconds() / 86400.0)
                freshness = decay_factor(age_days, half_life)
            entries.append({
                "id": rid, "name": name,
                "updated_at": updated.isoformat() if updated else None,
                "age_days": round(age_days, 1) if age_days is not None else None,
                "freshness": round(freshness, 3) if freshness is not None else None,
                "state": _state_for(freshness) if freshness is not None else "unknown",
            })

        counts = {"fresh": 0, "aging": 0, "stale": 0}
        for e in entries:
            if e["state"] in counts:
                counts[e["state"]] += 1
        unknown = sum(1 for e in entries if e["state"] == "unknown")

        # 优先级：陈旧 > 老化，同类内按类型权重 + 年龄倒序
        ranked = sorted(
            [e for e in entries if e["state"] in ("stale", "aging")],
            key=lambda e: (e["state"] != "stale", -spec["priority_weight"], -(e["age_days"] or 0)),
        )
        items = []
        for e in ranked[:top_stale]:
            items.append({
                "type": spec["key"],
                "id": e["id"],
                "name": e["name"],
                "updated_at": e["updated_at"],
                "age_days": e["age_days"],
                "freshness": e["freshness"],
                "state": e["state"],
                "priority": _PRIORITY_BY_STATE[e["state"]],
                "suggestion": "建议核实对外信息是否仍准确，如已变化则更新（平台不代写内容）",
            })
        priority_items.extend(items)

        oldest = max(entries, key=lambda e: e["age_days"] or -1) if entries else None
        sources.append({
            "key": spec["key"], "name": spec["name"], "table_note": spec["note"],
            "status": "ok",
            "note": "",
            "total": len(entries),
            "fresh": counts["fresh"], "aging": counts["aging"], "stale": counts["stale"],
            "unknown": unknown,
            "stale_ratio": round(counts["stale"] / len(entries), 3),
            "oldest": {k: oldest[k] for k in ("id", "name", "updated_at", "age_days", "freshness", "state")}
                      if oldest else None,
            "items": items,
        })
        totals["total"] += len(entries)
        totals["fresh"] += counts["fresh"]
        totals["aging"] += counts["aging"]
        totals["stale"] += counts["stale"]

    priority_items.sort(key=lambda i: (i["priority"] != "high", i["age_days"] is None, -(i["age_days"] or 0)))
    assessable = totals["fresh"] + totals["aging"] + totals["stale"]

    return {
        "generated_at": now.isoformat(),
        "module": MODULE_PATH,
        "method": METHOD,
        "half_life_days": half_life,
        "thresholds": {"fresh": FRESH_THRESHOLD, "aging": AGING_THRESHOLD},
        "sources": sources,
        "summary": {
            "total": totals["total"],
            "fresh": totals["fresh"],
            "aging": totals["aging"],
            "stale": totals["stale"],
            "stale_ratio": round(totals["stale"] / assessable, 3) if assessable else None,
            "assessable": assessable,
            "types_insufficient_data": [s["key"] for s in sources if s["status"] == "insufficient_data"],
        },
        "priority_items": priority_items[:10],
        "limitations": LIMITATIONS,
        "disclaimer": DISCLAIMER,
    }

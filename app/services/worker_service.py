"""F35 服务者匹配服务层 — 设计师/监理/预算师档案 + 多维评分"""

import json

from sqlalchemy import select, or_
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.service_worker import ServiceWorker, ServiceWorkerMatch


# ── 档案 CRUD ──

async def get_worker(db: AsyncSession, worker_id: str) -> ServiceWorker | None:
    result = await db.execute(select(ServiceWorker).where(ServiceWorker.id == worker_id))
    return result.scalar_one_or_none()


async def list_workers(
    db: AsyncSession,
    role: str | None = None,
    city: str | None = None,
    status_filter: str | None = None,
    limit: int = 50,
) -> list[ServiceWorker]:
    stmt = select(ServiceWorker)
    if role:
        stmt = stmt.where(ServiceWorker.role == role)
    if city:
        stmt = stmt.where(or_(ServiceWorker.city == city, ServiceWorker.city.is_(None)))
    if status_filter:
        stmt = stmt.where(ServiceWorker.status == status_filter)
    stmt = stmt.order_by(ServiceWorker.rating.desc()).limit(limit)
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def create_worker(db: AsyncSession, data: dict) -> ServiceWorker:
    # JSON 字段序列化
    for field in ("role_attributes", "certifications", "portfolio_urls"):
        val = data.pop(field, None)
        if val is not None and not isinstance(val, str):
            data[field] = json.dumps(val, ensure_ascii=False)
    worker = ServiceWorker(**data)
    db.add(worker)
    await db.commit()
    await db.refresh(worker)
    return worker


def parse_json_field(value: str | None, default):
    if not value:
        return default
    try:
        return json.loads(value)
    except Exception:
        return default


# ── 多维评分算法 ──

def _compute_designer_score(
    worker: ServiceWorker,
    city: str | None,
    district: str | None,
    required_styles: list[str],
    budget_hourly: int | None,
    min_experience: int,
) -> tuple[float, dict, str]:
    """设计师评分：风格 30 + 经验 20 + 评分 20 + 案例 10 + 价格 10 + 地域 10 = 100"""
    breakdown = {}
    reasons = []
    attrs = parse_json_field(worker.role_attributes, {})
    worker_styles = set(attrs.get("design_styles", []))
    portfolio_count = attrs.get("portfolio_count", worker.completed_projects)
    awards = attrs.get("awards", 0)

    # 1. 风格匹配（30 分）
    if required_styles:
        hit = len(worker_styles & set(required_styles))
        style_score = min(30, hit * 15)
        if hit == len(required_styles):
            reasons.append(f"风格完全匹配（{hit}/{len(required_styles)}）")
        elif hit > 0:
            reasons.append(f"风格部分匹配（{hit}/{len(required_styles)}）")
    else:
        style_score = 15
    breakdown["style"] = style_score

    # 2. 经验（20 分）
    if worker.years_of_experience >= 10:
        exp_score = 20
        reasons.append(f"资深设计师（{worker.years_of_experience} 年经验）")
    elif worker.years_of_experience >= 5:
        exp_score = 15
    elif worker.years_of_experience >= 3:
        exp_score = 10
    else:
        exp_score = 5
    breakdown["experience"] = exp_score

    # 3. 评分（20 分）
    rating_score = round((worker.rating / 5.0) * 20, 1)
    breakdown["rating"] = rating_score
    if worker.rating >= 4.5:
        reasons.append(f"高分设计师（{worker.rating}）")

    # 4. 案例数量（10 分）
    if portfolio_count >= 100:
        case_score = 10
    elif portfolio_count >= 50:
        case_score = 8
    elif portfolio_count >= 20:
        case_score = 6
    else:
        case_score = 3
    breakdown["portfolio"] = case_score
    if awards > 0:
        reasons.append(f"获奖设计师（{awards} 项）")

    # 5. 价格（10 分）
    if budget_hourly:
        if worker.hourly_rate <= budget_hourly:
            price_score = 10
            reasons.append(f"时薪 ¥{worker.hourly_rate} ≤ 预算 ¥{budget_hourly}")
        else:
            over = (worker.hourly_rate - budget_hourly) / budget_hourly
            price_score = max(0, int(10 * (1 - over)))
    else:
        price_score = 5
    breakdown["price"] = price_score

    # 6. 地域（10 分）
    if city and worker.city:
        if worker.city == city:
            loc_score = 7
            if district and worker.district == district:
                loc_score = 10
                reasons.append(f"同城同区（{city} {district}）")
            else:
                reasons.append(f"同城（{city}）")
        else:
            loc_score = 3
    else:
        loc_score = 5
    breakdown["location"] = loc_score

    total = sum(breakdown.values())
    total = round(min(100, total), 1)
    return total, breakdown, "；".join(reasons) if reasons else "综合匹配"


def _compute_supervisor_score(
    worker: ServiceWorker,
    city: str | None,
    district: str | None,
    required_phases: list[str],
    budget_daily: int | None,
    min_experience: int,
) -> tuple[float, dict, str]:
    """监理评分：阶段 30 + 资质 20 + 评分 20 + 经验 10 + 价格 10 + 地域 10 = 100"""
    breakdown = {}
    reasons = []
    attrs = parse_json_field(worker.role_attributes, {})
    worker_phases = set(attrs.get("phases", []))
    supervised_count = attrs.get("supervised_projects", worker.completed_projects)

    # 1. 阶段匹配（30 分）
    if required_phases:
        hit = len(worker_phases & set(required_phases))
        phase_score = min(30, hit * 15)
        if hit == len(required_phases):
            reasons.append(f"阶段全覆盖（{hit}/{len(required_phases)}）")
        elif hit > 0:
            reasons.append(f"阶段部分覆盖（{hit}/{len(required_phases)}）")
    else:
        phase_score = 15
    breakdown["phase"] = phase_score

    # 2. 资质（20 分）
    qual_map = {"A": 20, "B": 15, "C": 10, "D": 5}
    qual_score = qual_map.get(worker.qualification, 10)
    breakdown["qualification"] = qual_score
    if worker.qualification == "A":
        reasons.append("A级资质监理")
    cert = attrs.get("certificate")
    if cert:
        reasons.append(f"持证：{cert}")

    # 3. 评分（20 分）
    rating_score = round((worker.rating / 5.0) * 20, 1)
    breakdown["rating"] = rating_score

    # 4. 经验（10 分）
    if worker.years_of_experience >= 10:
        exp_score = 10
    elif worker.years_of_experience >= 5:
        exp_score = 7
    else:
        exp_score = 4
    breakdown["experience"] = exp_score
    if supervised_count >= 100:
        reasons.append(f"监理经验丰富（{supervised_count} 项目）")

    # 5. 价格（10 分）
    if budget_daily:
        if worker.daily_rate <= budget_daily:
            price_score = 10
        else:
            over = (worker.daily_rate - budget_daily) / budget_daily
            price_score = max(0, int(10 * (1 - over)))
    else:
        price_score = 5
    breakdown["price"] = price_score

    # 6. 地域（10 分）
    if city and worker.city:
        if worker.city == city:
            loc_score = 7
            if district and worker.district == district:
                loc_score = 10
        else:
            loc_score = 3
    else:
        loc_score = 5
    breakdown["location"] = loc_score

    total = sum(breakdown.values())
    total = round(min(100, total), 1)
    return total, breakdown, "；".join(reasons) if reasons else "综合匹配"


def _compute_estimator_score(
    worker: ServiceWorker,
    city: str | None,
    district: str | None,
    required_budget_types: list[str],
    budget_hourly: int | None,
    min_experience: int,
) -> tuple[float, dict, str]:
    """预算师评分：预算类型 30 + 准确率 25 + 评分 20 + 经验 10 + 价格 5 + 地域 10 = 100"""
    breakdown = {}
    reasons = []
    attrs = parse_json_field(worker.role_attributes, {})
    worker_types = set(attrs.get("budget_types", []))
    accuracy = attrs.get("accuracy_rate", 0.85)
    estimated_count = attrs.get("estimated_projects", worker.completed_projects)

    # 1. 预算类型匹配（30 分）
    if required_budget_types:
        hit = len(worker_types & set(required_budget_types))
        type_score = min(30, hit * 15)
        if hit == len(required_budget_types):
            reasons.append(f"预算类型全覆盖（{hit}/{len(required_budget_types)}）")
    else:
        type_score = 15
    breakdown["budget_type"] = type_score

    # 2. 准确率（25 分）
    acc_score = round(accuracy * 25, 1)
    breakdown["accuracy"] = acc_score
    if accuracy >= 0.95:
        reasons.append(f"高准确率（{accuracy*100:.1f}%）")

    # 3. 评分（20 分）
    rating_score = round((worker.rating / 5.0) * 20, 1)
    breakdown["rating"] = rating_score

    # 4. 经验（10 分）
    if worker.years_of_experience >= 8:
        exp_score = 10
    elif worker.years_of_experience >= 4:
        exp_score = 7
    else:
        exp_score = 4
    breakdown["experience"] = exp_score
    if estimated_count >= 100:
        reasons.append(f"预算经验丰富（{estimated_count} 项目）")

    # 5. 价格（5 分）
    if budget_hourly:
        if worker.hourly_rate <= budget_hourly:
            price_score = 5
        else:
            over = (worker.hourly_rate - budget_hourly) / budget_hourly
            price_score = max(0, int(5 * (1 - over)))
    else:
        price_score = 3
    breakdown["price"] = price_score

    # 6. 地域（10 分）
    if city and worker.city:
        if worker.city == city:
            loc_score = 7
            if district and worker.district == district:
                loc_score = 10
        else:
            loc_score = 3
    else:
        loc_score = 5
    breakdown["location"] = loc_score

    total = sum(breakdown.values())
    total = round(min(100, total), 1)
    return total, breakdown, "；".join(reasons) if reasons else "综合匹配"


# ── 匹配入口 ──

async def match_workers(
    db: AsyncSession,
    project_id: str,
    role: str,
    city: str | None = None,
    district: str | None = None,
    required_styles: list[str] | None = None,
    required_phases: list[str] | None = None,
    required_budget_types: list[str] | None = None,
    budget_hourly_rate_max: int | None = None,
    budget_daily_rate_max: int | None = None,
    min_rating: float = 0.0,
    min_experience: int = 0,
    top_n: int = 5,
) -> list[ServiceWorkerMatch]:
    """为项目匹配服务者（按角色选择评分算法）"""
    required_styles = required_styles or []
    required_phases = required_phases or []
    required_budget_types = required_budget_types or []

    # 候选筛选
    stmt = select(ServiceWorker).where(
        ServiceWorker.role == role,
        ServiceWorker.status != "offline",
        ServiceWorker.rating >= min_rating,
        ServiceWorker.years_of_experience >= min_experience,
    )
    if city:
        stmt = stmt.where(or_(ServiceWorker.city == city, ServiceWorker.city.is_(None)))
    workers = (await db.execute(stmt)).scalars().all()

    scored = []
    for worker in workers:
        if role == "designer":
            score, breakdown, rec = _compute_designer_score(
                worker, city, district, required_styles, budget_hourly_rate_max, min_experience
            )
        elif role == "supervisor":
            score, breakdown, rec = _compute_supervisor_score(
                worker, city, district, required_phases, budget_daily_rate_max, min_experience
            )
        else:  # estimator
            score, breakdown, rec = _compute_estimator_score(
                worker, city, district, required_budget_types, budget_hourly_rate_max, min_experience
            )
        scored.append((score, worker, breakdown, rec))

    scored.sort(key=lambda x: x[0], reverse=True)
    top = scored[:top_n]

    matches: list[ServiceWorkerMatch] = []
    for score, worker, breakdown, rec in top:
        m = ServiceWorkerMatch(
            project_id=project_id,
            worker_id=worker.id,
            role=role,
            match_score=score,
            score_breakdown=json.dumps(breakdown, ensure_ascii=False),
            recommendation=rec,
            status="pending",
        )
        db.add(m)
        matches.append(m)

    await db.commit()
    for m in matches:
        await db.refresh(m)
    return matches


async def get_project_worker_matches(
    db: AsyncSession,
    project_id: str,
    role: str | None = None,
) -> list[ServiceWorkerMatch]:
    stmt = (
        select(ServiceWorkerMatch)
        .where(ServiceWorkerMatch.project_id == project_id)
        .order_by(ServiceWorkerMatch.match_score.desc())
    )
    if role:
        stmt = stmt.where(ServiceWorkerMatch.role == role)
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def update_worker_match_status(
    db: AsyncSession, match_id: str, status: str
) -> ServiceWorkerMatch | None:
    result = await db.execute(select(ServiceWorkerMatch).where(ServiceWorkerMatch.id == match_id))
    match = result.scalar_one_or_none()
    if not match:
        return None
    match.status = status
    await db.commit()
    await db.refresh(match)
    return match

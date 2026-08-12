"""工程队服务 — F36 档案 CRUD + 智能匹配"""

import json
from datetime import datetime, timezone

from sqlalchemy import select, or_
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.construction_crew import ConstructionCrew, CrewMatch


# ── 匹配状态机 ──
# pending    → shortlisted (入围) | rejected (拒绝)
# shortlisted → hired (雇佣) | rejected (拒绝)
# hired      → 终态，不可再变
# rejected   → 终态，不可再变
MATCH_TRANSITIONS: dict[str, set[str]] = {
    "pending": {"shortlisted", "rejected"},
    "shortlisted": {"hired", "rejected"},
    "hired": set(),
    "rejected": set(),
}


class CrewMatchStateError(Exception):
    """工程队匹配状态机校验失败"""

    def __init__(self, current_status: str, action: str, allowed: set[str]):
        self.current_status = current_status
        self.action = action
        self.allowed = allowed
        super().__init__(
            f"匹配状态「{current_status}」不支持操作「{action}」，"
            f"允许的目标状态: {sorted(allowed) or '无（终态）'}"
        )


# ── 入驻审核状态机（F36）──
# pending（新入驻/提交审核）→ approved（通过）| rejected（驳回）
# rejected → pending（重新提交审核）
# approved → 终态
CREW_REVIEW_SUBMITTABLE = {"pending", "rejected"}
REVIEW_REQUIRED_FIELDS: dict[str, str] = {
    "license_no": "营业执照号(license_no)",
    "license_type": "执照类型(license_type)",
    "insurance_no": "保险单号(insurance_no)",
}


class CrewReviewError(Exception):
    """工程队入驻审核流程错误（缺材料 / 非法状态迁移）"""

    def __init__(self, message: str):
        self.message = message
        super().__init__(message)


def _assert_match_transition(match: CrewMatch, action: str, target: str) -> None:
    """校验匹配状态机"""
    allowed = MATCH_TRANSITIONS.get(match.status, set())
    if target not in allowed:
        raise CrewMatchStateError(match.status, action, allowed)


async def get_crew(db: AsyncSession, crew_id: str) -> ConstructionCrew | None:
    result = await db.execute(
        select(ConstructionCrew).where(ConstructionCrew.id == crew_id)
    )
    return result.scalar_one_or_none()


async def list_crews(
    db: AsyncSession,
    city: str | None = None,
    status: str | None = None,
    limit: int = 50,
) -> list[ConstructionCrew]:
    stmt = select(ConstructionCrew)
    if city:
        stmt = stmt.where(ConstructionCrew.city == city)
    if status:
        stmt = stmt.where(ConstructionCrew.status == status)
    stmt = stmt.order_by(ConstructionCrew.rating.desc()).limit(limit)
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def create_crew(db: AsyncSession, data: dict) -> ConstructionCrew:
    specialties = data.pop("specialties", [])
    data["specialties"] = json.dumps(specialties, ensure_ascii=False)
    crew = ConstructionCrew(**data)
    # F36：新入驻工程队一律先进入待审核（pending），审核通过前不可被匹配
    crew.review_status = "pending"
    db.add(crew)
    await db.commit()
    await db.refresh(crew)
    return crew


async def update_crew(db: AsyncSession, crew_id: str, data: dict) -> ConstructionCrew | None:
    """更新工程队元数据（设计 4.3：管理员绑定作品集代表作全景等）。

    返回 None 表示工程队不存在。
    """
    crew = await get_crew(db, crew_id)
    if not crew:
        return None
    for key, value in data.items():
        setattr(crew, key, value)
    await db.commit()
    await db.refresh(crew)
    return crew


async def submit_crew_review(
    db: AsyncSession,
    crew_id: str,
    materials: dict | None = None,
) -> ConstructionCrew | None:
    """提交入驻审核：补齐/校验执照与保险材料，进入 pending 待管理员审核。

    - 缺必填材料（license_no/license_type/insurance_no）抛 CrewReviewError
    - rejected → 重新提交回 pending；approved 为终态不可再提交
    """
    crew = await get_crew(db, crew_id)
    if not crew:
        return None
    if crew.review_status == "approved":
        raise CrewReviewError("工程队已审核通过，无需重复提交审核")

    for field, value in (materials or {}).items():
        if value is not None:
            setattr(crew, field, value)

    missing = [
        label for field, label in REVIEW_REQUIRED_FIELDS.items()
        if not (getattr(crew, field) or "").strip()
    ]
    if missing:
        raise CrewReviewError("缺少必填审核材料: " + "、".join(missing))

    if crew.review_status == "rejected":
        # 驳回后重新提交，进入新一轮审核
        crew.review_status = "pending"
        crew.reviewed_at = None
    await db.commit()
    await db.refresh(crew)
    return crew


async def review_crew(
    db: AsyncSession,
    crew_id: str,
    action: str,
    note: str | None = None,
) -> ConstructionCrew | None:
    """管理员审核入驻：approve → approved；reject → rejected（仅 pending 可审核）"""
    crew = await get_crew(db, crew_id)
    if not crew:
        return None
    if crew.review_status != "pending":
        raise CrewReviewError(
            f"工程队当前状态「{crew.review_status}」不可审核，仅 pending 待审核状态可操作"
        )
    if action not in ("approve", "reject"):
        raise CrewReviewError(f"非法审核操作「{action}」，仅支持 approve / reject")
    crew.review_status = "approved" if action == "approve" else "rejected"
    crew.review_note = note
    crew.reviewed_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(crew)
    return crew


def _parse_specialties(crew: ConstructionCrew) -> list[str]:
    try:
        return json.loads(crew.specialties or "[]")
    except Exception:
        return []


def _compute_match_score(
    crew: ConstructionCrew,
    city: str | None,
    district: str | None,
    required_specialties: list[str],
    budget_max: int | None,
    expected_duration: int | None,
) -> tuple[float, dict, str]:
    """计算匹配评分（0-100）

    评分维度：
    - 地域匹配（20 分）：同城 20 / 同区 25（满分上限 25）
    - 专长匹配（30 分）：每命中 1 项 +10，上限 30
    - 评分权重（20 分）：rating/5 × 20
    - 资质权重（10 分）：A=10 / B=7 / C=4 / D=2
    - 价格匹配（10 分）：在预算内 10，超出按比例递减
    - 工期匹配（5 分）：工期 ≤ 期望 5，超出递减
    """
    breakdown = {}
    reasons = []

    # 1. 地域
    location_score = 0
    if city and crew.city:
        if crew.city == city:
            location_score = 20
            if district and crew.district == district:
                location_score = 25
                reasons.append(f"同城同区（{city} {district}）")
            else:
                reasons.append(f"同城（{city}）")
        else:
            location_score = 5
    elif not city:
        location_score = 10  # 未指定地域
    breakdown["location"] = location_score

    # 2. 专长
    crew_specialties = set(_parse_specialties(crew))
    if required_specialties:
        hit = len(crew_specialties & set(required_specialties))
        specialty_score = min(30, hit * 10)
        if hit == len(required_specialties):
            reasons.append(f"专长完全匹配（{hit}/{len(required_specialties)}）")
        elif hit > 0:
            reasons.append(f"专长部分匹配（{hit}/{len(required_specialties)}）")
    else:
        specialty_score = 15  # 未要求专长
    breakdown["specialty"] = specialty_score

    # 3. 评分
    rating_score = (crew.rating / 5.0) * 20
    breakdown["rating"] = round(rating_score, 1)
    if crew.rating >= 4.5:
        reasons.append(f"高分工程队（{crew.rating}）")

    # 4. 资质
    qual_map = {"A": 10, "B": 7, "C": 4, "D": 2}
    qualification_score = qual_map.get(crew.qualification, 4)
    breakdown["qualification"] = qualification_score
    if crew.qualification == "A":
        reasons.append("A级资质")

    # 5. 价格
    if budget_max:
        if crew.daily_rate <= budget_max:
            price_score = 10
            reasons.append(f"日单价 ¥{crew.daily_rate} ≤ 预算 ¥{budget_max}")
        else:
            over_ratio = (crew.daily_rate - budget_max) / budget_max
            price_score = max(0, int(10 * (1 - over_ratio)))
    else:
        price_score = 5
    breakdown["price"] = price_score

    # 6. 工期
    if expected_duration:
        if crew.avg_duration <= expected_duration:
            duration_score = 5
        else:
            over_days = crew.avg_duration - expected_duration
            duration_score = max(0, 5 - int(over_days / 10))
    else:
        duration_score = 3
    breakdown["duration"] = duration_score

    total = (
        location_score + specialty_score + rating_score
        + qualification_score + price_score + duration_score
    )
    total = round(min(100, total), 1)
    recommendation = "；".join(reasons) if reasons else "综合匹配"
    return total, breakdown, recommendation


async def match_crews(
    db: AsyncSession,
    project_id: str,
    city: str | None = None,
    district: str | None = None,
    required_specialties: list[str] | None = None,
    budget_daily_rate_max: int | None = None,
    expected_duration_days: int | None = None,
    top_n: int = 5,
) -> list[CrewMatch]:
    """为项目匹配工程队"""
    required_specialties = required_specialties or []

    # 候选筛选：仅审核通过（approved）且状态非 offline 的工程队 + 地域过滤
    # F36：审核通过前工程队不得出现在匹配结果中
    stmt = select(ConstructionCrew).where(
        ConstructionCrew.review_status == "approved",
        ConstructionCrew.status != "offline",
    )
    if city:
        stmt = stmt.where(
            or_(ConstructionCrew.city == city, ConstructionCrew.city.is_(None))
        )
    crews = (await db.execute(stmt)).scalars().all()

    scored: list[tuple[float, ConstructionCrew, dict, str]] = []
    for crew in crews:
        score, breakdown, rec = _compute_match_score(
            crew, city, district, required_specialties,
            budget_daily_rate_max, expected_duration_days,
        )
        scored.append((score, crew, breakdown, rec))

    scored.sort(key=lambda x: x[0], reverse=True)
    top = scored[:top_n]

    matches: list[CrewMatch] = []
    for score, crew, breakdown, rec in top:
        m = CrewMatch(
            project_id=project_id,
            crew_id=crew.id,
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


async def get_project_matches(db: AsyncSession, project_id: str) -> list[CrewMatch]:
    result = await db.execute(
        select(CrewMatch)
        .where(CrewMatch.project_id == project_id)
        .order_by(CrewMatch.match_score.desc())
    )
    return list(result.scalars().all())


async def update_match_status(
    db: AsyncSession, match_id: str, status: str
) -> CrewMatch | None:
    result = await db.execute(
        select(CrewMatch).where(CrewMatch.id == match_id)
    )
    match = result.scalar_one_or_none()
    if not match:
        return None
    _assert_match_transition(match, "update_status", status)
    match.status = status
    await db.commit()
    await db.refresh(match)
    return match

"""站点 AI 可见度与阵地经营 API（v1.18.0）

借鉴来源：数智前线《万小智，让AI从网站生成走向企业经营》（2026-09-24）——
「AI 让网站生成变得非常容易，但围绕企业自有阵地的长期经营，仍缺解法」
「网站生成完成不是 AI 工作的终点，正在成为企业经营的起点」。

三个路由（均需 PASETO 鉴权 + 平台管理员权限）：
- GET  /api/ai-visibility                    站点 AI 可见度就绪度审计（P0）
- POST /api/remediation-plans                生成修复清单（P1，落库留痕）
- GET  /api/remediation-plans                清单列表
- GET  /api/remediation-plans/{plan_id}      清单详情
- POST /api/remediation-plans/{id}/apply     执行白名单条目（须 confirm=True）
- POST /api/remediation-plans/{id}/verify    复检（重新审计，确定性比对）
- POST /api/remediation-plans/{id}/rollback  回滚（按备份还原）
- GET  /api/content-freshness                公开内容陈旧度（「长草」）清单（P2）

诚实红线：审计为静态产物确定性检查，**不调用任何 AI 平台、不承诺引用或排名效果**；
修复只碰「说明书层」白名单动作，涉及企业事实/品牌承诺的条目一律只出清单不代做。
"""

from copy import deepcopy
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.database import get_db
from app.models.user import User
from app.rbac import require_platform_manage
from app.services import ai_visibility_service as avs
from app.services import content_freshness_service as cfs
from app.services import remediation_plan_service as rps

router = APIRouter(prefix="/ai-visibility", tags=["站点 AI 可见度（GEO）"])
remediation_router = APIRouter(prefix="/remediation-plans", tags=["站点修复清单"])
freshness_router = APIRouter(prefix="/content-freshness", tags=["公开内容新鲜度"])

settings = get_settings()


class PlanApplyRequest(BaseModel):
    """执行请求：必须显式确认（平台不自动改动站点产物）。"""

    item_ids: list[str] = Field(default_factory=list, description="要执行的条目；留空 = 执行全部白名单条目")
    confirm: bool = Field(default=False, description="须为 True，表示已逐条确认")


def _require_audit() -> None:
    if not settings.ai_visibility_audit_enabled:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="站点 AI 可见度审计未启用（ai_visibility_audit_enabled=False）",
        )


def _require_remediation() -> None:
    if not settings.remediation_plan_enabled:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="站点修复清单未启用（remediation_plan_enabled=False）",
        )


def _require_freshness() -> None:
    if not settings.content_freshness_monitor_enabled:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="内容新鲜度监测未启用（content_freshness_monitor_enabled=False）",
        )


# ════════════════════════════════════════════════════════════════
# P0 站点 AI 可见度审计
# ════════════════════════════════════════════════════════════════


@router.get("")
async def get_ai_visibility(
    static_root: str | None = Query(default=None, description="可选：指定站点静态产物目录（默认自动定位）"),
    current_user: User = Depends(require_platform_manage),
):
    """站点 AI 可见度就绪度审计（确定性静态检查，不做模型探测）。"""
    _require_audit()
    return avs.run_ai_visibility_audit(static_root=static_root)


# ════════════════════════════════════════════════════════════════
# P1 修复清单闭环
# ════════════════════════════════════════════════════════════════


@remediation_router.post("", status_code=status.HTTP_201_CREATED)
async def create_remediation_plan(
    current_user: User = Depends(require_platform_manage),
    db: AsyncSession = Depends(get_db),
):
    """按当前审计结果生成修复清单并落库（不执行任何改动）。"""
    _require_audit()
    _require_remediation()
    plan = rps.build_plan()
    record = await rps.create_plan(db, plan, created_by=current_user.id)
    return rps.plan_as_dict(record)


@remediation_router.get("")
async def list_remediation_plans(
    plan_status: str | None = Query(default=None, description="按状态过滤"),
    limit: int = Query(default=20, ge=1, le=100),
    current_user: User = Depends(require_platform_manage),
    db: AsyncSession = Depends(get_db),
):
    _require_remediation()
    records = await rps.list_plans(db, limit=limit, status=plan_status)
    return {"items": [rps.plan_as_dict(r) for r in records], "count": len(records)}


@remediation_router.get("/{plan_id}")
async def get_remediation_plan(
    plan_id: str,
    current_user: User = Depends(require_platform_manage),
    db: AsyncSession = Depends(get_db),
):
    _require_remediation()
    record = await rps.get_plan(db, plan_id)
    if not record:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="修复清单不存在")
    return rps.plan_as_dict(record)


@remediation_router.post("/{plan_id}/apply")
async def apply_remediation_plan(
    plan_id: str,
    payload: PlanApplyRequest,
    current_user: User = Depends(require_platform_manage),
    db: AsyncSession = Depends(get_db),
):
    """执行清单中的白名单条目（须 confirm=True；非白名单条目一律跳过并说明原因）。"""
    _require_audit()
    _require_remediation()
    record = await rps.get_plan(db, plan_id)
    if not record:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="修复清单不存在")
    if record.status == "rolled_back":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT,
                            detail="该清单已回滚，请重新生成后再执行")

    plan = {"items": deepcopy(record.items or []), "static_root": record.static_root}
    item_ids = payload.item_ids or [
        i["item_id"] for i in (record.items or []) if i.get("auto_executable")
    ]
    try:
        result = rps.apply_items(plan, item_ids, confirm=payload.confirm)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(e))

    record.items = plan["items"]
    record.backups = {**(record.backups or {}), **result["backups"]}
    record.status = "applied" if result["applied"] else record.status
    record.applied_at = datetime.now(timezone.utc) if result["applied"] else None
    await db.commit()
    await db.refresh(record)

    return {"plan_id": plan_id, "status": record.status, **result,
            "item_state": [{"item_id": i["item_id"], "state": i["state"],
                            "tier": i["tier"], "action": i["action"]} for i in plan["items"]]}


@remediation_router.post("/{plan_id}/verify")
async def verify_remediation_plan(
    plan_id: str,
    current_user: User = Depends(require_platform_manage),
    db: AsyncSession = Depends(get_db),
):
    """复检：重新跑审计，逐条比对源检查项是否已转 pass（执行 ≠ 生效）。"""
    _require_audit()
    _require_remediation()
    record = await rps.get_plan(db, plan_id)
    if not record:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="修复清单不存在")

    plan = {"items": deepcopy(record.items or []), "static_root": record.static_root}
    result = rps.verify_items(plan)
    record.items = plan["items"]
    verified_ids = {r["item_id"] for r in result["results"] if r["verified"]}
    record.status = "verified" if result["all_verified"] else (
        "partially_verified" if verified_ids else record.status
    )
    record.score_after = result["audit_after"]["score"]
    record.verified_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(record)
    return {"plan_id": plan_id, "status": record.status, **result}


@remediation_router.post("/{plan_id}/rollback")
async def rollback_remediation_plan(
    plan_id: str,
    current_user: User = Depends(require_platform_manage),
    db: AsyncSession = Depends(get_db),
):
    """按执行前备份还原站点产物（原文件不存在的新增文件则删除）。"""
    _require_remediation()
    record = await rps.get_plan(db, plan_id)
    if not record:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="修复清单不存在")
    if not record.backups:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="该清单无备份可回滚（未执行过）")

    result = rps.rollback_backups(record.backups)
    if result["success"]:
        plan = {"items": deepcopy(record.items or [])}
        for item in plan["items"]:
            if item.get("state") == "executed":
                item["state"] = "rolled_back"
        record.items = plan["items"]
        record.status = "rolled_back"
        record.rolled_back_at = datetime.now(timezone.utc)
        await db.commit()
        await db.refresh(record)
    return {"plan_id": plan_id, "status": record.status, **result}


# ════════════════════════════════════════════════════════════════
# P2 公开内容新鲜度（「长草」）监测
# ════════════════════════════════════════════════════════════════


@freshness_router.get("")
async def get_content_freshness(
    half_life_days: float | None = Query(default=None, gt=0, le=3650,
                                         description="半衰期天数（默认取 memory_decay_half_life_days）"),
    top_stale: int = Query(default=5, ge=1, le=20, description="每类返回的待更新条数"),
    current_user: User = Depends(require_platform_manage),
    db: AsyncSession = Depends(get_db),
):
    """公开内容陈旧度清单（只出清单不代写内容）。"""
    _require_freshness()
    return await cfs.compute_content_freshness(db, half_life_days=half_life_days, top_stale=top_stale)

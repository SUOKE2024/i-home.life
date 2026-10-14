"""站点修复清单闭环（v1.18.0）——诊断 → 清单 → 确认 → 执行 → 复检 → 回滚

借鉴来源：数智前线《万小智，让AI从网站生成走向企业经营》（2026-09-24）。
文中两个关键判断被本模块直接落为工程约束：

1. **「诊断完成，并不意味着问题得到解决」**——一份几十项的检查报告，若止步于清单，
   经营者看不懂、也推动不了修改。因此本模块把 `ai_visibility_service` 的审计结果
   转成**可执行的修复清单**，并对白名单动作提供「执行 → 复检 → 回滚」闭环。
2. **「判断 AI 该不该自动做一件事，不只看它能不能做，还要看做错以后用户能不能
   发现、能不能改回来」**——据此做三级自动化边界（见 `classify_tier`）：
   - `auto`：可逆 + 不改企业事实 + 执行后可确定性复检（白名单：生成 llms.txt、
     追加 robots.txt AI 爬虫声明块）；
   - `confirm`：可逆但不涉事实的站点配置类改动，须人工逐条确认（本版本不自动执行）；
   - `human_only`：涉及**企业事实、品牌承诺、发布权限、经营决策**，平台只出清单，
     不得代写代改（AI 不得编造服务范围、案例、资质、联系方式）。

边界（硬约束，勿放宽）：
- 只写**仓库内站点静态产物**（`webapp/**`），路径经 resolve 校验，拒绝越界写；
- 只碰「说明书层」（新增文件 / 追加声明块），**不改既有内容**、不动应用代码与后端；
- 执行前把原始内容全文备份入 `remediation_plans.backups`，`rollback` 逐条还原
  （原文件不存在的新增文件则删除）；
- 每条动作执行后由 `verify` 重新跑审计做**确定性复检**，不凭执行成功即认为修复生效；
- 第三方站点一律只诊断不改（本项目无第三方站点写入路径）。
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.services import ai_visibility_service as avs

PROJECT_ROOT = Path(__file__).resolve().parents[2]
MODULE_PATH = "app/services/remediation_plan_service.py"

PLAN_TYPE = "site_ai_visibility"

# 允许写入的仓库内根目录（拒绝越界写，含符号链接逃逸由 resolve 兜底）
ALLOWED_WRITE_ROOTS: tuple[str, ...] = ("webapp",)

BOUNDARIES: list[str] = [
    "只写仓库内 webapp/ 下的站点静态产物，拒绝任何越界路径",
    "只做「说明书层」动作（新增 llms.txt / 追加 robots.txt AI 爬虫声明块），不改既有内容",
    "涉及企业事实、品牌承诺、发布权限、经营决策的条目一律 human_only，平台只出清单不代写",
    "执行前全文备份，可一键回滚（新增文件回滚即删除）",
    "执行后须复检（重新审计确认该项转为 pass），不以执行成功代替修复生效",
]

HUMAN_ONLY_NOTE = (
    "该条目涉及企业事实 / 品牌承诺 / 发布权限，须由经营者本人确认与撰写；"
    "AI 不得代写服务范围、案例、资质与联系方式（此前已按该纪律约束 growth 类 Agent）。"
)


def _now_iso() -> str:
    return datetime.now(timezone(timedelta(hours=8), name="Asia/Shanghai")).isoformat()


def classify_tier(action: str | None, reversible: bool, changes_facts: bool) -> str:
    """三级自动化边界（确定性规则，无 LLM）。

    auto      → 白名单动作 + 可逆 + 不改事实
    human_only→ 不可逆，或改动企业事实/品牌承诺
    confirm   → 其余（可逆的站点配置类改动，须人工逐条确认）
    """
    if changes_facts or not reversible:
        return "human_only"
    if action in avs.AUTO_REMEDIATION_ACTIONS:
        return "auto"
    return "confirm"


def build_plan(audit: dict | None = None) -> dict:
    """把审计结果转成修复清单（不落库、不写文件，纯计算）。"""
    audit = audit or avs.run_ai_visibility_audit()
    items: list[dict] = []

    for idx, cand in enumerate(audit["remediation_candidates"], start=1):
        action = cand.get("action")
        tier = cand["tier"]
        if tier == "human_only":
            rationale = cand["rationale"] if "human" in cand["rationale"] else HUMAN_ONLY_NOTE
        else:
            rationale = cand["rationale"]
        auto_executable = tier == "auto" and action in avs.AUTO_REMEDIATION_ACTIONS
        items.append({
            "item_id": f"R{idx:02d}",
            "source_check_id": cand["source_check_id"],
            "title": cand["title"],
            "dimension": cand["dimension"],
            "current_status": cand["status"],
            "tier": tier,
            "action": action,
            "auto_executable": auto_executable,
            "reversible": tier != "human_only",
            "rationale": rationale,
            "evidence": cand["evidence"],
            "state": "proposed",
            "verified": None,
        })

    auto_items = [i for i in items if i["auto_executable"]]
    return {
        "generated_at": _now_iso(),
        "module": MODULE_PATH,
        "plan_type": PLAN_TYPE,
        "static_root": audit["static_root"],
        "source_audit": {
            "score": audit["score"],
            "level": audit["level"],
            "level_name": audit["level_name"],
            "static_root": audit["static_root"],
            "generated_at": audit["generated_at"],
        },
        "items": items,
        "auto_executable_items": [i["item_id"] for i in auto_items],
        "summary": {
            "item_count": len(items),
            "auto": sum(1 for i in items if i["tier"] == "auto"),
            "confirm": sum(1 for i in items if i["tier"] == "confirm"),
            "human_only": sum(1 for i in items if i["tier"] == "human_only"),
            "auto_executable": len(auto_items),
        },
        "boundaries": BOUNDARIES,
        "requires_confirmation": True,
        "confirm_note": "平台不会自动执行任何条目：须显式 confirm=True 逐条确认后才会动作。",
    }


# ════════════════════════════════════════════════════════════════
# 白名单动作实现（只碰「说明书层」）
# ════════════════════════════════════════════════════════════════


def _rel(path: Path) -> str:
    """相对仓库根的展示路径（仓库外路径回退绝对路径，便于测试与复检）。"""
    try:
        return str(path.relative_to(PROJECT_ROOT))
    except ValueError:
        return str(path)


def _safe_target(path: Path, allowed_root: Path | None = None) -> Path:
    """校验写入路径位于允许根目录内（防越界写）。

    `allowed_root` 仅由服务层内部/测试显式传入；HTTP 路径永不传，故默认口径恒为
    「仓库内 webapp/」，用户可控的 static_root 无法把写入引到仓库外。
    """
    resolved = path.resolve()
    roots = [allowed_root.resolve()] if allowed_root else [
        (PROJECT_ROOT / r).resolve() for r in ALLOWED_WRITE_ROOTS
    ]
    for root_path in roots:
        if resolved == root_path or root_path in resolved.parents:
            return resolved
    raise ValueError(f"拒绝越界写入：{resolved}（允许根：{[str(r) for r in roots]}）")


def build_llms_txt_content(artifacts: dict | None = None) -> str:
    """由站点**既有公开元数据**确定性生成 llms.txt 内容（不编造事实）。"""
    import re

    art = artifacts or avs.resolve_artifacts()
    title, desc, org_name = "", "", ""
    if art["index_html"]:
        html = art["index_html"].read_text(encoding="utf-8")
        m = re.search(r"<title[^>]*>(.*?)</title>", html, re.S | re.I)
        title = m.group(1).strip() if m else ""
        m = re.search(r"""<meta[^>]+name=["']description["'][^>]*content=["'](.*?)["']""", html, re.S | re.I)
        desc = m.group(1).strip() if m else ""
        ld = avs.parse_jsonld(html)
        org = next((b for b in ld["blocks"]
                    if isinstance(b, dict) and b.get("@type") == "Organization"), None)
        if org and org.get("name"):
            org_name = str(org["name"])

    urls: list[dict] = []
    if art["sitemap"]:
        urls = avs.parse_sitemap(art["sitemap"].read_text(encoding="utf-8"))["urls"]

    lines = [f"# {org_name or title or 'i-home.life'}", ""]
    if desc:
        lines += [f"> {desc}", ""]
    if urls:
        lines += ["## 站点页面", ""]
        for u in urls:
            lines.append(f"- {u['loc']}" + (f"（最后更新：{u['lastmod']}）" if u["lastmod"] else ""))
        lines.append("")
    lines += [
        "## 说明",
        "",
        "本文件由索克家居平台按站点既有公开元数据自动生成，供 AI 检索系统了解站点结构；",
        "事实性内容以页面正文为准，本文件不新增、不推断任何业务声明。",
        "",
        f"生成器：{MODULE_PATH}（内容确定性生成：同一站点产物下重复执行不产生差异）",
    ]
    return "\n".join(lines) + "\n"


AI_AGENT_BLOCK_HEADER = "# ── AI 检索类爬虫策略（v1.18.0 生成，可回滚）──"


def _robots_ai_block(declared: list[str]) -> str:
    missing = [ua for ua in avs.AI_CRAWLERS if ua not in declared]
    lines = [AI_AGENT_BLOCK_HEADER]
    for ua in missing:
        lines += [f"User-agent: {ua}", "Allow: /", "Disallow: /api/"]
    return "\n".join(lines) + "\n"


def execute_action(
    action: str,
    audit: dict | None = None,
    artifacts: dict | None = None,
    allowed_root: Path | None = None,
) -> dict:
    """执行单个白名单动作，返回 {changed, target, backup, note}。

    调用方负责在事务中落库备份；本函数只做文件级确定性动作。
    `artifacts` / `allowed_root` 供复检与测试显式指定站点目录（HTTP 路径不传）。
    """
    audit = audit or avs.run_ai_visibility_audit()
    art = artifacts or avs.resolve_artifacts()

    if action == "write_llms_txt":
        if art["public_dir"] is None:
            raise ValueError("未定位到站点静态产物目录，无法生成 llms.txt")
        target = _safe_target(art["public_dir"] / "llms.txt", allowed_root)
        existed = target.exists()
        backup = target.read_text(encoding="utf-8") if existed else None
        content = build_llms_txt_content(art)
        if existed and backup == content:
            return {"changed": False, "target": _rel(target),
                    "backup": {"existed": True, "content": backup}, "note": "内容与现状一致，未改动"}
        target.write_text(content, encoding="utf-8")
        return {"changed": True, "target": _rel(target),
                "backup": {"existed": existed, "content": backup},
                "note": f"已写入 llms.txt（{len(content)} 字节）"}

    if action == "update_robots_ai_agents":
        if art["robots"] is None:
            raise ValueError("未找到 robots.txt，无法追加 AI 爬虫声明（不新建该文件，避免覆盖既有策略）")
        target = _safe_target(art["robots"], allowed_root)
        original = target.read_text(encoding="utf-8")
        declared = audit.get("robots", {}).get("declared", [])
        if AI_AGENT_BLOCK_HEADER in original:
            return {"changed": False, "target": _rel(target),
                    "backup": {"existed": True, "content": original}, "note": "已存在生成块，未重复追加"}
        content = original.rstrip("\n") + "\n\n" + _robots_ai_block(declared)
        target.write_text(content, encoding="utf-8")
        return {"changed": True, "target": _rel(target),
                "backup": {"existed": True, "content": original},
                "note": "已追加 AI 爬虫声明块（既有规则未改动）"}

    raise ValueError(f"动作不在白名单：{action}")


def apply_items(
    plan: dict,
    item_ids: list[str],
    confirm: bool,
    artifacts: dict | None = None,
    allowed_root: Path | None = None,
) -> dict:
    """执行清单中指定的白名单条目（须显式 confirm）。

    `artifacts` / `allowed_root` 供测试与显式站点目录场景传入；HTTP 路径不传，
    此时按清单记录的 static_root 定位站点产物，写入范围仍受 `_safe_target` 限制。
    """
    if not confirm:
        raise ValueError("须显式 confirm=True 确认后才可执行（平台不自动改动站点产物）")

    by_id = {i["item_id"]: i for i in plan["items"]}
    unknown = [i for i in item_ids if i not in by_id]
    if unknown:
        raise ValueError(f"清单中不存在条目：{unknown}")

    art = artifacts or avs.resolve_artifacts(plan.get("static_root") or None)
    applied, skipped, backups = [], [], {}
    for item_id in item_ids:
        item = by_id[item_id]
        if not item["auto_executable"]:
            skipped.append({"item_id": item_id, "reason": f"tier={item['tier']} 不属可自动执行白名单"})
            continue
        result = execute_action(item["action"], audit=avs.run_ai_visibility_audit(), artifacts=art,
                                allowed_root=allowed_root)
        backups[result["target"]] = result["backup"]
        item["state"] = "executed"
        item["execution"] = {"target": result["target"], "note": result["note"],
                             "changed": result["changed"], "executed_at": _now_iso()}
        applied.append({"item_id": item_id, "target": result["target"],
                        "changed": result["changed"], "note": result["note"]})

    return {"applied": applied, "skipped": skipped, "backups": backups,
            "verification_required": True,
            "verify_note": "执行 ≠ 生效：请调用复检（重新审计）确认对应检查项已转 pass。"}


def verify_items(plan: dict, item_ids: list[str] | None = None, only_executed: bool = True) -> dict:
    """复检：重新跑审计，逐条比对源检查项是否已转 pass（确定性，不猜）。

    默认只复检**已执行**的条目（未执行的条目本来就未达标，混入会让复检结果失去意义）；
    显式传 `item_ids` 或 `only_executed=False` 可指定/全量复检。
    """
    after = avs.run_ai_visibility_audit(static_root=plan.get("static_root") or None)
    status_by_check = {c["id"]: c["status"] for c in after["checks"]}
    if item_ids is not None:
        wanted = set(item_ids)
        targets = [i for i in plan["items"] if i["item_id"] in wanted]
    elif only_executed:
        targets = [i for i in plan["items"] if i.get("state") in ("executed", "verified")]
    else:
        targets = list(plan["items"])
    results = []
    for item in targets:
        status = status_by_check.get(item["source_check_id"])
        verified = status == "pass"
        item["verified"] = verified
        item["state"] = "verified" if verified else item["state"]
        results.append({
            "item_id": item["item_id"],
            "source_check_id": item["source_check_id"],
            "status_after": status,
            "verified": verified,
            "note": "该项已转为 pass" if verified else "该项仍未达标，需人工处理或重新评估",
        })
    return {"verified_at": _now_iso(), "audit_after": {"score": after["score"], "level": after["level"]},
            "results": results,
            "all_verified": all(r["verified"] for r in results) if results else False}


def rollback_backups(backups: dict, allowed_root: Path | None = None) -> dict:
    """按备份还原（原文件不存在的新增文件则删除）。"""
    restored, removed, failed = [], [], []
    for rel_target, bak in (backups or {}).items():
        try:
            path = _safe_target(PROJECT_ROOT / rel_target, allowed_root)
        except ValueError as e:
            failed.append({"target": rel_target, "error": str(e)})
            continue
        try:
            if bak.get("existed"):
                path.write_text(bak["content"] or "", encoding="utf-8")
                restored.append(rel_target)
            elif path.exists():
                path.unlink()
                removed.append(rel_target)
        except OSError as e:  # 诚实报错，不静默当成功
            failed.append({"target": rel_target, "error": str(e)})
    return {"restored": restored, "removed": removed, "failed": failed,
            "success": not failed}


# ════════════════════════════════════════════════════════════════
# 落库（remediation_plans）
# ════════════════════════════════════════════════════════════════


async def create_plan(db: AsyncSession, plan: dict, created_by: str) -> "object":
    from app.models.remediation_plan import RemediationPlan

    record = RemediationPlan(
        id=str(uuid.uuid4()),
        plan_type=plan["plan_type"],
        status="proposed",
        static_root=plan["source_audit"]["static_root"],
        score_before=plan["source_audit"]["score"],
        items=plan["items"],
        summary=plan["summary"],
        created_by=created_by,
    )
    db.add(record)
    await db.commit()
    await db.refresh(record)
    return record


async def get_plan(db: AsyncSession, plan_id: str):
    from app.models.remediation_plan import RemediationPlan

    return await db.get(RemediationPlan, plan_id)


async def list_plans(db: AsyncSession, limit: int = 20, status: str | None = None):
    from app.models.remediation_plan import RemediationPlan

    stmt = select(RemediationPlan).order_by(desc(RemediationPlan.created_at)).limit(limit)
    if status:
        stmt = stmt.where(RemediationPlan.status == status)
    return list((await db.execute(stmt)).scalars().all())


def plan_as_dict(record) -> dict:
    return {
        "id": record.id,
        "generated_at": record.created_at.isoformat() if record.created_at else None,
        "module": MODULE_PATH,
        "plan_type": record.plan_type,
        "status": record.status,
        "static_root": record.static_root,
        "score_before": record.score_before,
        "score_after": record.score_after,
        "items": record.items or [],
        "summary": record.summary or {},
        "applied_at": record.applied_at.isoformat() if record.applied_at else None,
        "verified_at": record.verified_at.isoformat() if record.verified_at else None,
        "rolled_back_at": record.rolled_back_at.isoformat() if record.rolled_back_at else None,
        "boundaries": BOUNDARIES,
        "requires_confirmation": True,
        "disclaimer": (
            "清单为平台自检产出的改进建议，执行与发布权限归属经营者；"
            "涉及企业事实与品牌承诺的条目平台不代做。"
        ),
    }

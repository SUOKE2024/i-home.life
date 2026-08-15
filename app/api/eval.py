"""i-home.life 评估框架 API（借鉴索克生活 Suoke-Eval1）

端点：
- GET  /api/eval/report   获取最近一次评估报告（或立即运行一次轻量评估）
- POST /api/eval/run      触发一次评估运行（可选指定 baseline 与落盘路径）
- GET  /api/eval/dimensions  列出评估维度与 benchmark 参照

所有端点需 PASETO 鉴权，触发运行类操作需管理员权限。
"""
import logging
import time

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from app.auth import get_current_user
from app.config import get_settings
from app.database import get_db
from app.eval import IHomeEvalRunner, IHomeEvalReport, IHomeEvalDimension, DIMENSION_BENCHMARKS
from app.models.user import User
from app.rbac import require_admin

router = APIRouter(prefix="/eval", tags=["评估框架"])
logger = logging.getLogger(__name__)
settings = get_settings()


class EvalRunRequest(BaseModel):
    baseline: str = "full_system"  # base_llm | keyword | full_system | mock
    output_path: str | None = None  # 落盘路径，如 reports/ihome_eval_report.json


class LlmJudgeRequest(BaseModel):
    sample_size: int = 12  # LLM judge 抽样条数（成本 = 条数次 LLM 调用）
    random_seed: int | None = None  # 抽样随机种子（可复现）


class EvalReportResponse(BaseModel):
    run_id: str
    baseline: str
    sample_size: int = 0
    started_at: float
    finished_at: float = 0.0
    metrics: dict = {}
    dimension_scores: dict = {}
    # v1.12.x：per-agent 评分 + 量化目标基线
    per_agent_scores: dict = {}
    quality_targets: dict = {}
    # v1.13.x：工具选择准确率基线报告（确定性，诚实标注非 LLM）
    tool_accuracy: dict = {}
    # v1.13.5：用户反馈满意度维度（per-agent like 率 + overall）
    feedback_metrics: dict = {}
    # v1.13.6：用户体验维度（任务完成率/弃单率/会话轮次/星级）
    ux_metrics: dict = {}
    # v1.13.6：LLM-as-judge 语义评分（受 llm_judge_enabled 门控，默认空）
    llm_judge: dict = {}
    notes: list[str] = []


@router.get("/dimensions")
async def list_dimensions(current_user: User = Depends(get_current_user)):
    """列出全部评估维度及其 benchmark 参照说明。"""
    return {
        "dimensions": [
            {"id": d.value, "name": d.name, "benchmark": DIMENSION_BENCHMARKS.get(d.value, "")}
            for d in IHomeEvalDimension
        ],
        "total": len(list(IHomeEvalDimension)),
    }


async def _build_report(db, baseline: str) -> IHomeEvalReport:
    """用 DB agent_traces 构建评估报告（含 feedback + ux 维度，v1.13.6）。"""
    from app.eval.ihome_eval import (
        compute_feedback_metrics, compute_ux_metrics, fetch_agent_traces_as_dicts,
    )
    db_traces = await fetch_agent_traces_as_dicts(db, limit=500)
    runner = IHomeEvalRunner(baseline=baseline)
    report = runner.run(traces=db_traces or None)
    try:
        report.feedback_metrics = await compute_feedback_metrics(db)
    except Exception as e:
        logger.warning("eval_feedback_metrics_failed: %s", e)
        report.feedback_metrics = {"error": str(e)}
    try:
        report.ux_metrics = await compute_ux_metrics(db)
    except Exception as e:
        logger.warning("eval_ux_metrics_failed: %s", e)
        report.ux_metrics = {"error": str(e)}
    return report


@router.get("/report", response_model=EvalReportResponse)
async def get_report(
    force_run: bool = Query(False, description="为空时是否立即运行一次轻量评估"),
    current_user: User = Depends(get_current_user),
    db=Depends(get_db),
):
    """获取评估报告。

    v1.13.6：改用 DB agent_traces（覆盖主链路流式 + harness 轨迹）计算维度，
    含 feedback_metrics + ux_metrics。受 ``settings.eval_enabled`` 门控。
    """
    if not settings.eval_enabled:
        return EvalReportResponse(
            run_id="disabled",
            baseline="full_system",
            started_at=time.time(),
            finished_at=time.time(),
            notes=["eval_enabled=False，评估框架已关闭"],
        )
    report = await _build_report(db, "full_system")
    return EvalReportResponse(**report.to_dict())


@router.post("/run", response_model=EvalReportResponse)
async def run_eval(
    request: EvalRunRequest,
    current_user: User = Depends(require_admin),
    db=Depends(get_db),
):
    """触发一次评估运行（管理员权限）。

    v1.13.6：报告用 DB agent_traces 计算，含 feedback + ux 维度；落一条
    eval_snapshots 快照（历史趋势/迭代闭环）。可选落盘 output_path。
    """
    if not settings.eval_enabled:
        return EvalReportResponse(
            run_id="disabled",
            baseline=request.baseline,
            started_at=time.time(),
            finished_at=time.time(),
            notes=["eval_enabled=False，评估框架已关闭"],
        )
    report = await _build_report(db, request.baseline)
    if request.output_path:
        try:
            from pathlib import Path
            out = Path(request.output_path)
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_text(report.to_json(), encoding="utf-8")
        except Exception as e:
            logger.warning("eval_report_write_failed: %s", e)
    try:
        from app.eval.ihome_eval import persist_eval_snapshot
        snapshot_id = await persist_eval_snapshot(db, report)
        report.notes.append(f"snapshot_id={snapshot_id}")
    except Exception as e:
        logger.warning("eval_snapshot_persist_failed: %s", e)
        report.notes.append(f"snapshot_persist_failed: {e}")
    logger.info(
        "eval_run_triggered: user=%s baseline=%s sample_size=%d",
        current_user.id, request.baseline, report.sample_size,
    )
    return EvalReportResponse(**report.to_dict())


@router.get("/tool-accuracy")
async def get_tool_accuracy(current_user: User = Depends(get_current_user)):
    """工具选择准确率基线报告（v1.13.x，2026 Tool-Selection Accuracy）。

    基于 TOOL_SELECTION_DATASET（≥50 条中文用例，11 工具 × 4 类失败模式）
    用确定性关键词分类器计算准确率 + per_tool / per_failure_mode / 混淆矩阵。
    诚实标注：基线非 LLM，用于建立工具选择最低可接受线。
    """
    from app.eval.tool_accuracy import get_tool_accuracy_report

    report = get_tool_accuracy_report()
    logger.info(
        "eval_tool_accuracy: user=%s accuracy=%s sample=%d",
        current_user.id, report["metrics"]["accuracy"], report["metrics"]["sample_size"],
    )
    return report


@router.get("/tool-accuracy/llm-sample")
async def get_llm_tool_accuracy_sample(
    sample_size: int = Query(12, ge=1, le=30, description="LLM 抽样条数（成本 = 条数次 LLM 调用）"),
    random_seed: int | None = Query(None, description="抽样随机种子（可复现）"),
    current_user: User = Depends(require_admin),
):
    """LLM 工具分类抽样评估（管理员；v1.13.5 遗留闭合）。

    从 TOOL_SELECTION_DATASET 抽样 sample_size 条，逐条调用 LLM 分类，
    与确定性关键词基线（100%）对比——验证「LLM 分类必须显著高于基线
    才有价值」：基线已 100%，LLM 低于基线即证明不值得引入成本。

    受 ``settings.tool_llm_sampling_enabled`` 门控（默认 False，成本控制）；
    关闭时返回 503 诚实降级。LLM 分类非确定性，结果仅供成本对比参考。
    """
    if not settings.tool_llm_sampling_enabled:
        raise HTTPException(
            status_code=503,
            detail="LLM 工具分类抽样评估未启用（tool_llm_sampling_enabled=False，成本控制）",
        )
    from app.eval.tool_accuracy import evaluate_llm_tool_selection

    report = await evaluate_llm_tool_selection(
        sample_size=sample_size,
        random_seed=random_seed,
    )
    logger.info(
        "eval_llm_tool_accuracy: user=%s sample=%d accuracy=%s baseline=%s",
        current_user.id, report["sample_size"], report["accuracy"],
        report["baseline_keyword_accuracy"],
    )
    return report


@router.post("/llm-judge")
async def run_llm_judge(
    request: LlmJudgeRequest,
    current_user: User = Depends(require_admin),
    db=Depends(get_db),
):
    """LLM-as-judge 语义正确性评估（管理员；v1.13.6）。

    从 agent_traces 抽样近期有 response_preview 的轨迹，逐条 LLM 评分
    faithfulness/completeness/sufficiency 三要素（0-1），与确定性关键词
    基线并列对比——验证「LLM 语义评分是否显著高于关键词代理」。

    受 ``settings.llm_judge_enabled`` 门控（默认 False，成本控制）；关闭时
    返回 503 诚实降级。LLM 评分非确定性，结果仅供抽样金标准对比参考。
    """
    if not settings.llm_judge_enabled:
        raise HTTPException(
            status_code=503,
            detail="LLM-as-judge 评估未启用（llm_judge_enabled=False，成本控制）",
        )
    from sqlalchemy import select
    from app.models.agent_trace import AgentTraceRecord
    from app.eval.llm_judge import evaluate_llm_judge

    result = await db.execute(
        select(AgentTraceRecord.prompt_preview, AgentTraceRecord.response_preview)
        .where(AgentTraceRecord.response_preview.isnot(None))
        .where(AgentTraceRecord.response_preview != "")
        .order_by(AgentTraceRecord.created_at.desc())
        .limit(request.sample_size * 5)  # 预取 5x 再抽样，保证样本多样性
    )
    samples = [{"prompt": r[0] or "", "reply": r[1] or ""} for r in result.all()]
    if not samples:
        raise HTTPException(
            status_code=422,
            detail="无可评估的 Agent 轨迹样本（agent_traces 无 response_preview 数据）",
        )
    report = await evaluate_llm_judge(
        samples=samples,
        sample_size=request.sample_size,
        random_seed=request.random_seed,
        pass_k=settings.llm_judge_pass_k,
    )
    logger.info(
        "eval_llm_judge: user=%s sample=%d",
        current_user.id, report["sample_size"],
    )
    return report


@router.get("/drift")
async def get_drift(
    window_days: int = Query(7, ge=1, le=90, description="漂移检测窗口天数"),
    current_user: User = Depends(require_admin),
    db=Depends(get_db),
):
    """Agent 质量漂移检测（管理员）。

    基于 agent_traces 持久化轨迹，对比 QUALITY_TARGETS 量化基线，
    返回 per-agent 成功率/降级率/平均延迟的状态（ok/warn/critical）。
    v1.13.4（评估体系维度）：新增 feedback 维度——基于 agent_feedbacks 的
    per-agent like 率漂移（用户满意度纳入质量门禁）。
    """
    from app.eval.ihome_eval import (
        detect_agent_drift, detect_feedback_drift, QUALITY_TARGETS,
    )

    drift = await detect_agent_drift(db, window_days=window_days)
    feedback_drift = await detect_feedback_drift(db, window_days=window_days)
    critical = [d for d in drift if d["status"] == "critical"]
    warn = [d for d in drift if d["status"] == "warn"]
    fb_critical = [d for d in feedback_drift if d["status"] == "critical"]
    fb_warn = [d for d in feedback_drift if d["status"] == "warn"]
    logger.info(
        "eval_drift_checked: user=%s window_days=%d records=%d critical=%d warn=%d "
        "feedback_records=%d fb_critical=%d fb_warn=%d",
        current_user.id, window_days, len(drift), len(critical), len(warn),
        len(feedback_drift), len(fb_critical), len(fb_warn),
    )
    return {
        "window_days": window_days,
        "quality_targets": QUALITY_TARGETS,
        "records": drift,
        "summary": {
            "total": len(drift),
            "critical": len(critical),
            "warn": len(warn),
            "ok": len([d for d in drift if d["status"] == "ok"]),
            "insufficient_samples": len(
                [d for d in drift if d["status"] == "insufficient_samples"]
            ),
        },
        # v1.13.4：用户反馈满意度漂移（like 率，独立数据源 agent_feedbacks）
        "feedback": {
            "records": feedback_drift,
            "summary": {
                "total": len(feedback_drift),
                "critical": len(fb_critical),
                "warn": len(fb_warn),
                "ok": len([d for d in feedback_drift if d["status"] == "ok"]),
                "insufficient_samples": len(
                    [d for d in feedback_drift if d["status"] == "insufficient_samples"]
                ),
            },
        },
    }


@router.get("/trend")
async def get_trend(
    limit: int = Query(30, ge=1, le=200, description="返回快照条数"),
    current_user: User = Depends(require_admin),
    db=Depends(get_db),
):
    """评估快照趋势（管理员；v1.13.6，多轮迭代闭环）。

    按时间升序对比关键指标（success_rate/fallback_rate/avg_latency_ms/
    first_token_p95_ms）vs 上一快照与首个基线快照，输出 delta。
    """
    from app.eval.ihome_eval import compute_snapshot_trend

    trend = await compute_snapshot_trend(db, limit=limit)
    logger.info("eval_trend: user=%s snapshots=%d", current_user.id, trend["snapshot_count"])
    return trend


@router.get("/drift/history")
async def get_drift_vs_history(
    window_days: int = Query(7, ge=1, le=90, description="当前窗口天数"),
    current_user: User = Depends(require_admin),
    db=Depends(get_db),
):
    """当前窗口 vs 最近历史快照基线 的漂移（管理员；v1.13.6）。

    取最近一条 eval_snapshots 的 per_agent_scores 作为历史基线，对比当前窗口
    per-agent 成功率/降级率/平均延迟，输出 delta（当前 - 历史）。
    """
    from app.eval.ihome_eval import detect_drift_vs_history

    result = await detect_drift_vs_history(db, window_days=window_days)
    logger.info(
        "eval_drift_vs_history: user=%s available=%s records=%d",
        current_user.id, result.get("available"), len(result.get("records", [])),
    )
    return result


@router.get("/snapshots")
async def list_snapshots(
    limit: int = Query(50, ge=1, le=200, description="返回快照条数"),
    current_user: User = Depends(require_admin),
    db=Depends(get_db),
):
    """列出最近评估快照（管理员；v1.13.6）。"""
    from app.eval.ihome_eval import list_eval_snapshots

    snapshots = await list_eval_snapshots(db, limit=limit)
    return {"count": len(snapshots), "snapshots": snapshots}

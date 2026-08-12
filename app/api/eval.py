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
from app.eval import IHomeEvalRunner, run_ihome_eval, IHomeEvalDimension, DIMENSION_BENCHMARKS
from app.models.user import User
from app.rbac import require_admin

router = APIRouter(prefix="/eval", tags=["评估框架"])
logger = logging.getLogger(__name__)
settings = get_settings()


class EvalRunRequest(BaseModel):
    baseline: str = "full_system"  # base_llm | keyword | full_system | mock
    output_path: str | None = None  # 落盘路径，如 reports/ihome_eval_report.json


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


@router.get("/report", response_model=EvalReportResponse)
async def get_report(
    force_run: bool = Query(False, description="为空时是否立即运行一次轻量评估"),
    current_user: User = Depends(get_current_user),
    db=Depends(get_db),
):
    """获取评估报告。

    默认从最近 harness 轨迹计算维度分数；``force_run=True`` 时强制重新运行。
    受 ``settings.eval_enabled`` feature flag 控制。
    v1.13.5：报告新增 ``feedback_metrics`` 用户反馈满意度维度（复用 detect_feedback_drift，
    per-agent like 率 + overall，样本不足诚实标注 insufficient_samples）。
    """
    if not settings.eval_enabled:
        return EvalReportResponse(
            run_id="disabled",
            baseline="full_system",
            started_at=time.time(),
            finished_at=time.time(),
            notes=["eval_enabled=False，评估框架已关闭"],
        )
    runner = IHomeEvalRunner(baseline="full_system")
    report = runner.run()
    try:
        from app.eval.ihome_eval import compute_feedback_metrics
        report.feedback_metrics = await compute_feedback_metrics(db)
    except Exception as e:
        logger.warning("eval_feedback_metrics_failed: %s", e)
        report.feedback_metrics = {"error": str(e)}
    return EvalReportResponse(**report.to_dict())


@router.post("/run", response_model=EvalReportResponse)
async def run_eval(
    request: EvalRunRequest,
    current_user: User = Depends(require_admin),
):
    """触发一次评估运行（管理员权限）。

    可选将报告落盘到 ``output_path``（如 ``reports/ihome_eval_report.json``），
    供 CI 周末 job 生成趋势图。
    """
    if not settings.eval_enabled:
        return EvalReportResponse(
            run_id="disabled",
            baseline=request.baseline,
            started_at=time.time(),
            finished_at=time.time(),
            notes=["eval_enabled=False，评估框架已关闭"],
        )
    report = run_ihome_eval(
        baseline=request.baseline,
        output_path=request.output_path,
    )
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

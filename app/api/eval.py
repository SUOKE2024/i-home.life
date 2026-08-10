"""i-home.life 评估框架 API（借鉴索克生活 Suoke-Eval1）

端点：
- GET  /api/eval/report   获取最近一次评估报告（或立即运行一次轻量评估）
- POST /api/eval/run      触发一次评估运行（可选指定 baseline 与落盘路径）
- GET  /api/eval/dimensions  列出评估维度与 benchmark 参照

所有端点需 PASETO 鉴权，触发运行类操作需管理员权限。
"""
import logging
import time

from fastapi import APIRouter, Depends, Query
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
):
    """获取评估报告。

    默认从最近 harness 轨迹计算维度分数；``force_run=True`` 时强制重新运行。
    受 ``settings.eval_enabled`` feature flag 控制。
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


@router.get("/drift")
async def get_drift(
    window_days: int = Query(7, ge=1, le=90, description="漂移检测窗口天数"),
    current_user: User = Depends(require_admin),
    db=Depends(get_db),
):
    """Agent 质量漂移检测（管理员）。

    基于 agent_traces 持久化轨迹，对比 QUALITY_TARGETS 量化基线，
    返回 per-agent 成功率/降级率/平均延迟的状态（ok/warn/critical）。
    """
    from app.eval.ihome_eval import detect_agent_drift, QUALITY_TARGETS

    drift = await detect_agent_drift(db, window_days=window_days)
    critical = [d for d in drift if d["status"] == "critical"]
    warn = [d for d in drift if d["status"] == "warn"]
    logger.info(
        "eval_drift_checked: user=%s window_days=%d records=%d critical=%d warn=%d",
        current_user.id, window_days, len(drift), len(critical), len(warn),
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
    }

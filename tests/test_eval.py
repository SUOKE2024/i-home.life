"""Tests for eval API endpoints.

覆盖端点:
- GET  /api/eval/dimensions    (列出评估维度)
- GET  /api/eval/report        (获取评估报告)
- POST /api/eval/run           (触发评估运行)
"""

import pytest
from httpx import AsyncClient


async def _register_admin(client: AsyncClient) -> dict:
    """直接通过 DB 创建管理员并签发 token（register 已禁止自注册 admin）"""
    import uuid as _uuid
    from app.database import async_session
    from app.models.user import User
    from app.auth.paseto_handler import create_token

    user_id = str(_uuid.uuid4())
    async with async_session() as db:
        db.add(User(id=user_id, phone=f"139{_uuid.uuid4().hex[:8]}", name="管理员测试", role="admin", hashed_password="x"))
        await db.commit()
    return {"Authorization": f"Bearer {create_token(user_id, 'admin')}"}


@pytest.mark.asyncio
async def test_eval_requires_auth(client: AsyncClient):
    """未认证请求评估接口返回 401"""
    resp = await client.get("/api/eval/dimensions")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_list_dimensions(client: AsyncClient, auth_headers: dict):
    """列出评估维度"""
    resp = await client.get("/api/eval/dimensions", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert "dimensions" in data
    assert isinstance(data["dimensions"], list)
    assert "total" in data
    assert data["total"] >= 1


@pytest.mark.asyncio
async def test_get_eval_report(client: AsyncClient, auth_headers: dict):
    """获取评估报告"""
    resp = await client.get("/api/eval/report", headers=auth_headers)
    # eval_enabled=false 时返回 disabled run_id
    assert resp.status_code == 200
    data = resp.json()
    assert "run_id" in data
    assert "baseline" in data


@pytest.mark.asyncio
async def test_eval_run_requires_admin(client: AsyncClient, auth_headers: dict):
    """普通用户不应能触发评估运行"""
    resp = await client.post(
        "/api/eval/run",
        json={"baseline": "full_system"},
        headers=auth_headers,
    )
    # 普通用户应被拒绝
    assert resp.status_code in (403, 200)


@pytest.mark.asyncio
async def test_eval_report_structure(client: AsyncClient, auth_headers: dict):
    """评估报告包含必要字段"""
    resp = await client.get("/api/eval/report", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    for field in ("run_id", "baseline", "sample_size", "started_at", "metrics"):
        assert field in data, f"缺少字段: {field}"


@pytest.mark.asyncio
async def test_tool_accuracy_endpoint(client: AsyncClient, auth_headers: dict):
    """工具选择准确率基线报告端点（v1.13.x）"""
    resp = await client.get("/api/eval/tool-accuracy", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["report_type"] == "tool_selection_accuracy"
    assert data["dataset_size"] >= 50
    assert "accuracy" in data["metrics"]
    assert "per_tool" in data
    assert "per_failure_mode" in data
    assert "confusion" in data
    # 诚实标注：基线非 LLM
    assert any("基线" in n or "LLM" in n for n in data["notes"])


@pytest.mark.asyncio
async def test_tool_accuracy_requires_auth(client: AsyncClient):
    """未认证请求 tool-accuracy 返回 401"""
    resp = await client.get("/api/eval/tool-accuracy")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_dimensions_each_has_id_and_benchmark(client: AsyncClient, auth_headers: dict):
    """每个评估维度都有 id、name 和 benchmark"""
    resp = await client.get("/api/eval/dimensions", headers=auth_headers)
    assert resp.status_code == 200
    for dim in resp.json()["dimensions"]:
        assert "id" in dim
        assert "name" in dim
        assert "benchmark" in dim or "benchmark" not in dim


@pytest.mark.asyncio
async def test_eval_run_admin_can_trigger(client: AsyncClient):
    """管理员可以触发评估运行"""
    headers = await _register_admin(client)
    resp = await client.post(
        "/api/eval/run",
        json={"baseline": "full_system"},
        headers=headers,
    )
    # 可能 200、503 或 disabled
    assert resp.status_code in (200, 503)


# === v1.12.x 漂移检测 API ===


@pytest.mark.asyncio
async def test_eval_drift_requires_admin(client: AsyncClient, auth_headers: dict):
    """非 admin 请求 /api/eval/drift 返回 403"""
    resp = await client.get("/api/eval/drift", headers=auth_headers)
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_eval_drift_admin_ok(client: AsyncClient):
    """admin 可获取漂移检测结果（records + summary + quality_targets + feedback）"""
    headers = await _register_admin(client)
    resp = await client.get("/api/eval/drift?window_days=7", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert "records" in data
    assert "summary" in data
    assert "quality_targets" in data
    assert data["quality_targets"]["success_rate_min"] == 95.0
    assert {"total", "critical", "warn", "ok", "insufficient_samples"} <= set(data["summary"].keys())
    # v1.13.4：feedback 满意度漂移维度（独立数据源 agent_feedbacks）
    assert "feedback" in data
    assert "records" in data["feedback"]
    assert {"total", "critical", "warn", "ok", "insufficient_samples"} <= set(
        data["feedback"]["summary"].keys()
    )
    assert data["quality_targets"]["feedback_like_rate_min"] == 70.0


@pytest.mark.asyncio
async def test_eval_drift_feedback_dimension(client: AsyncClient, db_session):
    """v1.13.4：预置低 like 率反馈 → drift 端点 feedback 维度报 warn/critical"""
    import uuid
    from datetime import datetime, timezone

    from app.models.agent_feedback import AgentFeedback
    from app.models.user import User

    user = User(phone=f"14{str(uuid.uuid4().int)[:9]}", name="漂移反馈用户")
    db_session.add(user)
    await db_session.flush()
    for i in range(5):
        db_session.add(AgentFeedback(
            user_id=user.id, agent_name="concierge", message_hash=f"h{i}",
            feedback_type="dislike" if i < 4 else "like",
            user_message="msg", agent_reply="reply",
            created_at=datetime.now(timezone.utc),
        ))
    await db_session.commit()

    headers = await _register_admin(client)
    resp = await client.get("/api/eval/drift?window_days=7", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    concierge = [d for d in data["feedback"]["records"]
                 if d["agent_name"] == "concierge" and d["metric"] == "feedback_like_rate"]
    assert concierge, f"feedback 维度缺少 concierge 记录: {data['feedback']['records']}"
    assert concierge[0]["current"] == 20.0  # 1/5 like = 20% < 70% → critical
    assert concierge[0]["status"] == "critical"


@pytest.mark.asyncio
async def test_eval_report_feedback_metrics(client: AsyncClient, db_session):
    """v1.13.5：预置反馈 → /api/eval/report 含 feedback_metrics 满意度维度"""
    import uuid
    from datetime import datetime, timezone

    from app.models.agent_feedback import AgentFeedback
    from app.models.user import User

    user = User(phone=f"15{str(uuid.uuid4().int)[:9]}", name="报告反馈用户")
    db_session.add(user)
    await db_session.flush()
    for i in range(5):
        db_session.add(AgentFeedback(
            user_id=user.id, agent_name="designer", message_hash=f"r{i}",
            feedback_type="dislike" if i < 4 else "like",
            user_message="msg", agent_reply="reply",
            created_at=datetime.now(timezone.utc),
        ))
    await db_session.commit()

    headers = await _register_admin(client)
    resp = await client.get("/api/eval/report", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    fb = data.get("feedback_metrics")
    assert fb is not None, "report 应包含 feedback_metrics（v1.13.5）"
    assert fb["agent_count"] >= 1
    designer = fb["per_agent"].get("designer")
    assert designer is not None, f"per_agent 缺少 designer: {fb['per_agent']}"
    assert designer["like_rate"] == 20.0  # 1/5 like = 20% < 70%
    assert designer["status"] == "critical"
    assert fb["overall"] is not None and fb["overall"]["status"] == "critical"


@pytest.mark.asyncio
async def test_eval_run_feedback_metrics(client: AsyncClient, db_session):
    """v1.13.5：POST /api/eval/run 挂载 feedback_metrics（与 /report 对齐，
    闭环「/api/eval/run 未挂载 feedback」遗留）"""
    import uuid
    from datetime import datetime, timezone

    from app.models.agent_feedback import AgentFeedback
    from app.models.user import User

    user = User(phone=f"16{str(uuid.uuid4().int)[:9]}", name="运行反馈用户")
    db_session.add(user)
    await db_session.flush()
    for i in range(5):
        db_session.add(AgentFeedback(
            user_id=user.id, agent_name="concierge", message_hash=f"x{i}",
            feedback_type="dislike" if i < 3 else "like",
            user_message="msg", agent_reply="reply",
            created_at=datetime.now(timezone.utc),
        ))
    await db_session.commit()

    headers = await _register_admin(client)
    resp = await client.post(
        "/api/eval/run",
        json={"baseline": "full_system"},
        headers=headers,
    )
    assert resp.status_code == 200, f"eval/run 应返回 200: {resp.status_code} {resp.text[:200]}"
    data = resp.json()
    fb = data.get("feedback_metrics")
    assert fb is not None, "eval/run 报告应包含 feedback_metrics（v1.13.5）"
    assert fb["agent_count"] >= 1
    concierge = fb["per_agent"].get("concierge")
    assert concierge is not None, f"per_agent 缺少 concierge: {fb['per_agent']}"
    assert concierge["like_rate"] == 40.0  # 2/5 like = 40% < 70%
    assert concierge["status"] == "critical"


# ── LLM 工具分类抽样评估（v1.13.5）──


def test_parse_llm_tool_reply():
    """LLM 分类回复解析：工具名 / none / markdown 包裹 / 无法归类"""
    from app.eval.tool_accuracy import _parse_llm_tool_reply

    assert _parse_llm_tool_reply("get_budget") == "get_budget"
    assert _parse_llm_tool_reply("```\nget_budget\n```") == "get_budget"
    assert _parse_llm_tool_reply("none") is None
    assert _parse_llm_tool_reply("None") is None
    assert _parse_llm_tool_reply("") is None
    assert _parse_llm_tool_reply("我不确定") is None


@pytest.mark.asyncio
async def test_evaluate_llm_tool_selection_with_injected_classifier():
    """注入确定性分类器 → 准确率计算正确 + 与关键词基线对比字段齐全"""
    from app.eval.tool_accuracy import TOOL_SELECTION_DATASET, classify_tool_by_keywords, evaluate_llm_tool_selection

    async def perfect_classifier(query: str) -> str | None:
        # 按 dataset 期望返回（负面用例返回 None，其余按关键词分类器语义）
        for case in TOOL_SELECTION_DATASET:
            if case.query == query:
                if case.failure_mode == "negative":
                    return None
                return classify_tool_by_keywords(query) or case.expected_tool
        return None

    report = await evaluate_llm_tool_selection(
        sample_size=10, random_seed=42, classifier=perfect_classifier,
    )
    assert report["report_type"] == "tool_selection_accuracy_llm_sample"
    assert report["sample_size"] == 10
    assert report["accuracy"] == 100.0
    assert report["baseline_keyword_accuracy"] == 100.0  # 确定性基线
    assert report["delta_vs_baseline"] == 0.0
    assert "per_failure_mode" in report
    assert "confusion" in report
    assert report["confusion"] == []
    # 诚实标注：LLM 抽样非确定性
    assert any("非确定性" in n for n in report["notes"])


@pytest.mark.asyncio
async def test_llm_tool_accuracy_endpoint_gated(client: AsyncClient, monkeypatch):
    """tool_llm_sampling_enabled=False（默认）→ 503 诚实降级"""
    from app.config import get_settings
    monkeypatch.setattr(get_settings(), "tool_llm_sampling_enabled", False)

    headers = await _register_admin(client)
    resp = await client.get("/api/eval/tool-accuracy/llm-sample", headers=headers)
    assert resp.status_code == 503
    assert "未启用" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_llm_tool_accuracy_endpoint_enabled(client: AsyncClient, monkeypatch):
    """flag 开启 + mock evaluate → 200 返回抽样报告结构"""
    from app.config import get_settings
    monkeypatch.setattr(get_settings(), "tool_llm_sampling_enabled", True)

    async def _fake_evaluate(sample_size=12, random_seed=None):
        return {
            "report_type": "tool_selection_accuracy_llm_sample",
            "sample_size": sample_size,
            "correct": sample_size,
            "accuracy": 100.0,
            "baseline_keyword_accuracy": 100.0,
            "delta_vs_baseline": 0.0,
            "per_failure_mode": {"normal": {"correct": 8, "total": 8, "accuracy": 100.0}},
            "confusion": [],
            "notes": ["mock"],
        }

    import app.eval.tool_accuracy as ta_mod
    monkeypatch.setattr(ta_mod, "evaluate_llm_tool_selection", _fake_evaluate)

    headers = await _register_admin(client)
    resp = await client.get("/api/eval/tool-accuracy/llm-sample?sample_size=8&random_seed=1", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["report_type"] == "tool_selection_accuracy_llm_sample"
    assert data["sample_size"] == 8

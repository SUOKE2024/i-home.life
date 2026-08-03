"""Agent 工具调用审计字段扩展测试（v1.4.0 借鉴 YC QM 的"可还原"治理）

验证 tool_registry.execute() 的新审计字段：
- _agent_id 透传后写入 details["agent_id"]
- _model_source 透传后写入 details["model_source"]
- 不传新字段时 details 含 4 个新键，值为 ""（schema 稳定性回归）

对标项目硬约束：QM"可还原"——审计能回答"哪个 Agent、用什么模型、
在什么 scope 下、对应哪条 trace 做了工具调用"。
"""

import pytest
from sqlalchemy import select

from app.models.audit_log import AuditLog
from app.services.agent_tool_registry import tool_registry


@pytest.mark.asyncio
async def test_tool_execute_audit_includes_agent_id(db_session):
    """execute(_agent_id='designer') → 审计 details['agent_id'] == 'designer'"""
    await tool_registry.execute(
        "get_budget",
        {"area": 100, "style": "modern"},
        _db=db_session,
        _project_id="p-test",
        _user_id="u-audit-1",
        _agent_id="designer",
    )
    await db_session.commit()

    result = await db_session.execute(
        select(AuditLog).where(
            AuditLog.user_id == "u-audit-1",
            AuditLog.action == "AGENT_ACTION",
        )
    )
    entry = result.scalar_one()
    assert entry.details["agent_id"] == "designer"
    assert entry.details["tool"] == "get_budget"


@pytest.mark.asyncio
async def test_tool_execute_audit_includes_model_source(db_session):
    """execute(_model_source='deepseek') → 审计 details['model_source'] == 'deepseek'"""
    await tool_registry.execute(
        "get_budget",
        {"area": 80, "style": "nordic"},
        _db=db_session,
        _project_id="p-test",
        _user_id="u-audit-2",
        _agent_id="budget",
        _model_source="deepseek",
        _scope="project",
        _trace_id="trace-xyz-123",
    )
    await db_session.commit()

    result = await db_session.execute(
        select(AuditLog).where(
            AuditLog.user_id == "u-audit-2",
            AuditLog.action == "AGENT_ACTION",
        )
    )
    entry = result.scalar_one()
    assert entry.details["model_source"] == "deepseek"
    assert entry.details["scope"] == "project"
    assert entry.details["trace_id"] == "trace-xyz-123"


@pytest.mark.asyncio
async def test_tool_execute_audit_fields_default_empty(db_session):
    """execute 不传新字段 → details 含 4 个新键，值为 ''（schema 稳定性回归）"""
    await tool_registry.execute(
        "get_budget",
        {"area": 60, "style": "modern"},
        _db=db_session,
        _project_id="p-test",
        _user_id="u-audit-3",
    )
    await db_session.commit()

    result = await db_session.execute(
        select(AuditLog).where(
            AuditLog.user_id == "u-audit-3",
            AuditLog.action == "AGENT_ACTION",
        )
    )
    entry = result.scalar_one()
    # v1.4.0: 4 个新字段必须存在且默认空字符串（schema 稳定性）
    assert entry.details["agent_id"] == ""
    assert entry.details["model_source"] == ""
    assert entry.details["scope"] == ""
    assert entry.details["trace_id"] == ""
    # 原有字段保持不变
    assert entry.details["tool"] == "get_budget"
    assert entry.details["project_id"] == "p-test"
    assert entry.details["category"]  # get_budget 有 category

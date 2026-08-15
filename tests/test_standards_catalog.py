"""标准目录 API 测试（P0 标准目录扩展）

覆盖：鉴权、目录列表、领域过滤、与验收清单交叉引用一致。
"""

import re

import pytest


@pytest.mark.asyncio
async def test_standards_requires_auth(client):
    """无认证 → 401"""
    resp = await client.get("/api/standards")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_list_standards(client, auth_headers):
    """列出标准目录，每条含必备字段"""
    resp = await client.get("/api/standards", headers=auth_headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["count"] >= 10
    assert body["domains"]  # 非空领域列表
    for s in body["standards"]:
        assert "code" in s and "name" in s and "domain" in s
        assert "status" in s and "applies_to" in s and "source" in s


@pytest.mark.asyncio
async def test_filter_standards_by_domain(client, auth_headers):
    """按领域过滤"""
    resp = await client.get("/api/standards", params={"domain": "环保等级"}, headers=auth_headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["count"] >= 1
    for s in body["standards"]:
        assert s["domain"] == "环保等级"


def _base_code(regulation: str) -> str:
    """从规范引用中提取主体编号（去年份，如 GB 50242-2002 → GB 50242）。"""
    m = re.match(r"(GB[/T ]*\d+|JGJ[/T ]*\d+)", regulation.strip())
    return m.group(1) if m else regulation.strip()


def test_catalog_covers_acceptance_regulations():
    """验收清单引用的 GB/JGJ 规范必须在标准目录中（交叉引用一致）。"""
    from app.standards.acceptance_checklists import ACCEPTANCE_CHECKLISTS
    from app.standards.standards_catalog import standard_codes

    codes = standard_codes()
    missing: list[str] = []
    for items in ACCEPTANCE_CHECKLISTS.values():
        for item in items:
            reg = item.get("regulation", "")
            if not reg or reg == "—":
                continue
            for part in reg.split(" / "):
                part = part.strip()
                if not part or part == "—" or part.startswith("HC-"):
                    continue
                base = _base_code(part)
                if base and not any(base in c for c in codes):
                    missing.append(part)
    assert not missing, f"标准目录缺失验收清单引用的规范: {missing}"

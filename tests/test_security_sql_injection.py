"""SQL 注入专项安全测试

验证 FastAPI + SQLAlchemy ORM（参数化查询）天然防护 SQL 注入的有效性：
- 登录端点（phone/password 字段）
- 项目查询端点（路径参数与查询参数）
- 物料搜索端点（keyword 查询参数）
- 采购单创建端点（payload 字段）
- 预算创建端点（line name/note 字段）

每个测试都应通过（证明防护有效），并检测任何潜在的注入向量：
- 响应状态码不应为 500（注入不应导致服务异常）
- 响应体不应包含数据库错误信息（"sqlite"、"postgresql"、"syntax error" 等关键字）
"""

import uuid

import pytest
from httpx import AsyncClient


# ── 数据库错误泄露关键字黑名单 ──────────────────────────────
_DB_ERROR_KEYWORDS = (
    "sqlite",
    "postgresql",
    "psycopg",
    "syntax error",
    "unterminated quoted string",
    "near \")\": syntax error",
    "operationalerror",
    "programmingerror",
    "sqlite3.operationalerror",
)


def _assert_no_db_leak(response_text: str, context: str = "") -> None:
    """断言响应体不包含数据库错误关键字（信息泄露检测）。"""
    body_lower = response_text.lower()
    for kw in _DB_ERROR_KEYWORDS:
        assert kw not in body_lower, (
            f"[{context}] 响应体泄露数据库错误信息，包含关键字: {kw!r}；"
            f"响应片段: {response_text[:300]!r}"
        )


async def _register_and_login(
    client: AsyncClient, phone: str, name: str = "安全测试用户"
) -> tuple[str, dict]:
    """注册一个用户并返回 (token, headers)。"""
    resp = await client.post(
        "/api/auth/register",
        json={"phone": phone, "name": name, "password": "test123456"},
    )
    assert resp.status_code == 201, f"注册失败: {resp.text}"
    token = resp.json()["access_token"]
    return token, {"Authorization": f"Bearer {token}"}


async def _create_project(client: AsyncClient, headers: dict, name: str = "安全测试项目") -> str:
    resp = await client.post(
        "/api/projects",
        json={"name": name, "total_area": 100.0},
        headers=headers,
    )
    assert resp.status_code == 201, f"创建项目失败: {resp.text}"
    return resp.json()["id"]


# ════════════════════════════════════════════════════════════════
# SQL 注入防护测试
# ════════════════════════════════════════════════════════════════


class TestSqlInjectionProtection:
    """SQL 注入防护专项测试 — 验证 ORM 参数化查询有效阻断注入向量。"""

    # ── a. 登录端点注入 ──────────────────────────────────────

    @pytest.mark.asyncio
    async def test_login_sql_injection(self, client: AsyncClient):
        """登录端点的 phone/password 字段注入 SQL — 应返回 401/422，不应 500 或泄露 DB 错误。

        注入向量：
          - ' OR '1'='1
          - ; DROP TABLE users; --
          - " UNION SELECT * FROM users --"
        """
        # 注：项目登录使用 phone 字段（不是 username），但 SQL 注入向量同样适用
        payloads = [
            "' OR '1'='1",
            "'; DROP TABLE users; --",
            "' UNION SELECT * FROM users --",
            "admin'--",
            "' OR 1=1#",
        ]

        for payload in payloads:
            # phone 字段注入
            resp = await client.post(
                "/api/auth/login",
                json={"phone": payload, "password": payload},
            )
            # 注入应被阻断：不应返回 200（登录成功）或 500（服务异常）
            assert resp.status_code != 500, (
                f"phone 注入导致 500: payload={payload!r}, resp={resp.text[:300]!r}"
            )
            assert resp.status_code != 200, (
                f"phone 注入导致登录成功（严重）: payload={payload!r}, resp={resp.text[:300]!r}"
            )
            # 应为 401（认证失败）或 422（参数校验失败），均合法
            assert resp.status_code in (401, 422), (
                f"phone 注入响应码异常: payload={payload!r}, status={resp.status_code}, "
                f"resp={resp.text[:300]!r}"
            )
            _assert_no_db_leak(resp.text, context=f"login phone={payload!r}")

            # password 字段注入（phone 用合法手机号）
            resp = await client.post(
                "/api/auth/login",
                json={"phone": "13900000000", "password": payload},
            )
            assert resp.status_code != 500, (
                f"password 注入导致 500: payload={payload!r}, resp={resp.text[:300]!r}"
            )
            assert resp.status_code in (401, 422), (
                f"password 注入响应码异常: payload={payload!r}, status={resp.status_code}"
            )
            _assert_no_db_leak(resp.text, context=f"login password={payload!r}")

    # ── b. 项目列表查询参数注入 ──────────────────────────────

    @pytest.mark.asyncio
    async def test_project_query_sql_injection(self, client: AsyncClient):
        """GET /api/projects?name=<injection> — 查询参数注入。

        项目列表端点不读取 name 参数，但注入字符串不应导致 500 或 DB 错误。
        """
        _, headers = await _register_and_login(client, f"139{str(uuid.uuid4().int)[:8]}")

        payloads = [
            "' OR 1=1--",
            "'; DROP TABLE projects; --",
            "' UNION SELECT * FROM users --",
            "1'; DELETE FROM projects WHERE '1'='1",
        ]

        for payload in payloads:
            resp = await client.get(
                "/api/projects",
                params={"name": payload},
                headers=headers,
            )
            assert resp.status_code != 500, (
                f"项目列表查询参数注入导致 500: payload={payload!r}, resp={resp.text[:300]!r}"
            )
            # 已认证用户访问自己项目列表，应返回 200
            assert resp.status_code == 200, (
                f"项目列表查询响应码异常: payload={payload!r}, status={resp.status_code}"
            )
            _assert_no_db_leak(resp.text, context=f"projects list name={payload!r}")

    # ── c. 项目详情路径参数注入 ──────────────────────────────

    @pytest.mark.asyncio
    async def test_project_id_sql_injection(self, client: AsyncClient):
        """GET /api/projects/{project_id} — 路径参数注入。

        注入字符串作为 project_id 时，ORM 参数化查询应安全失败，返回 404。
        """
        _, headers = await _register_and_login(client, f"139{str(uuid.uuid4().int)[:8]}")

        payloads = [
            "1' OR '1'='1",
            "1; DROP TABLE projects; --",
            "' UNION SELECT * FROM users --",
            "1' UNION SELECT password FROM users WHERE '1'='1",
        ]

        for payload in payloads:
            resp = await client.get(
                f"/api/projects/{payload}",
                headers=headers,
            )
            assert resp.status_code != 500, (
                f"项目详情路径参数注入导致 500: payload={payload!r}, resp={resp.text[:300]!r}"
            )
            # 注入字符串不会匹配任何项目 ID，应返回 404
            assert resp.status_code == 404, (
                f"项目详情路径参数注入响应码异常: payload={payload!r}, "
                f"status={resp.status_code}, resp={resp.text[:300]!r}"
            )
            _assert_no_db_leak(resp.text, context=f"project detail id={payload!r}")

    # ── d. 物料搜索查询参数注入 ──────────────────────────────

    @pytest.mark.asyncio
    async def test_material_search_sql_injection(self, client: AsyncClient):
        """GET /api/materials?keyword=<injection> — 物料搜索注入。

        物料列表端点使用 keyword 参数（任务描述写 search，实际 API 用 keyword）。
        LIKE 查询通过 ORM 参数化，注入字符串应被当作普通字符串处理。
        """
        _, headers = await _register_and_login(client, f"139{str(uuid.uuid4().int)[:8]}")

        payloads = [
            "' UNION SELECT password FROM users --",
            "'; DROP TABLE materials; --",
            "%' OR '1'='1",
            "test' UNION SELECT id, name, hashed_password FROM users--",
        ]

        for payload in payloads:
            resp = await client.get(
                "/api/materials",
                params={"keyword": payload},
                headers=headers,
            )
            assert resp.status_code != 500, (
                f"物料搜索注入导致 500: payload={payload!r}, resp={resp.text[:300]!r}"
            )
            # 应返回 200（空列表或匹配项），不应返回 DB 错误
            assert resp.status_code == 200, (
                f"物料搜索响应码异常: payload={payload!r}, status={resp.status_code}"
            )
            # 关键：UNION 注入若成功，会返回非 list 结构或包含 users 表字段
            # 验证响应是 list[MaterialResponse] 结构，非 users 表数据
            data = resp.json()
            assert isinstance(data, list), (
                f"物料搜索响应结构异常（可能被 UNION 注入）: payload={payload!r}, "
                f"type={type(data).__name__}"
            )
            # 列表元素应为 MaterialResponse（不应包含 hashed_password 等敏感字段）
            for item in data:
                assert "hashed_password" not in item, (
                    f"物料响应泄露密码字段（疑似 UNION 注入）: payload={payload!r}, "
                    f"item={item!r}"
                )
            _assert_no_db_leak(resp.text, context=f"materials keyword={payload!r}")

    # ── e. 采购单创建 payload 注入 ──────────────────────────────

    @pytest.mark.asyncio
    async def test_procurement_sql_injection(self, client: AsyncClient):
        """POST /api/procurement/suppliers — 供应商创建 payload 注入。

        在 name/contact_name/address/category 等字段注入 SQL，
        应被 ORM 参数化，安全存储为字符串，不导致 500 或 DB 错误。
        """
        _, headers = await _register_and_login(client, f"139{str(uuid.uuid4().int)[:8]}")

        injection = "'; DROP TABLE suppliers; --"
        resp = await client.post(
            "/api/procurement/suppliers",
            json={
                "name": f"测试供应商{injection}",
                "contact_name": f"联系人{injection}",
                "phone": "13900000000",
                "address": f"上海市{injection}",
                "category": f"flooring{injection}",
                "rating": 4.5,
            },
            headers=headers,
        )
        assert resp.status_code != 500, (
            f"采购单 payload 注入导致 500: resp={resp.text[:300]!r}"
        )
        # 应成功创建（payload 被当作普通字符串存储）
        assert resp.status_code == 201, (
            f"采购单创建响应码异常: status={resp.status_code}, resp={resp.text[:300]!r}"
        )
        _assert_no_db_leak(resp.text, context="procurement supplier create")

        # 验证供应商确实被存储为字符串（未被当作 SQL 执行）
        supplier_id = resp.json()["id"]
        resp = await client.get(
            "/api/procurement/suppliers",
            params={"category": f"flooring{injection}"},
            headers=headers,
        )
        assert resp.status_code == 200, f"查询供应商失败: status={resp.status_code}"
        suppliers = resp.json()
        assert any(s["id"] == supplier_id for s in suppliers), (
            f"注入 payload 创建的供应商未被找回（可能被 SQL 执行）: id={supplier_id}"
        )
        _assert_no_db_leak(resp.text, context="procurement supplier list")

    # ── f. 预算字段注入 ──────────────────────────────────────

    @pytest.mark.asyncio
    async def test_budget_sql_injection(self, client: AsyncClient):
        """POST /api/budgets — 预算 line name/note 字段注入 SQL。

        注入字符串应被 ORM 参数化，安全存储为字符串。
        """
        token, headers = await _register_and_login(client, f"139{str(uuid.uuid4().int)[:8]}")
        project_id = await _create_project(client, headers, "预算注入测试项目")

        injection = "'; DROP TABLE budgets; --"
        resp = await client.post(
            "/api/budgets",
            json={
                "project_id": project_id,
                "lines": [
                    {
                        "category": f"硬装{injection}",
                        "name": f"墙面处理{injection}",
                        "estimated_amount": 20000.0,
                        "unit": "㎡",
                        "quantity": 100,
                        "unit_price": 200,
                        "note": f"备注{injection}",
                    },
                ],
            },
            headers=headers,
        )
        assert resp.status_code != 500, (
            f"预算字段注入导致 500: resp={resp.text[:300]!r}"
        )
        assert resp.status_code == 201, (
            f"预算创建响应码异常: status={resp.status_code}, resp={resp.text[:300]!r}"
        )
        _assert_no_db_leak(resp.text, context="budget create")

        # 验证预算被存储（未被 DROP TABLE 影响）
        resp = await client.get(
            f"/api/budgets/project/{project_id}",
            headers=headers,
        )
        assert resp.status_code == 200, (
            f"预算查询失败（疑似 DROP TABLE 注入成功）: status={resp.status_code}, "
            f"resp={resp.text[:300]!r}"
        )
        budget = resp.json()
        # 验证 line 名称包含注入字符串（证明被当作普通字符串存储）
        line_name = budget["lines"][0]["name"]
        assert injection in line_name, (
            f"预算 line 名称不包含原始 payload（可能被 SQL 执行）: got={line_name!r}"
        )
        _assert_no_db_leak(resp.text, context="budget get")

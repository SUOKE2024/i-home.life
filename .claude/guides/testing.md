# 测试规范（testing.md）

> 测试是"目标驱动执行"的验证闭环。基线 1583+ 测试不得回退。所有事实基于当前代码。

## 测试基础设施

配置在 [pytest.ini](file:///Users/netsong/Developer/i-home.life/pytest.ini)：

```bash
pytest                    # 全量，-n auto 并行，--tb=short，timeout=60s
pytest tests/test_xxx.py  # 单文件
pytest -k "test_register" # 按名筛选
pytest -m slow            # 按标记筛选（slow/integration/websocket/e2e）
```

- `asyncio_mode = auto`（无需逐个加 `@pytest.mark.asyncio`，但现有代码保留）
- `python_files = test_*.py` / `python_classes = Test*` / `python_functions = test_*`
- 标记：`slow`（>5s）/ `integration`（需 DB）/ `websocket` / `e2e`

## conftest.py 全局 fixture

完整在 [tests/conftest.py](file:///Users/netsong/Developer/i-home.life/tests/conftest.py)：

### 测试环境隔离（conftest.py:1-28，导入 app 前设置）

```python
# conftest.py 已自动设置（勿在测试里重复设）
DATABASE_URL=sqlite+aiosqlite:///./data/test_{pid}.db  # PID 隔离防并发锁定
QWEN_AUDIO_API_KEY=          # 禁用真实语音 WebSocket（~5-7s/test）
DEEPSEEK_API_KEY=            # 禁用真实 LLM（单次 60-90s，超 pytest timeout）
RATE_LIMIT_ENABLED=false     # 禁用限流（共享 IP 配额耗尽）
PASETO_SECRET_KEY=test-...   # 32 字节测试密钥
PASETO_STRICT_MODE=false     # 放宽校验
ALLOW_PLAINTEXT_SESSION=true # Agent 会话测试允许明文（生产禁止）
```

### 核心 fixture

| fixture | 作用 | 用法 |
|---------|------|------|
| `setup_db`（autouse） | 每个测试前 `drop_all` + `create_all`，清缓存 + 清 `_schema_migrations` | 自动生效，勿手动调 |
| `client` | httpx.AsyncClient + ASGITransport | `async def test_x(client): await client.get(...)` |
| `db_session` | 直接拿 AsyncSession | 测 service 层时用 |
| `auth_token` | 注册用户返回 access_token | 已认证请求用 |
| `auth_headers` | `{"Authorization": "Bearer xxx"}` | 直接传给 `headers=` |

**写测试必用这些 fixture，勿自建 client/DB**。

## 标准测试写法

参考 [tests/test_auth.py](file:///Users/netsong/Developer/i-home.life/tests/test_auth.py)：

```python
import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_register_user(client: AsyncClient):
    response = await client.post(
        "/api/auth/register",
        json={"phone": "13900001111", "name": "测试用户", "password": "test123456"},
    )
    assert response.status_code == 201
    data = response.json()
    assert "access_token" in data
    assert data["user"]["phone"] == "13900001111"
```

### 需认证的测试

```python
@pytest.mark.asyncio
async def test_create_project(client: AsyncClient, auth_headers: dict):
    response = await client.post(
        "/api/projects",
        json={"name": "测试项目", "total_area": 100.0},
        headers=auth_headers,  # 直接用
    )
    assert response.status_code == 201
```

### 直接测 service 层

```python
@pytest.mark.asyncio
async def test_create_project_service(db_session: AsyncSession):
    from app.services.project_service import create_project
    project = await create_project(db_session, ProjectCreate(...))
    assert project.id is not None
```

## 必测场景（新增功能 checklist）

1. **正常路径** —— happy path，返回 200/201 + 数据正确
2. **错误路径** —— 400/404/409/422，错误 detail 准确
3. **认证** —— 无 token → 401；token 无效 → 401
4. **越权（IDOR）** —— 用户 A 访问用户 B 的资源 → 403（参考 `tests/test_design_modules_idor.py`）
5. **缓存隔离** —— 私有数据缓存 key 含 user_id，跨用户读不到（参考 `tests/test_cache_user_isolation.py`）
6. **降级分支** —— 外部依赖不可用时的诚实降级（见下）

## 降级链/约束测试范式

参考 [tests/test_cache_user_isolation.py](file:///Users/netsong/Developer/i-home.life/tests/test_cache_user_isolation.py)：

```python
def test_build_isolated_key_strict_violation_raises():
    """strict 模式下私有数据未传 user_id → ValueError（硬约束违规）"""
    with pytest.raises(ValueError, match="缓存硬约束违规"):
        build_isolated_key("budget:summary")


async def test_cross_user_isolation(cache):
    """用户 A 的缓存用户 B 读不到"""
    await cache.set_isolated("budget:summary", "A的数据", user_id=42)
    # 用户 B 读
    result = await cache.get_isolated("budget:summary", user_id=99)
    assert result is None  # 隔离生效
```

**降级测试要点**：禁用真实依赖（conftest 已设），断言返回明确的降级标注（`mode: "feature_disabled"` / `[mock]` / 503），而非伪造数据。

## 禁止事项

- ❌ 测试里调真实 LLM/语音/渲染 API（conftest 已禁用 key）
- ❌ 自建 AsyncClient 或 DB session（用 `client` / `db_session` fixture）
- ❌ 测试间共享状态（`setup_db` autouse 已隔离，勿绕过）
- ❌ 用 `pytest.skip` 跳过已知 bug（应修复或标记 `xfail`）
- ❌ 测试依赖执行顺序（xdist 并行下不保证顺序）

## e2e 测试

`tests/e2e/` 有独立 conftest，覆盖完整业务流：

- `test_e2e_auth_flow.py` —— 注册→登录→token 刷新→登出
- `test_e2e_project_lifecycle.py` —— 创建项目→设计→预算→采购→施工→验收

e2e 标记 `@pytest.mark.e2e`，可单独跑：`pytest -m e2e`

## 覆盖率

- `.coveragerc` 配置
- 新增 API 模块必须 100% 有对应 `test_*.py`（v1.2.5 教训：曾 37 个 API 零测试）
- 重点模块（auth / cache / agents）目标覆盖率 >90%

## 运行命令速查

```bash
pytest                                    # 全量
pytest tests/test_auth.py -v              # 单文件详细
pytest -k "register or login"             # 按名筛选
pytest -m "not slow"                      # 跳过慢测试
pytest --lf                               # 只跑上次失败的
pytest -n 4                               # 4 进程并行
pytest tests/e2e/ -m e2e                  # e2e 套件
pre-commit run --all-files                # 提交前
```

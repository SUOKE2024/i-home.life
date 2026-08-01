# 新增 API 模板（new-api.md）

> 新增 API 端点的标准 checklist。吸取 v1.2.5 教训（曾 37 个 API 模块零测试）。
> 每新增一个 API 端点，逐项打勾。**遗漏任一项 = 未完成。**

## 涉及文件（5 处必改）

```
app/
├── models/xxx.py           # ORM 模型（如涉及新表）
├── schemas/xxx.py          # Pydantic 请求/响应模型
├── services/xxx_service.py # 业务逻辑
├── api/xxx.py              # 路由层
└── main.py                 # 注册 router（1 行）
tests/
└── test_xxx.py             # 测试（必补！）
```

## Checklist

### 1. ORM 模型（如涉及新表）

参考 [app/models/user.py](file:///Users/netsong/Developer/i-home.life/app/models/user.py)：

- [ ] 继承 `Base`（`from app.database import Base`）
- [ ] `__tablename__` 用复数 snake_case（如 `projects`）
- [ ] 主键 `id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))`
- [ ] `created_at` / `updated_at` 用 `DateTime(timezone=True)` + `server_default=func.now()`
- [ ] 关系字段用 `relationship` + `back_populates`
- [ ] 若涉及用户数据，加 `user_id` 外键 + 索引（缓存隔离前提）
- [ ] schema 迁移：新增 alembic 脚本 **或** 在 [database.py:_run_lightweight_migrations](file:///Users/netsong/Developer/i-home.life/app/database.py) 加 ALTER TABLE + 递增 `_SCHEMA_MIGRATION_VERSION`
- [ ] 跑 `python scripts/check_schema_drift.py` 验证无漂移

### 2. Pydantic Schema

参考 [app/schemas/user.py](file:///Users/netsong/Developer/i-home.life/app/schemas/user.py)：

- [ ] `XxxCreate` —— 请求体，字段加 `Field(min_length=..., max_length=...)` 约束
- [ ] `XxxUpdate` —— 更新体，可选字段用 `X | None = None`
- [ ] `XxxResponse` —— 响应体，加 `model_config = {"from_attributes": True}`（从 ORM 转换）
- [ ] `XxxListResponse` —— 列表响应（如需要）
- [ ] **响应模型不含敏感字段**（如 `hashed_password`）

### 3. Service 层

参考 [app/services/project_service.py](file:///Users/netsong/Developer/i-home.life/app/services/project_service.py)：

- [ ] 用函数式（`async def create_xxx(db: AsyncSession, ...) -> XxxModel`）
- [ ] 第一参数 `db: AsyncSession`，不自行创建 session
- [ ] 业务校验失败 `raise HTTPException(...)` 或自定义业务异常（如 `ProjectStateError`）
- [ ] 状态机用 `VALID_TRANSITIONS` dict + `_assert_transition`（参考 project_service.py）
- [ ] **缓存**：私有数据用 `cache.set_isolated/get_isolated`，**禁止**裸 `cache.set` 存私有数据
- [ ] 外部依赖不可用时诚实降级（返回 503 / 占位 + 标注），**禁止**硬编码假数据

### 4. 路由层

参考 [app/api/projects.py](file:///Users/netsong/Developer/i-home.life/app/api/projects.py)：

- [ ] `router = APIRouter(prefix="/xxx", tags=["xxx"])`
- [ ] 每个端点声明 `response_model`、`status_code`、`summary`、`description`、`responses`
- [ ] 认证：`current_user: User = Depends(get_current_user)`
- [ ] DB：`db: AsyncSession = Depends(get_db)`
- [ ] **越权校验**：访问他人资源时 `await verify_project_access(project_id, current_user, db)`（参考 [app/rbac.py](file:///Users/netsong/Developer/i-home.life/app/rbac.py)）
- [ ] 路由层保持薄，业务逻辑放 service

### 5. 注册路由

- [ ] [app/main.py](file:///Users/netsong/Developer/i-home.life/app/main.py) 加 `api_router.include_router(xxx.router)  # /api/xxx/*`
- [ ] 注意注册顺序：特定前缀（如 `/products/batch`）必须在通用前缀（`/products`）之前（main.py:349 注释）

### 6. 测试（必补！v1.2.5 教训）

参考 [tests/test_auth.py](file:///Users/netsong/Developer/i-home.life/tests/test_auth.py)：

- [ ] 正常路径：200/201 + 数据正确
- [ ] 错误路径：400/404/409/422 + detail 准确
- [ ] 无认证 → 401
- [ ] **越权（IDOR）**：用户 A 访问用户 B 资源 → 403（参考 `tests/test_design_modules_idor.py`）
- [ ] 缓存隔离（如涉及缓存）：跨用户读不到
- [ ] 降级分支（如涉及外部依赖）：不可用时诚实降级

### 7. 质量门禁

```bash
pytest tests/test_xxx.py -v       # 新测试通过
pytest                            # 全量不回退
pre-commit run --all-files        # flake8/mypy
python scripts/check_schema_drift.py  # schema 无漂移
```

## 完整示例骨架

```python
# app/schemas/budget.py
from pydantic import BaseModel, Field
class BudgetCreate(BaseModel):
    project_id: str
    total_amount: float = Field(ge=0)
class BudgetResponse(BaseModel):
    id: str
    project_id: str
    total_amount: float
    model_config = {"from_attributes": True}
```

```python
# app/services/budget_service.py
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.budget import Budget
from app.services.cache_service import cache

async def get_budget(db: AsyncSession, budget_id: str, user_id: str) -> Budget | None:
    # 先查缓存（隔离）
    cached = await cache.get_isolated("budget:detail", user_id=user_id, project_id=budget_id)
    if cached:
        return cached
    # 查 DB
    ...
    await cache.set_isolated("budget:detail", budget, user_id=user_id, project_id=budget_id, ttl=300)
    return budget
```

```python
# app/api/budgets.py
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from app.auth import get_current_user
from app.models.user import User
from app.rbac import verify_project_access
from app.services.budget_service import get_budget

router = APIRouter(prefix="/budgets", tags=["预算"])

@router.get("/{budget_id}", response_model=BudgetResponse)
async def get_budget_detail(
    budget_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    budget = await get_budget(db, budget_id, current_user.id)
    if not budget:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "预算不存在")
    await verify_project_access(budget.project_id, current_user, db)
    return BudgetResponse.model_validate(budget)
```

```python
# tests/test_budgets.py
import pytest
from httpx import AsyncClient

@pytest.mark.asyncio
async def test_get_budget_unauthorized(client: AsyncClient):
    """无认证 → 401"""
    resp = await client.get("/api/budgets/xxx")
    assert resp.status_code == 401

@pytest.mark.asyncio
async def test_get_budget_idor(client: AsyncClient, auth_headers: dict):
    """越权访问他人预算 → 403"""
    resp = await client.get("/api/budgets/other-user-budget-id", headers=auth_headers)
    assert resp.status_code == 403
```

## 勿忘

- 版本号若涉及前端联调，参考 `.claude/templates/version-bump.md` 同步
- 新增 feature flag 时同步 `config.py` + `.env.example` + `.env.production.example`
- CHANGELOG.md 记录变更（参考现有格式）

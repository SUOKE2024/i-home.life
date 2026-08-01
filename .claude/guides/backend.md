# 后端开发规范（backend.md）

> 后端 Python / FastAPI / ORM / alembic / PASETO / 缓存规范。所有事实基于当前代码，
> 改代码前先读对应源码确认模式未变。**只写项目特有约定，通用 Python/FastAPI 规范不重复。**

## 分层结构

```
app/
├── api/            # 路由层（HTTP 端点，薄）
├── services/       # 业务层（核心逻辑）
├── models/         # ORM 模型（SQLAlchemy 2.0 Mapped 风格）
├── schemas/        # Pydantic 请求/响应模型
├── agents/         # 22 个 AI Agent（见 mcp-agent.md）
├── auth/           # PASETO 鉴权
├── mcp/            # MCP 协议（见 mcp-agent.md）
└── middleware/     # 中间件
```

## 路由层约定

每个 API 模块用 `APIRouter(prefix="/xxx", tags=["xxx"])`，在 `app/main.py` 通过 `api_router.include_router(xxx.router)` 注册（见 main.py:347+）。主路由前缀 `/api`。

**标准路由写法**（参考 [app/api/auth.py](file:///Users/netsong/Developer/i-home.life/app/api/auth.py)）：

```python
from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from app.auth import get_current_user
from app.models.user import User

router = APIRouter(prefix="/projects", tags=["项目"])

@router.post("/", response_model=ProjectResponse, status_code=status.HTTP_201_CREATED)
async def create_project(
    data: ProjectCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    ...
```

- 路由层保持**薄**，业务逻辑放 `app/services/`
- 认证用 `Depends(get_current_user)`（来自 `app/auth`）
- 错误用 `raise HTTPException(status_code=..., detail=...)`
- 响应必须声明 `response_model`
- 路由注册顺序敏感：`product_batch` 必须在 `products` 之前（main.py:349 注释）

## ORM 模型约定

基类在 [app/database.py:43](file:///Users/netsong/Developer/i-home.life/app/database.py) `class Base(DeclarativeBase)`。用 SQLAlchemy 2.0 `Mapped` 风格（参考 [app/models/user.py](file:///Users/netsong/Developer/i-home.life/app/models/user.py)）：

```python
from sqlalchemy import String, DateTime, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base

class User(Base):
    __tablename__ = "users"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    projects = relationship("Project", back_populates="owner")
```

- 主键用 `String(36)` + `uuid.uuid4()`（非自增整数）
- 时间字段 `created_at`/`updated_at` 用 `DateTime(timezone=True)` + `server_default=func.now()`
- 关系用 `relationship` + `back_populates`（双向）
- 字段命名 snake_case，类名 PascalCase

## DB Session

`get_db` 异步生成器依赖（[app/database.py:47](file:///Users/netsong/Developer/i-home.life/app/database.py)）：

```python
async def get_db() -> AsyncSession:
    async with async_session() as session:
        try:
            yield session
        finally:
            await session.close()
```

- 开发 SQLite（StaticPool），生产 PostgreSQL（AsyncAdaptedQueuePool，pool_size=20）
- **禁止**在路由外直接用 `async_session()`，要走依赖注入
- `expire_on_commit=False` 已配置，commit 后对象仍可用

## schema 迁移（双轨制，勿混用）

1. **alembic 迁移**（`alembic/versions/`，标准 schema 变更走这条）
   - `alembic/env.py` 配置，`upgrade()`/`downgrade()` 函数
   - `op.create_table` / `op.add_column` 标准写法
2. **轻量级迁移**（`app/database.py:_run_lightweight_migrations`，仅给已有表加列）
   - 用 `inspect.has_table` 检查（**禁止** SELECT 不存在的表，PG 会事务污染）
   - 有 `_SCHEMA_MIGRATION_VERSION` 版本号，已应用则跳过
   - 新增列要同时在 `_run_lightweight_migrations` 加 ALTER TABLE + 递增版本号

**规则**：新增表/列时，ORM 模型 + alembic 迁移脚本 + （如适用）轻量级迁移，三处同步。改完跑 `scripts/check_schema_drift.py` 验证无漂移。

## PASETO 鉴权

完整实现在 [app/auth/paseto_handler.py](file:///Users/netsong/Developer/i-home.life/app/auth/paseto_handler.py)：

```python
# 创建 token
from app.auth.paseto_handler import create_token
token = create_token(user_id="xxx", role="homeowner")

# 验证 token（在依赖里用，业务代码通常不直接调）
from app.auth.paseto_handler import verify_token, TokenExpiredError, TokenInvalidError
payload = verify_token(token)  # 返回 {sub, role, iat, exp}
```

- 协议 `v4.local`，**禁止**改用 JWT
- 密钥 ≥32 字节，`paseto_strict_mode=True` 时硬校验（config.py `_validate_paseto_key`）
- 依赖注入用 `from app.auth import get_current_user`（路由层用 `Depends(get_current_user)`）
- 角色：homeowner / designer / contractor / supplier / admin
- 权限校验见 [app/rbac.py](file:///Users/netsong/Developer/i-home.life/app/rbac.py)

## 缓存服务

完整实现在 [app/services/cache_service.py](file:///Users/netsong/Developer/i-home.life/app/services/cache_service.py)，全局单例 `cache`：

```python
from app.services.cache_service import cache, build_isolated_key

# 私有数据（必须含 user_id）—— 推荐
await cache.set_isolated("budget:summary", value, user_id=42, project_id=7, ttl=300)
value = await cache.get_isolated("budget:summary", user_id=42, project_id=7)

# 公共数据（显式标注 public=True）
await cache.set_isolated("feature-flags", value, public=True, ttl=60)

# 原始 key 方式（仅公共数据用，私有数据必须走 isolated 方法）
await cache.set("public:xxx", value, ttl=300)

# 失效某用户全部缓存（登出/权限变更时）
await cache.invalidate_user_keys(user_id=42)
```

- **硬约束**：私有数据 cache key 必须含 `user_id`，`cache_user_isolation_strict=True` 时未传直接 raise
- key 格式：`public:{base}` 或 `u:{user_id}:p:{project_id}:{base}`
- 后端 Redis 优先，降级内存 dict（开发/测试环境）
- `delete_pattern` 用 SCAN 非阻塞（**禁止** `redis.keys()`，O(N) 阻塞主线程）

## Service 层约定

参考 [app/services/user_service.py](file:///Users/netsong/Developer/i-home.life/app/services/user_service.py)：

- 用**函数**或**类**均可，当前以函数为主（如 `create_user(db, data)`）
- 第一参数始终是 `db: AsyncSession`
- 错误用 `raise HTTPException(...)` 或自定义业务异常
- 密码哈希用 bcrypt（`_hash_password` / `_verify_password`），兼容历史 SHA256+salt/MD5 格式

## 配置与 feature flag

所有配置在 [app/config.py](file:///Users/netsong/Developer/i-home.life/app/config.py) `Settings` 类，用 `pydantic_settings`：

- 读配置用 `from app.config import get_settings`（`@lru_cache` 单例）
- 改 feature flag 默认值要同时改 `config.py` + `.env.example` + `.env.production.example`
- 灰度特性默认 False，验证后开 True

## 降级原则

任何外部依赖（LLM / Redis / OSS / 向量库 / 渲染后端）不可用时，**诚实降级**：

- 明确返回 503 / 占位结果 + 标注 `mode: "feature_disabled"` 或 `degraded: true`
- **禁止**用硬编码假数据伪装真实能力（v1.1.31 修复 6 处此类问题）
- 降级路径必须可测试（写测试覆盖降级分支）

## 质量门禁

```bash
pytest                                    # 全量测试，基线 1491 passed 不得回退
pre-commit run --all-files                # flake8 + trailing-whitespace + detect-private-key
mypy app/                                 # 静态类型
python scripts/check_schema_drift.py      # schema 漂移检查
```

新增 API 必须补 `tests/test_xxx.py`（v1.2.5 教训：曾 37 个 API 模块零测试）。

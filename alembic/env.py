"""Alembic 环境配置

支持 SQLite (Phase 1) 与 PostgreSQL (Phase 2) 双数据库,
通过 DATABASE_URL 环境变量自动切换。
"""

import os
from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

# 项目根目录加入 sys.path
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.config import get_settings
from app.database import Base

# 导入所有模型,确保 autogenerate 能检测到
from app.models import user, project, material, budget, procurement, construction, settlement, floorplan, file_attachment  # noqa: F401
from app.models import survey, change_order, payment, chat, construction_crew, progress_alert, quality, service_worker  # noqa: F401

config = context.config

# 从应用 settings 注入数据库 URL
settings = get_settings()
config.set_main_option("sqlalchemy.url", settings.database_url.replace("+aiosqlite", "").replace("+asyncpg", ""))

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """离线模式:生成 SQL 脚本"""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """在线模式:直接连接数据库执行"""
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()

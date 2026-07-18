from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine, AsyncSession
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy import select, func
from sqlalchemy.pool import StaticPool

from app.config import get_settings

settings = get_settings()

# SQLite 使用 StaticPool 保持单连接，避免文件锁定和 selectinload 兼容问题
_engine_kwargs = {"echo": settings.debug}
if "sqlite" in settings.database_url:
    _engine_kwargs["poolclass"] = StaticPool
    _engine_kwargs["connect_args"] = {"check_same_thread": False}

engine = create_async_engine(settings.database_url, **_engine_kwargs)

async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


async def get_db() -> AsyncSession:
    async with async_session() as session:
        try:
            yield session
        finally:
            await session.close()


async def _run_lightweight_migrations():  # noqa: C901
    """轻量级 schema 迁移：为已有表添加缺失列。

    SQLAlchemy 的 create_all 只创建不存在的表，不会给已有表添加新列。
    此函数检查关键表的列并执行 ALTER TABLE ADD COLUMN。
    生产环境中应在 init_db() 后自动调用。
    """
    from sqlalchemy import text, inspect
    import logging

    async with engine.begin() as conn:
        def _get_table_columns(sync_conn, table_name):
            insp = inspect(sync_conn)
            if not insp.has_table(table_name):
                return None
            return [col["name"] for col in insp.get_columns(table_name)]

        # 检查 users 表
        user_cols = await conn.run_sync(
            lambda sync_conn: _get_table_columns(sync_conn, "users")
        )
        if user_cols is not None:
            user_migrations = [
                ("users", "sub_role", "VARCHAR(30)"),
                ("users", "is_verified", "BOOLEAN DEFAULT 0 NOT NULL"),
            ]
            for table, column, coltype in user_migrations:
                if column not in user_cols:
                    await conn.execute(
                        text(f"ALTER TABLE {table} ADD COLUMN {column} {coltype}")
                    )
                    logging.getLogger("ihome").info(
                        f"migration: ALTER TABLE {table} ADD COLUMN {column} {coltype}"
                    )

        # 检查 projects 表（v1.0.14 修复：project_type/source/scan_session_id
        # 在模型中存在但 init 迁移未包含，导致生产库查询 500）
        project_cols = await conn.run_sync(
            lambda sync_conn: _get_table_columns(sync_conn, "projects")
        )
        if project_cols is not None:
            project_migrations = [
                ("projects", "project_type", "VARCHAR(30) NOT NULL DEFAULT 'full_renovation'"),
                ("projects", "source", "VARCHAR(20) NOT NULL DEFAULT 'manual'"),
                ("projects", "scan_session_id", "VARCHAR(36)"),
            ]
            for table, column, coltype in project_migrations:
                if column not in project_cols:
                    await conn.execute(
                        text(f"ALTER TABLE {table} ADD COLUMN {column} {coltype}")
                    )
                    logging.getLogger("ihome").info(
                        f"migration: ALTER TABLE {table} ADD COLUMN {column} {coltype}"
                    )

        # RBAC 权限表：检查并创建 permissions 和 role_permissions 表
        # 这些表可能已在 create_all 中创建；若 SQLite 增量模式，则手动添加
        _has_permissions = bool(await conn.run_sync(
            lambda sync_conn: _get_table_columns(sync_conn, "permissions")
        ))
        if not _has_permissions:
            await conn.execute(text(
                "CREATE TABLE IF NOT EXISTS permissions ("
                "  id VARCHAR(36) PRIMARY KEY,"
                "  code VARCHAR(100) UNIQUE NOT NULL,"
                "  name VARCHAR(200) NOT NULL,"
                "  resource VARCHAR(100) NOT NULL,"
                "  action VARCHAR(50) NOT NULL,"
                "  description VARCHAR(500),"
                "  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP"
                ")"
            ))
            logging.getLogger("ihome").info("migration: CREATE TABLE permissions")

        # 检查 payments 表（F15 分阶段支付 / 电子发票字段）
        payment_cols = await conn.run_sync(
            lambda sync_conn: _get_table_columns(sync_conn, "payments")
        )
        if payment_cols is not None:
            payment_migrations = [
                ("payments", "stage_code", "VARCHAR(30)"),
                ("payments", "stage_order", "INTEGER DEFAULT 0 NOT NULL"),
                ("payments", "due_at", "TIMESTAMP"),
                ("payments", "invoice_no", "VARCHAR(50)"),
                ("payments", "invoice_url", "VARCHAR(500)"),
                ("payments", "invoiced_at", "TIMESTAMP"),
            ]
            for table, column, coltype in payment_migrations:
                if column not in payment_cols:
                    await conn.execute(
                        text(f"ALTER TABLE {table} ADD COLUMN {column} {coltype}")
                    )
                    logging.getLogger("ihome").info(
                        f"migration: ALTER TABLE {table} ADD COLUMN {column} {coltype}"
                    )

        # 检查 settlements 表（F14 异常检测与人工复核字段）
        settlement_cols = await conn.run_sync(
            lambda sync_conn: _get_table_columns(sync_conn, "settlements")
        )
        if settlement_cols is not None:
            settlement_migrations = [
                ("settlements", "anomaly_count", "INTEGER DEFAULT 0 NOT NULL"),
                ("settlements", "critical_anomaly_count", "INTEGER DEFAULT 0 NOT NULL"),
                ("settlements", "suggested_deduction", "FLOAT DEFAULT 0.0 NOT NULL"),
                ("settlements", "review_required", "BOOLEAN DEFAULT 0 NOT NULL"),
                ("settlements", "review_reason", "VARCHAR(500)"),
                ("settlements", "reviewed_by", "VARCHAR(36)"),
            ]
            for table, column, coltype in settlement_migrations:
                if column not in settlement_cols:
                    await conn.execute(
                        text(f"ALTER TABLE {table} ADD COLUMN {column} {coltype}")
                    )
                    logging.getLogger("ihome").info(
                        f"migration: ALTER TABLE {table} ADD COLUMN {column} {coltype}"
                    )

        # 检查 settlement_lines 表（F14 异常标记字段）
        settlement_line_cols = await conn.run_sync(
            lambda sync_conn: _get_table_columns(sync_conn, "settlement_lines")
        )
        if settlement_line_cols is not None:
            settlement_line_migrations = [
                ("settlement_lines", "is_anomaly", "BOOLEAN DEFAULT 0 NOT NULL"),
                ("settlement_lines", "anomaly_type", "VARCHAR(50)"),
                ("settlement_lines", "anomaly_severity", "VARCHAR(20)"),
                ("settlement_lines", "anomaly_detail", "VARCHAR(500)"),
            ]
            for table, column, coltype in settlement_line_migrations:
                if column not in settlement_line_cols:
                    await conn.execute(
                        text(f"ALTER TABLE {table} ADD COLUMN {column} {coltype}")
                    )
                    logging.getLogger("ihome").info(
                        f"migration: ALTER TABLE {table} ADD COLUMN {column} {coltype}"
                    )

        # 检查 file_attachments 表（message_id 外键字段）
        fa_cols = await conn.run_sync(
            lambda sync_conn: _get_table_columns(sync_conn, "file_attachments")
        )
        if fa_cols is not None:
            fa_migrations = [
                ("file_attachments", "message_id", "VARCHAR(36)"),
            ]
            for table, column, coltype in fa_migrations:
                if column not in fa_cols:
                    await conn.execute(
                        text(f"ALTER TABLE {table} ADD COLUMN {column} {coltype}")
                    )
                    logging.getLogger("ihome").info(
                        f"migration: ALTER TABLE {table} ADD COLUMN {column} {coltype}"
                    )

        _has_role_permissions = bool(await conn.run_sync(
            lambda sync_conn: _get_table_columns(sync_conn, "role_permissions")
        ))
        if not _has_role_permissions:
            await conn.execute(text(
                "CREATE TABLE IF NOT EXISTS role_permissions ("
                "  id VARCHAR(36) PRIMARY KEY,"
                "  role VARCHAR(30) NOT NULL,"
                "  permission_code VARCHAR(100) NOT NULL REFERENCES permissions(code),"
                "  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,"
                "  UNIQUE(role, permission_code)"
                ")"
            ))
            logging.getLogger("ihome").info("migration: CREATE TABLE role_permissions")


async def init_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    # 轻量级 schema 迁移：检查并添加缺失列（防止 create_all 不更新已有表）
    await _run_lightweight_migrations()

    from app.models.user import User
    from app.models.material import MaterialCategory, Material
    from app.models.procurement import Supplier
    from app.services.user_service import _hash_password

    async with async_session() as db:
        result = await db.execute(select(func.count()).select_from(User))
        if result.scalar() > 0:
            return

        categories = [
            {"name": "地面材料", "code": "flooring", "description": "瓷砖、地板、石材等"},
            {"name": "墙面材料", "code": "wall", "description": "乳胶漆、墙布、墙砖等"},
            {"name": "顶面材料", "code": "ceiling", "description": "吊顶、石膏线等"},
            {"name": "厨卫设备", "code": "kitchen_bath", "description": "橱柜、卫浴、五金等"},
            {"name": "门窗", "code": "doors_windows", "description": "室内门、入户门、窗户等"},
            {"name": "水电材料", "code": "mep", "description": "电线、水管、开关插座等"},
            {"name": "定制家具", "code": "custom_furniture", "description": "衣柜、书柜、榻榻米等"},
            {"name": "软装", "code": "soft_decor", "description": "窗帘、灯具、挂画等"},
            {"name": "家电", "code": "appliances", "description": "空调、冰箱、洗衣机等"},
        ]
        for cat_data in categories:
            db.add(MaterialCategory(**cat_data))
        await db.flush()

        result = await db.execute(select(MaterialCategory))
        category_map = {cat.code: cat.id for cat in result.scalars().all()}

        materials = [
            # 地面材料 (30)
            {"category_code": "flooring", "name": "750×1500 大板砖", "sku": "FLR-001", "unit": "㎡", "unit_price": 198.0, "brand": "东鹏", "spec": "750×1500mm 亮面"},
            {"category_code": "flooring", "name": "600×1200 木纹砖", "sku": "FLR-002", "unit": "㎡", "unit_price": 128.0, "brand": "马可波罗", "spec": "600×1200mm 木纹"},
            {"category_code": "flooring", "name": "强化复合地板", "sku": "FLR-003", "unit": "㎡", "unit_price": 158.0, "brand": "圣象", "spec": "12mm 耐磨"},
            {"category_code": "flooring", "name": "实木多层地板", "sku": "FLR-004", "unit": "㎡", "unit_price": 328.0, "brand": "大自然", "spec": "15mm 橡木"},
            {"category_code": "flooring", "name": "防滑地砖", "sku": "FLR-005", "unit": "㎡", "unit_price": 88.0, "brand": "东鹏", "spec": "300×300mm"},
            {"category_code": "flooring", "name": "大理石门槛", "sku": "FLR-006", "unit": "条", "unit_price": 120.0, "brand": "天然大理石", "spec": "900×150mm"},
            {"category_code": "flooring", "name": "600×600 抛光砖", "sku": "FLR-007", "unit": "㎡", "unit_price": 68.0, "brand": "诺贝尔", "spec": "600×600mm"},
            {"category_code": "flooring", "name": "900×900 柔光砖", "sku": "FLR-008", "unit": "㎡", "unit_price": 168.0, "brand": "冠珠", "spec": "900×900mm 柔光"},
            {"category_code": "flooring", "name": "实木地板", "sku": "FLR-009", "unit": "㎡", "unit_price": 580.0, "brand": "安信", "spec": "910×125×18mm 柚木"},
            {"category_code": "flooring", "name": "SPC石塑地板", "sku": "FLR-010", "unit": "㎡", "unit_price": 88.0, "brand": "肯帝亚", "spec": "4mm 防水"},
            {"category_code": "flooring", "name": "水磨石地砖", "sku": "FLR-011", "unit": "㎡", "unit_price": 238.0, "brand": "欧神诺", "spec": "600×600mm"},
            {"category_code": "flooring", "name": "亚光木纹砖", "sku": "FLR-012", "unit": "㎡", "unit_price": 148.0, "brand": "鹰牌", "spec": "200×1200mm"},
            {"category_code": "flooring", "name": "防静电地板", "sku": "FLR-013", "unit": "㎡", "unit_price": 298.0, "brand": "汇丽", "spec": "600×600×35mm"},
            {"category_code": "flooring", "name": "自流平水泥", "sku": "FLR-014", "unit": "㎡", "unit_price": 45.0, "brand": "汉高", "spec": "5mm厚"},
            {"category_code": "flooring", "name": "进口强化地板", "sku": "FLR-015", "unit": "㎡", "unit_price": 228.0, "brand": "快步QuickStep", "spec": "8mm 比利时进口"},
            {"category_code": "flooring", "name": "户外防腐木地板", "sku": "FLR-016", "unit": "㎡", "unit_price": 380.0, "brand": "丰胜", "spec": "140×25mm 樟子松"},
            {"category_code": "flooring", "name": "天然大理石地砖", "sku": "FLR-017", "unit": "㎡", "unit_price": 680.0, "brand": "高时", "spec": "800×800mm 爵士白"},
            {"category_code": "flooring", "name": "微水泥地面", "sku": "FLR-018", "unit": "㎡", "unit_price": 320.0, "brand": "TT微水泥", "spec": "3mm 无缝"},
            {"category_code": "flooring", "name": "瓷砖胶", "sku": "FLR-019", "unit": "包", "unit_price": 55.0, "brand": "德高", "spec": "20kg C2型"},
            {"category_code": "flooring", "name": "美缝剂", "sku": "FLR-020", "unit": "支", "unit_price": 88.0, "brand": "卓高", "spec": "400ml 亚浅灰"},
            {"category_code": "flooring", "name": "水泥砂浆", "sku": "FLR-021", "unit": "吨", "unit_price": 480.0, "brand": "海螺", "spec": "M10砌筑"},
            {"category_code": "flooring", "name": "900×1800岩板", "sku": "FLR-022", "unit": "㎡", "unit_price": 480.0, "brand": "蒙娜丽莎", "spec": "900×1800mm 连纹"},
            {"category_code": "flooring", "name": "金刚砂耐磨地坪", "sku": "FLR-023", "unit": "㎡", "unit_price": 68.0, "brand": "西卡", "spec": "5kg/㎡"},
            {"category_code": "flooring", "name": "实木踢脚线", "sku": "FLR-024", "unit": "m", "unit_price": 28.0, "brand": "大自然", "spec": "80×12mm 实木"},
            {"category_code": "flooring", "name": "铝合金踢脚线", "sku": "FLR-025", "unit": "m", "unit_price": 22.0, "brand": "法狮龙", "spec": "60mm高 极简"},
            {"category_code": "flooring", "name": "水泥自流平找平", "sku": "FLR-026", "unit": "㎡", "unit_price": 35.0, "brand": "德高", "spec": "3mm"},
            {"category_code": "flooring", "name": "蓄光防滑踏步砖", "sku": "FLR-027", "unit": "㎡", "unit_price": 158.0, "brand": "东鹏", "spec": "300×300mm"},
            {"category_code": "flooring", "name": "地毯砖", "sku": "FLR-028", "unit": "㎡", "unit_price": 178.0, "brand": "ICC", "spec": "600×600mm"},
            {"category_code": "flooring", "name": "弹性地板胶", "sku": "FLR-029", "unit": "桶", "unit_price": 185.0, "brand": "汉高百得", "spec": "5kg"},
            {"category_code": "flooring", "name": "岩板背景墙地台", "sku": "FLR-030", "unit": "m", "unit_price": 298.0, "brand": "蒙娜丽莎", "spec": "800×2600mm"},
            # 墙面材料 (25)
            {"category_code": "wall", "name": "净味乳胶漆", "sku": "WLL-001", "unit": "桶", "unit_price": 680.0, "brand": "立邦", "spec": "18L 净味"},
            {"category_code": "wall", "name": "400×800 瓷片", "sku": "WLL-002", "unit": "㎡", "unit_price": 88.0, "brand": "东鹏", "spec": "400×800mm 亮面"},
            {"category_code": "wall", "name": "艺术漆", "sku": "WLL-003", "unit": "㎡", "unit_price": 280.0, "brand": "嘉宝莉", "spec": "雅晶石系列"},
            {"category_code": "wall", "name": "无纺布墙布", "sku": "WLL-004", "unit": "㎡", "unit_price": 168.0, "brand": "欧雅", "spec": "2.8m幅宽"},
            {"category_code": "wall", "name": "防水涂料", "sku": "WLL-005", "unit": "桶", "unit_price": 420.0, "brand": "雨虹", "spec": "18kg JS防水"},
            {"category_code": "wall", "name": "300×600 瓷片", "sku": "WLL-006", "unit": "㎡", "unit_price": 58.0, "brand": "马可波罗", "spec": "300×600mm"},
            {"category_code": "wall", "name": "硅藻泥", "sku": "WLL-007", "unit": "㎡", "unit_price": 198.0, "brand": "兰舍", "spec": "2mm厚 平涂"},
            {"category_code": "wall", "name": "肌理漆", "sku": "WLL-008", "unit": "㎡", "unit_price": 238.0, "brand": "立邦", "spec": "质感系列"},
            {"category_code": "wall", "name": "PVC墙纸", "sku": "WLL-009", "unit": "卷", "unit_price": 158.0, "brand": "玉兰", "spec": "0.53×10m"},
            {"category_code": "wall", "name": "护墙板", "sku": "WLL-010", "unit": "㎡", "unit_price": 328.0, "brand": "法狮龙", "spec": "实木多层 5mm"},
            {"category_code": "wall", "name": "岩板上墙", "sku": "WLL-011", "unit": "㎡", "unit_price": 780.0, "brand": "蒙娜丽莎", "spec": "800×2600mm 连纹"},
            {"category_code": "wall", "name": "水泥艺术墙面", "sku": "WLL-012", "unit": "㎡", "unit_price": 360.0, "brand": "磐多魔", "spec": "3mm 无缝"},
            {"category_code": "wall", "name": "金属饰面板", "sku": "WLL-013", "unit": "㎡", "unit_price": 450.0, "brand": "阿鲁克邦", "spec": "3mm 铝塑板"},
            {"category_code": "wall", "name": "木饰面", "sku": "WLL-014", "unit": "㎡", "unit_price": 420.0, "brand": "科定", "spec": "3mm 科技木皮"},
            {"category_code": "wall", "name": "镜面玻璃", "sku": "WLL-015", "unit": "㎡", "unit_price": 288.0, "brand": "台玻", "spec": "5mm 银镜"},
            {"category_code": "wall", "name": "耐水腻子", "sku": "WLL-016", "unit": "袋", "unit_price": 38.0, "brand": "美巢", "spec": "20kg"},
            {"category_code": "wall", "name": "墙固界面剂", "sku": "WLL-017", "unit": "桶", "unit_price": 128.0, "brand": "美巢", "spec": "18kg"},
            {"category_code": "wall", "name": "防霉乳胶漆", "sku": "WLL-018", "unit": "桶", "unit_price": 780.0, "brand": "多乐士", "spec": "18L 森呼吸"},
            {"category_code": "wall", "name": "黑板漆", "sku": "WLL-019", "unit": "桶", "unit_price": 298.0, "brand": "芬琳", "spec": "2.7L"},
            {"category_code": "wall", "name": "磁性漆", "sku": "WLL-020", "unit": "桶", "unit_price": 360.0, "brand": "福乐阁", "spec": "1L"},
            {"category_code": "wall", "name": "纤维墙布", "sku": "WLL-021", "unit": "㎡", "unit_price": 220.0, "brand": "艾是", "spec": "2.8m幅宽"},
            {"category_code": "wall", "name": "PU线条", "sku": "WLL-022", "unit": "m", "unit_price": 45.0, "brand": "法式线条", "spec": "3cm宽"},
            {"category_code": "wall", "name": "瓷砖背胶", "sku": "WLL-023", "unit": "桶", "unit_price": 168.0, "brand": "雨虹", "spec": "5kg"},
            {"category_code": "wall", "name": "免漆板", "sku": "WLL-024", "unit": "张", "unit_price": 198.0, "brand": "兔宝宝", "spec": "2440×1220×18mm"},
            {"category_code": "wall", "name": "竹木纤维墙板", "sku": "WLL-025", "unit": "㎡", "unit_price": 168.0, "brand": "科吉星", "spec": "9mm"},
            # 顶面材料 (15)
            {"category_code": "ceiling", "name": "铝扣板吊顶", "sku": "CEL-001", "unit": "㎡", "unit_price": 128.0, "brand": "欧普", "spec": "300×300mm"},
            {"category_code": "ceiling", "name": "石膏板吊顶", "sku": "CEL-002", "unit": "㎡", "unit_price": 95.0, "brand": "龙牌", "spec": "9.5mm"},
            {"category_code": "ceiling", "name": "集成吊顶电器", "sku": "CEL-003", "unit": "台", "unit_price": 980.0, "brand": "欧普", "spec": "300×600 五合一"},
            {"category_code": "ceiling", "name": "石膏线", "sku": "CEL-004", "unit": "m", "unit_price": 18.0, "brand": "银桥", "spec": "8cm 素线"},
            {"category_code": "ceiling", "name": "轻钢龙骨", "sku": "CEL-005", "unit": "m", "unit_price": 8.0, "brand": "龙牌", "spec": "38×12×1.0"},
            {"category_code": "ceiling", "name": "矿棉板吊顶", "sku": "CEL-006", "unit": "㎡", "unit_price": 78.0, "brand": "星牌", "spec": "600×600×14mm"},
            {"category_code": "ceiling", "name": "PVC扣板", "sku": "CEL-007", "unit": "㎡", "unit_price": 48.0, "brand": "联塑", "spec": "200mm宽"},
            {"category_code": "ceiling", "name": "防水石膏板", "sku": "CEL-008", "unit": "张", "unit_price": 58.0, "brand": "龙牌", "spec": "9.5mm 耐水"},
            {"category_code": "ceiling", "name": "暖风机", "sku": "CEL-009", "unit": "台", "unit_price": 1280.0, "brand": "松下", "spec": "300×300 遥控"},
            {"category_code": "ceiling", "name": "换气扇", "sku": "CEL-010", "unit": "台", "unit_price": 368.0, "brand": "艾美特", "spec": "300×300 静音"},
            {"category_code": "ceiling", "name": "线型灯槽", "sku": "CEL-011", "unit": "m", "unit_price": 78.0, "brand": "西顿", "spec": "20×20 预埋"},
            {"category_code": "ceiling", "name": "木方", "sku": "CEL-012", "unit": "根", "unit_price": 35.0, "brand": "无", "spec": "40×30×3000mm"},
            {"category_code": "ceiling", "name": "吊顶收边条", "sku": "CEL-013", "unit": "m", "unit_price": 15.0, "brand": "法狮龙", "spec": "L型"},
            {"category_code": "ceiling", "name": "GRG造型天花", "sku": "CEL-014", "unit": "㎡", "unit_price": 680.0, "brand": "可耐福", "spec": "定制造型"},
            {"category_code": "ceiling", "name": "软膜天花", "sku": "CEL-015", "unit": "㎡", "unit_price": 280.0, "brand": "巴力", "spec": "透光膜"},
            # 厨卫设备 (25)
            {"category_code": "kitchen_bath", "name": "石英石台面", "sku": "KB-001", "unit": "m", "unit_price": 680.0, "brand": "中迅", "spec": "20mm 厚"},
            {"category_code": "kitchen_bath", "name": "台下盆洗手盆", "sku": "KB-002", "unit": "个", "unit_price": 580.0, "brand": "科勒", "spec": "500×400mm"},
            {"category_code": "kitchen_bath", "name": "恒温花洒", "sku": "KB-003", "unit": "套", "unit_price": 1680.0, "brand": "高仪", "spec": "恒温38℃"},
            {"category_code": "kitchen_bath", "name": "智能马桶", "sku": "KB-004", "unit": "个", "unit_price": 3980.0, "brand": "TOTO", "spec": "即热式"},
            {"category_code": "kitchen_bath", "name": "不锈钢水槽", "sku": "KB-005", "unit": "个", "unit_price": 880.0, "brand": "欧琳", "spec": "760×450mm"},
            {"category_code": "kitchen_bath", "name": "抽拉龙头", "sku": "KB-006", "unit": "个", "unit_price": 980.0, "brand": "摩恩", "spec": "不锈钢"},
            {"category_code": "kitchen_bath", "name": "浴缸", "sku": "KB-007", "unit": "个", "unit_price": 4980.0, "brand": "科勒", "spec": "1700×800mm 亚克力"},
            {"category_code": "kitchen_bath", "name": "淋浴房", "sku": "KB-008", "unit": "套", "unit_price": 3280.0, "brand": "朗司", "spec": "900×900mm 不锈钢"},
            {"category_code": "kitchen_bath", "name": "浴室柜", "sku": "KB-009", "unit": "套", "unit_price": 2880.0, "brand": "恒洁", "spec": "800mm 落地"},
            {"category_code": "kitchen_bath", "name": "镜柜", "sku": "KB-010", "unit": "个", "unit_price": 1280.0, "brand": "心海伽蓝", "spec": "800×700mm 带灯"},
            {"category_code": "kitchen_bath", "name": "地漏", "sku": "KB-011", "unit": "个", "unit_price": 128.0, "brand": "潜水艇", "spec": "防臭芯"},
            {"category_code": "kitchen_bath", "name": "三角阀", "sku": "KB-012", "unit": "个", "unit_price": 35.0, "brand": "九牧", "spec": "全铜"},
            {"category_code": "kitchen_bath", "name": "油烟机", "sku": "KB-013", "unit": "台", "unit_price": 3580.0, "brand": "方太", "spec": "侧吸 21m³/min"},
            {"category_code": "kitchen_bath", "name": "燃气灶", "sku": "KB-014", "unit": "台", "unit_price": 2280.0, "brand": "方太", "spec": "5.0kW 双灶"},
            {"category_code": "kitchen_bath", "name": "电热水器", "sku": "KB-015", "unit": "台", "unit_price": 1680.0, "brand": "海尔", "spec": "60L"},
            {"category_code": "kitchen_bath", "name": "前置过滤器", "sku": "KB-016", "unit": "个", "unit_price": 580.0, "brand": "沁园", "spec": "40μm冲洗"},
            {"category_code": "kitchen_bath", "name": "RO净水器", "sku": "KB-017", "unit": "台", "unit_price": 2980.0, "brand": "安吉尔", "spec": "600G"},
            {"category_code": "kitchen_bath", "name": "垃圾处理器", "sku": "KB-018", "unit": "台", "unit_price": 2280.0, "brand": "爱适易", "spec": "E200"},
            {"category_code": "kitchen_bath", "name": "厨房挂件套装", "sku": "KB-019", "unit": "套", "unit_price": 480.0, "brand": "摩恩", "spec": "太空铝 5件套"},
            {"category_code": "kitchen_bath", "name": "马桶喷枪", "sku": "KB-020", "unit": "个", "unit_price": 168.0, "brand": "潜水艇", "spec": "一进二出"},
            {"category_code": "kitchen_bath", "name": "恒温毛巾架", "sku": "KB-021", "unit": "个", "unit_price": 1280.0, "brand": "卡迪欧", "spec": "600×1000mm 电热"},
            {"category_code": "kitchen_bath", "name": "壁挂马桶水箱", "sku": "KB-022", "unit": "套", "unit_price": 1680.0, "brand": "吉博力", "spec": "隐藏式水箱"},
            {"category_code": "kitchen_bath", "name": "入墙式龙头预埋件", "sku": "KB-023", "unit": "套", "unit_price": 680.0, "brand": "高仪", "spec": "暗装"},
            {"category_code": "kitchen_bath", "name": "卫生间扶手", "sku": "KB-024", "unit": "个", "unit_price": 168.0, "brand": "摩恩", "spec": "不锈钢 400mm"},
            {"category_code": "kitchen_bath", "name": "排水管隔音棉", "sku": "KB-025", "unit": "卷", "unit_price": 88.0, "brand": "无", "spec": "50mm厚 自粘"},
            # 门窗 (20)
            {"category_code": "doors_windows", "name": "实木复合门", "sku": "DW-001", "unit": "扇", "unit_price": 1880.0, "brand": "TATA", "spec": "800×2000mm"},
            {"category_code": "doors_windows", "name": "推拉门", "sku": "DW-002", "unit": "㎡", "unit_price": 780.0, "brand": "轩尼斯", "spec": "极窄边框"},
            {"category_code": "doors_windows", "name": "断桥铝窗户", "sku": "DW-003", "unit": "㎡", "unit_price": 880.0, "brand": "凤铝", "spec": "70系列双层中空"},
            {"category_code": "doors_windows", "name": "防盗门", "sku": "DW-004", "unit": "樘", "unit_price": 3980.0, "brand": "盼盼", "spec": "甲级 950×2050mm"},
            {"category_code": "doors_windows", "name": "谷仓门", "sku": "DW-005", "unit": "扇", "unit_price": 2280.0, "brand": "无", "spec": "实木 900×2100mm"},
            {"category_code": "doors_windows", "name": "隐形门", "sku": "DW-006", "unit": "扇", "unit_price": 3880.0, "brand": "TATA", "spec": "定制 墙板同色"},
            {"category_code": "doors_windows", "name": "折叠门", "sku": "DW-007", "unit": "扇", "unit_price": 1680.0, "brand": "轩尼斯", "spec": "PVC 4折"},
            {"category_code": "doors_windows", "name": "系统窗", "sku": "DW-008", "unit": "㎡", "unit_price": 1280.0, "brand": "旭格", "spec": "75系列 三层中空"},
            {"category_code": "doors_windows", "name": "纱窗", "sku": "DW-009", "unit": "个", "unit_price": 280.0, "brand": "凤铝", "spec": "304不锈钢 金刚网"},
            {"category_code": "doors_windows", "name": "门吸", "sku": "DW-010", "unit": "个", "unit_price": 38.0, "brand": "固特", "spec": "不锈钢"},
            {"category_code": "doors_windows", "name": "门锁", "sku": "DW-011", "unit": "把", "unit_price": 268.0, "brand": "名门", "spec": "静音磁吸"},
            {"category_code": "doors_windows", "name": "指纹锁", "sku": "DW-012", "unit": "把", "unit_price": 2280.0, "brand": "凯迪仕", "spec": "3D人脸识别"},
            {"category_code": "doors_windows", "name": "合页", "sku": "DW-013", "unit": "副", "unit_price": 68.0, "brand": "海蒂诗", "spec": "不锈钢 3mm"},
            {"category_code": "doors_windows", "name": "铝合金平开窗", "sku": "DW-014", "unit": "㎡", "unit_price": 580.0, "brand": "凤铝", "spec": "50系列普通"},
            {"category_code": "doors_windows", "name": "飘窗栏杆", "sku": "DW-015", "unit": "m", "unit_price": 280.0, "brand": "无", "spec": "304不锈钢"},
            {"category_code": "doors_windows", "name": "阳台推拉门", "sku": "DW-016", "unit": "㎡", "unit_price": 980.0, "brand": "皇派", "spec": "重型推拉"},
            {"category_code": "doors_windows", "name": "防火门", "sku": "DW-017", "unit": "樘", "unit_price": 2580.0, "brand": "盼盼", "spec": "乙级钢制"},
            {"category_code": "doors_windows", "name": "玻璃隔断", "sku": "DW-018", "unit": "㎡", "unit_price": 680.0, "brand": "朗斯", "spec": "10mm钢化"},
            {"category_code": "doors_windows", "name": "窗台石", "sku": "DW-019", "unit": "m", "unit_price": 180.0, "brand": "天然大理石", "spec": "200mm宽 爵士白"},
            {"category_code": "doors_windows", "name": "铝合金百叶窗", "sku": "DW-020", "unit": "㎡", "unit_price": 320.0, "brand": "凤铝", "spec": "固定式"},
            # 水电材料 (25)
            {"category_code": "mep", "name": "BV铜芯线 4mm²", "sku": "MEP-001", "unit": "卷", "unit_price": 320.0, "brand": "远东", "spec": "4mm² 100m"},
            {"category_code": "mep", "name": "PPR热水管", "sku": "MEP-002", "unit": "m", "unit_price": 18.0, "brand": "伟星", "spec": "25×4.2mm"},
            {"category_code": "mep", "name": "五孔插座", "sku": "MEP-003", "unit": "个", "unit_price": 28.0, "brand": "公牛", "spec": "10A"},
            {"category_code": "mep", "name": "弱电箱", "sku": "MEP-004", "unit": "个", "unit_price": 180.0, "brand": "施耐德", "spec": "300×400mm"},
            {"category_code": "mep", "name": "BV铜芯线 2.5mm²", "sku": "MEP-005", "unit": "卷", "unit_price": 198.0, "brand": "远东", "spec": "2.5mm² 100m"},
            {"category_code": "mep", "name": "网线 CAT6", "sku": "MEP-006", "unit": "箱", "unit_price": 580.0, "brand": "安普", "spec": "305m 六类"},
            {"category_code": "mep", "name": "PVC线管", "sku": "MEP-007", "unit": "根", "unit_price": 12.0, "brand": "联塑", "spec": "20mm 3m"},
            {"category_code": "mep", "name": "暗盒", "sku": "MEP-008", "unit": "个", "unit_price": 3.0, "brand": "公牛", "spec": "86型"},
            {"category_code": "mep", "name": "空气开关", "sku": "MEP-009", "unit": "个", "unit_price": 168.0, "brand": "施耐德", "spec": "63A 2P"},
            {"category_code": "mep", "name": "配电箱", "sku": "MEP-010", "unit": "个", "unit_price": 280.0, "brand": "施耐德", "spec": "16回路"},
            {"category_code": "mep", "name": "地插", "sku": "MEP-011", "unit": "个", "unit_price": 198.0, "brand": "公牛", "spec": "纯铜 防水"},
            {"category_code": "mep", "name": "防水盒", "sku": "MEP-012", "unit": "个", "unit_price": 15.0, "brand": "公牛", "spec": "86型"},
            {"category_code": "mep", "name": "HDMI线 4K", "sku": "MEP-013", "unit": "根", "unit_price": 98.0, "brand": "绿联", "spec": "10m"},
            {"category_code": "mep", "name": "排水管", "sku": "MEP-014", "unit": "m", "unit_price": 25.0, "brand": "联塑", "spec": "PVC 110mm"},
            {"category_code": "mep", "name": "地暖分水器", "sku": "MEP-015", "unit": "路", "unit_price": 128.0, "brand": "曼瑞德", "spec": "不锈钢"},
            {"category_code": "mep", "name": "地暖管", "sku": "MEP-016", "unit": "m", "unit_price": 12.0, "brand": "伟星", "spec": "PERT 20mm"},
            {"category_code": "mep", "name": "水表", "sku": "MEP-017", "unit": "个", "unit_price": 268.0, "brand": "宁波水表", "spec": "15mm"},
            {"category_code": "mep", "name": "燃气软管", "sku": "MEP-018", "unit": "m", "unit_price": 35.0, "brand": "航天晨光", "spec": "不锈钢波纹管"},
            {"category_code": "mep", "name": "法兰", "sku": "MEP-019", "unit": "个", "unit_price": 18.0, "brand": "联塑", "spec": "PPR 25mm"},
            {"category_code": "mep", "name": "管卡", "sku": "MEP-020", "unit": "个", "unit_price": 2.0, "brand": "联塑", "spec": "20mm"},
            {"category_code": "mep", "name": "生料带", "sku": "MEP-021", "unit": "卷", "unit_price": 8.0, "brand": "潜水艇", "spec": "20m×12mm"},
            {"category_code": "mep", "name": "86型墙壁开关", "sku": "MEP-022", "unit": "个", "unit_price": 35.0, "brand": "公牛", "spec": "双开单控"},
            {"category_code": "mep", "name": "感应开关", "sku": "MEP-023", "unit": "个", "unit_price": 128.0, "brand": "公牛", "spec": "红外感应"},
            {"category_code": "mep", "name": "电视线", "sku": "MEP-024", "unit": "卷", "unit_price": 168.0, "brand": "秋叶原", "spec": "SYWV 75-5 100m"},
            {"category_code": "mep", "name": "等电位端子箱", "sku": "MEP-025", "unit": "个", "unit_price": 88.0, "brand": "施耐德", "spec": "TD28"},
            # 定制家具 (25)
            {"category_code": "custom_furniture", "name": "定制衣柜", "sku": "CF-001", "unit": "㎡", "unit_price": 1280.0, "brand": "索菲亚", "spec": "E0级颗粒板"},
            {"category_code": "custom_furniture", "name": "定制橱柜", "sku": "CF-002", "unit": "m", "unit_price": 2280.0, "brand": "欧派", "spec": "地柜+吊柜"},
            {"category_code": "custom_furniture", "name": "定制鞋柜", "sku": "CF-003", "unit": "㎡", "unit_price": 980.0, "brand": "尚品宅配", "spec": "E1级颗粒板"},
            {"category_code": "custom_furniture", "name": "定制书柜", "sku": "CF-004", "unit": "㎡", "unit_price": 1080.0, "brand": "索菲亚", "spec": "E0级颗粒板"},
            {"category_code": "custom_furniture", "name": "定制榻榻米", "sku": "CF-005", "unit": "㎡", "unit_price": 1680.0, "brand": "维意定制", "spec": "E0级板材"},
            {"category_code": "custom_furniture", "name": "定制电视柜", "sku": "CF-006", "unit": "m", "unit_price": 1280.0, "brand": "欧派", "spec": "悬空式"},
            {"category_code": "custom_furniture", "name": "定制餐边柜", "sku": "CF-007", "unit": "㎡", "unit_price": 1380.0, "brand": "尚品宅配", "spec": "嵌入式"},
            {"category_code": "custom_furniture", "name": "定制阳台柜", "sku": "CF-008", "unit": "㎡", "unit_price": 1180.0, "brand": "索菲亚", "spec": "防水板材"},
            {"category_code": "custom_furniture", "name": "定制浴室柜", "sku": "CF-009", "unit": "套", "unit_price": 2580.0, "brand": "心海伽蓝", "spec": "实木多层防水"},
            {"category_code": "custom_furniture", "name": "实木餐桌", "sku": "CF-010", "unit": "张", "unit_price": 2980.0, "brand": "源氏木语", "spec": "1400×800mm 黑胡桃"},
            {"category_code": "custom_furniture", "name": "实木床+床头柜", "sku": "CF-011", "unit": "套", "unit_price": 4980.0, "brand": "源氏木语", "spec": "1800×2000mm 橡木"},
            {"category_code": "custom_furniture", "name": "梳妆台", "sku": "CF-012", "unit": "张", "unit_price": 1680.0, "brand": "全友", "spec": "800×450mm"},
            {"category_code": "custom_furniture", "name": "定制酒柜", "sku": "CF-013", "unit": "㎡", "unit_price": 1580.0, "brand": "欧派", "spec": "玻璃门板"},
            {"category_code": "custom_furniture", "name": "定制衣帽间", "sku": "CF-014", "unit": "㎡", "unit_price": 1880.0, "brand": "索菲亚", "spec": "U型布局"},
            {"category_code": "custom_furniture", "name": "板材切割加工费", "sku": "CF-015", "unit": "次", "unit_price": 500.0, "brand": "加工厂", "spec": "封边+打孔"},
            {"category_code": "custom_furniture", "name": "五金拉手", "sku": "CF-016", "unit": "个", "unit_price": 38.0, "brand": "固特", "spec": "锌合金"},
            {"category_code": "custom_furniture", "name": "抽屉滑轨", "sku": "CF-017", "unit": "副", "unit_price": 88.0, "brand": "海蒂诗", "spec": "450mm 缓冲"},
            {"category_code": "custom_furniture", "name": "衣通", "sku": "CF-018", "unit": "根", "unit_price": 68.0, "brand": "海蒂诗", "spec": "600mm"},
            {"category_code": "custom_furniture", "name": "气撑", "sku": "CF-019", "unit": "支", "unit_price": 58.0, "brand": "海蒂诗", "spec": "上翻门"},
            {"category_code": "custom_furniture", "name": "定制护墙板", "sku": "CF-020", "unit": "㎡", "unit_price": 680.0, "brand": "科定", "spec": "实木贴皮"},
            {"category_code": "custom_furniture", "name": "床垫", "sku": "CF-021", "unit": "张", "unit_price": 3280.0, "brand": "喜临门", "spec": "1800×2000mm 独立弹簧"},
            {"category_code": "custom_furniture", "name": "办公椅", "sku": "CF-022", "unit": "把", "unit_price": 1980.0, "brand": "西昊", "spec": "人体工学"},
            {"category_code": "custom_furniture", "name": "换鞋凳", "sku": "CF-023", "unit": "个", "unit_price": 580.0, "brand": "源氏木语", "spec": "800mm 实木"},
            {"category_code": "custom_furniture", "name": "沙发边几", "sku": "CF-024", "unit": "个", "unit_price": 680.0, "brand": "吱音", "spec": "450mm直径"},
            {"category_code": "custom_furniture", "name": "全身镜", "sku": "CF-025", "unit": "面", "unit_price": 480.0, "brand": "无", "spec": "500×1600mm"},
            # 软装 (25)
            {"category_code": "soft_decor", "name": "电动窗帘轨道", "sku": "SD-001", "unit": "套", "unit_price": 1280.0, "brand": "杜亚", "spec": "3m 静音"},
            {"category_code": "soft_decor", "name": "LED无主灯", "sku": "SD-002", "unit": "套", "unit_price": 2680.0, "brand": "欧普", "spec": "全屋套餐 12灯"},
            {"category_code": "soft_decor", "name": "布艺沙发", "sku": "SD-003", "unit": "套", "unit_price": 4980.0, "brand": "芝华仕", "spec": "三人位 科技布"},
            {"category_code": "soft_decor", "name": "窗帘", "sku": "SD-004", "unit": "m", "unit_price": 198.0, "brand": "摩力克", "spec": "雪尼尔 定高2.8m"},
            {"category_code": "soft_decor", "name": "纱帘", "sku": "SD-005", "unit": "m", "unit_price": 88.0, "brand": "摩力克", "spec": "白纱 定高2.8m"},
            {"category_code": "soft_decor", "name": "罗马杆", "sku": "SD-006", "unit": "m", "unit_price": 68.0, "brand": "摩力克", "spec": "铝合金 28mm"},
            {"category_code": "soft_decor", "name": "轨道灯", "sku": "SD-007", "unit": "m", "unit_price": 168.0, "brand": "西顿", "spec": "3线 含灯头"},
            {"category_code": "soft_decor", "name": "筒灯", "sku": "SD-008", "unit": "个", "unit_price": 78.0, "brand": "西顿", "spec": "7W 3000K 开孔75mm"},
            {"category_code": "soft_decor", "name": "射灯", "sku": "SD-009", "unit": "个", "unit_price": 128.0, "brand": "西顿", "spec": "12W 4000K"},
            {"category_code": "soft_decor", "name": "吊灯", "sku": "SD-010", "unit": "盏", "unit_price": 1280.0, "brand": "设计师款", "spec": "8头 黄铜"},
            {"category_code": "soft_decor", "name": "壁灯", "sku": "SD-011", "unit": "盏", "unit_price": 380.0, "brand": "设计师款", "spec": "金属玻璃"},
            {"category_code": "soft_decor", "name": "落地灯", "sku": "SD-012", "unit": "盏", "unit_price": 880.0, "brand": "造作", "spec": "北欧风 阅读灯"},
            {"category_code": "soft_decor", "name": "装饰画", "sku": "SD-013", "unit": "幅", "unit_price": 480.0, "brand": "无", "spec": "600×800mm"},
            {"category_code": "soft_decor", "name": "地毯", "sku": "SD-014", "unit": "张", "unit_price": 1680.0, "brand": "无", "spec": "2000×3000mm 羊毛"},
            {"category_code": "soft_decor", "name": "抱枕", "sku": "SD-015", "unit": "个", "unit_price": 128.0, "brand": "无", "spec": "450×450mm"},
            {"category_code": "soft_decor", "name": "绿植", "sku": "SD-016", "unit": "盆", "unit_price": 380.0, "brand": "无", "spec": "琴叶榕 1.5m"},
            {"category_code": "soft_decor", "name": "挂钟", "sku": "SD-017", "unit": "个", "unit_price": 280.0, "brand": "无", "spec": "400mm 静音"},
            {"category_code": "soft_decor", "name": "花瓶摆件", "sku": "SD-018", "unit": "套", "unit_price": 358.0, "brand": "无", "spec": "3件套"},
            {"category_code": "soft_decor", "name": "晾衣架", "sku": "SD-019", "unit": "套", "unit_price": 1680.0, "brand": "好太太", "spec": "电动升降"},
            {"category_code": "soft_decor", "name": "防滑垫", "sku": "SD-020", "unit": "张", "unit_price": 88.0, "brand": "无", "spec": "600×900mm"},
            {"category_code": "soft_decor", "name": "电表箱装饰画", "sku": "SD-021", "unit": "幅", "unit_price": 258.0, "brand": "无", "spec": "推拉式"},
            {"category_code": "soft_decor", "name": "入户地垫", "sku": "SD-022", "unit": "张", "unit_price": 198.0, "brand": "无", "spec": "800×1200mm"},
            {"category_code": "soft_decor", "name": "踏脚凳", "sku": "SD-023", "unit": "个", "unit_price": 258.0, "brand": "无", "spec": "实木"},
            {"category_code": "soft_decor", "name": "调味架", "sku": "SD-024", "unit": "个", "unit_price": 168.0, "brand": "无", "spec": "不锈钢 三层"},
            {"category_code": "soft_decor", "name": "筷子消毒机", "sku": "SD-025", "unit": "台", "unit_price": 398.0, "brand": "索克斯", "spec": "紫外线"},
            # 家电 (25)
            {"category_code": "appliances", "name": "中央空调", "sku": "APP-001", "unit": "套", "unit_price": 12800.0, "brand": "大金", "spec": "一拖四"},
            {"category_code": "appliances", "name": "燃气热水器", "sku": "APP-002", "unit": "台", "unit_price": 3280.0, "brand": "林内", "spec": "16L 恒温"},
            {"category_code": "appliances", "name": "嵌入式洗碗机", "sku": "APP-003", "unit": "台", "unit_price": 4580.0, "brand": "西门子", "spec": "13套"},
            {"category_code": "appliances", "name": "对开门冰箱", "sku": "APP-004", "unit": "台", "unit_price": 5999.0, "brand": "海尔", "spec": "500L 变频"},
            {"category_code": "appliances", "name": "洗烘一体机", "sku": "APP-005", "unit": "台", "unit_price": 4499.0, "brand": "小天鹅", "spec": "10kg"},
            {"category_code": "appliances", "name": "嵌入式烤箱", "sku": "APP-006", "unit": "台", "unit_price": 5980.0, "brand": "西门子", "spec": "71L"},
            {"category_code": "appliances", "name": "嵌入式蒸箱", "sku": "APP-007", "unit": "台", "unit_price": 4980.0, "brand": "方太", "spec": "42L"},
            {"category_code": "appliances", "name": "微波炉", "sku": "APP-008", "unit": "台", "unit_price": 880.0, "brand": "格兰仕", "spec": "25L 变频"},
            {"category_code": "appliances", "name": "电饭煲", "sku": "APP-009", "unit": "台", "unit_price": 1280.0, "brand": "象印", "spec": "IH 5L"},
            {"category_code": "appliances", "name": "电视 65寸", "sku": "APP-010", "unit": "台", "unit_price": 5999.0, "brand": "索尼", "spec": "65X90K 4K"},
            {"category_code": "appliances", "name": "回音壁", "sku": "APP-011", "unit": "套", "unit_price": 2980.0, "brand": "索尼", "spec": "HT-S350"},
            {"category_code": "appliances", "name": "吸尘器", "sku": "APP-012", "unit": "台", "unit_price": 2980.0, "brand": "戴森", "spec": "V12"},
            {"category_code": "appliances", "name": "扫地机器人", "sku": "APP-013", "unit": "台", "unit_price": 3980.0, "brand": "科沃斯", "spec": "T30 自动洗拖布"},
            {"category_code": "appliances", "name": "新风系统", "sku": "APP-014", "unit": "套", "unit_price": 8800.0, "brand": "远大", "spec": "全屋 250m³/h"},
            {"category_code": "appliances", "name": "空气净化器", "sku": "APP-015", "unit": "台", "unit_price": 2980.0, "brand": "小米", "spec": "MAX"},
            {"category_code": "appliances", "name": "智能音箱", "sku": "APP-016", "unit": "台", "unit_price": 599.0, "brand": "小米", "spec": "小爱Pro"},
            {"category_code": "appliances", "name": "智能门锁", "sku": "APP-017", "unit": "把", "unit_price": 2280.0, "brand": "小米", "spec": "全自动Pro"},
            {"category_code": "appliances", "name": "摄像头", "sku": "APP-018", "unit": "个", "unit_price": 358.0, "brand": "小米", "spec": "2K"},
            {"category_code": "appliances", "name": "电动晾衣架", "sku": "APP-019", "unit": "套", "unit_price": 1680.0, "brand": "好太太", "spec": "带照明"},
            {"category_code": "appliances", "name": "浴霸", "sku": "APP-020", "unit": "台", "unit_price": 880.0, "brand": "欧普", "spec": "300×600 风暖"},
            {"category_code": "appliances", "name": "电水壶", "sku": "APP-021", "unit": "台", "unit_price": 398.0, "brand": "象印", "spec": "4L 真空保温"},
            {"category_code": "appliances", "name": "即热饮水机", "sku": "APP-022", "unit": "台", "unit_price": 1280.0, "brand": "小米", "spec": "管线机"},
            {"category_code": "appliances", "name": "破壁机", "sku": "APP-023", "unit": "台", "unit_price": 1280.0, "brand": "九阳", "spec": "静音"},
            {"category_code": "appliances", "name": "咖啡机", "sku": "APP-024", "unit": "台", "unit_price": 4980.0, "brand": "德龙", "spec": "全自动"},
            {"category_code": "appliances", "name": "风管机", "sku": "APP-025", "unit": "台", "unit_price": 4980.0, "brand": "格力", "spec": "3P 变频"},
        ]
        for mat_data in materials:
            code = mat_data.pop("category_code")
            db.add(Material(category_id=category_map[code], **mat_data))

        suppliers = [
            {"name": "东鹏瓷砖旗舰店", "contact_name": "王经理", "phone": "13901000001", "address": "佛山市禅城区", "category": "flooring", "rating": 4.5},
            {"name": "马可波罗瓷砖", "contact_name": "李经理", "phone": "13901000002", "address": "东莞市莞城区", "category": "flooring", "rating": 4.3},
            {"name": "圣象地板", "contact_name": "赵经理", "phone": "13901000003", "address": "上海市浦东新区", "category": "flooring", "rating": 4.6},
            {"name": "立邦涂料", "contact_name": "陈经理", "phone": "13901000004", "address": "上海市徐汇区", "category": "wall", "rating": 4.4},
            {"name": "欧派家居", "contact_name": "刘经理", "phone": "13901000005", "address": "广州市天河区", "category": "custom_furniture", "rating": 4.7},
            {"name": "索菲亚衣柜", "contact_name": "张经理", "phone": "13901000006", "address": "广州市增城区", "category": "custom_furniture", "rating": 4.5},
            {"name": "科勒卫浴", "contact_name": "吴经理", "phone": "13901000007", "address": "上海市静安区", "category": "kitchen_bath", "rating": 4.8},
            {"name": "TOTO卫浴", "contact_name": "周经理", "phone": "13901000008", "address": "北京市朝阳区", "category": "kitchen_bath", "rating": 4.6},
            {"name": "远东电缆", "contact_name": "孙经理", "phone": "13901000009", "address": "宜兴市高塍镇", "category": "mep", "rating": 4.2},
            {"name": "大金空调", "contact_name": "黄经理", "phone": "13901000010", "address": "上海市长宁区", "category": "appliances", "rating": 4.9},
            {"name": "西门子家电", "contact_name": "钱经理", "phone": "13901000011", "address": "南京市玄武区", "category": "appliances", "rating": 4.7},
            {"name": "TATA木门", "contact_name": "杨经理", "phone": "13901000012", "address": "北京市通州区", "category": "doors_windows", "rating": 4.4},
        ]
        for sup_data in suppliers:
            db.add(Supplier(**sup_data))

        demo_user = User(
            phone="13800138000",
            name="张先生",
            role="homeowner",
            hashed_password=_hash_password("123456"),
        )
        db.add(demo_user)

        # ── 第二个演示用户（设计师） ──
        designer = User(
            phone="13900139000",
            name="李设计师",
            role="designer",
            hashed_password=_hash_password("123456"),
        )
        db.add(designer)
        await db.flush()

        # ── 演示项目（多种状态） ──
        from app.models.project import Project
        import uuid as _uuid
        from datetime import datetime as _dt

        demo_projects = [
            Project(
                id=str(_uuid.uuid4()),
                name="现代简约三房·西湖花园",
                address="杭州市西湖区西湖花园 12-1-301",
                total_area=120.0,
                status="active",
                project_type="full_renovation",
                source="manual",
                owner_id=demo_user.id,
                created_at=_dt(2026, 7, 8, 10, 0, 0),
            ),
            Project(
                id=str(_uuid.uuid4()),
                name="北欧风两居改造·阳光100",
                address="北京市朝阳区阳光100 3-2-1501",
                total_area=88.0,
                status="completed",
                project_type="full_renovation",
                source="manual",
                owner_id=demo_user.id,
                created_at=_dt(2026, 6, 15, 9, 0, 0),
            ),
            Project(
                id=str(_uuid.uuid4()),
                name="南湖花园独栋别墅",
                address="南京市江宁区南湖花园 8 号",
                total_area=260.0,
                status="active",
                project_type="full_renovation",
                source="ar_measure",
                owner_id=demo_user.id,
                created_at=_dt(2026, 7, 5, 14, 0, 0),
            ),
            Project(
                id=str(_uuid.uuid4()),
                name="青年公寓翻新·自如寓",
                address="上海市浦东新区自如寓 A-1205",
                total_area=56.0,
                status="completed",
                project_type="hard_decoration",
                source="manual",
                owner_id=demo_user.id,
                created_at=_dt(2026, 7, 10, 8, 30, 0),
            ),
            Project(
                id=str(_uuid.uuid4()),
                name="城市花园 Loft·高新公馆",
                address="成都市高新区高新公馆 2-1805",
                total_area=75.0,
                status="active",
                project_type="soft_furnishing",
                source="manual",
                owner_id=demo_user.id,
                created_at=_dt(2026, 7, 12, 11, 0, 0),
            ),
        ]
        for proj in demo_projects:
            db.add(proj)

        # ── F26 家具品类库 seed 数据 ──
        from app.models.furniture_catalog import FurnitureCatalogItem

        furniture_items = [
            # 客厅家具
            {"category": "living_room", "subcategory": "sofa", "name": "北欧简约三人沙发", "brand": "林氏木业", "model": "LS-SF-001", "width": 2100, "depth": 850, "height": 800, "material": "棉麻", "color": "浅灰", "style": "nordic", "price": 4980.0, "sale_price": 4580.0, "rating": 4.6, "sales_count": 1200, "stock_count": 50, "ar_preview_supported": True, "tags": ["热销", "新品"], "status": "active"},
            {"category": "living_room", "subcategory": "sofa", "name": "现代轻奢三人沙发", "brand": "顾家家居", "model": "GJ-SF-002", "width": 2200, "depth": 900, "height": 820, "material": "科技布", "color": "深灰", "style": "modern", "price": 6280.0, "sale_price": 5680.0, "rating": 4.8, "sales_count": 860, "stock_count": 30, "ar_preview_supported": True, "tags": ["热销"], "status": "active"},
            {"category": "living_room", "subcategory": "coffee_table", "name": "岩板茶几", "brand": "全友家居", "model": "QY-CT-001", "width": 1200, "depth": 600, "height": 420, "material": "岩板+不锈钢", "color": "黑色", "style": "modern", "price": 1980.0, "sale_price": 1680.0, "rating": 4.5, "sales_count": 540, "stock_count": 80, "ar_preview_supported": True, "status": "active"},
            {"category": "living_room", "subcategory": "tv_cabinet", "name": "悬空式电视柜", "brand": "索菲亚", "model": "SF-TV-001", "width": 1800, "depth": 350, "height": 300, "material": "颗粒板", "color": "白色", "style": "modern", "price": 2280.0, "rating": 4.4, "sales_count": 320, "stock_count": 40, "ar_preview_supported": True, "status": "active"},
            # 卧室家具
            {"category": "bedroom", "subcategory": "bed", "name": "1.8m实木床", "brand": "源氏木语", "model": "YS-BD-001", "width": 2000, "depth": 1800, "height": 400, "material": "橡木", "color": "原木色", "style": "nordic", "price": 4980.0, "sale_price": 4480.0, "rating": 4.7, "sales_count": 980, "stock_count": 25, "ar_preview_supported": True, "tags": ["热销"], "status": "active"},
            {"category": "bedroom", "subcategory": "nightstand", "name": "北欧实木床头柜", "brand": "源氏木语", "model": "YS-NS-001", "width": 450, "depth": 400, "height": 550, "material": "橡木", "color": "原木色", "style": "nordic", "price": 680.0, "rating": 4.5, "sales_count": 420, "stock_count": 60, "ar_preview_supported": True, "status": "active"},
            {"category": "bedroom", "subcategory": "wardrobe", "name": "定制衣柜", "brand": "索菲亚", "model": "SF-WD-001", "width": 2400, "depth": 600, "height": 2700, "material": "颗粒板", "color": "白色", "style": "modern", "price": 4280.0, "rating": 4.6, "sales_count": 350, "stock_count": 20, "ar_preview_supported": True, "status": "active"},
            # 餐厅家具
            {"category": "dining_room", "subcategory": "dining_table", "name": "黑胡桃实木餐桌", "brand": "源氏木语", "model": "YS-DT-001", "width": 1400, "depth": 800, "height": 750, "material": "黑胡桃木", "color": "深棕", "style": "modern", "price": 2980.0, "sale_price": 2680.0, "rating": 4.8, "sales_count": 280, "stock_count": 35, "ar_preview_supported": True, "status": "active"},
            {"category": "dining_room", "subcategory": "chair", "name": "北欧餐椅", "brand": "林氏木业", "model": "LS-CH-001", "width": 450, "depth": 500, "height": 850, "material": "实木+布艺", "color": "灰色", "style": "nordic", "price": 380.0, "rating": 4.3, "sales_count": 1500, "stock_count": 200, "ar_preview_supported": True, "status": "active"},
            # 书房家具
            {"category": "study", "subcategory": "desk", "name": "实木书桌", "brand": "源氏木语", "model": "YS-DK-001", "width": 1400, "depth": 700, "height": 750, "material": "橡木", "color": "原木色", "style": "nordic", "price": 2280.0, "rating": 4.6, "sales_count": 180, "stock_count": 45, "ar_preview_supported": True, "status": "active"},
            {"category": "study", "subcategory": "bookshelf", "name": "简约书柜", "brand": "全友家居", "model": "QY-BS-001", "width": 800, "depth": 300, "height": 2000, "material": "颗粒板", "color": "白色", "style": "modern", "price": 1880.0, "rating": 4.2, "sales_count": 220, "stock_count": 50, "ar_preview_supported": True, "status": "active"},
            # 玄关家具
            {"category": "entrance", "subcategory": "shoe_cabinet", "name": "入户鞋柜", "brand": "索菲亚", "model": "SF-SC-001", "width": 1200, "depth": 350, "height": 1000, "material": "颗粒板", "color": "白色", "style": "modern", "price": 1280.0, "rating": 4.4, "sales_count": 190, "stock_count": 55, "ar_preview_supported": True, "status": "active"},
            # 新中式风格
            {"category": "living_room", "subcategory": "sofa", "name": "新中式实木沙发", "brand": "曲美", "model": "QM-SF-001", "width": 2300, "depth": 900, "height": 800, "material": "胡桃木+棉麻", "color": "深棕", "style": "chinese", "price": 8800.0, "rating": 4.9, "sales_count": 120, "stock_count": 10, "ar_preview_supported": True, "tags": ["高端"], "status": "active"},
            {"category": "living_room", "subcategory": "coffee_table", "name": "新中式茶台", "brand": "曲美", "model": "QM-CT-001", "width": 1400, "depth": 700, "height": 450, "material": "胡桃木", "color": "深棕", "style": "chinese", "price": 3680.0, "rating": 4.7, "sales_count": 80, "stock_count": 15, "ar_preview_supported": True, "status": "active"},
            # 工业风
            {"category": "living_room", "subcategory": "coffee_table", "name": "工业风铁艺茶几", "brand": "吱音", "model": "ZY-CT-001", "width": 1000, "depth": 550, "height": 400, "material": "铁艺+实木", "color": "黑色", "style": "industrial", "price": 1280.0, "rating": 4.3, "sales_count": 160, "stock_count": 40, "ar_preview_supported": True, "status": "active"},
        ]

        for fur_data in furniture_items:
            db.add(FurnitureCatalogItem(**fur_data))

        # ── RBAC 权限种子数据 ──
        from app.models.permission import Permission, RolePermission
        from app.rbac import DEFAULT_PERMISSIONS, DEFAULT_ROLE_PERMISSIONS

        # 检查是否已有权限数据
        perm_result = await db.execute(select(func.count()).select_from(Permission))
        if perm_result.scalar() == 0:
            for perm_data in DEFAULT_PERMISSIONS:
                db.add(Permission(**perm_data))
            await db.flush()

            # 插入默认角色权限映射
            for role, perm_codes in DEFAULT_ROLE_PERMISSIONS.items():
                for code in perm_codes:
                    db.add(RolePermission(role=role, permission_code=code))

        await db.commit()

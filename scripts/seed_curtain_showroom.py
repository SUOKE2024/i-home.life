"""窗帘智能展厅种子数据 — 单店铺「官渡区帘享空间窗帘布艺经营部」

幂等：已存在同名展厅则跳过。
同时创建「窗帘布艺」物料分类 + 每个展品对应的 Material（复用 /api/materials/bom 加入 BOM）。

用法：
  python scripts/seed_curtain_showroom.py
"""

import asyncio
import logging
import os
import sys

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

# 项目根目录加入 sys.path（与 scripts/verify_self_evolution.py 同款），
# 支持直接 `python scripts/seed_curtain_showroom.py` 运行。
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.database import async_session, init_db  # noqa: E402
from app.models.curtain_showroom import (  # noqa: E402
    CurtainInstallation,
    CurtainLightingPreset,
    CurtainProduct,
    CurtainSeries,
    CurtainShowroom,
    CurtainShowroomArea,
)
from app.models.material import Material, MaterialCategory  # noqa: E402

logger = logging.getLogger("seed_curtain_showroom")

STORE_NAME = "官渡区帘享空间窗帘布艺经营部"
CATEGORY_NAME = "窗帘布艺"
CATEGORY_CODE = "curtain_fabric"


def _configure_logging() -> None:
    if not logger.handlers:
        logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s %(levelname)s %(name)s %(message)s",
        )
    logger.setLevel(logging.INFO)


# (code, name, render_type, description)
INSTALLATIONS = [
    ("roman_rod", "罗马杆", "roman_rod", "经典罗马杆，窗帘环挂钩，适合客厅/主卧"),
    ("track", "轨道", "track", "静音直轨/弯轨，隐藏式轨道，适合飘窗/阳台"),
    ("hook", "挂钩", "hook", "四叉钩/吊环挂钩，褶皱均匀，易拆洗"),
    ("grommet", "打孔", "grommet", "金属孔环打孔穿杆，垂坠感强，现代简约"),
    ("blind", "百叶", "blind", "横/竖百叶，可调光，适合书房/厨卫"),
    ("roller", "卷帘", "roller", "卷轴升降，遮光/透光可选，适合卧室/办公室"),
]

# (code, name, time_of_day, light_color, ambient_intensity, description)
LIGHTING_PRESETS = [
    ("morning", "晨光", "morning", "#ffe3c2", 1.0, "清晨柔暖侧光"),
    ("noon", "正午", "noon", "#ffffff", 1.4, "正午明亮白光"),
    ("dusk", "黄昏", "dusk", "#ffb26b", 0.9, "黄昏暖橙逆光"),
    ("night", "夜景", "night", "#9ab0ff", 0.55, "夜晚冷蓝 + 室内暖灯"),
    ("warm", "暖光", "warm", "#ffd9a0", 1.1, "室内暖黄灯光"),
    ("cool", "冷光", "cool", "#d0e4ff", 1.0, "室内冷白灯光"),
]

# (name, description)
SERIES = [
    ("轻奢提花系列", "高精密提花面料，肌理细腻，适合轻奢/法式风格"),
    ("现代简约系列", "素色遮光/棉麻，线条利落，适合现代简约"),
    ("新中式系列", "中式纹样与天然麻料，适合新中式/原木风"),
    ("儿童房系列", "环保亲肤、卡通肌理，遮光与趣味兼顾"),
]

# (series_name, name, brand, fabric, color, unit_price, description)
PRODUCTS = [
    ("轻奢提花系列", "高精密提花 · 米白", "帘享自营", "提花", "米白", 168.0, "高精密提花，垂坠挺括，轻奢质感"),
    ("轻奢提花系列", "高精密提花 · 雾霾蓝", "帘享自营", "提花", "雾霾蓝", 188.0, "低饱和雾霾蓝，法式轻奢"),
    ("轻奢提花系列", "雪尼尔绒 · 奶油", "帘享精选", "雪尼尔", "奶油", 218.0, "雪尼尔绒面，亲肤厚实，遮光保暖"),
    ("现代简约系列", "全遮光布 · 静谧灰", "帘享自营", "遮光布", "静谧灰", 128.0, "物理全遮光，卧室助眠"),
    ("现代简约系列", "棉麻混纺 · 原麻", "帘享自营", "棉麻", "原麻", 98.0, "棉麻天然肌理，透气亲肤"),
    ("现代简约系列", "雪尼尔绒 · 藏青", "帘享精选", "雪尼尔", "藏青", 198.0, "厚重雪尼尔，现代沉稳"),
    ("新中式系列", "提花麻 · 黛青", "帘享自营", "棉麻", "黛青", 158.0, "新中式黛青，山水纹样"),
    ("新中式系列", "棉麻 · 米杏", "帘享自营", "棉麻", "米杏", 138.0, "米杏暖调，原木风百搭"),
    ("儿童房系列", "卡通提花 · 云朵白", "帘享精选", "提花", "云朵白", 118.0, "卡通云朵提花，环保亲肤"),
    ("儿童房系列", "全遮光 · 浅粉", "帘享自营", "遮光布", "浅粉", 108.0, "浅粉遮光，儿童房温馨"),
    ("现代简约系列", "透光纱帘 · 白纱", "帘享自营", "纱", "白纱", 68.0, "透光柔纱，客厅/阳台氛围"),
    ("新中式系列", "透光纱帘 · 米金", "帘享自营", "纱", "米金", 78.0, "米金柔纱，新中式雅致"),
]

# (name, description, installation_code, default_product_name)
AREAS = [
    ("客厅飘窗区", "罗马杆 + 高精密提花，展示客厅主帘效果", "roman_rod", "高精密提花 · 米白"),
    ("卧室遮光区", "静音轨道 + 全遮光布，展示卧室助眠效果", "track", "全遮光布 · 静谧灰"),
    ("阳台纱帘区", "挂钩 + 透光纱帘，展示阳台氛围效果", "hook", "透光纱帘 · 白纱"),
]


async def _get_or_create_category(db: AsyncSession) -> MaterialCategory:
    result = await db.execute(
        select(MaterialCategory).where(MaterialCategory.code == CATEGORY_CODE)
    )
    category = result.scalar_one_or_none()
    if category:
        return category
    category = MaterialCategory(name=CATEGORY_NAME, code=CATEGORY_CODE, description="窗帘/布艺面料")
    db.add(category)
    await db.flush()
    return category


async def _get_or_create_material(db: AsyncSession, category: MaterialCategory, name: str, brand: str,
                                  fabric: str, color: str, unit_price: float, sku: str) -> Material:
    result = await db.execute(select(Material).where(Material.sku == sku))
    material = result.scalar_one_or_none()
    if material:
        return material
    material = Material(
        category_id=category.id,
        name=name,
        sku=sku,
        unit="米",
        unit_price=unit_price,
        brand=brand or None,
        spec=f"{fabric} · {color}" if color else fabric,
        description=f"窗帘面料：{fabric}" + (f"（{color}）" if color else ""),
    )
    db.add(material)
    await db.flush()
    return material


async def seed_curtain_showroom() -> bool:
    await init_db()
    async with async_session() as db:
        # 幂等：同名展厅已存在则跳过
        exist = await db.execute(
            select(CurtainShowroom).where(CurtainShowroom.name == STORE_NAME)
        )
        if exist.scalar_one_or_none():
            print(f"ℹ️  窗帘展厅「{STORE_NAME}」已存在，跳过注入")
            return False

        showroom = CurtainShowroom(
            name=STORE_NAME,
            description="官渡区帘享空间窗帘布艺经营部 · 智能展厅（3D 换装 / 时间灯光 / 安装方式 / 热点加 BOM）",
        )
        db.add(showroom)
        await db.flush()

        # 系列
        series_map: dict[str, CurtainSeries] = {}
        for idx, (name, desc) in enumerate(SERIES):
            s = CurtainSeries(showroom_id=showroom.id, name=name, description=desc, sort_order=idx)
            db.add(s)
            series_map[name] = s
        await db.flush()

        # 安装方式
        installation_map: dict[str, CurtainInstallation] = {}
        for idx, (code, name, render_type, desc) in enumerate(INSTALLATIONS):
            ins = CurtainInstallation(code=code, name=name, render_type=render_type,
                                      description=desc, sort_order=idx)
            db.add(ins)
            installation_map[code] = ins
        await db.flush()

        # 灯光预设
        for idx, (code, name, time_of_day, light_color, ambient, desc) in enumerate(LIGHTING_PRESETS):
            db.add(CurtainLightingPreset(
                code=code, name=name, time_of_day=time_of_day,
                light_color=light_color, ambient_intensity=ambient,
                description=desc, sort_order=idx,
            ))
        await db.flush()

        # 物料分类 + 展品（含 Material 映射）
        category = await _get_or_create_category(db)
        product_map: dict[str, CurtainProduct] = {}
        for idx, (series_name, name, brand, fabric, color, price, desc) in enumerate(PRODUCTS):
            sku = f"LX-{idx + 1:03d}"
            material = await _get_or_create_material(db, category, name, brand, fabric, color, price, sku)
            product = CurtainProduct(
                showroom_id=showroom.id,
                series_id=series_map[series_name].id,
                material_id=material.id,
                name=name,
                sku=sku,
                brand=brand,
                fabric=fabric,
                color=color,
                unit="米",
                unit_price=price,
                description=desc,
                sort_order=idx,
            )
            db.add(product)
            product_map[name] = product
        await db.flush()

        # 展示区域
        for idx, (name, desc, ins_code, default_name) in enumerate(AREAS):
            db.add(CurtainShowroomArea(
                showroom_id=showroom.id,
                name=name,
                description=desc,
                installation_id=installation_map[ins_code].id,
                default_product_id=product_map[default_name].id,
                sort_order=idx,
            ))
        await db.commit()

        print(f"✅ 窗帘智能展厅注入完成：{STORE_NAME}")
        print(
            f"   - 系列 {len(SERIES)} 个 / 展品 {len(PRODUCTS)} 款 / "
            f"安装方式 {len(INSTALLATIONS)} 种 / 灯光预设 {len(LIGHTING_PRESETS)} 种 / "
            f"展示区域 {len(AREAS)} 个"
        )
        return True


if __name__ == "__main__":
    _configure_logging()
    asyncio.run(seed_curtain_showroom())

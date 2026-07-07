"""F24/F25 软装搭配 + 收纳系统服务层 — AI 搭配 + 配色和谐度 + 预算 + 收纳推荐"""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.soft_furnishing import SoftFurnishingScheme, SoftFurnishingItem, StorageSystem


# ── 风格配色 + 单品推荐规则库 ──
STYLE_PRESETS: dict[str, dict] = {
    "modern": {
        "color_scheme": {
            "primary": "#3E3E3E",       # 深灰 主色
            "secondary": "#D9D9D9",     # 浅灰 辅色
            "accent": "#C9A961",        # 香槟金 点缀色
        },
        "items": [
            {"item_type": "sofa", "name": "科技布三人沙发", "color": "深灰", "material": "科技布", "price": 4980.0},
            {"item_type": "coffee_table", "name": "岩板茶几", "color": "黑色", "material": "岩板+不锈钢", "price": 1980.0},
            {"item_type": "tv_cabinet_alt", "name": "悬空电视柜", "color": "白色", "material": "板材", "price": 2280.0},
            {"item_type": "lamp", "name": "极简落地灯", "color": "黑色", "material": "金属", "price": 880.0},
            {"item_type": "curtain", "name": "遮光窗帘", "color": "浅灰", "material": "雪尼尔", "price": 198.0},
        ],
    },
    "北欧": {
        "color_scheme": {
            "primary": "#E8DCC8",       # 浅木色 主色
            "secondary": "#8C8C8C",     # 灰色 辅色
            "accent": "#7BA05B",        # 草绿 点缀色
        },
        "items": [
            {"item_type": "sofa", "name": "布艺三人沙发", "color": "浅灰", "material": "棉麻", "price": 4280.0},
            {"item_type": "coffee_table", "name": "白橡木茶几", "color": "原木色", "material": "白橡木", "price": 1680.0},
            {"item_type": "rug", "name": "几何羊毛地毯", "color": "米白", "material": "羊毛", "price": 1680.0},
            {"item_type": "plant", "name": "琴叶榕", "color": "绿色", "material": "活体植物", "price": 380.0},
            {"item_type": "pillow", "name": "针织抱枕", "color": "灰白", "material": "棉", "price": 128.0},
        ],
    },
    "新中式": {
        "color_scheme": {
            "primary": "#5D3A1A",       # 胡桃木 主色
            "secondary": "#E8D8B8",     # 米黄 辅色
            "accent": "#8B0000",        # 中国红 点缀色
        },
        "items": [
            {"item_type": "sofa", "name": "实木雕花沙发", "color": "胡桃木色", "material": "胡桃木+棉麻", "price": 8800.0},
            {"item_type": "coffee_table", "name": "茶台", "color": "原木色", "material": "老榆木", "price": 5800.0},
            {"item_type": "artwork", "name": "山水水墨画", "color": "黑白", "material": "宣纸", "price": 980.0},
            {"item_type": "lamp", "name": "新中式落地灯", "color": "古铜", "material": "铜+亚麻", "price": 1280.0},
            {"item_type": "plant", "name": "文竹盆景", "color": "绿色", "material": "活体植物", "price": 280.0},
        ],
    },
    "美式": {
        "color_scheme": {
            "primary": "#4A2C2A",       # 深棕 主色
            "secondary": "#C9A57B",     # 卡其 辅色
            "accent": "#2C3E50",        # 深蓝 点缀色
        },
        "items": [
            {"item_type": "sofa", "name": "美式真皮沙发", "color": "深棕", "material": "头层牛皮", "price": 9800.0},
            {"item_type": "coffee_table", "name": "复古实木茶几", "color": "深棕", "material": "樱桃木", "price": 3280.0},
            {"item_type": "lamp", "name": "铜艺台灯", "color": "古铜", "material": "铜+玻璃", "price": 680.0},
            {"item_type": "rug", "name": "波斯风地毯", "color": "深红", "material": "化纤", "price": 2280.0},
            {"item_type": "artwork", "name": "复古油画", "color": "暖色", "material": "油画布", "price": 880.0},
        ],
    },
    "法式": {
        "color_scheme": {
            "primary": "#FFFFFF",       # 白色 主色
            "secondary": "#E8E0D0",     # 米色 辅色
            "accent": "#C9A961",        # 金色 点缀色
        },
        "items": [
            {"item_type": "sofa", "name": "法式丝绒沙发", "color": "米白", "material": "丝绒", "price": 7800.0},
            {"item_type": "coffee_table", "name": "雕花茶几", "color": "白色金色", "material": "MDF+树脂", "price": 3280.0},
            {"item_type": "lamp", "name": "水晶吊灯", "color": "金色", "material": "水晶+铜", "price": 4280.0},
            {"item_type": "artwork", "name": "法式装饰镜", "color": "金色", "material": "镜面+树脂", "price": 1880.0},
            {"item_type": "curtain", "name": "法式纱帘", "color": "白色", "material": "纱", "price": 198.0},
        ],
    },
    "工业": {
        "color_scheme": {
            "primary": "#2C2C2C",       # 黑色 主色
            "secondary": "#8B5A2B",     # 原木色 辅色
            "accent": "#B87333",        # 铜色 点缀色
        },
        "items": [
            {"item_type": "sofa", "name": "工业风皮质沙发", "color": "深棕", "material": "做旧皮", "price": 5800.0},
            {"item_type": "coffee_table", "name": "铁艺茶几", "color": "黑色", "material": "铁+原木", "price": 1880.0},
            {"item_type": "lamp", "name": "爱迪生吊灯", "color": "铜色", "material": "铜+玻璃", "price": 880.0},
            {"item_type": "artwork", "name": "做旧装饰画", "color": "黑白", "material": "画布", "price": 480.0},
            {"item_type": "rug", "name": "复古地毯", "color": "深色", "material": "棉", "price": 980.0},
        ],
    },
    "日式": {
        "color_scheme": {
            "primary": "#D4B896",       # 原木色 主色
            "secondary": "#F5F0E6",     # 米色 辅色
            "accent": "#7BA05B",        # 抹茶绿 点缀色
        },
        "items": [
            {"item_type": "sofa", "name": "原木矮沙发", "color": "原木色", "material": "白蜡木+棉麻", "price": 5280.0},
            {"item_type": "coffee_table", "name": "榻榻米茶几", "color": "原木色", "material": "杉木", "price": 1280.0},
            {"item_type": "rug", "name": "蔺草地毯", "color": "米色", "material": "蔺草", "price": 680.0},
            {"item_type": "plant", "name": "枯山水盆景", "color": "绿色", "material": "活体植物", "price": 380.0},
            {"item_type": "lamp", "name": "和纸落地灯", "color": "米白", "material": "和纸+木", "price": 880.0},
        ],
    },
}

# 人均收纳容量基准 (升/人)
STORAGE_PER_PERSON_L = 200.0
# 收纳利用率 (内部填充 + 层板厚度损耗)
STORAGE_UTILIZATION = 0.7


# ── 方案 CRUD ──


async def create_scheme(db: AsyncSession, data: dict) -> SoftFurnishingScheme:
    scheme = SoftFurnishingScheme(**data)
    db.add(scheme)
    await db.commit()
    await db.refresh(scheme)
    return scheme


async def get_scheme(db: AsyncSession, scheme_id: str) -> SoftFurnishingScheme | None:
    result = await db.execute(
        select(SoftFurnishingScheme)
        .where(SoftFurnishingScheme.id == scheme_id)
        .options(
            selectinload(SoftFurnishingScheme.items),
            selectinload(SoftFurnishingScheme.storages),
        )
    )
    return result.scalar_one_or_none()


async def list_schemes_by_project(db: AsyncSession, project_id: str) -> list[SoftFurnishingScheme]:
    result = await db.execute(
        select(SoftFurnishingScheme)
        .where(SoftFurnishingScheme.project_id == project_id)
        .order_by(SoftFurnishingScheme.created_at.desc())
    )
    return list(result.scalars().all())


async def delete_scheme(db: AsyncSession, scheme_id: str) -> bool:
    scheme = await get_scheme(db, scheme_id)
    if not scheme:
        return False
    await db.delete(scheme)
    await db.commit()
    return True


async def _update_budget_used(db: AsyncSession, scheme: SoftFurnishingScheme) -> None:
    """重新计算方案已用预算 (单品价格 × 数量 之和)"""
    result = await db.execute(
        select(SoftFurnishingItem).where(SoftFurnishingItem.scheme_id == scheme.id)
    )
    items = result.scalars().all()
    used = sum(float(i.price or 0) * int(i.quantity or 1) for i in items)
    scheme.budget_used = round(used, 2)
    await db.commit()
    await db.refresh(scheme)


# ── 单品 CRUD ──


async def add_item(db: AsyncSession, scheme_id: str, data: dict) -> SoftFurnishingItem:
    item = SoftFurnishingItem(scheme_id=scheme_id, **data)
    db.add(item)
    await db.commit()
    await db.refresh(item)
    # 同步预算
    scheme = await get_scheme(db, scheme_id)
    if scheme:
        await _update_budget_used(db, scheme)
    return item


async def list_items(db: AsyncSession, scheme_id: str) -> list[SoftFurnishingItem]:
    result = await db.execute(
        select(SoftFurnishingItem)
        .where(SoftFurnishingItem.scheme_id == scheme_id)
        .order_by(SoftFurnishingItem.created_at)
    )
    return list(result.scalars().all())


async def delete_item(db: AsyncSession, item_id: str) -> bool:
    result = await db.execute(select(SoftFurnishingItem).where(SoftFurnishingItem.id == item_id))
    item = result.scalar_one_or_none()
    if not item:
        return False
    scheme_id = item.scheme_id
    await db.delete(item)
    await db.commit()
    # 同步预算
    scheme = await get_scheme(db, scheme_id)
    if scheme:
        await _update_budget_used(db, scheme)
    return True


async def update_item_status(db: AsyncSession, item_id: str, new_status: str) -> SoftFurnishingItem | None:
    result = await db.execute(select(SoftFurnishingItem).where(SoftFurnishingItem.id == item_id))
    item = result.scalar_one_or_none()
    if not item:
        return None
    item.status = new_status
    await db.commit()
    await db.refresh(item)
    return item


# ── 收纳系统 CRUD ──


async def add_storage(db: AsyncSession, scheme_id: str, data: dict) -> StorageSystem:
    storage = StorageSystem(scheme_id=scheme_id, **data)
    db.add(storage)
    await db.commit()
    await db.refresh(storage)
    return storage


async def list_storages(db: AsyncSession, scheme_id: str) -> list[StorageSystem]:
    result = await db.execute(
        select(StorageSystem)
        .where(StorageSystem.scheme_id == scheme_id)
        .order_by(StorageSystem.created_at)
    )
    return list(result.scalars().all())


# ── AI 软装搭配 (规则引擎) ──


async def ai_match_soft_furnishing(db: AsyncSession, scheme: SoftFurnishingScheme) -> dict:
    """根据风格推荐配色 + 单品组合

    基于规则引擎匹配 STYLE_PRESETS,写入方案的 color_scheme 并生成推荐单品。
    """
    preset = STYLE_PRESETS.get(scheme.style, STYLE_PRESETS["modern"])

    # 更新方案配色
    scheme.color_scheme = preset["color_scheme"]
    await db.commit()
    await db.refresh(scheme)

    # 写入推荐单品 (planned 状态)
    created_items: list[SoftFurnishingItem] = []
    for item_data in preset["items"]:
        # 避免重复添加: 同名同类型跳过
        existing = await db.execute(
            select(SoftFurnishingItem).where(
                SoftFurnishingItem.scheme_id == scheme.id,
                SoftFurnishingItem.item_type == item_data["item_type"],
                SoftFurnishingItem.name == item_data["name"],
            )
        )
        if existing.scalar_one_or_none():
            continue
        item = SoftFurnishingItem(
            scheme_id=scheme.id,
            item_type=item_data["item_type"],
            name=item_data["name"],
            color=item_data.get("color"),
            material=item_data.get("material"),
            price=item_data.get("price", 0.0),
            quantity=1,
            status="planned",
        )
        db.add(item)
        created_items.append(item)

    await db.commit()
    for it in created_items:
        await db.refresh(it)

    # 同步预算
    await _update_budget_used(db, scheme)
    if scheme.status == "draft":
        scheme = await get_scheme(db, scheme.id)

    return {
        "style": scheme.style,
        "color_scheme": preset["color_scheme"],
        "recommended_items": [
            {
                "id": it.id,
                "item_type": it.item_type,
                "name": it.name,
                "color": it.color,
                "material": it.material,
                "price": it.price,
            }
            for it in created_items
        ],
    }


# ── 配色和谐度 (60-30-10 法则) ──


def compute_color_harmony(scheme: SoftFurnishingScheme) -> dict:
    """配色和谐度计算

    60-30-10 法则: 主色 60% + 辅色 30% + 点缀色 10%。
    基于单品颜色分布统计,计算与法则的偏差给出评分。
    """
    color_scheme = scheme.color_scheme or {}
    if not color_scheme:
        return {
            "score": 0.0,
            "primary_pct": 0.0,
            "secondary_pct": 0.0,
            "accent_pct": 0.0,
            "suggestion": "方案尚未设置配色,建议先执行 AI 搭配或手动设置 color_scheme",
        }

    primary = color_scheme.get("primary")
    secondary = color_scheme.get("secondary")
    accent = color_scheme.get("accent")

    # 按单品颜色统计分布
    items = scheme.items or []
    color_count: dict[str, int] = {}
    total = 0
    for it in items:
        c = (it.color or "").strip()
        if not c:
            continue
        color_count[c] = color_count.get(c, 0) + 1
        total += 1

    if total == 0:
        # 无单品时直接按法则给满分基础分
        return {
            "score": 80.0,
            "primary_pct": 60.0,
            "secondary_pct": 30.0,
            "accent_pct": 10.0,
            "suggestion": "尚未录入单品颜色,已按 60-30-10 法则给出基准分",
        }

    # 主/辅/点缀色占比
    primary_pct = (color_count.get(primary, 0) / total) * 100 if primary else 0
    secondary_pct = (color_count.get(secondary, 0) / total) * 100 if secondary else 0
    accent_pct = (color_count.get(accent, 0) / total) * 100 if accent else 0

    # 评分:与 60/30/10 的偏差越小,分数越高
    dev = abs(primary_pct - 60) + abs(secondary_pct - 30) + abs(accent_pct - 10)
    score = max(0.0, 100.0 - dev)

    suggestion = None
    if score < 60:
        suggestion = "配色比例偏离 60-30-10 法则较多,建议调整单品颜色分布"
    elif score < 85:
        suggestion = "配色基本和谐,可适度增加点缀色比例"

    return {
        "score": round(score, 1),
        "primary_pct": round(primary_pct, 1),
        "secondary_pct": round(secondary_pct, 1),
        "accent_pct": round(accent_pct, 1),
        "suggestion": suggestion,
    }


# ── 预算使用情况 ──


def compute_budget_usage(scheme: SoftFurnishingScheme) -> dict:
    """预算使用率计算"""
    total = float(scheme.budget_total or 0)
    used = float(scheme.budget_used or 0)
    remaining = total - used
    usage_pct = (used / total * 100) if total > 0 else 0.0

    if total <= 0:
        status = "normal"
    elif used > total:
        status = "over"
    elif usage_pct >= 80:
        status = "warning"
    else:
        status = "normal"

    return {
        "budget_total": round(total, 2),
        "budget_used": round(used, 2),
        "budget_remaining": round(remaining, 2),
        "usage_pct": round(usage_pct, 1),
        "status": status,
    }


# ── 收纳方案推荐 ──


def recommend_storage_solution(room_name: str, room_area: float, family_size: int) -> dict:
    """收纳方案推荐

    规则: 人均收纳容量 ≥ 200L
    """
    if family_size <= 0:
        family_size = 1
    if room_area <= 0:
        room_area = 0.0

    recommended_total = family_size * STORAGE_PER_PERSON_L

    # 按房间类型推荐收纳类型组合
    room_lower = room_name or ""
    if "卧" in room_lower:
        suggestions = [
            {"storage_type": "衣柜", "capacity_l": recommended_total * 0.5, "compartment_count": 6, "reason": "卧室主收纳,挂衣+折叠分区"},
            {"storage_type": "吊柜", "capacity_l": recommended_total * 0.2, "compartment_count": 4, "reason": "利用墙面顶部空间"},
            {"storage_type": "地柜", "capacity_l": recommended_total * 0.3, "compartment_count": 4, "reason": "床尾/窗边储物"},
        ]
    elif "厨" in room_lower:
        suggestions = [
            {"storage_type": "厨柜", "capacity_l": recommended_total * 0.7, "compartment_count": 8, "reason": "厨房主收纳,分区存放"},
            {"storage_type": "吊柜", "capacity_l": recommended_total * 0.3, "compartment_count": 4, "reason": "上方轻物收纳"},
        ]
    elif "书" in room_lower or "工作" in room_lower:
        suggestions = [
            {"storage_type": "书柜", "capacity_l": recommended_total * 0.7, "compartment_count": 8, "reason": "书籍+文档分类"},
            {"storage_type": "储物间", "capacity_l": recommended_total * 0.3, "compartment_count": 4, "reason": "杂物收纳"},
        ]
    elif "玄关" in room_lower or "门厅" in room_lower:
        suggestions = [
            {"storage_type": "鞋柜", "capacity_l": recommended_total * 0.6, "compartment_count": 6, "reason": "鞋类+出门物品"},
            {"storage_type": "吊柜", "capacity_l": recommended_total * 0.4, "compartment_count": 3, "reason": "换季物品"},
        ]
    else:
        # 客厅/通用
        suggestions = [
            {"storage_type": "衣柜", "capacity_l": recommended_total * 0.4, "compartment_count": 6, "reason": "通用主收纳"},
            {"storage_type": "储物间", "capacity_l": recommended_total * 0.4, "compartment_count": 4, "reason": "杂物收纳"},
            {"storage_type": "吊柜", "capacity_l": recommended_total * 0.2, "compartment_count": 3, "reason": "辅助收纳"},
        ]

    return {
        "room_name": room_name,
        "room_area": room_area,
        "family_size": family_size,
        "recommended_capacity_l": round(recommended_total, 1),
        "suggestions": suggestions,
    }


# ── 收纳容量计算 ──


def compute_storage_capacity(storage: StorageSystem) -> dict:
    """收纳容量计算 (利用率 0.7)

    返回总容量与有效容量。
    """
    total = float(storage.total_capacity_l or 0)
    effective = total * STORAGE_UTILIZATION
    return {
        "total_capacity_l": round(total, 2),
        "utilization_rate": STORAGE_UTILIZATION,
        "effective_capacity_l": round(effective, 2),
    }

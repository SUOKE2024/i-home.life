"""设计流程编排演示数据 — 为现有供应商补充 styles + price_tier

目的：设计流程编排（/api/design-flow）按「风格 + 价格档位」硬过滤供应商，
而 scripts/seed.py 创建的 12 个供应商只有 category/rating，styles 为空、price_tier
为默认 standard，导致匹配不到候选。本脚本幂等补充 styles/price_tier，覆盖
modern/nordic/japanese/luxury/chinese/industrial 风格 × economy/standard/premium 档位。

用法：
  PYTHONPATH=. .venv/bin/python scripts/seed_design_flow_demo.py
"""

import asyncio
import json

from sqlalchemy import select

from app.database import async_session, init_db
from app.models.procurement import Supplier


# 供应商名 → (styles, price_tier)
SUPPLIER_STYLES = {
    "东鹏瓷砖旗舰店": (["modern", "chinese"], "economy"),
    "马可波罗瓷砖": (["modern"], "economy"),
    "圣象地板": (["modern", "nordic"], "standard"),
    "立邦涂料": (["modern", "japanese"], "economy"),
    "欧派家居": (["modern", "luxury"], "premium"),
    "索菲亚衣柜": (["modern", "nordic", "japanese"], "standard"),
    "科勒卫浴": (["luxury", "modern"], "premium"),
    "TOTO卫浴": (["modern", "nordic"], "standard"),
    "远东电缆": (["modern", "industrial"], "economy"),
    "大金空调": (["modern", "luxury"], "premium"),
    "西门子家电": (["modern", "luxury"], "standard"),
    "TATA木门": (["modern", "japanese", "chinese"], "standard"),
}


async def seed() -> None:
    await init_db()
    async with async_session() as db:
        result = await db.execute(select(Supplier))
        suppliers = list(result.scalars().all())

        updated = 0
        for s in suppliers:
            if s.name in SUPPLIER_STYLES:
                styles, tier = SUPPLIER_STYLES[s.name]
                s.styles = json.dumps(styles, ensure_ascii=False)
                s.price_tier = tier
                updated += 1
        await db.commit()

        print(f"✅ 已补充 {updated} 个供应商的 styles / price_tier")
        for s in suppliers:
            if s.name in SUPPLIER_STYLES:
                print(f"  · {s.name} → styles={s.styles_list} / price_tier={s.price_tier}")


if __name__ == "__main__":
    asyncio.run(seed())

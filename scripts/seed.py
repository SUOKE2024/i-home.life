import asyncio

from sqlalchemy import select

from app.database import async_session, init_db
from app.models.material import MaterialCategory, Material
from app.models.procurement import Supplier
from app.services.user_service import _hash_password
from app.models.user import User

CATEGORIES = [
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

MATERIALS = [
    {"category_code": "flooring", "name": "750×1500 大板砖", "sku": "FLR-001", "unit": "㎡", "unit_price": 198.0, "brand": "东鹏", "spec": "750×1500mm 亮面"},
    {"category_code": "flooring", "name": "600×1200 木纹砖", "sku": "FLR-002", "unit": "㎡", "unit_price": 128.0, "brand": "马可波罗", "spec": "600×1200mm 木纹"},
    {"category_code": "flooring", "name": "强化复合地板", "sku": "FLR-003", "unit": "㎡", "unit_price": 158.0, "brand": "圣象", "spec": "12mm 耐磨"},
    {"category_code": "flooring", "name": "实木多层地板", "sku": "FLR-004", "unit": "㎡", "unit_price": 328.0, "brand": "大自然", "spec": "15mm 橡木"},
    {"category_code": "flooring", "name": "防滑地砖", "sku": "FLR-005", "unit": "㎡", "unit_price": 88.0, "brand": "东鹏", "spec": "300×300mm"},
    {"category_code": "flooring", "name": "大理石门槛", "sku": "FLR-006", "unit": "条", "unit_price": 120.0, "brand": "天然大理石", "spec": "900×150mm"},
    {"category_code": "wall", "name": "净味乳胶漆", "sku": "WLL-001", "unit": "桶", "unit_price": 680.0, "brand": "立邦", "spec": "18L 净味"},
    {"category_code": "wall", "name": "400×800 瓷片", "sku": "WLL-002", "unit": "㎡", "unit_price": 88.0, "brand": "东鹏", "spec": "400×800mm 亮面"},
    {"category_code": "wall", "name": "艺术漆", "sku": "WLL-003", "unit": "㎡", "unit_price": 280.0, "brand": "嘉宝莉", "spec": "雅晶石系列"},
    {"category_code": "wall", "name": "无纺布墙布", "sku": "WLL-004", "unit": "㎡", "unit_price": 168.0, "brand": "欧雅", "spec": "2.8m幅宽"},
    {"category_code": "wall", "name": "防水涂料", "sku": "WLL-005", "unit": "桶", "unit_price": 420.0, "brand": "雨虹", "spec": "18kg JS防水"},
    {"category_code": "ceiling", "name": "铝扣板吊顶", "sku": "CEL-001", "unit": "㎡", "unit_price": 128.0, "brand": "欧普", "spec": "300×300mm"},
    {"category_code": "ceiling", "name": "石膏板吊顶", "sku": "CEL-002", "unit": "㎡", "unit_price": 95.0, "brand": "龙牌", "spec": "9.5mm"},
    {"category_code": "kitchen_bath", "name": "石英石台面", "sku": "KB-001", "unit": "m", "unit_price": 680.0, "brand": "中迅", "spec": "20mm 厚"},
    {"category_code": "kitchen_bath", "name": "台下盆洗手盆", "sku": "KB-002", "unit": "个", "unit_price": 580.0, "brand": "科勒", "spec": "500×400mm"},
    {"category_code": "kitchen_bath", "name": "恒温花洒", "sku": "KB-003", "unit": "套", "unit_price": 1680.0, "brand": "高仪", "spec": "恒温38℃"},
    {"category_code": "kitchen_bath", "name": "智能马桶", "sku": "KB-004", "unit": "个", "unit_price": 3980.0, "brand": "TOTO", "spec": "即热式"},
    {"category_code": "kitchen_bath", "name": "不锈钢水槽", "sku": "KB-005", "unit": "个", "unit_price": 880.0, "brand": "欧琳", "spec": "760×450mm"},
    {"category_code": "doors_windows", "name": "实木复合门", "sku": "DW-001", "unit": "扇", "unit_price": 1880.0, "brand": "TATA", "spec": "800×2000mm"},
    {"category_code": "doors_windows", "name": "推拉门", "sku": "DW-002", "unit": "㎡", "unit_price": 780.0, "brand": "轩尼斯", "spec": "极窄边框"},
    {"category_code": "doors_windows", "name": "断桥铝窗户", "sku": "DW-003", "unit": "㎡", "unit_price": 880.0, "brand": "凤铝", "spec": "70系列双层中空"},
    {"category_code": "mep", "name": "BV铜芯线 4mm²", "sku": "MEP-001", "unit": "卷", "unit_price": 320.0, "brand": "远东", "spec": "4mm² 100m"},
    {"category_code": "mep", "name": "PPR热水管", "sku": "MEP-002", "unit": "m", "unit_price": 18.0, "brand": "伟星", "spec": "25×4.2mm"},
    {"category_code": "mep", "name": "五孔插座", "sku": "MEP-003", "unit": "个", "unit_price": 28.0, "brand": "公牛", "spec": "10A"},
    {"category_code": "mep", "name": "弱电箱", "sku": "MEP-004", "unit": "个", "unit_price": 180.0, "brand": "施耐德", "spec": "300×400mm"},
    {"category_code": "custom_furniture", "name": "定制衣柜", "sku": "CF-001", "unit": "㎡", "unit_price": 1280.0, "brand": "索菲亚", "spec": "E0级颗粒板"},
    {"category_code": "custom_furniture", "name": "定制橱柜", "sku": "CF-002", "unit": "m", "unit_price": 2280.0, "brand": "欧派", "spec": "地柜+吊柜"},
    {"category_code": "custom_furniture", "name": "定制鞋柜", "sku": "CF-003", "unit": "㎡", "unit_price": 980.0, "brand": "尚品宅配", "spec": "E1级颗粒板"},
    {"category_code": "soft_decor", "name": "电动窗帘轨道", "sku": "SD-001", "unit": "套", "unit_price": 1280.0, "brand": "杜亚", "spec": "3m 静音"},
    {"category_code": "soft_decor", "name": "LED无主灯", "sku": "SD-002", "unit": "套", "unit_price": 2680.0, "brand": "欧普", "spec": "全屋套餐 12灯"},
    {"category_code": "soft_decor", "name": "布艺沙发", "sku": "SD-003", "unit": "套", "unit_price": 4980.0, "brand": "芝华仕", "spec": "三人位 科技布"},
    {"category_code": "appliances", "name": "中央空调", "sku": "APP-001", "unit": "套", "unit_price": 12800.0, "brand": "大金", "spec": "一拖四"},
    {"category_code": "appliances", "name": "燃气热水器", "sku": "APP-002", "unit": "台", "unit_price": 3280.0, "brand": "林内", "spec": "16L 恒温"},
    {"category_code": "appliances", "name": "嵌入式洗碗机", "sku": "APP-003", "unit": "台", "unit_price": 4580.0, "brand": "西门子", "spec": "13套"},
    {"category_code": "appliances", "name": "对开门冰箱", "sku": "APP-004", "unit": "台", "unit_price": 5999.0, "brand": "海尔", "spec": "500L 变频"},
    {"category_code": "appliances", "name": "洗烘一体机", "sku": "APP-005", "unit": "台", "unit_price": 4499.0, "brand": "小天鹅", "spec": "10kg"},
]

SUPPLIERS = [
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


async def seed():
    await init_db()

    async with async_session() as db:
        result = await db.execute(select(MaterialCategory))
        if result.scalars().first():
            print("数据库已有数据，跳过种子")
            return

        for cat_data in CATEGORIES:
            cat = MaterialCategory(**cat_data)
            db.add(cat)
        await db.flush()

        result = await db.execute(select(MaterialCategory))
        category_map = {cat.code: cat.id for cat in result.scalars().all()}

        for mat_data in MATERIALS:
            code = mat_data.pop("category_code")
            mat = Material(category_id=category_map[code], **mat_data)
            db.add(mat)

        for sup_data in SUPPLIERS:
            sup = Supplier(**sup_data)
            db.add(sup)

        demo_user = User(
            phone="13800138000",
            name="张先生",
            role="homeowner",
            hashed_password=_hash_password("123456"),
        )
        db.add(demo_user)

        await db.commit()
        print(f"种子数据: {len(CATEGORIES)} 分类, {len(MATERIALS)} 物料, {len(SUPPLIERS)} 供应商, 1 用户")
        print("演示账户: 13800138000 / 123456")


if __name__ == "__main__":
    asyncio.run(seed())

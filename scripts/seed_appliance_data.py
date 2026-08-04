#!/usr/bin/env python3
"""测试辅助：为家电管理页面造种子数据

用途：console-src 的 /console/appliance 页面 useAsync 加载
GET /api/appliances/categories 与 GET /api/appliances/search。
当数据库无家电数据时，页面显示「暂无家电数据」空态，无法验证内容渲染。
本脚本通过 POST 端点创建 3 个分类 + 若干家电实例，使页面能渲染卡片列表。

幂等性：
  - 按 code 去重，已存在的分类跳过
  - 按 (name + brand + model) 去重，已存在的家电跳过
  - 可重复执行，不会产生重复数据

用法：
  python scripts/seed_appliance_data.py
  python scripts/seed_appliance_data.py --clear  # 清理本脚本创建的数据

复用 test_auto_relogin.py 处理 token 过期，无需手动登录。
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

# 复用同目录的 auto_relogin 工具
sys.path.insert(0, str(Path(__file__).parent))
from test_auto_relogin import AutoReloginClient, DEFAULT_BASE_URL, DEFAULT_PHONE, DEFAULT_PASSWORD  # noqa: E402

# ── 种子数据（对齐 app/models/appliance.py subcategory 枚举）──

CATEGORIES = [
    {"name": "大家电", "code": "major_appliance", "description": "空调、冰箱、洗衣机等大件家电"},
    {"name": "厨房电器", "code": "kitchen_appliance", "description": "油烟机、灶具、洗碗机等厨房设备"},
    {"name": "生活电器", "code": "home_appliance", "description": "净水器、扫地机器人、新风系统等"},
]

# category_code → 家电列表
APPLIANCES = [
    # 大家电
    {"category_code": "major_appliance", "name": "变频壁挂空调 1.5匹", "brand": "美的", "model": "KFR-35GW",
     "subcategory": "air_conditioner", "spec": "1.5匹 一级能效 变频冷暖", "power_rating": 980,
     "energy_label": "一级", "price": 3299, "tags": ["节能", "静音", "智能"]},
    {"category_code": "major_appliance", "name": "对开门冰箱 451L", "brand": "海尔", "model": "BCD-451WDPELU1",
     "subcategory": "refrigerator", "spec": "451L 风冷无霜 变频", "power_rating": 120,
     "energy_label": "一级", "price": 4599, "tags": ["节能", "风冷无霜"]},
    {"category_code": "major_appliance", "name": "滚筒洗衣机 10kg", "brand": "小天鹅", "model": "TG100V62ADS5",
     "subcategory": "washing_machine", "spec": "10kg 变频 洗烘一体", "power_rating": 220,
     "energy_label": "一级", "price": 2899, "tags": ["洗烘一体", "静音"]},
    {"category_code": "major_appliance", "name": "电热水器 60L", "brand": "史密斯", "model": "EWH-60EA7",
     "subcategory": "water_heater", "spec": "60L 速热 一级能效", "power_rating": 3000,
     "energy_label": "一级", "price": 1899, "tags": ["速热", "安全"]},
    {"category_code": "major_appliance", "name": "4K 智能电视 55寸", "brand": "小米", "model": "L55M7-EA",
     "subcategory": "tv", "spec": '55寸 4K HDR 智能电视', "power_rating": 150,
     "energy_label": "二级", "price": 2199, "tags": ["4K", "智能"]},
    # 厨房电器
    {"category_code": "kitchen_appliance", "name": "侧吸式油烟机 23m³", "brand": "方太", "model": "JCD7",
     "subcategory": "range_hood", "spec": "23m³/min 侧吸 大吸力", "power_rating": 260,
     "energy_label": "二级", "price": 3499, "tags": ["大吸力", "静音"]},
    {"category_code": "kitchen_appliance", "name": "燃气灶 双灶定时", "brand": "老板", "model": "JZT-57B6D",
     "subcategory": "cooktop", "spec": "双灶 5.0kW 定时 熄火保护", "power_rating": 0,
     "energy_label": None, "price": 1599, "tags": ["定时", "熄火保护"]},
    {"category_code": "kitchen_appliance", "name": "嵌入式洗碗机 13套", "brand": "西门子", "model": "SJ235W01JC",
     "subcategory": "dishwasher", "spec": "13套 嵌入式 热风烘干", "power_rating": 1700,
     "energy_label": "一级", "price": 5999, "tags": ["嵌入式", "热风烘干"]},
    {"category_code": "kitchen_appliance", "name": "蒸烤一体机", "brand": "凯度", "model": "ST28A-X7",
     "subcategory": "steam_oven", "spec": "28L 蒸烤一体 嵌入式", "power_rating": 2000,
     "energy_label": "二级", "price": 4299, "tags": ["蒸烤一体", "嵌入式"]},
    # 生活电器
    {"category_code": "home_appliance", "name": "RO 反渗透净水器 600G", "brand": "沁园", "model": "QR-RU-06A",
     "subcategory": "water_purifier", "spec": "600G RO 反渗透 无桶大流量", "power_rating": 40,
     "energy_label": None, "price": 2599, "tags": ["RO", "大流量"]},
    {"category_code": "home_appliance", "name": "扫拖机器人 L7", "brand": "石头", "model": "A10S",
     "subcategory": "robot_vacuum", "spec": "激光导航 自动洗拖 6000Pa", "power_rating": 67,
     "energy_label": None, "price": 3199, "tags": ["激光导航", "自动洗拖"]},
    {"category_code": "home_appliance", "name": "新风系统 全热交换", "brand": "松下", "model": "FY-35ZM1C",
     "subcategory": "fresh_air_system", "spec": "350m³/h 全热交换 PM2.5 过滤", "power_rating": 120,
     "energy_label": None, "price": 6899, "tags": ["全热交换", "PM2.5"]},
]


def seed(client: AutoReloginClient) -> int:
    """创建分类与家电，返回创建数量。"""
    created = 0

    # 1. 创建分类（幂等：按 code 去重）
    status, cats = client.get("/api/appliances/categories")
    if status != 200:
        print(f"[FAIL] 获取分类列表失败: HTTP {status}", file=sys.stderr)
        return 1
    existing_codes = {c.get("code") for c in cats}

    code_to_id: dict[str, str] = {c["code"]: c["id"] for c in cats}
    for cat in CATEGORIES:
        if cat["code"] in existing_codes:
            print(f"  SKIP 分类已存在: {cat['name']} ({cat['code']})")
            continue
        status, body = client.post("/api/appliances/categories", body=cat)
        if status == 201:
            code_to_id[cat["code"]] = body["id"]
            created += 1
            print(f"  OK   创建分类: {cat['name']} → {body['id'][:8]}")
        else:
            print(f"  FAIL 创建分类失败 {cat['name']}: HTTP {status} {body}", file=sys.stderr)

    if not code_to_id:
        print("[FAIL] 无可用分类，无法创建家电", file=sys.stderr)
        return 1

    # 2. 创建家电（幂等：按 name+brand+model 去重）
    status, existing_apps = client.get("/api/appliances/search")
    if status != 200:
        print(f"[FAIL] 获取家电列表失败: HTTP {status}", file=sys.stderr)
        return 1
    existing_keys = {(a.get("name"), a.get("brand"), a.get("model")) for a in existing_apps}

    for app in APPLIANCES:
        key = (app["name"], app["brand"], app["model"])
        if key in existing_keys:
            print(f"  SKIP 家电已存在: {app['name']} ({app['brand']})")
            continue
        category_id = code_to_id.get(app["category_code"])
        if not category_id:
            print(f"  SKIP 无分类映射: {app['name']} (code={app['category_code']})", file=sys.stderr)
            continue
        payload = {k: v for k, v in app.items() if k != "category_code"}
        payload["category_id"] = category_id
        status, body = client.post("/api/appliances", body=payload)
        if status == 201:
            created += 1
            print(f"  OK   创建家电: {app['name']} ({app['brand']}) → {body['id'][:8]}")
        else:
            print(f"  FAIL 创建家电失败 {app['name']}: HTTP {status} {body}", file=sys.stderr)

    # 3. 汇总
    status, final_cats = client.get("/api/appliances/categories")
    status, final_apps = client.get("/api/appliances/search")
    print(f"\n[完成] 本次创建 {created} 条，当前共 {len(final_cats)} 分类 / {len(final_apps)} 家电")
    return 0


def clear(client: AutoReloginClient) -> int:
    """清理本脚本创建的数据。"""
    status, apps = client.get("/api/appliances/search")
    if status != 200:
        print(f"[FAIL] 获取家电列表失败: HTTP {status}", file=sys.stderr)
        return 1
    deleted = 0
    for app in apps:
        name = app.get("name", "")
        # 仅删除本脚本创建的（按名称匹配种子数据中的 name）
        seed_names = {a["name"] for a in APPLIANCES}
        if name in seed_names:
            status, _ = client.delete(f"/api/appliances/{app['id']}")
            if status == 204:
                deleted += 1
                print(f"  DEL  家电: {name}")
            else:
                print(f"  FAIL 删除家电失败 {name}: HTTP {status}", file=sys.stderr)

    status, cats = client.get("/api/appliances/categories")
    for cat in cats:
        code = cat.get("code", "")
        if code in {c["code"] for c in CATEGORIES}:
            status, _ = client.delete(f"/api/appliances/categories/{cat['id']}")
            if status == 204:
                deleted += 1
                print(f"  DEL  分类: {cat['name']}")
            else:
                print(f"  FAIL 删除分类失败 {cat['name']}: HTTP {status} (可能有关联家电未删)", file=sys.stderr)

    print(f"\n[完成] 删除 {deleted} 条")
    return 0


def _cli() -> int:
    parser = argparse.ArgumentParser(description="索克家居 家电种子数据工具")
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL, help=f"后端地址（默认 {DEFAULT_BASE_URL}）")
    parser.add_argument("--clear", action="store_true", help="清理本脚本创建的种子数据")
    args = parser.parse_args()

    client = AutoReloginClient(base_url=args.base_url)
    print(f"连接 {args.base_url}（token 自动管理）\n")

    if args.clear:
        return clear(client)
    return seed(client)


if __name__ == "__main__":
    sys.exit(_cli())

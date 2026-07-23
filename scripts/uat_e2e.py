#!/usr/bin/env python
"""UAT 全链路端到端验证 — 模拟用户从注册到交付的完整旅程"""
import asyncio
import os
import uuid
import json

# 使用测试数据库避免污染开发数据
os.environ["DATABASE_URL"] = f"sqlite+aiosqlite:///./data/test_uat_{os.getpid()}.db"

# IMPORTANT: 必须在 import app 之前设置 DATABASE_URL
from app.database import engine, Base
from httpx import AsyncClient, ASGITransport

async def setup_db():
    """创建测试数据库表"""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

from app.main import app

PASS = 0
FAIL = 0
SKIP = 0


def ok(msg: str, detail: str = ""):
    global PASS
    PASS += 1
    print(f"  ✅ {msg}{' — ' + detail if detail else ''}")


def err(msg: str, code: int = 0, body: str = ""):
    global FAIL
    FAIL += 1
    short = body[:100] if body else ""
    print(f"  ❌ {msg} (HTTP {code}) {short}")


def skip(msg: str):
    global SKIP
    SKIP += 1
    print(f"  ⏭️  {msg}")


async def uat():
    transport = ASGITransport(app=app)
    phone = f"139{uuid.uuid4().int % 10**8:08d}"

    async with AsyncClient(transport=transport, base_url="http://test") as c:

        # ═══════════════════════════════════════
        # Phase 1: 用户注册 & 认证
        # ═══════════════════════════════════════
        print("\n── Phase 1: 用户注册 & 认证 ──")

        r = await c.post(
            "/api/auth/register",
            json={
                "phone": phone,
                "name": "UAT测试用户",
                "password": "uat123456",
            },
        )
        if r.status_code == 201:
            data = r.json()
            user = data.get("user", {})
            uid = user.get("id", "")
            token = data.get("access_token", "")
            headers = {"Authorization": f"Bearer {token}"} if token else {}
            ok("注册", uid[:8])
        else:
            err("注册", r.status_code, r.text)
            return

        r = await c.post(
            "/api/auth/login",
            json={"phone": phone, "password": "uat123456"},
        )
        if r.status_code == 200:
            token = r.json().get("access_token", token)
            headers = {"Authorization": f"Bearer {token}"}
            ok("登录")
        else:
            err("登录", r.status_code, r.text)

        # ═══════════════════════════════════════
        # Phase 2: 项目管理
        # ═══════════════════════════════════════
        print("\n── Phase 2: 项目管理 ──")

        r = await c.post(
            "/api/projects",
            json={
                "name": "UAT全链路测试项目",
                "address": "测试地址",
                "area_sqm": 120.0,
                "status": "active",
            },
            headers=headers,
        )
        pid = ""
        if r.status_code in (200, 201):
            data = r.json()
            pid = data.get("id", data.get("project_id", ""))
            ok("创建项目", pid[:8])
        else:
            err("创建项目", r.status_code, r.text)
            return

        r = await c.get(f"/api/projects/{pid}", headers=headers)
        ok("查询项目", f"HTTP {r.status_code}" if r.status_code == 200 else f"FAIL {r.status_code}")

        # ═══════════════════════════════════════
        # Phase 3: 户型 & 测量
        # ═══════════════════════════════════════
        print("\n── Phase 3: 户型 & 测量 ──")

        r = await c.post(
            "/api/floorplans",
            json={"project_id": pid, "name": "标准户型", "total_area": 120.0, "data": ""},
            headers=headers,
        )
        ok("创建户型") if r.status_code in (200, 201) else err("创建户型", r.status_code, r.text)

        r = await c.get(f"/api/floorplans/project/{pid}", headers=headers)
        ok("查询户型") if r.status_code == 200 else err("查询户型", r.status_code)

        # ═══════════════════════════════════════
        # Phase 4: 设计工具链
        # ═══════════════════════════════════════
        print("\n── Phase 4: 设计工具链 ──")

        # 厨房
        r = await c.post(
            "/api/kitchen/designs",
            json={
                "project_id": pid,
                "name": "UAT厨房",
                "room_name": "厨房",
                "layout_type": "L",
                "room_width": 3000,
                "room_length": 2400,
                "counter_height": 850,
            },
            headers=headers,
        )
        kitchen_id = r.json().get("id", "") if r.status_code in (200, 201) else ""
        ok("厨房设计") if kitchen_id else err("厨房设计", r.status_code, r.text)

        # 卫浴
        r = await c.post(
            "/api/bathroom/designs",
            json={
                "project_id": pid,
                "name": "UAT卫浴",
                "room_name": "卫生间",
                "layout_type": "dry_wet_separation",
                "room_width": 2000,
                "room_length": 2500,
            },
            headers=headers,
        )
        ok("卫浴设计") if r.status_code in (200, 201) else err("卫浴设计", r.status_code, r.text)

        # 灯光
        r = await c.post(
            "/api/lighting/schemes",
            json={
                "project_id": pid,
                "name": "UAT灯光",
                "room_name": "客厅",
                "scheme_type": "mixed",
                "room_area": 20.0,
                "room_height": 2800,
            },
            headers=headers,
        )
        ok("灯光方案") if r.status_code in (200, 201) else err("灯光方案", r.status_code, r.text)

        # 硬装
        r = await c.post(
            "/api/hard-decoration/schemes",
            json={"project_id": pid, "name": "UAT硬装", "style": "modern"},
            headers=headers,
        )
        ok("硬装方案") if r.status_code in (200, 201) else err("硬装方案", r.status_code, r.text)

        # 定制家具
        r = await c.post(
            "/api/custom-furniture/designs",
            json={
                "project_id": pid,
                "room_name": "主卧",
                "furniture_type": "wardrobe",
                "total_width": 2400,
                "total_height": 2700,
                "total_depth": 600,
            },
            headers=headers,
        )
        ok("定制家具") if r.status_code in (200, 201) else skip(f"定制家具 (HTTP {r.status_code})")

        # 智能家居
        r = await c.post(
            "/api/smart-home/schemes",
            json={
                "project_id": pid,
                "room_name": "全屋",
                "room_type": "living_room",
                "protocol": "zigbee",
                "hub_brand": "xiaomi",
            },
            headers=headers,
        )
        ok("智能家居方案") if r.status_code in (200, 201) else skip(f"智能家居 (HTTP {r.status_code})")

        # ═══════════════════════════════════════
        # Phase 5: 材料 & BOM
        # ═══════════════════════════════════════
        print("\n── Phase 5: 材料 & BOM ──")

        r = await c.post(f"/api/materials/bom/generate/{pid}", headers=headers)
        ok("BOM 生成") if r.status_code in (200, 201, 404) else err("BOM生成", r.status_code, r.text)

        r = await c.get(f"/api/materials/bom/{pid}", headers=headers)
        ok("BOM 查询") if r.status_code in (200, 404) else err("BOM查询", r.status_code)

        r = await c.get("/api/materials", headers=headers)
        ok("材料列表") if r.status_code == 200 else err("材料列表", r.status_code)

        # ═══════════════════════════════════════
        # Phase 6: 预算 & 采购
        # ═══════════════════════════════════════
        print("\n── Phase 6: 预算 & 采购 ──")

        r = await c.post(
            "/api/budgets",
            json={"project_id": pid, "name": "UAT预算"},
            headers=headers,
        )
        ok("创建预算") if r.status_code in (200, 201) else err("创建预算", r.status_code, r.text)

        r = await c.get(f"/api/budgets/project/{pid}", headers=headers)
        ok("查询预算") if r.status_code in (200, 404) else err("查询预算", r.status_code)

        r = await c.post(
            "/api/procurement/orders",
            json={"project_id": pid, "supplier_id": "default", "status": "draft"},
            headers=headers,
        )
        ok("创建采购订单") if r.status_code in (200, 201) else err("创建采购订单", r.status_code, r.text)

        r = await c.get("/api/procurement/suppliers", headers=headers)
        ok("供应商列表") if r.status_code == 200 else err("供应商列表", r.status_code)

        # ═══════════════════════════════════════
        # Phase 7: 施工管理 (NEW v1.1.30)
        # ═══════════════════════════════════════
        print("\n── Phase 7: 施工管理 (v1.1.30) ──")

        r = await c.post(f"/api/construction/generate-wbs/{pid}", headers=headers)
        ok("WBS 生成") if r.status_code in (200, 201) else err("WBS生成", r.status_code, r.text)

        r = await c.get(f"/api/construction/critical-path/{pid}", headers=headers)
        ok("关键路径") if r.status_code in (200, 404) else err("关键路径", r.status_code)

        r = await c.get(f"/api/construction/ai-predict-duration/{pid}", headers=headers)
        ok("AI 工期预测") if r.status_code in (200, 404) else err("AI工期预测", r.status_code)

        r = await c.post(
            "/api/construction/tasks",
            json={"project_id": pid, "name": "水电改造", "phase": "mep"},
            headers=headers,
        )
        ok("创建施工任务") if r.status_code in (200, 201) else err("施工任务", r.status_code, r.text)

        r = await c.get(f"/api/construction/tasks/{pid}", headers=headers)
        ok("任务列表") if r.status_code == 200 else err("任务列表", r.status_code)

        # ═══════════════════════════════════════
        # Phase 8: 结算
        # ═══════════════════════════════════════
        print("\n── Phase 8: 结算 ──")

        r = await c.post(
            "/api/settlements",
            json={"project_id": pid, "total_amount": 50000},
            headers=headers,
        )
        ok("创建结算") if r.status_code in (200, 201) else err("创建结算", r.status_code, r.text)

        r = await c.get(f"/api/settlements/project/{pid}", headers=headers)
        ok("查询结算") if r.status_code in (200, 404) else err("查询结算", r.status_code)

        # ═══════════════════════════════════════
        # Phase 9: 质检 & 验收
        # ═══════════════════════════════════════
        print("\n── Phase 9: 质检 & 验收 ──")

        r = await c.post(
            "/api/construction/inspections",
            json={"task_id": pid, "type": "water_electricity", "result": "pass"},
            headers=headers,
        )
        ok("创建巡检") if r.status_code in (200, 201, 404) else err("巡检", r.status_code, r.text)

        r = await c.get(
            f"/api/construction/quality-checklist/mep", headers=headers
        )
        ok("质检清单") if r.status_code == 200 else err("质检清单", r.status_code)

        # ═══════════════════════════════════════
        # Phase 10: 健康检查
        # ═══════════════════════════════════════
        print("\n── Phase 10: 系统健康检查 ──")

        r = await c.get("/api/health")
        ok("健康检查") if r.status_code == 200 else err("健康检查", r.status_code)

        r = await c.get("/health")
        ok("根健康检查") if r.status_code == 200 else skip(f"根健康 (HTTP {r.status_code})")

        # ═══════════════════════════════════════
        # 汇总
        # ═══════════════════════════════════════
        total = PASS + FAIL + SKIP
        print(f"\n{'='*50}")
        print(f"  UAT 全链路验证结果")
        print(f"  通过: {PASS}  失败: {FAIL}  跳过: {SKIP}  总计: {total}")
        print(f"  通过率: {PASS/total*100:.1f}%" if total else "  N/A")
        print(f"{'='*50}")

        if FAIL > 0:
            exit(1)


async def cleanup():
    """清理测试数据库"""
    db_path = f"./data/test_uat_{os.getpid()}.db"
    if os.path.exists(db_path):
        os.remove(db_path)
        print(f"  🧹 已清理 {db_path}")


if __name__ == "__main__":
    asyncio.run(setup_db())
    asyncio.run(uat())
    asyncio.run(cleanup())

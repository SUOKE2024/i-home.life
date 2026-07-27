#!/usr/bin/env python
"""量房流程全链路 E2E 验证 — 覆盖 schema 标准化 + 业务操作 + 数据一致性"""
import asyncio
import os
import sys

_project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

os.environ["DATABASE_URL"] = f"sqlite+aiosqlite:///./data/test_survey_e2e_{os.getpid()}.db"

from app.database import engine, Base

async def setup_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

from app.main import app
from httpx import AsyncClient, ASGITransport
from app.models.user import User

PASS = 0
FAIL = 0

def ok(msg, detail=""):
    global PASS; PASS += 1
    print(f"  ✅ {msg}{' — ' + detail if detail else ''}")

def err(msg, code=0, body=""):
    global FAIL; FAIL += 1
    short = str(body)[:120] if body else ""
    print(f"  ❌ {msg} (HTTP {code}) {short}")

async def main():
    transport = ASGITransport(app=app)

    print("\n" + "=" * 60)
    print("  量房全链路 E2E 验证")
    print("=" * 60)

    async with AsyncClient(transport=transport, base_url="http://test") as c:
        # ── 注册/登录 ──
        r = await c.post("/api/auth/register", json={
            "phone": "13800000001", "name": "量房测试", "password": "test123456"
        })
        assert r.status_code == 201
        token = r.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}
        ok("注册 + 获取 token")

        # ── 创建项目 ──
        r = await c.post("/api/projects", json={
            "name": "量房E2E测试项目", "address": "深圳市南山区", "area_sqm": 120.0, "status": "active"
        }, headers=headers)
        assert r.status_code in (200, 201)
        pid = r.json()["id"]
        ok("创建项目", pid[:8])

        # ═══════════════════════════════════════
        # 1. Schema 验证: SurveyCreate
        # ═══════════════════════════════════════
        print("\n── 1. Schema 验证: SurveyCreate ──")

        r = await c.post("/api/surveys", json={
            "project_id": pid,
            "name": "全功能测试测量",
            "surveyor": "张工",
            "method": "lidar",
            "scene_type": "indoor",
            "wall_height": 2.8,
            "rooms": [
                {"name": "客厅", "room_type": "living_room", "width": 6.0, "length": 5.0, "height": 3.2, "notes": "挑高设计"},
                {"name": "主卧", "room_type": "bedroom", "width": 4.0, "length": 3.5},
                {"name": "厨房", "room_type": "kitchen", "width": 3.0, "length": 2.5},
            ],
            "scan_data": '{"raw_points": 50000, "duration_sec": 120}',
            "voice_transcript": "用户说：「测量客厅」→ AI:「请对准墙角」→ 用户确认",
            "device_info": '{"device": "iPhone 15 Pro", "os": "iOS 18.2", "lidar": true}',
            "notes": "E2E 验证用"
        }, headers=headers)

        if r.status_code != 201:
            err("创建测量（含全字段）", r.status_code, r.text)
            return
        data = r.json()
        sid = data["id"]
        ok("创建测量", f"survey_id={sid[:8]}")

        # 验证 schema 结构化返回
        rooms = data.get("rooms", [])
        if not isinstance(rooms, list) or len(rooms) != 3:
            err("响应 rooms 不是 list[3]", 0, f"type={type(rooms).__name__}, len={len(rooms)}")
        else:
            ok("rooms 是结构化列表", f"len={len(rooms)}")

        # 验证首个房间有 height
        r0 = rooms[0]
        if r0.get("name") == "客厅" and r0.get("height") == 3.2:
            ok("客厅 height=3.2 (挑高字段)", f"area={r0['area']}")
        else:
            err(f"客厅 height 期望 3.2", 0, str(r0))

        # 验证 area 自动计算
        r2 = rooms[2]
        if r2.get("area") == 7.5:
            ok("厨房 area 自动计算 3.0×2.5=7.5")
        else:
            err(f"厨房 area 期望 7.5", 0, str(r2))

        # 验证新字段
        checks = [
            ("scan_data", data.get("scan_data") is not None, "scan_data 非空"),
            ("voice_transcript", data.get("voice_transcript") is not None, "voice_transcript 非空"),
            ("device_info", data.get("device_info") is not None, "device_info 非空"),
            ("scene_type", data.get("scene_type") == "indoor", "scene_type=indoor"),
            ("total_area", data.get("total_area") == 51.5, f"total_area=51.5 (got {data.get('total_area')})"),
        ]
        for label, cond, desc in checks:
            if cond:
                ok(desc)
            else:
                err(desc, 0, str(data.get(label)))

        # ═══════════════════════════════════════
        # 2. Schema 验证: SurveyUpdate
        # ═══════════════════════════════════════
        print("\n── 2. Schema 验证: SurveyUpdate ──")

        r = await c.put(f"/api/surveys/{sid}", json={
            "scene_type": "balcony",
            "device_info": '{"device": "updated"}',
            "scan_data": '{"status": "re-scanned"}',
            "voice_transcript": "重新测量完成",
        }, headers=headers)

        if r.status_code != 200:
            err("更新测量（scene_type+device_info+scan+voice）", r.status_code, r.text)
        else:
            data = r.json()
            checks2 = [
                ("scene_type", data.get("scene_type") == "balcony", "scene_type → balcony"),
                ("device_info", data.get("device_info") == '{"device": "updated"}', "device_info 已更新"),
                ("scan_data", data.get("scan_data") == '{"status": "re-scanned"}', "scan_data 已更新"),
                ("voice_transcript", data.get("voice_transcript") == "重新测量完成", "voice_transcript 已更新"),
                ("rooms 仍在", len(data.get("rooms", [])) == 3, "rooms 保留 3 个房间"),
            ]
            for label, cond, desc in checks2:
                if cond:
                    ok(desc)
                else:
                    err(desc, 0, str(data.get(label)))

        # ═══════════════════════════════════════
        # 3. 获取单条测量详情
        # ═══════════════════════════════════════
        print("\n── 3. 获取测量详情 ──")

        r = await c.get(f"/api/surveys/{sid}", headers=headers)
        if r.status_code != 200:
            err("获取测量详情", r.status_code, r.text)
        else:
            data = r.json()
            if data.get("rooms") and isinstance(data["rooms"], list):
                ok("详情 rooms 结构化返回", f"len={len(data['rooms'])}")
            else:
                err(f"详情 rooms 非结构化: {type(data.get('rooms')).__name__}")

        # ═══════════════════════════════════════
        # 4. Apply survey → project floors/rooms
        # ═══════════════════════════════════════
        print("\n── 4. Apply 测量 → 楼层/房间 ──")

        r = await c.post(f"/api/surveys/{sid}/apply", headers=headers)
        if r.status_code != 200:
            err("Apply 测量到项目", r.status_code, r.text)
        else:
            rjson = r.json()
            ok("Apply 成功", f"added={rjson['added']}, updated={rjson['updated']}, total={rjson['total_area']}㎡")

        # 验证项目 total_area 已更新
        r = await c.get(f"/api/projects/{pid}", headers=headers)
        if r.status_code == 200:
            proj_area = r.json().get("total_area", 0)
            if proj_area == 51.5:
                ok("项目 total_area 已同步", f"{proj_area}㎡")
            else:
                err(f"项目 total_area 期望 51.5", 0, str(proj_area))

        # ═══════════════════════════════════════
        # 5. FloorPlan 验证
        # ═══════════════════════════════════════
        print("\n── 5. FloorPlan 验证 ──")

        # 不传 data（使用默认 ""）
        r = await c.post("/api/floorplans", json={
            "project_id": pid,
            "name": "测试户型方案",
            "total_area": 51.5,
            "room_count": 3,
        }, headers=headers)
        if r.status_code in (200, 201):
            ok("创建户型（data 默认空）", f"status={r.status_code}")
        else:
            err("创建户型（data 默认空）", r.status_code, r.text)

        # ═══════════════════════════════════════
        # 6. 认证校验
        # ═══════════════════════════════════════
        print("\n── 6. 认证越权校验 ──")

        r = await c.get("/api/surveys/project/no-such-id")
        ok("无认证列表", f"HTTP {r.status_code}") if r.status_code in (401, 403) else err("无认证列表", r.status_code)

        # ═══════════════════════════════════════
        # 7. 列表查询
        # ═══════════════════════════════════════
        print("\n── 7. 测量列表查询 ──")

        r = await c.get(f"/api/surveys/project/{pid}", headers=headers)
        if r.status_code == 200:
            surveys = r.json()
            if len(surveys) >= 1:
                ok("列表查询", f"{len(surveys)} 条记录")
            else:
                err("列表为空", 0)
        else:
            err("列表查询失败", r.status_code)

        # ═══════════════════════════════════════
        # 8. 删除测量
        # ═══════════════════════════════════════
        print("\n── 8. 删除测量 ──")

        r = await c.delete(f"/api/surveys/{sid}", headers=headers)
        ok("删除测量", f"HTTP {r.status_code}") if r.status_code == 204 else err("删除测量", r.status_code, r.text)

        # 验证已删除
        r = await c.get(f"/api/surveys/{sid}", headers=headers)
        ok("删除后 404", f"HTTP {r.status_code}") if r.status_code == 404 else err("删除后仍可访问", r.status_code)

    # ── 汇总 ──
    total = PASS + FAIL
    print(f"\n{'='*60}")
    print(f"  量房 E2E 验证结果")
    print(f"  通过: {PASS}  失败: {FAIL}  总计: {total}")
    print(f"  通过率: {PASS/total*100:.1f}%" if total else "  N/A")
    print(f"{'='*60}")

    if FAIL > 0:
        sys.exit(1)

async def cleanup():
    db_path = f"./data/test_survey_e2e_{os.getpid()}.db"
    if os.path.exists(db_path):
        os.remove(db_path)
        print(f"  🧹 已清理 {db_path}")

if __name__ == "__main__":
    asyncio.run(setup_db())
    try:
        asyncio.run(main())
    finally:
        asyncio.run(cleanup())

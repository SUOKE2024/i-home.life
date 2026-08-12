#!/usr/bin/env python3
"""演示项目全景全量全链路验证脚本

对演示业主（张先生 13800138000）名下的全部模拟项目，逐一调用所有功能模块
API 端点，校验状态码与数据量，输出 Markdown 报告。用于「种子数据完整、真实、
合理」与「全景全量全链路验证完整功能模块」的自动化核验。

用法：
  python scripts/verify_demo_projects.py                 # 默认 http://localhost:8000
  python scripts/verify_demo_projects.py https://i-home.life
  python scripts/verify_demo_projects.py https://118.31.223.213:8081
"""

import json
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

API = (sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8000").rstrip("/")
PHONE = "13800138000"
PASSWORD = "123456"

REPORT_DIR = Path(__file__).resolve().parent.parent / "reports"
REPORT = REPORT_DIR / f"demo-projects-verify-{time.strftime('%Y%m%d-%H%M%S')}.md"

# 各项目模块预期数据量（对齐 scripts/seed_demo_data.py DEMO_PROJECTS 配置）
# key 为项目名；值为 {端点关键字: 预期数据量}，-1 表示期望 200 但不校验数量
EXPECT = {
    "云栖雅苑 · 智能整装": {
        "floorplans": 1, "budget_lines": 9, "tasks": 7, "milestones": 5,
        "alerts": 3, "quality_issues": 2, "quality_assessments": 1,
        "orders": 2, "order_lines": 3, "settlement_lines": 4, "schemes": 3, "devices": 8,
        "feed": 9,
    },
    "滇池湖畔 · 现代简约": {
        "floorplans": 1, "budget_lines": 8, "tasks": 4, "milestones": 5,
        "alerts": 1, "quality_issues": 1, "quality_assessments": 0,
        "orders": 2, "order_lines": 2, "settlement_lines": 0, "schemes": 2, "devices": 5,
        "feed": 6,
    },
    "翠湖名邸 · 原木奶油风": {
        "floorplans": 1, "budget_lines": 6, "tasks": 0, "milestones": 5,
        "alerts": 0, "quality_issues": 0, "quality_assessments": 0,
        "orders": 0, "order_lines": 0, "settlement_lines": 0, "schemes": 1, "devices": 3,
        "feed": 4,
    },
}

# 校验失败项
FAILURES: list[str] = []
PASS_COUNT = 0
FAIL_COUNT = 0


def _req(method: str, path: str, token: str | None = None, body: dict | None = None):
    # 节流：后端限流 60 次/分钟/IP，错峰避免 429（单次验证约 45 请求，间隔 0.3s 足够）
    time.sleep(0.3)
    url = API + path
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("Content-Type", "application/json")
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            raw = resp.read()
            return resp.status, (json.loads(raw) if raw else None)
    except urllib.error.HTTPError as e:
        return e.code, None
    except Exception as e:  # noqa: BLE001 — 网络/超时等统一捕获
        return 0, {"error": str(e)}


def _check(name: str, ok: bool, detail: str) -> None:
    global PASS_COUNT, FAIL_COUNT
    if ok:
        PASS_COUNT += 1
        print(f"  ✅ {name}: {detail}")
    else:
        FAIL_COUNT += 1
        FAILURES.append(f"{name}: {detail}")
        print(f"  ❌ {name}: {detail}")


def _len(value) -> int:
    if isinstance(value, list):
        return len(value)
    if isinstance(value, dict):
        return len(value)
    return 0


def main() -> int:
    print("# 演示项目全景全量全链路验证报告")
    print(f"\n**时间**: {time.strftime('%Y-%m-%d %H:%M:%S')} | **API**: `{API}`")
    print()

    lines = ["# 演示项目全景全量全链路验证报告",
             f"\n**时间**: {time.strftime('%Y-%m-%d %H:%M:%S')} | **API**: `{API}`",
             f"\n**账号**: {PHONE}（演示业主）", ""]

    # ── 1. 登录 ──
    status, data = _req("POST", "/api/auth/login", body={"phone": PHONE, "password": PASSWORD})
    token = (data or {}).get("access_token") if status == 200 else None
    if not token:
        print("❌ 演示账号登录失败，终止验证")
        lines.append("## ❌ 演示账号登录失败")
        REPORT_DIR.mkdir(parents=True, exist_ok=True)
        REPORT.write_text("\n".join(lines), encoding="utf-8")
        return 1
    print("✅ 演示账号登录成功")
    lines.append("## ✅ 认证\n- `POST /api/auth/login` → 200，获取 PASETO Token")

    # ── 2. 全库/材料（全局模块）──
    print("\n## 全局模块")
    lines.append("\n## 全局模块")
    s, d = _req("GET", "/api/dashboard/overview", token)
    ov_projects = ((d or {}).get("projects") or {}).get("total", 0) if s == 200 else -1
    _check(f"dashboard/overview (HTTP {s})", s == 200 and ov_projects >= 3,
           f"项目总数 {ov_projects} ≥ 3")
    lines.append(f"- `GET /api/dashboard/overview` → {s}，项目总数 {ov_projects}")
    s, d = _req("GET", "/api/materials/categories", token)
    _check(f"materials/categories (HTTP {s})", s == 200 and _len(d) >= 5, f"{_len(d)} 个分类")
    lines.append(f"- `GET /api/materials/categories` → {s}，{_len(d)} 个分类")

    # ── 3. 逐项目全链路 ──
    s, projects = _req("GET", "/api/projects", token)
    if s != 200 or not isinstance(projects, list):
        print("❌ 项目列表获取失败")
        return 1
    print(f"\n## 逐项目全链路（共 {len(projects)} 个项目）")
    lines.append(f"\n## 逐项目全链路（共 {len(projects)} 个项目）")

    for proj in projects:
        pid = proj["id"]
        pname = proj["name"]
        expect = EXPECT.get(pname, {})
        print(f"\n### {pname}（{proj.get('status')} / {proj.get('phase')}）")
        lines.append(f"\n### {pname}（{proj.get('status')} / {proj.get('phase')}）")

        checks: list[tuple[str, Any, int, int]] = []

        # 项目详情
        s, d = _req("GET", f"/api/projects/{pid}", token)
        ok = s == 200 and d is not None
        checks.append(("project_detail", ok, 1 if ok else -1, 1))
        _check(f"project_detail (HTTP {s})", ok, "返回项目详情")

        # 户型
        s, plans = _req("GET", f"/api/floorplans/project/{pid}", token)
        checks.append(("floorplans", s == 200, _len(plans), expect.get("floorplans", -1)))
        _check(f"floorplans (HTTP {s})", s == 200 and _len(plans) == expect.get("floorplans", -1),
               f"{_len(plans)} 个户型（预期 {expect.get('floorplans')}）")
        if plans:
            s, plan_d = _req("GET", f"/api/floorplans/{plans[0]['id']}", token)
            _check(f"floorplan_detail (HTTP {s})", s == 200 and plan_d is not None, "含 rooms 几何")
            checks.append(("floorplan_detail", s == 200, 1 if s == 200 else -1, 1))

        # 预算
        s, budget = _req("GET", f"/api/budgets/project/{pid}", token)
        b_lines = _len((budget or {}).get("lines")) if isinstance(budget, dict) else -1
        checks.append(("budget_lines", s == 200, b_lines, expect.get("budget_lines", -1)))
        _check(f"budget (HTTP {s})", s == 200 and b_lines == expect.get("budget_lines", -1),
               f"{b_lines} 条明细（预期 {expect.get('budget_lines')}）")

        # 施工任务
        s, tasks = _req("GET", f"/api/construction/tasks/{pid}", token)
        checks.append(("tasks", s == 200, _len(tasks), expect.get("tasks", -1)))
        _check(f"construction/tasks (HTTP {s})", s == 200 and _len(tasks) == expect.get("tasks", -1),
               f"{_len(tasks)} 个任务（预期 {expect.get('tasks')}）")

        # 进度预警
        s, alerts = _req("GET", f"/api/construction/progress-alerts/{pid}", token)
        checks.append(("alerts", s == 200, _len(alerts), expect.get("alerts", -1)))
        _check(f"progress-alerts (HTTP {s})", s == 200 and _len(alerts) == expect.get("alerts", -1),
               f"{_len(alerts)} 条预警（预期 {expect.get('alerts')}）")

        # 里程碑
        s, milestones = _req("GET", f"/api/construction/milestones/{pid}", token)
        checks.append(("milestones", s == 200, _len(milestones), expect.get("milestones", -1)))
        _check(f"milestones (HTTP {s})", s == 200 and _len(milestones) == expect.get("milestones", -1),
               f"{_len(milestones)} 条（预期 {expect.get('milestones')}）")

        # 质检问题
        s, issues = _req("GET", f"/api/construction/quality-issues/{pid}", token)
        checks.append(("quality_issues", s == 200, _len(issues), expect.get("quality_issues", -1)))
        _check(f"quality-issues (HTTP {s})", s == 200 and _len(issues) == expect.get("quality_issues", -1),
               f"{_len(issues)} 条（预期 {expect.get('quality_issues')}）")

        # 采购订单 + 明细
        s, orders = _req("GET", f"/api/procurement/orders/{pid}", token)
        order_line_count = sum(_len((o or {}).get("lines")) for o in orders) if isinstance(orders, list) else -1
        checks.append(("orders", s == 200, _len(orders), expect.get("orders", -1)))
        _check(f"procurement/orders (HTTP {s})", s == 200 and _len(orders) == expect.get("orders", -1),
               f"{_len(orders)} 个订单（预期 {expect.get('orders')}）")
        _check("order_lines", order_line_count == expect.get("order_lines", -1),
               f"{order_line_count} 条明细（预期 {expect.get('order_lines')}）")
        checks.append(("order_lines", order_line_count == expect.get("order_lines", -1),
                       order_line_count, expect.get("order_lines", -1)))

        # 结算 + 明细（无结算项目 API 返回 404 属合理行为，等价于 0 行）
        s, settlement = _req("GET", f"/api/settlements/project/{pid}", token)
        expect_sl = expect.get("settlement_lines", -1)
        if expect_sl == 0:
            ok = (s == 200 and isinstance(settlement, dict)
                  and _len((settlement or {}).get("lines")) == 0) or s == 404
            s_lines = 0
        else:
            s_lines = _len((settlement or {}).get("lines")) if isinstance(settlement, dict) else -1
            ok = s == 200 and s_lines == expect_sl
        checks.append(("settlement_lines", ok, s_lines, expect_sl))
        _check(f"settlements (HTTP {s})", ok, f"{s_lines} 条明细（预期 {expect_sl}）")

        # 智能家居方案（响应含 device_count 字段，无 devices 列表）
        s, schemes = _req("GET", f"/api/smart-home/schemes/project/{pid}", token)
        device_count = sum((x or {}).get("device_count", 0) for x in schemes) if isinstance(schemes, list) else -1
        checks.append(("schemes", s == 200, _len(schemes), expect.get("schemes", -1)))
        _check(f"smart-home/schemes (HTTP {s})", s == 200 and _len(schemes) == expect.get("schemes", -1),
               f"{_len(schemes)} 个方案（预期 {expect.get('schemes')}）")
        checks.append(("devices", s == 200, device_count, expect.get("devices", -1)))
        _check("smart_devices", device_count == expect.get("devices", -1),
               f"{device_count} 个设备（预期 {expect.get('devices')}）")

        # 首页 feed
        s, feed = _req("GET", f"/api/feed/{pid}", token)
        cards = _len((feed or {}).get("cards")) if isinstance(feed, dict) else -1
        checks.append(("feed", s == 200, cards, expect.get("feed", -1)))
        _check(f"feed (HTTP {s})", s == 200 and cards == expect.get("feed", -1),
               f"{cards} 张卡片（预期 {expect.get('feed')}）")

        # 报告行（checks 索引：0 详情 /1 户型 /2 户型详情 /3 预算 /4 任务 /5 预警 /6 里程碑 /
        # 7 质检 /8 订单 /9 订单明细 /10 结算 /11 方案 /12 设备 /13 feed）
        lines.append(f"- 项目详情 `GET /api/projects/{pid}`（上文记录）")
        lines.append(f"- 户型 {checks[1][2]}/{checks[1][3]} · 预算明细 {checks[3][2]}/{checks[3][3]} · "
                     f"施工任务 {checks[4][2]}/{checks[4][3]} · 预警 {checks[5][2]}/{checks[5][3]} · "
                     f"里程碑 {checks[6][2]}/{checks[6][3]} · 质检问题 {checks[7][2]}/{checks[7][3]} · "
                     f"采购订单 {checks[8][2]}/{checks[8][3]}（明细 {checks[9][2]}/{checks[9][3]}）· "
                     f"结算明细 {checks[10][2]}/{checks[10][3]} · 智能家居方案 {checks[11][2]}/{checks[11][3]}"
                     f"（设备 {checks[12][2]}/{checks[12][3]}）· feed {checks[13][2]}/{checks[13][3]}")

    # ── 汇总 ──
    print(f"\n## 汇总：PASS {PASS_COUNT} / FAIL {FAIL_COUNT}")
    lines.append(f"\n## 汇总\n- ✅ PASS: {PASS_COUNT}\n- ❌ FAIL: {FAIL_COUNT}")
    if FAILURES:
        print("失败项：")
        lines.append("\n### 失败项")
        for f in FAILURES:
            print(f"  - {f}")
            lines.append(f"- {f}")
    else:
        print("🎉 全部功能模块验证通过")
        lines.append("\n🎉 全部功能模块验证通过")

    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    REPORT.write_text("\n".join(lines), encoding="utf-8")
    print(f"\n报告已保存: {REPORT}")
    return 0 if FAIL_COUNT == 0 else 1


if __name__ == "__main__":
    sys.exit(main())

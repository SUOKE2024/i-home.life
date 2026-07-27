#!/usr/bin/env python3
"""前后端全量全链路 E2E 验证 — v1.2.4+
适配 Flutter SPA 架构，涵盖 PASETO 认证 / Project CRUD / Agent LLM / 物料 / Web 资源 / 详细健康检查
"""

import json, os, sys, time, urllib.request, urllib.error

API_HOST = os.environ.get("API_HOST", "http://118.31.223.213:8081")
BASE = API_HOST + "/api"
passed = 0
total = 0
errors = []  # 收集失败项详情

def api(method, path, body=None, token=None, timeout=30):
    """调用 API 端点，返回 (status_code, parsed_json_body)。

    注意：部分端点（如 DELETE）返回 204 No Content 无响应体，
    此时 parsed_json_body 为 {}。
    """
    url = BASE + path
    data = json.dumps(body).encode() if body else None
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("Content-Type", "application/json")
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            raw = r.read()
            if r.status == 204 or not raw.strip():
                return r.status, {}
            return r.status, json.loads(raw.decode())
    except urllib.error.HTTPError as e:
        raw = e.read()
        if e.code == 204 or not raw.strip():
            return e.code, {}
        try:
            return e.code, json.loads(raw.decode())
        except json.JSONDecodeError:
            return e.code, {"raw": raw.decode()[:500]}
    except Exception as ex:
        return 0, {"error": str(ex)}

def check(name, ok, detail=""):
    global passed, total
    total += 1
    if ok:
        passed += 1
        print(f"  OK  {name}")
    else:
        errors.append(f"{name}" + (f"  ({detail})" if detail else ""))
        print(f"  FAIL {name}" + (f"  [{detail}]" if detail else ""))

def skip(name):
    """跳过检查（不纳入通过/失败统计）"""
    print(f"  SKIP {name}")

# ════════════════
print("=" * 55)
print("  前后端全量全链路 E2E 验证")
print("=" * 55)

# 1. Health
print("\n[1] 健康检查")
s, d = api("GET", "/health")
check("GET /api/health -> 200", s == 200 and d.get("status") == "ok")
check("Version: " + d.get("version", "?"), d.get("version") is not None)

# 2. Auth
print("\n[2] PASETO 认证")
s, d = api("POST", "/auth/login",
    body={"phone": "13800138000", "password": "123456"})
check("POST /auth/login -> 200", s == 200)
TOKEN = d.get("access_token", "")
check("access_token exists", len(TOKEN) > 20)
check("token prefix v4.local.", TOKEN.startswith("v4.local."))
s, d = api("GET", "/auth/me", token=TOKEN)
check("GET /auth/me -> 200", s == 200 and d.get("phone") == "13800138000")
s, _ = api("GET", "/auth/me", token="invalid")
check("Invalid token -> 401", s == 401)

# 3. Project CRUD
print("\n[3] 项目 CRUD")
s, d = api("POST", "/projects", token=TOKEN, body={
    "name": "E2E 验证项目",
    "address": "北京",
    "total_area": 100.0,
    "project_type": "full_renovation",
})
PROJECT_ID = d.get("id", "")
check("POST /projects -> 201/200", s in (200, 201),
      f"HTTP {s} => {d.get('detail', json.dumps(d, ensure_ascii=False)[:200])}")
check("project.id returned", len(PROJECT_ID) > 0)
s, d = api("GET", "/projects", token=TOKEN)
check("GET /projects -> 200", s == 200 and isinstance(d, list))
if PROJECT_ID:
    s, d = api("GET", f"/projects/{PROJECT_ID}", token=TOKEN)
    check("GET /projects/:id -> 200", s == 200 and d.get("name") == "E2E 验证项目")
else:
    skip("GET /projects/:id (跳过，无 PROJECT_ID)")

# 4. Agent 真实 LLM（推理模型，每项 ~15-60s）
print("\n[4] Agent 真实 LLM 调用")

agents = [
    ("designer",    "一句话描述北欧风格的设计特点"),
    ("concierge",   "装修第一步做什么？请简要回答"),
    ("budget",      "120平米装修预算范围？简答"),
    ("settlement",  "装修完工结算要注意什么？简答"),
]

for at, msg in agents:
    sys.stdout.write(f"  {at:20s} ... "); sys.stdout.flush()
    t0 = time.time()
    s, d_ = api("POST", "/agents/chat",
        body={"message": msg, "agent_type": at},
        token=TOKEN, timeout=240)
    elapsed = int(time.time() - t0)
    ok = s == 200 and "reply" in d_
    reply_len = len(d_.get("reply", "")) if ok else 0
    status = f"OK  HTTP {s}  ({elapsed}s, {reply_len} chars)" if ok else f"FAIL HTTP {s} ({elapsed}s)"
    check(f"{at:20s} -> {status}", ok)

# 5. Materials
print("\n[5] 物料库")
s, d = api("GET", "/materials/categories", token=TOKEN)
check("GET /materials/categories -> 200", s == 200,
      f"HTTP {s} => {d.get('detail', str(d)[:200])}")

# 5b. Materials list (需要认证)
s, _ = api("GET", "/materials?limit=5", token=TOKEN)
check("GET /materials (auth) -> 200", s == 200,
      f"HTTP {s}")

# 5c. Materials no-auth rejection
s, _ = api("GET", "/materials?limit=5")
check("GET /materials (no auth) -> 401/403", s in (401, 403),
      f"HTTP {s}")

# 6. Web 静态资源（Flutter SPA 架构）
print("\n[6] Web 静态资源 (Flutter SPA)")
WEB_HOST = os.environ.get("API_HOST", "http://118.31.223.213:8081")
# v1.2.0+: 项目已迁移到 Flutter SPA，旧 HTML 页面不存在（nginx 返回 410）
# 仅检查 Flutter SPA 核心资源 + PWA 文件
flutter_assets = {
    "/index.html":          200,   # Flutter 入口
    "/main.dart.js":        200,   # Flutter JS 产物（Flutter 3.x+ 使用 main.dart.js）
    "/flutter.js":          200,   # Flutter 加载器
    "/manifest.json":       200,   # PWA 清单
    "/sw.js":               200,   # Service Worker
    "/version.json":        200,   # 构建版本
    "/favicon.png":         200,   # 网站图标
    "/flutter_service_worker.js": 200,  # Flutter 的 PWA Service Worker
}

for path, expected_status in flutter_assets.items():
    try:
        r = urllib.request.urlopen(f"{WEB_HOST}{path}", timeout=5)
        ok = r.status == expected_status
        detail = f"HTTP {r.status}" if not ok else ""
    except urllib.error.HTTPError as e:
        ok = False
        detail = f"HTTP {e.code}"
    except Exception as ex:
        ok = False
        detail = str(ex)[:100]
    check(path, ok, detail)

# 7. 详细健康检查
print("\n[7] 健康检查详情")
s, d = api("GET", "/health/detail", token=TOKEN)
check("GET /api/health/detail -> 200", s == 200,
      f"HTTP {s}")
if s == 200:
    checks = d.get("checks", {})
    # database 必须 ok
    db_status = checks.get("database", {}).get("status", "unknown")
    check(f"  database: {db_status}", db_status == "ok",
          f"status={db_status}")
    # secret_manager: ok / disabled / 缺 status 但有 fingerprint 均为正常状态
    sm = checks.get("secret_manager", {})
    if sm.get("enabled") is False:
        print(f"  OK   secret_manager: disabled (feature flag off)")
        passed += 1; total += 1
    elif sm.get("status") == "ok":
        check(f"  secret_manager: ok", True)
    elif sm.get("paseto_key_fingerprint"):
        print(f"  OK   secret_manager: enabled (fingerprint={sm['paseto_key_fingerprint']}, vault={sm.get('vault_configured', False)})")
        passed += 1; total += 1
    else:
        sm_status = sm.get("status", "unknown")
        check(f"  secret_manager: {sm_status}", sm_status == "ok",
              f"status={sm_status}")
    # disk/redis 可能为 degraded/disabled，仅报告不判失败
    for component in ["disk", "redis"]:
        if component in checks:
            status_val = checks[component].get("status", "unknown")
            print(f"  INFO {component}: {status_val}")

# 8. Cleanup
print("\n[8] 清理")
if PROJECT_ID:
    s, _ = api("DELETE", f"/projects/{PROJECT_ID}", token=TOKEN)
    check(f"DELETE /projects/:id -> 200/204", s in (200, 204),
          f"HTTP {s}")
else:
    skip("DELETE /projects/:id (跳过，无 PROJECT_ID)")

# ════════════════
pct = passed * 100 // total if total else 0
print(f"\n{'=' * 55}")
print(f"  E2E: {passed}/{total} 通过 ({pct}%)")
if errors:
    print(f"\n  失败项 ({len(errors)}):")
    for e in errors:
        print(f"    - {e}")
if passed == total:
    print("  全量全链路验证通过!")
else:
    print(f"  共 {len(errors)} 项未通过")
print(f"{'=' * 55}")

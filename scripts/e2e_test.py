#!/usr/bin/env python3
"""前后端全量全链路 E2E 验证 — 快速版（跳过 FunctionCall Agent，耗时 ~3min）"""

import json, os, sys, time, urllib.request, urllib.error

BASE = os.environ.get("API_BASE", "http://118.31.223.213:8081/api")
passed = 0
total = 0

def api(method, path, body=None, token=None, timeout=30):
    url = BASE + path
    data = json.dumps(body).encode() if body else None
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("Content-Type", "application/json")
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            body = r.read().decode() if r.status != 204 else "{}"
            return r.status, json.loads(body)
    except urllib.error.HTTPError as e:
        body = e.read().decode() if e.code != 204 else "{}"
        return e.code, json.loads(body)
    except Exception as e:
        return 0, {"error": str(e)}

def check(name, ok):
    global passed, total
    total += 1
    if ok:
        passed += 1
    print(f"  {'OK' if ok else 'FAIL'} {name}")

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
    "name": "E2E 验证项目", "address": "北京", "area": 100.0, "style": "现代"
})
PROJECT_ID = d.get("id", "")
check("POST /projects -> 201", s == 201)
check("project.id returned", len(PROJECT_ID) > 0)
s, d = api("GET", "/projects", token=TOKEN)
check("GET /projects -> 200", s == 200 and isinstance(d, list))
s, d = api("GET", f"/projects/{PROJECT_ID}", token=TOKEN)
check("GET /projects/:id -> 200", s == 200 and d.get("name") == "E2E 验证项目")

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
s, _ = api("GET", "/materials/categories", token=TOKEN)
check("GET /materials/categories -> 200", s == 200)

# 6. Web Static
print("\n[6] Web 静态资源")
static = [
    "/index.html", "/login.html", "/workbench.html", "/demo.html",
    "/our-story.html", "/settings.html", "/timeline.html",
    "/manifest.json", "/sw.js", "/robots.txt", "/sitemap.xml",
    "/assets/js/api-client.js", "/assets/js/router.js",
    "/assets/css/workbench.css",
]
for f in static:
    try:
        r = urllib.request.urlopen(f"http://118.31.223.213:8081{f}", timeout=5)
        ok = r.status == 200
    except:
        ok = False
    check(f, ok)

# 7. Cleanup
print("\n[7] 清理")
s, _ = api("DELETE", f"/projects/{PROJECT_ID}", token=TOKEN)
check(f"DELETE /projects/:id -> 200/204", s in (200, 204))

# ════════════════
pct = passed * 100 // total if total else 0
print(f"\n{'=' * 55}")
print(f"  E2E: {passed}/{total} 通过 ({pct}%)")
if passed == total:
    print("  全量全链路验证通过!")
print(f"{'=' * 55}")

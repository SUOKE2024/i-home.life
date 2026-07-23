#!/usr/bin/env python3
"""i-home.life API 负载基准测试

使用方式:
  # 1. 启动后端
  source .venv/bin/activate && python -m app.main

  # 2. 运行基准
  python3 scripts/bench-api.py

  # 自定义参数
  python3 scripts/bench-api.py --url http://localhost:8766 --concurrency 20 --requests 200

输出:
  reports/api-bench-YYYYMMDD-HHMMSS.json + .md

v1.2.1 P1-10 修复：原 bench 对鉴权端点（/api/projects 等）不发 Bearer token、
对 POST 端点（register/login）不发 JSON body，导致 100% 4xx 被计为"错误"，
perf-baseline-after.json 7 端点中 6 个 100% 错误率，性能对比结论不可信。
现增加：① 预注册 bench 用户获取 token ② 鉴权 GET 自动带 Authorization
③ register 每请求生成唯一手机号（避免 409）④ login 用有效凭据。
"""
import argparse
import json
import os
import time
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

PROJECT_DIR = Path(__file__).resolve().parent.parent
REPORTS_DIR = PROJECT_DIR / "reports"
REPORTS_DIR.mkdir(exist_ok=True)

# 默认测试端点（优先测试轻量级、高频调用的接口）
DEFAULT_ENDPOINTS = [
    ("GET", "/api/health", "健康检查"),
    ("GET", "/api/openapi.json", "OpenAPI 规范"),
    ("POST", "/api/auth/register", "用户注册"),
    ("POST", "/api/auth/login", "用户登录"),
    ("GET", "/api/projects", "项目列表"),
    ("GET", "/api/materials", "物料列表"),
    ("GET", "/api/config/feature-flags", "特性开关"),
]

# 需要 Bearer token 的 GET 端点前缀
AUTHED_PREFIXES = ("/api/projects", "/api/materials", "/api/config/feature-flags")

BENCH_PASSWORD = "bench123456"


def _post_json(base_url: str, path: str, payload: dict, timeout: int = 10) -> dict:
    """发送 JSON POST 请求，返回解析后的 JSON。"""
    body = json.dumps(payload).encode()
    req = Request(
        f"{base_url}{path}",
        data=body,
        method="POST",
        headers={"Content-Type": "application/json"},
    )
    with urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read())


def setup_bench_user(base_url: str) -> str:
    """预注册一个 bench 用户并返回 access_token，供鉴权 GET 端点使用。

    register 返回 409（已存在）时回退到 login。
    """
    phone = f"139{str(uuid.uuid4().int)[:8]}"
    try:
        data = _post_json(
            base_url,
            "/api/auth/register",
            {"phone": phone, "name": "bench", "password": BENCH_PASSWORD},
        )
        token = data.get("access_token")
        if token:
            return token
    except HTTPError as e:
        if e.code != 409:
            raise
    # 回退：登录已存在用户
    data = _post_json(
        base_url,
        "/api/auth/login",
        {"phone": phone, "name": "bench", "password": BENCH_PASSWORD},
    )
    token = data.get("access_token")
    if not token:
        raise RuntimeError("bench 用户注册/登录均未拿到 access_token")
    return token


def build_request(base_url: str, method: str, path: str, auth_token: str | None) -> Request:
    """根据端点构造单个请求（含鉴权头 / POST body）。

    - GET 鉴权端点：附加 Authorization: Bearer <token>
    - POST /api/auth/register：每请求唯一手机号（避免 409 冲突）
    - POST /api/auth/login：使用 bench 用户凭据（需先 setup_bench_user 同号注册）
    """
    headers: dict[str, str] = {}
    data: bytes | None = None

    # v1.2.1：压测旁路令牌。若设置了 BENCH_RATE_LIMIT_BYPASS_TOKEN 环境变量
    # （需与后端 RATE_LIMIT_BENCH_TOKEN 配置一致），所有请求携带 X-Bench-Token 头，
    # 后端中间件据此跳过速率限制，使基线测量原始吞吐而非限流行为。
    # 未设置时此头不发，后端按正常限流处理（高并发下会出现 429）。
    if _BENCH_TOKEN:
        headers["X-Bench-Token"] = _BENCH_TOKEN

    if method == "GET" and any(path.startswith(p) for p in AUTHED_PREFIXES):
        if auth_token:
            headers["Authorization"] = f"Bearer {auth_token}"
    elif method == "POST" and path == "/api/auth/register":
        phone = f"139{str(uuid.uuid4().int)[:8]}"
        data = json.dumps(
            {"phone": phone, "name": "bench", "password": BENCH_PASSWORD}
        ).encode()
        headers["Content-Type"] = "application/json"
    elif method == "POST" and path == "/api/auth/login":
        # login 端点用预注册用户凭据（setup_bench_user 注册的同一手机号）
        # 注意：register 端点已用唯一手机号，login 这里复用 bench_token 对应用户
        # 无法获知其手机号，故 login 端点单独再注册一个稳定用户用于登录压测
        data = json.dumps(
            {"phone": _LOGIN_PHONE, "name": "bench", "password": BENCH_PASSWORD}
        ).encode()
        headers["Content-Type"] = "application/json"

    return Request(f"{base_url}{path}", data=data, method=method, headers=headers)


# login 压测用的稳定用户手机号（setup 时注册，压测时反复登录）
_LOGIN_PHONE: str = ""

# 压测旁路令牌（main() 从 BENCH_RATE_LIMIT_BYPASS_TOKEN 环境变量读取）
# 非空时 build_request 会为每个请求附加 X-Bench-Token 头，后端据此跳过限流。
_BENCH_TOKEN: str = ""


def setup_login_user(base_url: str) -> str:
    """注册一个专供 login 端点压测的稳定用户，返回其手机号。"""
    global _LOGIN_PHONE
    _LOGIN_PHONE = f"139{str(uuid.uuid4().int)[:8]}"
    _post_json(
        base_url,
        "/api/auth/register",
        {"phone": _LOGIN_PHONE, "name": "bench", "password": BENCH_PASSWORD},
    )
    return _LOGIN_PHONE


def measure_single(base_url: str, method: str, path: str, auth_token: str | None) -> dict:
    """测量单个请求的响应时间（毫秒）"""
    start = time.perf_counter()
    try:
        req = build_request(base_url, method, path, auth_token)
        with urlopen(req, timeout=10) as resp:
            status = resp.status
            elapsed_ms = (time.perf_counter() - start) * 1000
            return {"path": path, "method": method, "status": status, "elapsed_ms": elapsed_ms, "error": None}
    except HTTPError as e:
        # HTTP 错误状态（4xx/5xx）：服务器可达但业务失败，记录状态码便于诊断
        elapsed_ms = (time.perf_counter() - start) * 1000
        return {
            "path": path,
            "method": method,
            "status": e.code,
            "elapsed_ms": elapsed_ms,
            "error": f"HTTP {e.code}",
        }
    except Exception as e:
        elapsed_ms = (time.perf_counter() - start) * 1000
        return {"path": path, "method": method, "status": 0, "elapsed_ms": elapsed_ms, "error": str(e)}


def run_concurrent(url: str, endpoint: tuple, concurrency: int, total: int, auth_token: str | None) -> dict:
    """对单个端点执行并发压力测试"""
    method, path, label = endpoint
    results = []
    errors = 0
    start = time.perf_counter()

    with ThreadPoolExecutor(max_workers=concurrency) as executor:
        futures = [
            executor.submit(measure_single, url, method, path, auth_token)
            for _ in range(total)
        ]
        for future in as_completed(futures):
            r = future.result()
            results.append(r)
            if r["error"]:
                errors += 1

    elapsed = time.perf_counter() - start
    latencies = [r["elapsed_ms"] for r in results]
    latencies.sort()

    if not latencies:
        return {"label": label, "path": path, "total": 0, "errors": total, "error": "all_failed"}

    def pct(p: float) -> float:
        idx = int(len(latencies) * p / 100)
        return latencies[min(idx, len(latencies) - 1)]

    # 统计错误状态码分布（便于诊断 401/422/409 等）
    status_dist: dict[str, int] = {}
    for r in results:
        key = str(r["status"]) if r["status"] else "conn_err"
        status_dist[key] = status_dist.get(key, 0) + 1

    return {
        "label": label,
        "path": path,
        "method": method,
        "total": total,
        "errors": errors,
        "elapsed_sec": round(elapsed, 2),
        "rps": round(total / elapsed, 1) if elapsed > 0 else 0,
        "avg_ms": round(sum(latencies) / len(latencies), 2),
        "min_ms": round(latencies[0], 2),
        "p50_ms": round(pct(50), 2),
        "p90_ms": round(pct(90), 2),
        "p99_ms": round(pct(99), 2),
        "max_ms": round(latencies[-1], 2),
        "status_dist": status_dist,
    }


def write_report(results: list[dict], config: dict, out_json: Path, out_md: Path):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    payload = {"timestamp": ts, "config": config, "results": results}
    out_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    lines = [
        "# i-home.life API 负载基准测试报告",
        f"**时间**: {ts}",
        f"**目标**: {config['url']}",
        f"**并发**: {config['concurrency']} | **总请求**: {config['requests']}",
        "",
        "## 结果",
        "",
        "| 端点 | 方法 | 请求数 | 错误 | RPS | Avg(ms) | P50(ms) | P90(ms) | P99(ms) | Max(ms) |",
        "|------|------|--------|------|-----|---------|---------|---------|---------|---------|",
    ]
    for r in results:
        if "error" in r and "status_dist" not in r:
            err_row = (
                f"| {r['label']} | {r.get('method', '')} | {r.get('total', 0)} "
                f"| {r.get('errors', 0)} | - | - | - | - | - | - |"
            )
            lines.append(err_row)
        else:
            data_row = (
                f"| {r['label']} | {r['method']} | {r['total']} | {r['errors']} "
                f"| {r['rps']} | {r['avg_ms']} | {r['p50_ms']} "
                f"| {r['p90_ms']} | {r['p99_ms']} | {r['max_ms']} |"
            )
            lines.append(data_row)
    lines += [
        "",
        "## 健康阈值",
        "",
        "| 指标 | 优秀 | 良好 | 需优化 |",
        "|------|------|------|--------|",
        "| P50 | <50ms | <100ms | >200ms |",
        "| P90 | <200ms | <500ms | >1000ms |",
        "| 错误率 | 0% | <1% | >5% |",
        "",
        "---",
        "*报告由 scripts/bench-api.py 自动生成*",
    ]
    out_md.write_text("\n".join(lines), encoding="utf-8")


def parse_endpoints(spec: str | None) -> list[tuple] | None:
    """解析 --endpoints 参数；返回 None 表示用默认端点。"""
    if not spec:
        return None
    endpoints = []
    for part in spec.split(";"):
        part = part.strip()
        if not part:
            continue
        m, rest = part.split(":", 1)
        p, label = rest.split(",", 1) if "," in rest else (rest, rest)
        endpoints.append((m.strip(), p.strip(), label.strip()))
    return endpoints


def main():
    ap = argparse.ArgumentParser(description="i-home.life API 负载基准测试")
    ap.add_argument("--url", default="http://localhost:8766", help="后端 API 地址")
    ap.add_argument("--concurrency", type=int, default=10, help="并发 worker 数")
    ap.add_argument("--requests", type=int, default=100, help="每个端点总请求数")
    ap.add_argument("--endpoints", default=None,
                    help="自定义端点, 用分号分隔多个端点, 每个格式 METHOD:/path[,label]; "
                         "例如 'GET:/api/health,健康检查;GET:/api/openapi.json,OpenAPI'")
    args = ap.parse_args()

    endpoints = parse_endpoints(args.endpoints) or DEFAULT_ENDPOINTS

    url = args.url.rstrip("/")
    config = {"url": url, "concurrency": args.concurrency, "requests": args.requests}

    # v1.2.1：读取压测旁路令牌。需与后端 RATE_LIMIT_BENCH_TOKEN 配置一致。
    # 设置后所有请求携带 X-Bench-Token 头跳过限流，测量原始吞吐；
    # 未设置时高并发下会出现 429（基线将反映限流行为而非真实性能）。
    global _BENCH_TOKEN
    _BENCH_TOKEN = os.environ.get("BENCH_RATE_LIMIT_BYPASS_TOKEN", "")

    print("╔══════════════════════════════════════════════╗")
    print("║  i-home.life API 负载基准测试                  ║")
    print("╠══════════════════════════════════════════════╣")
    print(f"  目标: {url}")
    print(f"  并发: {args.concurrency} | 每端点请求: {args.requests}")
    print(f"  端点: {len(endpoints)} 个")
    print(f"  限流旁路: {'已启用（X-Bench-Token）' if _BENCH_TOKEN else '未启用（高并发将触发 429）'}")

    # v1.2.1：预注册 bench 用户，供鉴权 GET + login 压测使用
    auth_token = None
    needs_auth = any(
        m == "GET" and any(p.startswith(pre) for pre in AUTHED_PREFIXES)
        for m, p, _ in endpoints
    )
    needs_login = any(m == "POST" and p == "/api/auth/login" for m, p, _ in endpoints)
    if needs_auth or needs_login:
        print("  预注册 bench 用户...")
        try:
            auth_token = setup_bench_user(url)
            print(f"  ✓ 鉴权 token 已获取（用于 GET 鉴权端点）")
            if needs_login:
                setup_login_user(url)
                print(f"  ✓ login 压测用户已注册（{_LOGIN_PHONE}）")
        except Exception as e:
            print(f"  ⚠ 预注册失败（鉴权/login 端点将报错）: {e}")

    print("╞══════════════════════════════════════════════╡")

    results = []
    for ep in endpoints:
        label = ep[2]
        print(f"  [{label}] 测试中...")
        r = run_concurrent(url, ep, args.concurrency, args.requests, auth_token)
        results.append(r)
        errors = r.get('errors', 1)
        rps_val = r.get('rps', 0)
        p50_val = r.get('p50_ms', '-')
        p90_val = r.get('p90_ms', '-')
        dist = r.get('status_dist', {})
        status = "OK" if errors == 0 else f"{errors} 错误 {dist}"
        print(f"    RPS={rps_val} | P50={p50_val}ms | P90={p90_val}ms | {status}")

    ts = datetime.now().strftime("%Y%m%d-%H%M%S")
    out_json = REPORTS_DIR / f"api-bench-{ts}.json"
    out_md = REPORTS_DIR / f"api-bench-{ts}.md"
    write_report(results, config, out_json, out_md)

    print("")
    print(f"  JSON: {out_json}")
    print(f"  Markdown: {out_md}")
    print("╚══════════════════════════════════════════════╝")


if __name__ == "__main__":
    main()

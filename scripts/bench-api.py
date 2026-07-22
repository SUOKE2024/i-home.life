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
"""
import argparse
import json
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path
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


def measure_single(base_url: str, method: str, path: str) -> dict:
    """测量单个请求的响应时间（毫秒）"""
    start = time.perf_counter()
    try:
        req = Request(f"{base_url}{path}", method=method)
        with urlopen(req, timeout=10) as resp:
            status = resp.status
            elapsed_ms = (time.perf_counter() - start) * 1000
            return {"path": path, "method": method, "status": status, "elapsed_ms": elapsed_ms, "error": None}
    except Exception as e:
        elapsed_ms = (time.perf_counter() - start) * 1000
        return {"path": path, "method": method, "status": 0, "elapsed_ms": elapsed_ms, "error": str(e)}


def run_concurrent(url: str, endpoint: tuple, concurrency: int, total: int) -> dict:
    """对单个端点执行并发压力测试"""
    method, path, label = endpoint
    results = []
    errors = 0
    start = time.perf_counter()

    with ThreadPoolExecutor(max_workers=concurrency) as executor:
        futures = [executor.submit(measure_single, url, method, path) for _ in range(total)]
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
        if "error" in r:
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


def main():
    ap = argparse.ArgumentParser(description="i-home.life API 负载基准测试")
    ap.add_argument("--url", default="http://localhost:8766", help="后端 API 地址")
    ap.add_argument("--concurrency", type=int, default=10, help="并发 worker 数")
    ap.add_argument("--requests", type=int, default=100, help="每个端点总请求数")
    ap.add_argument("--endpoints", default=None,
                    help="自定义端点, 用分号分隔多个端点, 每个格式 METHOD:/path[,label]; "
                         "例如 'GET:/api/health,健康检查;GET:/api/openapi.json,OpenAPI'")
    args = ap.parse_args()

    # 解析端点 (分号分隔多个端点, 每个格式 METHOD:/path[,label])
    if args.endpoints:
        endpoints = []
        for part in args.endpoints.split(";"):
            part = part.strip()
            if not part:
                continue
            m, rest = part.split(":", 1)
            p, label = rest.split(",", 1) if "," in rest else (rest, rest)
            endpoints.append((m.strip(), p.strip(), label.strip()))
    else:
        endpoints = DEFAULT_ENDPOINTS

    url = args.url.rstrip("/")
    config = {"url": url, "concurrency": args.concurrency, "requests": args.requests}

    print("╔══════════════════════════════════════════════╗")
    print("║  i-home.life API 负载基准测试                  ║")
    print("╠══════════════════════════════════════════════╣")
    print(f"  目标: {url}")
    print(f"  并发: {args.concurrency} | 每端点请求: {args.requests}")
    print(f"  端点: {len(endpoints)} 个")
    print("╞══════════════════════════════════════════════╡")

    results = []
    for ep in endpoints:
        label = ep[2]
        print(f"  [{label}] 测试中...")
        r = run_concurrent(url, ep, args.concurrency, args.requests)
        results.append(r)
        errors = r.get('errors', 1)
        rps_val = r.get('rps', 0)
        p50_val = r.get('p50_ms', '-')
        p90_val = r.get('p90_ms', '-')
        status = "OK" if errors == 0 else f"{errors} 错误"
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

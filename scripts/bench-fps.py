#!/usr/bin/env python3
"""i-home.life FPS 自动化基准测试

使用方式:
  # 1. 启动后端
  bash scripts/deploy.sh start

  # 2. 启动静态服务
  cd web && python3 -m http.server 9090 &

  # 3. 运行 FPS 基准(需要 Chrome/Chromium)
  python3 scripts/bench-fps.py

  # 自定义 URL
  python3 scripts/bench-fps.py --url http://118.31.223.213:8081/studio.html --preset 126

输出:
  reports/fps-bench-YYYYMMDD-HHMMSS.json + .md
"""

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from datetime import datetime
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parent.parent
REPORTS_DIR = PROJECT_DIR / "reports"
REPORTS_DIR.mkdir(exist_ok=True)


def find_chrome() -> str | None:
    """查找 Chrome/Chromium 可执行文件"""
    candidates = [
        "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
        "/Applications/Chromium.app/Contents/MacOS/Chromium",
        "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge",
        "google-chrome",
        "chromium",
        "chromium-browser",
    ]
    for c in candidates:
        if shutil.which(c) or os.path.exists(c):
            return c
    return None


def build_bench_html(target_url: str, preset: str, duration: int) -> str:
    """生成基准测试 HTML(注入到 iframe 中跑 studio.html)"""
    return f"""<!DOCTYPE html>
<html>
<head><meta charset="utf-8"><title>FPS Bench</title></head>
<body>
<iframe id="frame" src="{target_url}" style="width:1280px;height:800px;border:0;"></iframe>
<script>
const PRESET = "{preset}";
const DURATION = {duration} * 1000;
const result = {{ preset: PRESET, samples: [], avgFps: 0, minFps: 0, maxFps: 0, frames: 0, duration: 0 }};

const start = performance.now();
let last = start, frames = 0;

function tick(now) {{
  frames++;
  if (now - last >= 1000) {{
    result.samples.push(frames);
    frames = 0;
    last = now;
  }}
  if (now - start < DURATION) {{
    requestAnimationFrame(tick);
  }} else {{
    result.duration = (now - start) / 1000;
    result.frames = result.samples.reduce((a,b)=>a+b,0);
    result.avgFps = result.frames / result.duration;
    result.minFps = Math.min(...result.samples);
    result.maxFps = Math.max(...result.samples);
    document.title = "BENCH_DONE:" + JSON.stringify(result);
  }}
}}

// 等待 iframe 加载后触发预设并开始测量
const frame = document.getElementById('frame');
frame.addEventListener('load', () => {{
  try {{
    // 点击预设按钮(126㎡ / 160㎡ / 90㎡)
    const btns = frame.contentDocument.querySelectorAll('button');
    for (const b of btns) {{
      if (b.textContent.includes(PRESET + '㎡')) {{ b.click(); break; }}
    }}
  }} catch (e) {{ /* 跨域无法访问,正常情况 */ }}
  setTimeout(() => requestAnimationFrame(tick), 500);
}});

// 自动开始(即使 iframe 跨域也能测量合成层 FPS)
setTimeout(() => requestAnimationFrame(tick), 2000);
</script>
</body>
</html>"""


def run_bench(url: str, preset: str, duration: int, chrome: str) -> dict:
    """运行单次基准测试,返回结果字典"""
    bench_html = build_bench_html(url, preset, duration)
    with tempfile.NamedTemporaryFile(suffix=".html", mode="w", delete=False) as f:
        f.write(bench_html)
        bench_path = f.name

    try:
        user_data_dir = tempfile.mkdtemp(prefix="chrome-bench-")
        proc = subprocess.Popen(
            [
                chrome,
                "--headless=new",
                "--disable-gpu=false",
                "--use-gl=swiftshader",
                "--enable-webgl",
                "--no-sandbox",
                "--disable-dev-shm-usage",
                f"--user-data-dir={user_data_dir}",
                "--virtual-time-budget=15000",
                f"file://{bench_path}",
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
        )
        try:
            proc.wait(timeout=duration + 30)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait()
    finally:
        try:
            os.unlink(bench_path)
        except OSError:
            pass

    # Headless 模式下无法直接拿到 title 变化,这里返回降级结果
    # 真机测试时请人工在 MatePad/iPad 上打开 bench.html 查看控制台输出
    return {
        "preset": preset,
        "url": url,
        "duration": duration,
        "note": "headless_limitation",
        "avgFps": 0,
        "minFps": 0,
        "maxFps": 0,
        "samples": [],
    }


def probe_api(api_base: str) -> dict:
    """探测后端 API 状态,自动填充可机器验证的指标"""
    import urllib.request
    import urllib.error

    info = {"api_base": api_base, "health": "unknown", "endpoints": 0, "materials": 0}
    try:
        with urllib.request.urlopen(f"{api_base}/health", timeout=5) as r:
            info["health"] = "ok" if r.status == 200 else "fail"
    except Exception:
        info["health"] = "unreachable"
    try:
        with urllib.request.urlopen(f"{api_base}/openapi.json", timeout=5) as r:
            spec = json.loads(r.read().decode())
            info["endpoints"] = len(spec.get("paths", {}))
    except Exception:
        pass
    try:
        with urllib.request.urlopen(f"{api_base}/materials?limit=1", timeout=5) as r:
            data = json.loads(r.read().decode())
            info["materials"] = len(data) if isinstance(data, list) else 0
    except Exception:
        pass
    return info


def write_report(results: list[dict], api_info: dict, out_json: Path, out_md: Path):
    """输出 JSON + Markdown 报告"""
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    payload = {"timestamp": ts, "api": api_info, "benchmarks": results}
    out_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    lines = [
        "# i-home.life FPS 自动化基准测试报告",
        f"**时间**: {ts}",
        f"**API**: {api_info['api_base']} ({api_info['health']})",
        f"**端点数**: {api_info['endpoints']}",
        f"**物料 SKU**: {api_info['materials']}",
        "",
        "## 基准结果",
        "",
        "| 预设 | 平均 FPS | 最低 | 最高 | 时长(s) | 备注 |",
        "|------|---------|------|------|---------|------|",
    ]
    for r in results:
        note = r.get("note", "")
        lines.append(
            f"| {r['preset']}㎡ | {r['avgFps']:.1f} | {r['minFps']} | {r['maxFps']} | {r['duration']} | {note} |"
        )
    lines += [
        "",
        "## AC-8 判定",
        "",
        "| AC | 标准 | 判定 |",
        "|----|------|------|",
        "| AC-8 | FPS ≥ 30 | " + ("✅ PASS" if any(r["avgFps"] >= 30 for r in results if r["avgFps"] > 0) else "⏳ 需真机验证") + " |",
        "",
        "## 真机验证步骤",
        "",
        "1. 启动后端: `bash scripts/deploy.sh start`",
        "2. 启动静态: `cd web && python3 -m http.server 9090`",
        "3. MatePad/iPad 浏览器打开: `http://<HOST_IP>:9090/studio.html`",
        "4. 点击对应预设户型,观察右下角 FPS 数字(≥30 即 PASS)",
        "5. 或在本机运行: `python3 scripts/bench-fps.py --headless`",
        "",
        "---",
        "*报告由 scripts/bench-fps.py 自动生成*",
    ]
    out_md.write_text("\n".join(lines), encoding="utf-8")


def main():
    ap = argparse.ArgumentParser(description="i-home.life FPS 基准测试")
    ap.add_argument("--url", default="http://localhost:9090/studio.html", help="被测页面 URL")
    ap.add_argument("--api", default="http://localhost:8081", help="后端 API 地址")
    ap.add_argument("--presets", default="90,126,160", help="测试预设(逗号分隔)")
    ap.add_argument("--duration", type=int, default=10, help="每个预设采样时长(秒)")
    ap.add_argument("--headless", action="store_true", help="尝试 headless 浏览器测试")
    args = ap.parse_args()

    print(f"╔══════════════════════════════════════════════╗")
    print(f"║  i-home.life FPS 基准测试                     ║")
    print(f"╠══════════════════════════════════════════════╣")

    api_info = probe_api(args.api)
    print(f"  API: {api_info['health']} | 端点: {api_info['endpoints']} | 物料: {api_info['materials']}")

    results = []
    presets = [p.strip() for p in args.presets.split(",") if p.strip()]

    if args.headless:
        chrome = find_chrome()
        if not chrome:
            print("  ⚠️  未找到 Chrome/Chromium,跳过 headless 测试")
        else:
            print(f"  Chrome: {chrome}")
            for preset in presets:
                print(f"  [{preset}㎡] 测试中...")
                r = run_bench(args.url, preset, args.duration, chrome)
                results.append(r)
                print(f"    avg={r['avgFps']:.1f} min={r['minFps']} max={r['maxFps']}")
    else:
        print("  ℹ️  未启用 --headless,仅生成测试模板")
        for preset in presets:
            results.append({
                "preset": preset, "url": args.url, "duration": args.duration,
                "avgFps": 0, "minFps": 0, "maxFps": 0, "samples": [],
                "note": "需真机或 --headless 模式"
            })

    ts = datetime.now().strftime("%Y%m%d-%H%M%S")
    out_json = REPORTS_DIR / f"fps-bench-{ts}.json"
    out_md = REPORTS_DIR / f"fps-bench-{ts}.md"
    write_report(results, api_info, out_json, out_md)

    print(f"")
    print(f"  ✅ JSON: {out_json}")
    print(f"  ✅ Markdown: {out_md}")
    print(f"╚══════════════════════════════════════════════╝")


if __name__ == "__main__":
    main()

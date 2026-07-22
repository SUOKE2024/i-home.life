#!/usr/bin/env python3
"""基线对比脚本 (v1.1.27 / Day 6)

对比 before / after 两份 bench-api.py 产出的 JSON, 判定性能回归。

用法:
  python3 scripts/compare-baseline.py \\
      --before reports/perf-baseline-before.json \\
      --after  reports/perf-baseline-after.json \\
      [--threshold 0.10] [--report reports/perf-comparison.md]

判定规则:
  - 逐端点比较 P90 (主) 与 P50 (辅)。
  - after 比 before 慢超过 --threshold (默认 10%) → 视为回归。
  - 任一端点回归即整体 fail (exit 1); 全部通过 exit 0。
  - 缺少 before 时降级为"仅记录"模式 (exit 0), 便于首次建立基线。

JSON 输入格式 (bench-api.py 产出):
  {"timestamp": ..., "config": {...}, "results": [
    {"label": ..., "path": ..., "p50_ms": ..., "p90_ms": ..., "rps": ...}, ...
  ]}
"""
import argparse
import json
import sys
from datetime import datetime
from pathlib import Path


def load_results(path: Path) -> dict[str, dict]:
    """加载 bench JSON, 返回 {path: metrics} 映射。"""
    data = json.loads(path.read_text(encoding="utf-8"))
    return {r["path"]: r for r in data.get("results", []) if "path" in r}


def fmt_pct(delta: float) -> str:
    sign = "+" if delta >= 0 else ""
    return f"{sign}{delta * 100:.1f}%"


def main() -> int:
    ap = argparse.ArgumentParser(description="性能基线 before/after 对比")
    ap.add_argument("--before", type=Path, help="before 基线 JSON (bench-api.py 产出)")
    ap.add_argument("--after", type=Path, required=True, help="after 基线 JSON")
    ap.add_argument("--threshold", type=float, default=0.10,
                    help="回归阈值 (小数, 默认 0.10=10%%); after 比 before 慢超过此值则 fail")
    ap.add_argument("--report", type=Path, help="对比报告 Markdown 输出路径")
    args = ap.parse_args()

    if not args.after.exists():
        print(f"❌ after 基线不存在: {args.after}", file=sys.stderr)
        return 2

    after = load_results(args.after)

    # 缺少 before → 仅记录模式
    if args.before is None or not args.before.exists():
        print(f"⚠️  未提供 before 基线, 降级为仅记录模式 (首次建立基线)")
        print(f"   after 基线: {args.after}")
        print(f"   端点数: {len(after)}")
        if args.report:
            _write_report_only(after, args.after, args.report)
            print(f"   报告: {args.report}")
        return 0

    before = load_results(args.before)
    common = sorted(set(before) & set(after))
    if not common:
        print("❌ before 与 after 无共同端点, 无法对比", file=sys.stderr)
        return 2

    regressions: list[str] = []
    rows: list[dict] = []
    for path in common:
        b, a = before[path], after[path]
        # 跳过全错的端点
        if a.get("errors", 0) > 0 and a.get("total", 0) > 0 and a["errors"] == a["total"]:
            rows.append({"path": path, "label": a.get("label", path),
                         "b_p90": "-", "a_p90": "-", "delta_p90": "-",
                         "b_p50": "-", "a_p50": "-", "delta_p50": "-",
                         "status": "SKIP (after 全失败)"})
            continue
        b_p90, a_p90 = b.get("p90_ms"), a.get("p90_ms")
        b_p50, a_p50 = b.get("p50_ms"), a.get("p50_ms")
        row = {"path": path, "label": a.get("label", path)}
        # P90 为主判定指标
        if b_p90 and a_p90 and b_p90 > 0:
            delta = (a_p90 - b_p90) / b_p90
            row.update(b_p90=b_p90, a_p90=a_p90, delta_p90=delta)
            status = "REGRESSION" if delta > args.threshold else "OK"
            if delta > args.threshold:
                regressions.append(f"{a.get('label', path)} P90 {b_p90}→{a_p90}ms ({fmt_pct(delta)})")
            row["status"] = status
        else:
            row.update(b_p90=b_p90 or "-", a_p90=a_p90 or "-", delta_p90="-", status="?")
        # P50 辅助
        if b_p50 and a_p50 and b_p50 > 0:
            row["b_p50"], row["a_p50"] = b_p50, a_p50
            row["delta_p50"] = (a_p50 - b_p50) / b_p50
        else:
            row.update(b_p50=b_p50 or "-", a_p50=a_p50 or "-", delta_p50="-")
        rows.append(row)

    # 控制台摘要
    print("╔══════════════════════════════════════════════╗")
    print("║  性能基线对比 (before → after)                ║")
    print("╠══════════════════════════════════════════════╣")
    print(f"  before: {args.before}")
    print(f"  after:  {args.after}")
    print(f"  回归阈值: {args.threshold * 100:.0f}%  |  对比端点: {len(common)}")
    print("╞══════════════════════════════════════════════╡")
    for r in rows:
        d90 = r.get("delta_p90")
        d90s = fmt_pct(d90) if isinstance(d90, float) else "-"
        print(f"  [{r['status']:9s}] {r['label']:16s} P90 {r['b_p90']}→{r['a_p90']}ms ({d90s})")
    print("╞══════════════════════════════════════════════╡")

    if args.report:
        _write_comparison_report(rows, args.before, args.after, args.threshold, args.report)
        print(f"  报告: {args.report}")

    if regressions:
        print(f"❌ {len(regressions)} 个端点性能回归超阈值:")
        for rg in regressions:
            print(f"   - {rg}")
        print("╚══════════════════════════════════════════════╝")
        return 1
    print("✅ 无端点性能回归超阈值")
    print("╚══════════════════════════════════════════════╝")
    return 0


def _write_comparison_report(rows, before_path, after_path, threshold, report_path):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    lines = [
        "# 性能基线对比报告 (before → after)",
        f"**生成时间**: {ts}",
        f"**before**: `{before_path}`",
        f"**after**: `{after_path}`",
        f"**回归阈值**: P90 慢 {threshold * 100:.0f}% 即判回归",
        "",
        "## 端点对比",
        "",
        "| 端点 | 标签 | before P50(ms) | after P50(ms) | ΔP50 | before P90(ms) | after P90(ms) | ΔP90 | 状态 |",
        "|------|------|-----------------|---------------|------|-----------------|---------------|------|------|",
    ]
    for r in rows:
        d50 = r.get("delta_p50")
        d90 = r.get("delta_p90")
        d50s = fmt_pct(d50) if isinstance(d50, float) else "-"
        d90s = fmt_pct(d90) if isinstance(d90, float) else "-"
        lines.append(
            f"| {r['path']} | {r['label']} | {r['b_p50']} | {r['a_p50']} | {d50s} "
            f"| {r['b_p90']} | {r['a_p90']} | {d90s} | {r['status']} |"
        )
    lines += [
        "",
        "## 判定",
        "",
        f"- 回归端点数: {sum(1 for r in rows if r['status'] == 'REGRESSION')}",
        f"- 通过端点数: {sum(1 for r in rows if r['status'] == 'OK')}",
        f"- 跳过端点数: {sum(1 for r in rows if r['status'].startswith('SKIP'))}",
        "",
        "---",
        "*报告由 scripts/compare-baseline.py 自动生成*",
    ]
    report_path.write_text("\n".join(lines), encoding="utf-8")


def _write_report_only(after, after_path, report_path):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    lines = [
        "# 性能基线报告 (after, 首次建立)",
        f"**生成时间**: {ts}",
        f"**after**: `{after_path}`",
        "",
        "> 未提供 before 基线, 本报告仅记录 after 数值, 作为后续回归对比的基准。",
        "",
        "## 端点数值",
        "",
        "| 端点 | 标签 | 方法 | 请求数 | 错误 | RPS | P50(ms) | P90(ms) | P99(ms) |",
        "|------|------|------|--------|------|-----|---------|---------|---------|",
    ]
    for path, r in sorted(after.items()):
        lines.append(
            f"| {path} | {r.get('label', path)} | {r.get('method', '')} | {r.get('total', 0)} "
            f"| {r.get('errors', 0)} | {r.get('rps', '-')} | {r.get('p50_ms', '-')} "
            f"| {r.get('p90_ms', '-')} | {r.get('p99_ms', '-')} |"
        )
    lines += ["", "---", "*报告由 scripts/compare-baseline.py 自动生成*"]
    report_path.write_text("\n".join(lines), encoding="utf-8")


if __name__ == "__main__":
    sys.exit(main())

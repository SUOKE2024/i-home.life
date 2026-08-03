#!/usr/bin/env python3
"""测试基线核对脚本：跑全量 pytest 并与基线对比，防止测试回退。

用途：
  - CI / pre-commit / 发布前验证：全量测试通过数不得低于基线（CLAUDE.md 硬约束
    「pytest 基线不得回退」的可执行化）
  - 新增功能后更新基线：python scripts/check_test_baseline.py --update

基线文件：
  scripts/test_baseline.json  — {"passed": N, "skipped": M, "updated_at": ...}

用法:
  python scripts/check_test_baseline.py            # 核对基线（不通过则退出码 1）
  python scripts/check_test_baseline.py --update   # 以当前通过数更新基线
  python scripts/check_test_baseline.py --tests tests/test_agent_memory.py  # 仅跑指定路径

退出码:
  0 = 全量测试通过且 passed >= 基线
  1 = 有失败/错误，或 passed < 基线（回退）
  2 = 参数/环境错误（如未装 pytest）
"""
import argparse
import json
import os
import re
import subprocess
import sys
from datetime import datetime, timezone

# 项目根目录加入 sys.path
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_BASELINE_FILE = os.path.join(_ROOT, "scripts", "test_baseline.json")


# ANSI 颜色转义（ini addopts 强制 --color=yes，captured 输出含转义码）
_ANSI_RE = re.compile(r"\x1b\[[0-9;]*m")


def strip_ansi(text: str) -> str:
    return _ANSI_RE.sub("", text)


def parse_summary(line: str) -> dict:
    """解析 pytest 汇总行（兼容 -n auto / 纯串行 / warnings / ANSI 变体）。

    示例: '1520 passed, 12 skipped in 65s'
          '1 failed, 1519 passed in 60s'
          '3 failed, 1529 passed, 5 errors in 100s'
    """
    counts = {"passed": 0, "failed": 0, "skipped": 0, "errors": 0}
    for part in re.split(r"[,;]", line):
        # search 而非 match：容忍 "= 3 failed" 等前缀
        m = re.search(r"(\d+)\s+(failed|passed|skipped|errors)", part)
        if m:
            counts[m.group(2)] = int(m.group(1))
    return counts


def find_summary(output: str) -> dict:
    """从 pytest -q 输出中提取最后一条包含 passed/failed 的汇总行"""
    output = strip_ansi(output)
    for line in reversed(output.splitlines()):
        line = line.strip()
        if re.search(r"\d+\s+(passed|failed)", line):
            counts = parse_summary(line)
            if counts["passed"] or counts["failed"] or counts["errors"]:
                return counts
    return {"passed": 0, "failed": 0, "skipped": 0, "errors": 0}


def load_baseline() -> dict:
    if os.path.exists(_BASELINE_FILE):
        try:
            with open(_BASELINE_FILE, encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError):
            print(f"WARNING: 基线文件 {_BASELINE_FILE} 解析失败，按空基线处理", file=sys.stderr)
    return {"passed": 0, "skipped": 0}


def save_baseline(counts: dict) -> None:
    data = {
        "passed": counts["passed"],
        "skipped": counts["skipped"],
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    with open(_BASELINE_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"已更新基线: {_BASELINE_FILE} -> {data}")


def resolve_python() -> str:
    """优先使用项目 venv 的 python（含 pytest-xdist），否则用当前解释器"""
    venv_py = os.path.join(_ROOT, ".venv", "bin", "python")
    if os.path.exists(venv_py):
        return venv_py
    return sys.executable


def main() -> int:
    parser = argparse.ArgumentParser(description="pytest 测试基线核对")
    parser.add_argument("--update", action="store_true", help="以当前通过数更新基线")
    parser.add_argument("--tests", default="", help="仅跑指定测试路径（默认全量 tests/）")
    args = parser.parse_args()

    cmd = [resolve_python(), "-m", "pytest", "-q", "--no-header", "-p", "no:cacheprovider"]
    if args.tests:
        cmd.append(args.tests)
    else:
        cmd.append("tests")

    print(f"运行: {' '.join(cmd)}")
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, cwd=_ROOT)
    except FileNotFoundError:
        print("ERROR: 无法运行 pytest（未安装或环境异常）", file=sys.stderr)
        return 2

    output = proc.stdout + proc.stderr
    counts = find_summary(output)
    # pytest 退出码 5 = 无测试收集（视为异常）
    if counts["passed"] == 0 and counts["failed"] == 0 and counts["errors"] == 0:
        print("ERROR: 未解析到测试汇总，pytest 可能未收集到用例", file=sys.stderr)
        print(output[-2000:], file=sys.stderr)
        return 2

    print(
        f"本次结果: passed={counts['passed']} failed={counts['failed']} "
        f"skipped={counts['skipped']} errors={counts['errors']}"
    )

    if args.update:
        if counts["failed"] > 0 or counts["errors"] > 0:
            print("RESULT: FAIL — 存在失败/错误用例，拒绝更新基线", file=sys.stderr)
            print(output[-3000:], file=sys.stderr)
            return 1
        save_baseline(counts)
        return 0

    baseline = load_baseline()
    print(f"基线要求: passed>={baseline.get('passed', 0)} failed=0 errors=0")

    ok = True
    if counts["failed"] > 0 or counts["errors"] > 0:
        print("RESULT: FAIL — 存在失败/错误用例")
        ok = False
    elif counts["passed"] < baseline.get("passed", 0):
        print(
            f"RESULT: FAIL — 测试回退（passed {counts['passed']} < 基线 {baseline.get('passed', 0)}）"
        )
        ok = False
    else:
        print(f"RESULT: PASS — passed {counts['passed']} >= 基线 {baseline.get('passed', 0)}")

    if not ok:
        print(output[-3000:], file=sys.stderr)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())

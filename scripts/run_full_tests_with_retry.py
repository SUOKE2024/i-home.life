#!/usr/bin/env python3
"""全量测试 + flaky 自动重试脚本（2026-08-12）

背景：全量回归中发现若干环境性 flaky 用例（ar_scan 异步 TaskGroup / voice LLM
分类非确定 / 高负载下 DB 时序），并行首跑偶发失败、单独复跑即通过；xdist 偶发
worker 崩溃级联导致整轮结果作废。本脚本在首跑失败后自动对失败用例单独【串行】
重试，把 flaky 与真回归区分开，避免整轮重跑。

用法：
  python scripts/run_full_tests_with_retry.py                      # 全量 + 失败重试 2 次
  python scripts/run_full_tests_with_retry.py --retries 3          # 指定重试次数
  python scripts/run_full_tests_with_retry.py --tests tests/test_agent_case.py  # 限定范围
  python scripts/run_full_tests_with_retry.py --wait-clean         # 先等低负载窗口再跑
  python scripts/run_full_tests_with_retry.py --keep-logs          # 保留各轮日志（默认清理）

流程：
  0.（可选）--wait-clean：轮询等待无其他 pytest 进程且系统负载低于阈值（默认 60s 一次）
  1. 首跑：pytest -n auto --timeout=60（--tests 指定则跑该范围）
  2. 解析失败用例节点 ID（FAILED 行）+ xdist worker 崩溃节点（INTERNALERROR crashitem）
  3. 失败用例【串行】单独重试，最多 retries 次（每轮只重跑仍失败的）
  4. 汇总：首跑失败 N → 重试后通过 M → 仍失败 K；退出码 0=全部通过（含重试），1=仍有失败

退出码：
  0 = 首跑全过，或失败用例经重试后全部通过
  1 = 重试后仍有失败（疑似真回归，需人工排查）
  2 = 参数/环境错误
"""
import argparse
import os
import re
import shlex
import subprocess
import sys
import time
from datetime import datetime

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_LOG_DIR = "/tmp"
_LOG_PREFIX = "pytest_retry"


def resolve_python() -> str:
    """优先使用项目 venv 的 python（含 pytest-xdist），否则用当前解释器"""
    venv_py = os.path.join(_ROOT, ".venv", "bin", "python")
    if os.path.exists(venv_py):
        return venv_py
    return sys.executable


def run_pytest(targets: list[str], log_path: str, parallel: bool = False) -> int:
    """运行 pytest 并落日志，返回退出码。

    parallel=True 时首跑用 -n auto（项目全量惯例，多 worker 提速）；
    重试一律串行（避免 xdist worker 崩溃级联导致整轮作废）。
    """
    cmd = [resolve_python(), "-m", "pytest", "-q", "--color=no",
           "-p", "no:cacheprovider", "--timeout=60"]
    if parallel:
        cmd.append("-n")
        cmd.append("auto")
    cmd += targets
    print(f"运行: {' '.join(cmd)}\n日志: {log_path}")
    try:
        with open(log_path, "w", encoding="utf-8") as f:
            proc = subprocess.run(cmd, stdout=f, stderr=subprocess.STDOUT, cwd=_ROOT)
    except FileNotFoundError:
        print("ERROR: 无法运行 pytest（未安装或环境异常）", file=sys.stderr)
        return 2
    return proc.returncode


def read_text(path: str) -> str:
    try:
        with open(path, encoding="utf-8", errors="replace") as f:
            return f.read()
    except OSError:
        return ""


def parse_failed_node_ids(log_path: str) -> list[str]:
    """从 pytest 输出解析失败用例节点 ID（FAILED 行）+ worker 崩溃节点"""
    text = read_text(log_path)
    ids: list[str] = []
    # 常规失败：`FAILED tests/test_x.py::test_y - reason`
    for m in re.finditer(r"^FAILED\s+(\S+)\s+-", text, re.MULTILINE):
        if m.group(1) not in ids:
            ids.append(m.group(1))
    # xdist worker 崩溃：`AssertionError: ('tests/test_energy_monitor.py::test_xxx', ...)`
    for m in re.finditer(r"\('([^']+::[^']+)'", text):
        if m.group(1) not in ids:
            ids.append(m.group(1))
    return ids


def parse_summary(text: str) -> dict:
    """解析 pytest 汇总行（passed/failed/errors/skipped）"""
    counts = {"passed": 0, "failed": 0, "skipped": 0, "errors": 0}
    for line in reversed(text.splitlines()):
        if not re.search(r"\d+\s+(passed|failed)", line):
            continue
        for part in re.split(r"[,;]", line):
            m = re.search(r"(\d+)\s+(failed|passed|skipped|errors)", part)
            if m:
                counts[m.group(2)] = int(m.group(1))
        return counts
    return counts


def log_path_for(stamp: str, label: str) -> str:
    return os.path.join(_LOG_DIR, f"{_LOG_PREFIX}_{stamp}_{label}.log")


def cleanup(logs: list[str], keep: bool) -> None:
    if keep:
        return
    for log in logs:
        try:
            os.remove(log)
        except OSError:
            pass


def wait_for_clean_window(load_threshold: float, max_wait_min: int) -> bool:
    """轮询等待低负载窗口：无其他 pytest 进程且系统负载低于阈值。

    供 --wait-clean 使用（「安排低负载时段」）：外部会话并发跑测试会污染
    全量结果/耗尽资源，等机器安静后再启动首跑。
    """
    deadline = time.time() + max_wait_min * 60
    while True:
        other = _other_pytest_processes()
        load = os.getloadavg()[0]
        if not other and load < load_threshold:
            print(f"低负载窗口就绪: 无其他 pytest 进程，负载 {load:.1f} < {load_threshold}，开始运行")
            return True
        if time.time() >= deadline:
            print(f"ERROR: 等待低负载窗口超时（{max_wait_min} 分钟），仍有其他 pytest 进程 "
                  f"{len(other)} 个、负载 {load:.1f}", file=sys.stderr)
            return False
        print(f"等待低负载窗口: 其他 pytest 进程 {len(other)} 个，负载 {load:.1f}"
              f"（阈值 {load_threshold}），60s 后重试...")
        time.sleep(60)


def _other_pytest_processes() -> list[str]:
    """返回除本脚本外正在运行的 pytest 进程 PID 列表（pgrep 兼容 macOS/Linux）"""
    try:
        out = subprocess.run(["pgrep", "-f", "pytest"], capture_output=True, text=True, timeout=10)
    except (OSError, subprocess.TimeoutExpired):
        return []
    own = str(os.getpid())
    return [pid for pid in out.stdout.split() if pid and pid != own]


def retry_failed(still_failed: list[str], retries: int, stamp: str) -> tuple[list[str], list[str]]:
    """串行重试失败用例，返回（仍失败列表, 本轮日志列表）"""
    logs: list[str] = []
    for attempt in range(1, retries + 1):
        log_path = log_path_for(stamp, f"r{attempt:02d}_retry")
        logs.append(log_path)
        retry_exit = run_pytest(still_failed, log_path)
        passed_now = [nid for nid in still_failed if nid not in parse_failed_node_ids(log_path)]
        still_failed = parse_failed_node_ids(log_path)
        print(f"重试 {attempt}/{retries}: 本轮通过 {len(passed_now)}，仍失败 "
              f"{len(still_failed)} (exit={retry_exit})")
        if not still_failed:
            break
        time.sleep(2)  # 轮次间小间隔，降低负载峰值
    return still_failed, logs


def main() -> int:
    parser = argparse.ArgumentParser(description="全量测试 + flaky 自动重试")
    parser.add_argument("--retries", type=int, default=3, help="失败用例重试次数（默认 3）")
    parser.add_argument("--tests", default="tests", help="测试范围（默认全量 tests/）")
    parser.add_argument("--wait-clean", action="store_true",
                        help="先等低负载窗口（无其他 pytest 进程且负载低于阈值）再跑")
    parser.add_argument("--load-threshold", type=float, default=4.0,
                        help="--wait-clean 的负载阈值（默认 4.0）")
    parser.add_argument("--max-wait", type=int, default=180,
                        help="--wait-clean 最大等待分钟数（默认 180）")
    parser.add_argument("--keep-logs", action="store_true", help="保留各轮日志（默认清理）")
    args = parser.parse_args()
    if args.retries < 0:
        print("ERROR: --retries 不能为负", file=sys.stderr)
        return 2

    if args.wait_clean and not wait_for_clean_window(args.load_threshold, args.max_wait):
        return 1

    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    first_log = log_path_for(stamp, "01_first")
    # --tests 允许多个空格分隔的目标（目录/文件/节点 ID），按 shell 规则拆分
    first_targets = shlex.split(args.tests) or ["tests"]
    first_exit = run_pytest(first_targets, first_log, parallel=True)
    first_summary = parse_summary(read_text(first_log))
    print(f"首跑汇总: passed={first_summary['passed']} failed={first_summary['failed']} "
          f"errors={first_summary['errors']} skipped={first_summary['skipped']} (exit={first_exit})")

    failed_ids = parse_failed_node_ids(first_log)
    if not failed_ids:
        if first_exit == 0 and first_summary["failed"] == 0 and first_summary["errors"] == 0:
            print("RESULT: PASS — 首跑全部通过，无需重试")
            cleanup([first_log], args.keep_logs)
            return 0
        print("WARNING: 有失败/错误/异常退出但未能解析出节点 ID（详见首跑日志）", file=sys.stderr)
        print(read_text(first_log)[-2000:], file=sys.stderr)
        cleanup([first_log], args.keep_logs)
        return 1
    print(f"需重试用例 {len(failed_ids)} 个:\n  " + "\n  ".join(failed_ids))

    still_failed, retry_logs = retry_failed(failed_ids, args.retries, stamp)
    if not still_failed:
        print(f"RESULT: PASS — {len(failed_ids)} 个失败用例经重试后全部通过（flaky）")
        cleanup([first_log] + retry_logs, args.keep_logs)
        return 0
    print(f"RESULT: FAIL — 仍有 {len(still_failed)} 个用例失败（疑似真回归）:\n  "
          + "\n  ".join(still_failed), file=sys.stderr)
    cleanup([first_log] + retry_logs, args.keep_logs)
    return 1


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
"""轮换 i-home.life FC 定时器静态 admin 令牌（PASETO v4.public）。

背景：FC 定时器 `ihome-timer$ihome-timer` 以静态 `API_TOKEN` 调用
`/api/admin/{daily-briefing,skill-evolution,supplier-daily-briefing}`。该令牌由
`scripts/mint_paseto_token.py` 以生产 `PASETO_PRIVATE_KEY` 手工签发、**无自动轮换**，
到期当天三个任务会静默 401；认证迁移前的 legacy `v4.local.` 旧令牌仅靠
`PASETO_LOCAL_ACCEPT_UNTIL` 过渡窗口存活。

本脚本把「签发 → 合并 FC 环境变量 → 回填 → 复验」收敛为可重复、可观测的一键流程，
消除「到期静默失效」与「手工回填漏键」两类隐患。

两个子命令对应两种执行环境（可跨机组合）：

  mint   在 **持有生产私钥** 的机器（ECS `/opt/ihome`）执行：用生产 `PASETO_PRIVATE_KEY`
         签发 v4.public 永续凭据，落盘到 --out（权限 600），**不回显令牌明文**。
  apply  在 **配置了 aliyun CLI** 的机器执行：读 --token-file，读回 FC 现有环境变量并
         **合并**（只改 API_TOKEN，保留 TARGET_URLS 等其余键），写回后再读回复验。

典型流程::

    # 1) ECS 签发（cd /opt/ihome；私钥由 app settings 从 /opt/ihome/.env 读取）
    .venv/bin/python - mint --sub <admin_user_id> --out /tmp/ihome_rotate_token.txt < scripts/rotate_timer_token.py
    # 2) 取回令牌（scp/ssh，勿 echo）
    scp root@<ecs>:/tmp/ihome_rotate_token.txt /tmp/ihome_rotate_token.txt
    # 3) 合并回填 FC（默认 dry-run，显式 --apply 才写）
    python3 scripts/rotate_timer_token.py apply --token-file /tmp/ihome_rotate_token.txt
    python3 scripts/rotate_timer_token.py apply --token-file /tmp/ihome_rotate_token.txt --apply
    # 4) 复验
    python3 scripts/rotate_timer_token.py verify

安全约束：**任何路径都不打印令牌明文**（仅长度/前缀/指纹/剩余天数）；令牌文件按 600 落盘；
`apply` 默认 dry-run；FC 环境变量按「读-合并-写」而非整表替换，避免丢失 TARGET_URLS。
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from datetime import datetime, timedelta, timezone

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

DEFAULT_FUNCTION = "ihome-timer$ihome-timer"
DEFAULT_TOKEN_FILE = "/tmp/ihome_rotate_token.txt"
DEFAULT_TTL_DAYS = 180.0


# ────────────────────────────── helpers ──────────────────────────────
def _aliyun(args: list[str], profile: str | None, region: str | None) -> dict:
    """调用 aliyun CLI 并返回解析后的 JSON；失败即抛 RuntimeError（含 stderr）。"""
    cmd = ["aliyun", "fc", *args]
    if profile:
        cmd += ["--profile", profile]
    if region:
        cmd += ["--region", region]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
    except FileNotFoundError as e:
        raise RuntimeError("未找到 aliyun CLI；请在配置了 aliyun 的机器上执行 apply/verify") from e
    if proc.returncode != 0:
        raise RuntimeError(f"aliyun 调用失败({proc.returncode}): {proc.stderr.strip() or proc.stdout.strip()}")
    try:
        return json.loads(proc.stdout)
    except json.JSONDecodeError as e:
        raise RuntimeError(f"aliyun 返回非 JSON: {proc.stdout[:200]}") from e


def _read_fc_env(function: str, profile: str | None, region: str | None) -> dict:
    cfg = _aliyun(["GetFunction", "--functionName", function], profile, region)
    return dict(cfg.get("environmentVariables") or {})


def _token_meta(token: str) -> str:
    tok = token.strip()
    return f"len={len(tok)} prefix={tok[:10]}"


def _remaining_days(token: str) -> float | None:
    """从 v4.public 令牌 payload 读 exp（payload 可读、非加密）。失败返回 None。

    PASETO v4.public 的 payload = base64url(message || 64 字节 Ed25519 签名)，
    解析 JSON 前必须去掉尾部签名，否则 UTF-8 解码失败（旧实现即因此恒返回 None）。
    """
    try:
        from base64 import urlsafe_b64decode

        parts = token.strip().split(".")
        if len(parts) < 3:
            return None
        pad = "=" * (-len(parts[2]) % 4)
        raw = urlsafe_b64decode(parts[2] + pad)
        message = raw[:-64] if len(raw) > 64 else raw
        payload = json.loads(message.decode())
        exp = datetime.fromisoformat(str(payload["exp"]).replace("Z", "+00:00"))
        if exp.tzinfo is None:
            exp = exp.replace(tzinfo=timezone.utc)
        return (exp - datetime.now(timezone.utc)).total_seconds() / 86400
    except Exception:
        return None


# ────────────────────────────── mint ──────────────────────────────
def cmd_mint(args: argparse.Namespace) -> int:
    if args.ttl_days <= 0:
        print("✗ --ttl-days 必须为正数", file=sys.stderr)
        return 2
    from app.auth.paseto_handler import create_ops_token  # 延后导入以复用 settings（读 .env）

    token = create_ops_token(args.sub, args.role, int(args.ttl_days * 86400))
    if not token.startswith("v4.public."):
        print(f"✗ 签发结果非 v4.public（实际前缀 {token[:10]}）——生产协议必须为 v4.public", file=sys.stderr)
        return 3

    with open(args.out, "w", encoding="utf-8") as fh:
        fh.write(token)
    os.chmod(args.out, 0o600)

    remaining = _remaining_days(token)
    print(f"✓ 已签发 v4.public 定时器令牌 → {args.out}（权限 600）")
    print(f"  {_token_meta(token)} | sub={args.sub} role={args.role}")
    if remaining is not None:
        print(f"  剩余有效天数: {remaining:.1f}（约 {timedelta(days=remaining).days} 天）")
    print("  ⚠️ 令牌明文已落盘，请勿 echo/提交；下一步在 aliyun 机器执行 apply 合并回填 FC。")
    return 0


# ────────────────────────────── apply ──────────────────────────────
def cmd_apply(args: argparse.Namespace) -> int:
    try:
        with open(args.token_file, encoding="utf-8") as fh:
            token = fh.read().strip()
    except FileNotFoundError:
        print(f"✗ 令牌文件不存在：{args.token_file}", file=sys.stderr)
        return 2
    if not token.startswith("v4.public."):
        print(f"✗ 令牌文件内容非 v4.public（前缀 {token[:10]}）——拒绝回填", file=sys.stderr)
        return 3

    current = _read_fc_env(args.function, args.profile, args.region)
    merged = {**current, "API_TOKEN": token}

    print(f"FC 函数: {args.function}")
    print(f"  现有 env 键: {sorted(current.keys())}")
    print(f"  API_TOKEN 现状: {_token_meta(current.get('API_TOKEN',''))}")
    print(f"  API_TOKEN 拟更新为: {_token_meta(token)}")
    print(f"  TARGET_URLS 保留: {current.get('TARGET_URLS','(缺失)')[:90]}")

    missing = [k for k in current if k not in merged]
    if missing:
        print(f"✗ 合并后丢失键（拒绝写入）：{missing}", file=sys.stderr)
        return 4

    if not args.apply:
        print("\n[dry-run] 未写入。加 --apply 才会调用 UpdateFunction。")
        return 0

    body = json.dumps({"environmentVariables": merged}, ensure_ascii=False)
    _aliyun(["UpdateFunction", "--functionName", args.function, "--body", body], args.profile, args.region)

    after = _read_fc_env(args.function, args.profile, args.region)
    ok = after.get("API_TOKEN", "").startswith("v4.public.") and set(current).issubset(set(after))
    print(f"\n✓ 已回填 FC。复验 API_TOKEN: {_token_meta(after.get('API_TOKEN',''))}")
    print(f"  键集完整（无丢失）: {set(current).issubset(set(after))}")
    if not ok:
        print("✗ 复验未通过，请检查", file=sys.stderr)
        return 5
    print("下一步：verify 或用新令牌实测任一 admin 端点。")
    return 0


# ────────────────────────────── verify ──────────────────────────────
def cmd_verify(args: argparse.Namespace) -> int:
    env = _read_fc_env(args.function, args.profile, args.region)
    tok = env.get("API_TOKEN", "")
    print(f"FC 函数: {args.function}")
    print(f"  现有 env 键: {sorted(env.keys())}")
    print(f"  API_TOKEN: {_token_meta(tok)}")
    is_public = tok.startswith("v4.public.")
    print(f"  协议: {'v4.public ✅' if is_public else ('legacy v4.local ⚠️' if tok.startswith('v4.local.') else '未知 ⚠️')}")
    remaining = _remaining_days(tok) if is_public else None
    if remaining is not None:
        flag = "⚠️ 建议尽快轮换" if remaining < args.warn_days else "✅ 余量充足"
        print(f"  剩余有效天数: {remaining:.1f}（阈值 {args.warn_days:g} 天）→ {flag}")
    elif tok.startswith("v4.local."):
        print("  ⚠️ legacy v4.local 令牌剩余寿命受 PASETO_LOCAL_ACCEPT_UNTIL 约束（见 ECS .env），过期即静默 401")
    return 0 if is_public else 6


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="轮换 i-home FC 定时器静态 admin 令牌（v4.public）")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_mint = sub.add_parser("mint", help="用生产私钥签发 v4.public 长效令牌（在持有私钥的机器执行）")
    p_mint.add_argument("--sub", required=True, help="真实存在且启用的 admin 用户 id")
    p_mint.add_argument("--role", default="admin")
    p_mint.add_argument("--ttl-days", type=float, default=DEFAULT_TTL_DAYS, help=f"有效期（天，默认 {DEFAULT_TTL_DAYS:g}）")
    p_mint.add_argument("--out", default=DEFAULT_TOKEN_FILE, help=f"令牌落盘路径（600，默认 {DEFAULT_TOKEN_FILE}）")
    p_mint.set_defaults(func=cmd_mint)

    for name, fn, helptext in (
        ("apply", cmd_apply, "读回并合并回填 FC 环境变量（默认 dry-run）"),
        ("verify", cmd_verify, "复验 FC 令牌协议与剩余寿命"),
    ):
        p = sub.add_parser(name, help=helptext)
        p.add_argument("--function", default=DEFAULT_FUNCTION, help=f"FC 函数名（默认 {DEFAULT_FUNCTION}）")
        p.add_argument("--profile", default="production", help="aliyun profile（默认 production）")
        p.add_argument("--region", default=None, help="aliyun region（默认取 profile）")
        if name == "apply":
            p.add_argument("--token-file", default=DEFAULT_TOKEN_FILE)
            p.add_argument("--apply", action="store_true", help="真正写入（缺省为 dry-run）")
        if name == "verify":
            p.add_argument("--warn-days", type=float, default=45.0, help="剩余天数告警阈值（默认 45）")
        p.set_defaults(func=fn)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())

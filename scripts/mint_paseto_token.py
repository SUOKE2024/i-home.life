#!/usr/bin/env python3
"""签发运维用长效 PASETO v4.public 令牌（如 i-home FC 定时器静态 admin 令牌）。

背景：FC 定时器 `ihome-timer` 以静态 `API_TOKEN` 调用
`/api/admin/{daily-briefing,skill-evolution,supplier-daily-briefing}`。
认证改造切 v4.public 后，旧的手工签发 v4.local 静态令牌会被验签拒绝，
需用本脚本以 Ed25519 私钥重签一枚长效 v4.public 令牌并回填 FC 环境变量。

用法（在 i-home.life 仓库根执行，环境需与生产一致：PASETO_PRIVATE_KEY / PASETO_SECRET_KEY 等）：

    PASETO_PRIVATE_KEY='<Ed25519 私钥 PEM 或 k4.secret. PASERK>' \
      python3 scripts/mint_paseto_token.py --sub <admin_user_id> --role admin --ttl-days 400

要点：
- `--sub` 必须是数据库真实存在且启用的用户 id，且 `--role` 具备目标端点所需权限；
  端点经 `get_current_user` 按 `sub` 查库（admin 角色走硬编码 bypass），sub 不存在会 401。
- 输出即令牌原文，请写入 FC 环境变量 `API_TOKEN` 并同步部署侧记录（无自动轮换）。
- 该令牌 TTL 由本脚本显式指定（默认 400 天）；用户 access 令牌仍固定钳制在 45 分钟，
  本入口仅供离线运维使用，不得经任何 HTTP 端点调用。
"""
from __future__ import annotations

import argparse
import os
import sys

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)


def main() -> int:
    parser = argparse.ArgumentParser(description="签发运维用长效 PASETO v4.public 令牌")
    parser.add_argument("--sub", required=True, help="令牌 subject：真实存在且启用的用户 id")
    parser.add_argument("--role", default="admin", help="角色（默认 admin；端点权限所需）")
    parser.add_argument("--ttl-days", type=float, default=400.0, help="有效期（天，默认 400）")
    args = parser.parse_args()

    if args.ttl_days <= 0:
        parser.error("--ttl-days 必须为正数")

    from app.auth.paseto_handler import create_ops_token  # noqa: E402（延后导入以复用 settings）

    token = create_ops_token(args.sub, args.role, int(args.ttl_days * 86400))
    print(token)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

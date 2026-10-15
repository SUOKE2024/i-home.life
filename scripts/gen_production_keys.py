#!/usr/bin/env python3
"""生成 i-home.life 生产 PASETO 密钥集（v4.public 认证改造）。

产出写入 env 文件（默认 ``production-keys.env``，权限 600），供注入 ECS/systemd 环境：

- ``PASETO_PRIVATE_KEY``  签发侧 Ed25519 私钥，PASERK ``k4.secret.``（单行、env 友好）
- ``PASETO_PUBLIC_KEY``   验签侧 Ed25519 公钥，PASERK ``k4.public.``
- ``PASETO_SECRET_KEY``   对称派生主密钥（≥32 字节、非默认值）——设备凭据加密/会话加密/
  审计 HMAC/微信 state/ATH 握手/支付意图 HMAC 均由其派生，务必与旧值一并轮换并保留
- ``PASETO_LOCAL_ACCEPT_UNTIL`` 过渡窗口：接受 legacy v4.local 令牌的截止 epoch
  （默认 now+48h；设 0 表示不接受存量旧令牌）

安全约束：**不在 stdout 打印任何私钥/对称密钥明文**，仅输出指纹与下一步；文件已存在时需 --force；
文件按 600 落盘。请勿将生成物提交到版本库（``*.env`` 应在 .gitignore 内）。

用法::

    python3 scripts/gen_production_keys.py                      # 生成 production-keys.env
    python3 scripts/gen_production_keys.py --out /etc/ihome/prod.env
    python3 scripts/gen_production_keys.py --accept-window-hours 0   # 不启用 legacy 过渡窗口
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import os
import secrets
import sys
import time

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ed25519

_SECRET_PREFIX = "k4.secret."
_PUBLIC_PREFIX = "k4.public."
_DEFAULT_OUT = "production-keys.env"
# 与 app/config.py 的默认占位一致，生成器绝不会产出该值
_DEFAULT_PLACEHOLDER = "change-me-to-a-random-32-byte-key-minimum"


def _b64url_nopad(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode().rstrip("=")


def _b64url_decode(s: str) -> bytes:
    s = s.strip()
    return base64.urlsafe_b64decode(s + "=" * (-len(s) % 4))


def generate_keypair() -> tuple[str, str, str]:
    """返回 (private_paserk, public_paserk, fingerprint)。

    私钥 PASERK 载荷为 64 字节 ``seed||pub``（与 app/auth/paseto_handler
    ``_normalize_secret`` 的 64 字节分支一致），公钥 PASERK 为 32 字节裸公钥。
    """
    sk = ed25519.Ed25519PrivateKey.generate()
    seed = sk.private_bytes(
        serialization.Encoding.Raw,
        serialization.PrivateFormat.Raw,
        serialization.NoEncryption(),
    )
    pub = sk.public_key().public_bytes(
        serialization.Encoding.Raw, serialization.PublicFormat.Raw
    )
    private_paserk = _SECRET_PREFIX + _b64url_nopad(seed + pub)
    public_paserk = _PUBLIC_PREFIX + _b64url_nopad(pub)

    # 自检：解码私钥 PASERK 的前 32 字节(种子)应能推导出与公钥 PASERK 相同的公钥
    decoded_priv = _b64url_decode(private_paserk[len(_SECRET_PREFIX):])
    assert len(decoded_priv) == 64, "私钥 PASERK 载荷应为 64 字节"
    derived = ed25519.Ed25519PrivateKey.from_private_bytes(decoded_priv[:32]).public_key()
    derived_raw = derived.public_bytes(
        serialization.Encoding.Raw, serialization.PublicFormat.Raw
    )
    assert derived_raw == _b64url_decode(public_paserk[len(_PUBLIC_PREFIX):]), "密钥对自检失败"

    fingerprint = hashlib.sha256(derived_raw).hexdigest()[:8]  # 与 /health 指纹口径一致
    return private_paserk, public_paserk, fingerprint


def _render_env(private_paserk: str, public_paserk: str, secret_key: str, accept_until: float) -> str:
    lines = [
        "# i-home.life 生产 PASETO 密钥（认证改造 v4.public）",
        f"# 生成时间(UTC): {time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())}",
        "# 权限 600；请勿提交到版本库。轮换 PASETO_PRIVATE_KEY/PASETO_PUBLIC_KEY 时须成对更新。",
        "",
        "PASETO_PRIVATE_KEY=" + private_paserk,
        "PASETO_PUBLIC_KEY=" + public_paserk,
        "PASETO_SECRET_KEY=" + secret_key,
    ]
    if accept_until > 0:
        lines.append(f"PASETO_LOCAL_ACCEPT_UNTIL={accept_until:.0f}")
    else:
        lines.append("# PASETO_LOCAL_ACCEPT_UNTIL=0  # 不接受存量 legacy v4.local 令牌")
    lines += [
        "",
        "# 生态 SSO：需从索克生活密钥集/Vault 取得其公钥（k4.public. PASERK）填入",
        "# ECOSYSTEM_PUBLIC_PASERK=k4.public.xxxx",
        "# 可选收口：生产要求 Redis 不可达时按「已撤销」处理则设 1",
        "# TOKEN_REVOCATION_FAIL_CLOSED=0",
        "",
    ]
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="生成 i-home.life 生产 PASETO 密钥集")
    parser.add_argument("--out", default=_DEFAULT_OUT, help=f"输出 env 文件（默认 {_DEFAULT_OUT}）")
    parser.add_argument(
        "--accept-window-hours",
        type=float,
        default=48.0,
        help="legacy v4.local 过渡窗口小时数（默认 48；0 表示不启用）",
    )
    parser.add_argument("--force", action="store_true", help="覆盖已存在的输出文件")
    args = parser.parse_args(argv)

    if os.path.exists(args.out) and not args.force:
        print(f"✗ 目标文件已存在：{args.out}（如需覆盖请加 --force）", file=sys.stderr)
        return 2

    private_paserk, public_paserk, fingerprint = generate_keypair()
    secret_key = secrets.token_urlsafe(48)
    assert secret_key != _DEFAULT_PLACEHOLDER and len(secret_key.encode()) >= 32

    accept_until = time.time() + args.accept_window_hours * 3600 if args.accept_window_hours > 0 else 0.0

    with open(args.out, "w", encoding="utf-8") as fh:
        fh.write(_render_env(private_paserk, public_paserk, secret_key, accept_until))
    os.chmod(args.out, 0o600)

    print(f"✓ 已生成生产密钥：{args.out}（权限 600）")
    print(f"  公钥指纹(SHA256 前 8 位, 与 /api/health/detail 口径一致): {fingerprint}")
    if accept_until > 0:
        print(f"  legacy v4.local 过渡窗口至: {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(accept_until))}")
    print("下一步：")
    print("  1) 将上述 env 注入 ECS/systemd 运行环境（勿提交版本库）")
    print("  2) 生态 SSO：填入 ECOSYSTEM_PUBLIC_PASERK（索克生活公钥），否则生态登录不可用")
    print("  3) FC 定时器：用同一 PASETO_PRIVATE_KEY 重签静态 admin 令牌")
    print("       PASETO_PRIVATE_KEY=<本文件中的值> python3 scripts/mint_paseto_token.py "
          "--sub <真实admin用户id> --role admin --ttl-days 400")
    print("     并回填控制台/FC 的 API_TOKEN")
    print("  4) 上线顺序：先放量客户端 refresh 能力，再让服务端 45min access TTL 生效")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Backfill legacy plaintext refresh tokens to AES-GCM ciphertext.

新写入的 refresh 令牌已由 app/services/refresh_token_store.py 加密落库；
本脚本用于把历史明文行一次性转换为密文。默认 dry-run，不打印任何令牌值。

Usage:
  python3 scripts/backfill_refresh_token_encryption.py
  python3 scripts/backfill_refresh_token_encryption.py --apply
"""
from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from sqlalchemy import select  # noqa: E402

from app.database import async_session  # noqa: E402
from app.models.refresh_token import RefreshToken  # noqa: E402
from app.services.refresh_token_store import encrypt_refresh_token  # noqa: E402


async def backfill(apply: bool) -> int:
    async with async_session() as db:
        result = await db.execute(
            select(RefreshToken).where(~RefreshToken.token_text.startswith("v1."))
        )
        rows = result.scalars().all()

        converted = 0
        for row in rows:
            if not row.token_text or row.token_text.startswith("v1."):
                continue
            row.token_text = encrypt_refresh_token(row.token_text)
            converted += 1

        if apply:
            await db.commit()
        else:
            await db.rollback()

        print(f"scanned={len(rows)} converted={converted} applied={apply}")
        if not apply:
            print("dry-run：未写库；确认后加 --apply")
        return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Encrypt legacy refresh token rows")
    parser.add_argument("--apply", action="store_true", help="write changes to database")
    args = parser.parse_args()
    return asyncio.run(backfill(args.apply))


if __name__ == "__main__":
    raise SystemExit(main())

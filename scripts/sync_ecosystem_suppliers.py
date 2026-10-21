#!/usr/bin/env python3
"""索克家居 → 索克生活 canonical registry 存量供应商回填。

用法（需与生产一致的 PASETO/DB 环境）::

    ECOSYSTEM_SYNC_URL=https://api.suoke.life ECOSYSTEM_SYNC_KEY=*** \
      .venv/bin/python scripts/sync_ecosystem_suppliers.py --dry-run
    ECOSYSTEM_SYNC_URL=... ECOSYSTEM_SYNC_KEY=... \
      .venv/bin/python scripts/sync_ecosystem_suppliers.py

幂等：registry 以 (brand=ihome, local_id=supplier.id) 去重；重复执行只更新本地名称。
密钥不打印。
"""
from __future__ import annotations

import argparse
import asyncio
import os
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

import httpx  # noqa: E402
from sqlalchemy import select  # noqa: E402

from app.database import async_session  # noqa: E402
from app.models.procurement import Supplier  # noqa: E402

_PATH = "/api/v1/ecosystem/suppliers/batch-link"


async def _load(limit: int | None) -> list[dict]:
    async with async_session() as db:
        stmt = (
            select(Supplier)
            .where(Supplier.deleted_at.is_(None))
            .order_by(Supplier.created_at)
        )
        if limit:
            stmt = stmt.limit(limit)
        rows = (await db.execute(stmt)).scalars().all()
    return [
        {
            "brand": "ihome",
            "local_id": str(s.id),
            "local_name": str(s.name or "")[:255],
            "partner_type": "merchant",
            "status": "active" if s.is_active else "suspended",
            "metadata": {
                "category": s.category,
                "is_verified": bool(s.is_verified),
                "source": "i-home.backfill",
            },
        }
        for s in rows
    ]


async def _push(url: str, key: str, items: list[dict]) -> dict:
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.post(
            url.rstrip("/") + _PATH,
            json={"items": items},
            headers={"X-Ecosystem-Sync-Key": key},
        )
    if resp.status_code >= 300:
        raise RuntimeError(f"同步失败 HTTP {resp.status_code}: {resp.text[:200]}")
    return (resp.json() or {}).get("data") or {}


async def main() -> int:
    parser = argparse.ArgumentParser(description="回填家居供应商到 canonical registry")
    parser.add_argument("--url", default=os.environ.get("ECOSYSTEM_SYNC_URL", ""))
    parser.add_argument("--key", default=os.environ.get("ECOSYSTEM_SYNC_KEY", ""))
    parser.add_argument("--batch-size", type=int, default=200)
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    items = await _load(args.limit or None)
    print(f"本地供应商: {len(items)} 条")
    if args.dry_run:
        for item in items[:5]:
            print(f"  · {item['local_id']} {item['local_name']} ({item['status']})")
        print("[dry-run] 未发送")
        return 0
    if not args.url or not args.key:
        print("✗ 缺少 ECOSYSTEM_SYNC_URL / ECOSYSTEM_SYNC_KEY", file=sys.stderr)
        return 2

    created = updated = 0
    for start in range(0, len(items), max(1, args.batch_size)):
        data = await _push(args.url, args.key, items[start:start + args.batch_size])
        created += int(data.get("created", 0))
        updated += int(data.get("updated", 0))
        print(f"  批次 {start // args.batch_size + 1}: +{data.get('created', 0)} 新建 / "
              f"{data.get('updated', 0)} 更新")

    print(f"✓ 完成：created={created} updated={updated}")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))

"""业务日期北京时区回归测试（v1.13.4 遗留闭环：UTC 跨日错位）

边界约定（CHANGELOG v1.13.4）：DB 存储字段 + 查询窗口保留 UTC；
对外展示与业务日期标识统一 +08:00（_BJ_TZ 固定偏移，不依赖 tzdata）。

单号（整改单号 / 采购业务单号）含日期段必须用 _BJ_TZ 生成，
否则北京 00:00–07:59（此时 UTC 仍为前一天）会跨日错位。
本测试固定时刻为北京 2026-08-13 00:30（= UTC 2026-08-12 16:30），
验证单号日期段为北京日期 20260813 而非 UTC 的 20260812。
"""

import datetime as _dt
from datetime import datetime, timezone

import pytest

from app.services import quality_service, procurement_enhanced_service


class _FakeBJClock(datetime):
    """固定时刻：北京 2026-08-13 00:30（UTC 2026-08-12 16:30，跨日场景）"""

    @classmethod
    def now(cls, tz=None):
        fixed = _dt.datetime(2026, 8, 12, 16, 30, tzinfo=timezone.utc)
        return fixed.astimezone(tz) if tz is not None else fixed


@pytest.mark.asyncio
async def test_quality_order_no_uses_bj_cross_day(monkeypatch):
    """整改单号 RO-YYYYMMDD：北京 00:30 应为北京日期（若误用 UTC 得 20260812）"""
    monkeypatch.setattr(quality_service, "datetime", _FakeBJClock)
    order_no = await quality_service.generate_order_no()
    assert order_no.startswith("RO-20260813-"), f"单号日期段跨日错位: {order_no}"


@pytest.mark.asyncio
async def test_procurement_gen_no_uses_bj_cross_day(monkeypatch):
    """业务单号 PREFIX-YYYYMMDD：北京 00:30 应为北京日期"""
    monkeypatch.setattr(procurement_enhanced_service, "datetime", _FakeBJClock)
    no = await procurement_enhanced_service._gen_no("PO")
    assert no.startswith("PO-20260813-"), f"单号日期段跨日错位: {no}"

"""Agent 时间/空间感知上下文服务 — 统一构建感知注入块

提供：
- build_time_context: 北京时间（Asia/Shanghai）当前时间/星期注入
- build_location_context: 用户城市位置注入（读取长期记忆 location 类目）
- build_nearby_poi_context: 真实 LBS 周边 POI 注入（高德，仅真实数据）
- build_agent_context: 组合 时间 + 位置 + 周边POI + 长期记忆，供 chat/stream 端点注入 user_ctx

设计约束：
- 各 builder 独立受 feature flag 控制（agent_time_awareness_enabled 等）
- 失败优雅降级（返回空块），不阻断主对话流程
- 诚实降级：GPS 定位仅在逆地理编码（真实 key）成功时落库/注入城市；
  未配置 key 时返回空块，绝不伪造 POI/城市
- 隐私：GPS 精确定位不做长期记忆明文扩散，只落库粗粒度城市
"""

from __future__ import annotations

import logging
from datetime import datetime
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.models.agent_memory import AgentMemory
from app.services import agent_memory_service

logger = logging.getLogger(__name__)

# 业务默认时区：目标用户群体为中国大陆家装业主
_DEFAULT_TZ = "Asia/Shanghai"
_WEEKDAY_CN = ("周一", "周二", "周三", "周四", "周五", "周六", "周日")


def build_time_context() -> str:
    """构建时间感知上下文（北京时间）。

    Returns:
        「当前时间：2026年08月02日 周六 20:30（北京时间）」；禁用时返回空字符串
    """
    settings = get_settings()
    if not settings.agent_time_awareness_enabled:
        return ""
    try:
        tz = ZoneInfo(_DEFAULT_TZ)
    except (ZoneInfoNotFoundError, ValueError):  # 无 tzdata 时降级系统时区
        tz = None
    now = datetime.now(tz=tz) if tz else datetime.now()
    weekday = _WEEKDAY_CN[now.weekday()]
    tz_label = "北京时间" if tz else "本地时间"
    return (
        f"当前时间：{now.year}年{now.month:02d}月{now.day:02d}日 "
        f"{weekday} {now.hour:02d}:{now.minute:02d}（{tz_label}）"
    )


async def build_location_context(db: AsyncSession | None, user_id: str) -> str:
    """构建空间感知上下文（用户所在城市，读取长期记忆）。

    Returns:
        「用户所在城市：北京」；未记录城市或禁用时返回空字符串
    """
    settings = get_settings()
    if not settings.agent_location_awareness_enabled:
        return ""
    if db is None or not user_id:
        return ""
    try:
        from sqlalchemy import select
        stmt = select(AgentMemory).where(
            AgentMemory.user_id == user_id,
            AgentMemory.category == "location",
            AgentMemory.memory_key == "city",
        )
        result = await db.execute(stmt)
        city = result.scalar_one_or_none()
        if city and city.memory_value:
            return f"用户所在城市：{city.memory_value}"
    except Exception as e:
        logger.debug("agent_context.location_failed: %s", e)
    return ""


# 周边 POI 注入关键词（家装场景默认，覆盖建材/五金/家电卖场/小区）
_POI_KEYWORDS = "建材市场|五金|家电卖场|小区"


async def build_nearby_poi_context(location: str, limit: int = 5) -> str:
    """构建真实 LBS 周边 POI 上下文（高德 /place/around）。

    闭环链路：客户端 GPS → 空间感知注入周边建材/五金/小区真实 POI，
    供 Agent 回答「附近哪里有建材市场」类问题。仅注入真实数据：
    未配置高德 key 或网络失败时返回空字符串（诚实降级，不伪造 POI）。

    Args:
        location: 中心点经纬度 "lng,lat"
        limit: 返回 POI 条数上限

    Returns:
        格式化 POI 块文本；不可用/无数据时返回空字符串
    """
    settings = get_settings()
    if not settings.agent_location_awareness_enabled or not location:
        return ""
    from app.services import amap_service
    if not amap_service.is_real_key():
        return ""  # 诚实降级：无 key 不注入伪造 POI
    try:
        data = await amap_service.search_nearby_poi(
            location=location, keywords=_POI_KEYWORDS, radius=3000, limit=limit,
        )
    except Exception as e:
        logger.debug("agent_context.nearby_poi_failed: %s", e)
        return ""
    pois = data.get("pois") or []
    if not pois:
        return ""
    lines = []
    for p in pois:
        name = p.get("name")
        if not name:
            continue
        dist = p.get("distance")
        lines.append(f"- {name}（{dist}米外）" if dist else f"- {name}")
    if not lines:
        return ""
    return "【用户位置周边POI】\n" + "\n".join(lines)


async def _regeo_and_store_city(
    db: AsyncSession | None, user_id: str, location: str,
    scope: str, project_id: str | None,
) -> str:
    """GPS 经纬度 → 逆地理编码城市 → 落库长期记忆（location/city）。

    诚实降级：仅真实 key 且逆地理编码成功时返回城市并落库；
    未配置 key 时不做任何伪造/落库（精确定位不扩散为 PII 记忆）。

    Returns:
        城市上下文文本（「用户所在城市：xx」）或空字符串
    """
    settings = get_settings()
    if not settings.agent_location_awareness_enabled:
        return ""
    if not location or db is None or not user_id:
        return ""
    from app.services import amap_service
    if not amap_service.is_real_key():
        return ""  # 诚实降级：无 key 无法确定城市
    try:
        result = await amap_service.regeo(location)
    except Exception as e:
        logger.debug("agent_context.regeo_failed: %s", e)
        return ""
    city = result.get("city") or ""
    if not city:
        return ""
    try:
        await agent_memory_service.save_memory(
            db, user_id, agent_memory_service.CATEGORY_LOCATION,
            "city", city, source="lbs_geo",
            scope=scope, project_id=project_id,
        )
    except Exception as e:
        logger.debug("agent_context.city_memory_save_failed: %s", e)
    return f"用户所在城市：{city}"


async def build_agent_context(
    db: AsyncSession | None, user_id: str, project_id: str | None = None,
    location: str | None = None,
) -> str:
    """组合时间 + 位置(+GPS/LBS) + 长期记忆上下文块。

    v1.4.x：project_id 非空时，长期记忆按 scope=project + project_id 过滤注入
    （借鉴 YC QM Scope，项目维度记忆不污染其他项目）。project_id 为空时
    注入 personal 作用域记忆（兼容旧行为）。

    v1.8.x 闭环（LBS 真实 POI）：location 非空时（客户端 GPS）：
    - 逆地理编码 → 城市落库长期记忆 + 注入城市上下文（仅真实 key）
    - 周边真实 POI（建材/五金/家电卖场/小区）注入（仅真实 key）
    location 为空时回退记忆城市（兼容旧行为）。

    Returns:
        合并后的上下文文本（多行）；全部禁用/无数据时返回空字符串
    """
    settings = get_settings()
    if not user_id:
        return ""

    # scope 由 project_id 推导：有 project_id → project 作用域；否则 personal
    scope = agent_memory_service.SCOPE_PROJECT if project_id else agent_memory_service.SCOPE_PERSONAL

    blocks: list[str] = []
    if settings.agent_time_awareness_enabled:
        t = build_time_context()
        if t:
            blocks.append(t)
    if settings.agent_location_awareness_enabled and db is not None:
        if location:
            loc = await _regeo_and_store_city(db, user_id, location, scope, project_id)
            if loc:
                blocks.append(loc)
        else:
            loc = await build_location_context(db, user_id)
            if loc:
                blocks.append(loc)
        if location:
            poi = await build_nearby_poi_context(location)
            if poi:
                blocks.append(poi)
    if settings.agent_memory_enabled and db is not None:
        from app.services.agent_memory_service import build_memory_context
        mem = await build_memory_context(db, user_id, scope=scope, project_id=project_id)
        if mem:
            blocks.append(mem)
    return "\n".join(blocks)

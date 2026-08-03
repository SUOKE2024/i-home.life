"""高德地图 LBS 服务 — 真实 POI 搜索统一封装

统一封装高德 Web 服务 API（v3），供：
- app/api/location.py（位置服务路由）
- agent_tool_registry（Agent 的 search_poi 工具）
- agent 上下文空间感知注入
使用。

诚实降级约束（对齐 CLAUDE.md）：
- 真实 key 通过 settings.amap_api_key 配置，配置后返回 source="real" 的真实 POI
- 未配置 key 时返回空 POI 列表并标注 source="demo"，绝不伪造真实数据
"""

from __future__ import annotations

import logging

import httpx

from app.config import get_settings

logger = logging.getLogger(__name__)

_AMAP_BASE = "https://restapi.amap.com/v3"


def is_real_key() -> bool:
    """是否配置了真实高德 key"""
    return bool(get_settings().amap_api_key)


def _build_url(path: str, **params) -> str:
    base = _AMAP_BASE
    qs = "&".join(f"{k}={v}" for k, v in params.items() if v)
    key = get_settings().amap_api_key or "demo"  # demo key: 仅返回模拟数据
    return f"{base}{path}?key={key}&{qs}" if qs else f"{base}{path}?key={key}"


async def amap_get(path: str, **params) -> dict:
    """调用高德接口（网络失败/非 1 状态时返回错误结构，不抛异常）"""
    url = _build_url(path, **params)
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(url)
            resp.raise_for_status()
            data = resp.json()
        if data.get("status") != "1":
            return {"error": data.get("info", "请求失败"), "count": "0", "pois": []}
        return data
    except Exception as e:
        logger.warning("amap_get_failed path=%s err=%s", path, e)
        return {"error": "高德 API 不可用或未配置 KEY", "count": "0", "pois": []}


async def search_nearby_poi(
    location: str,
    keywords: str = "",
    radius: int = 3000,
    limit: int = 10,
    types: str = "",
) -> dict:
    """周边 POI 搜索（高德 /place/around）

    Args:
        location: "lng,lat"（如 116.481028,39.989643）
        keywords: 搜索关键词（如 建材市场）
        radius: 搜索半径（米），默认 3000
        limit: 返回条数上限
        types: 高德 POI 类型编码（如 060300=建材五金市场，留空按 keywords 全匹配）
    """
    data = await amap_get(
        "/place/around",
        location=location, keywords=keywords, radius=str(radius),
        offset=str(limit), types=types,
    )
    pois = data.get("pois", [])
    items = [
        {
            "name": p.get("name"),
            "address": p.get("address"),
            "location": p.get("location"),
            "city": p.get("cityname") or p.get("city"),
            "district": p.get("adname"),
            "type": p.get("type"),
            "distance": p.get("distance"),
        }
        for p in pois[:limit]
    ]
    return {
        "count": len(items),
        "source": "real" if is_real_key() else "demo",
        "pois": items,
    }


async def search_poi_text(
    keywords: str,
    city: str = "",
    types: str = "",
    limit: int = 10,
) -> dict:
    """关键词 POI 搜索（高德 /place/text，楼盘/建材等）"""
    data = await amap_get(
        "/place/text", keywords=keywords, city=city,
        types=types or "120300|120302|120303|060300", offset=str(limit),
    )
    pois = data.get("pois", [])
    items = [
        {
            "name": p.get("name"),
            "address": p.get("address"),
            "location": p.get("location"),
            "city": p.get("cityname"),
            "district": p.get("adname"),
            "type": p.get("type"),
        }
        for p in pois[:limit]
    ]
    return {
        "count": len(items),
        "source": "real" if is_real_key() else "demo",
        "pois": items,
    }


async def regeo(location: str) -> dict:
    """逆地理编码 — 经纬度 → 城市/区县（高德 /geocode/regeo）

    供 Agent 空间感知将客户端 GPS 坐标转为粗粒度城市（落库长期记忆），
    避免精确定位（PII）明文扩散。未配置 key / 失败时返回 {"error": ...}。

    Args:
        location: "lng,lat"（如 116.481028,39.989643）

    Returns:
        {"city": 城市名, "district": 区县, "source": "real"}；失败时 {"error": ...}
    """
    data = await amap_get("/geocode/regeo", location=location)
    if "error" in data or "regeocode" not in data:
        return {"error": data.get("error", "高德逆地理编码不可用或未配置 KEY")}
    comps = (data.get("regeocode") or {}).get("addressComponent") or {}
    # 直辖市（北京/上海/天津/重庆）city 字段可能为空，回退 province
    city = comps.get("city") or comps.get("province") or ""
    if isinstance(city, list):
        city = city[0] if city else (comps.get("province") or "")
    return {
        "city": city,
        "district": comps.get("district", ""),
        "adcode": comps.get("adcode", ""),
        "source": "real" if is_real_key() else "demo",
    }

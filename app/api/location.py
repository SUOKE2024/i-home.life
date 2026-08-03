"""高德地图定位服务 — 地址智能补全 + IP定位 + 附近楼盘/POI 搜索

真实 POI 数据链路统一走 app/services/amap_service（配置 amap_api_key 后
返回 source="real" 的真实数据；未配置时诚实降级为 demo 空结果）。
"""
import structlog
from fastapi import APIRouter, Depends, Query

from app.auth import get_current_user
from app.models.user import User
from app.services import amap_service

router = APIRouter(prefix="/location", tags=["位置服务"])
_log = structlog.get_logger("location")


@router.get("/search")
async def search_places(keywords: str, city: str = "", limit: int = Query(10, ge=1, le=50),
                        current_user: User = Depends(get_current_user)):
    """搜索附近楼盘/小区 — 高德 POI 搜索"""
    return await amap_service.search_poi_text(keywords=keywords, city=city, limit=limit)


@router.get("/around")
async def search_around(
    location: str = Query(..., description="中心点经纬度，格式 lng,lat（如 116.481028,39.989643）"),
    keywords: str = Query("", description="搜索关键词（如 建材市场/五金/家电卖场）"),
    radius: int = Query(3000, ge=100, le=50000, description="搜索半径（米）"),
    limit: int = Query(10, ge=1, le=25),
    current_user: User = Depends(get_current_user),
):
    """周边 POI 搜索（真实 LBS）— 以经纬度为中心检索周边建材/小区等 POI"""
    return await amap_service.search_nearby_poi(
        location=location, keywords=keywords, radius=radius, limit=limit,
    )


@router.get("/geocode")
async def geocode(address: str, city: str = "", current_user: User = Depends(get_current_user)):
    """地址 → 经纬度 + 结构化地址"""
    try:
        data = await amap_service.amap_get("/geocode/geo", address=address, city=city)
    except Exception:
        _log.warning("amap_geocode_failed", address=address, city=city, exc_info=True)
        return {"error": "高德 API 不可用或未配置 KEY"}

    geos = data.get("geocodes", [])
    if not geos:
        return {"error": "未找到匹配地址", "count": 0}

    g = geos[0]
    return {
        "count": len(geos),
        "result": {
            "formatted_address": g.get("formatted_address"),
            "province": g.get("province"),
            "city": g.get("city"),
            "district": g.get("district"),
            "location": g.get("location"),
            "level": g.get("level"),
        },
    }


@router.get("/autocomplete")
async def autocomplete(
    keywords: str, city: str = "北京", limit: int = 8,
    current_user: User = Depends(get_current_user),
):
    """地址输入智能提示 — 合并 POI 搜索 + 地理编码"""
    result = {"pois": [], "locations": []}

    # POI 搜索（楼盘/小区）
    poi_data = await amap_service.search_poi_text(keywords=keywords, city=city, limit=limit)
    result["pois"] = poi_data.get("pois", [])

    # IP 定位(仅首次，用于确定当前城市)
    try:
        ip_data = await amap_service.amap_get("/ip")
        result["current_city"] = ip_data.get("city", "")
        result["current_location"] = {
            "province": ip_data.get("province", ""),
            "city": ip_data.get("city", ""),
            "rectangle": ip_data.get("rectangle", ""),
        }
    except Exception:
        _log.debug("amap_ip_location_failed", exc_info=True)

    return result

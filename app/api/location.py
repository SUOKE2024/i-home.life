"""高德地图定位服务 — 地址智能补全 + IP定位 + 附近楼盘搜索"""
import httpx
from fastapi import APIRouter

from app.config import get_settings

router = APIRouter(prefix="/location", tags=["位置服务"])
settings = get_settings()


def _build_url(path: str, **params) -> str:
    base = "https://restapi.amap.com/v3"
    qs = "&".join(f"{k}={v}" for k, v in params.items() if v)
    key = settings.amap_api_key or "demo"  # demo key: 仅返回模拟数据
    return f"{base}{path}?key={key}&{qs}" if qs else f"{base}{path}?key={key}"


async def _amap_get(path: str, **params) -> dict:
    url = _build_url(path, **params)
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.get(url)
        resp.raise_for_status()
        data = resp.json()
        if data.get("status") != "1":
            return {"error": data.get("info", "请求失败"), "count": "0", "pois": []}
        return data


@router.get("/search")
async def search_places(keywords: str, city: str = "", limit: int = 10):
    """搜索附近楼盘/小区 — 高德 POI 搜索"""
    try:
        data = await _amap_get(
            "/place/text", keywords=keywords, city=city,
            types="120300|120302|120303", offset=str(limit),
        )
    except Exception:
        return {"pois": [], "hint": "高德 API 不可用或未配置 KEY"}

    pois = data.get("pois", [])
    return {
        "count": len(pois),
        "pois": [
            {
                "name": p.get("name"),
                "address": p.get("address"),
                "location": p.get("location"),  # "lng,lat"
                "city": p.get("cityname"),
                "district": p.get("adname"),
                "type": p.get("type"),
            }
            for p in pois[:limit]
        ],
    }


@router.get("/geocode")
async def geocode(address: str, city: str = ""):
    """地址 → 经纬度 + 结构化地址"""
    try:
        data = await _amap_get("/geocode/geo", address=address, city=city)
    except Exception:
        return {"error": "高德 API 不可用或未配置 KEY"}

    geos = data.get("geocodes", [])
    if not geos:
        return {"error": "未找到匹配地址", "count": 0}

    g = geos[0]
    lng, lat = g.get("location", ",").split(",") if g.get("location") else ("", "")
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
async def autocomplete(keywords: str, city: str = "北京", limit: int = 8):
    """地址输入智能提示 — 合并 POI 搜索 + 地理编码"""
    result = {"pois": [], "locations": []}

    # POI 搜索（楼盘/小区）
    try:
        poi_data = await _amap_get(
            "/place/text", keywords=keywords, city=city,
            types="120300|120302|120303|120000", offset=str(limit),
        )
        for p in poi_data.get("pois", [])[:limit]:
            result["pois"].append({
                "name": p.get("name"), "address": p.get("address"),
                "location": p.get("location"), "type": "poi",
            })
    except Exception:
        pass

    # IP 定位(仅首次，用于确定当前城市)
    try:
        ip_data = await _amap_get("/ip")
        result["current_city"] = ip_data.get("city", "")
        result["current_location"] = {
            "province": ip_data.get("province", ""),
            "city": ip_data.get("city", ""),
            "rectangle": ip_data.get("rectangle", ""),
        }
    except Exception:
        pass

    return result

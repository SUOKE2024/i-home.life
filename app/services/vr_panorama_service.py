"""视觉表现层 VR 全景服务层 — 全景图渲染 + 热点管理 + VR 场景漫游

核心能力:
1. 全景图 CRUD 与渲染 (mock 实现:生成等距柱状全景图占位 URL)
2. 热点管理 (跳转其他房间/户型/外部链接)
3. VR 场景组合 (多全景图按顺序组合,支持 fade/warp/none 过渡)
4. 场景总时长估算 (按热点数量和过渡时间)
"""

import json
import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.vr_panorama import VRPanorama, VRScene


# ──────────────────────────────────────────────────────────────
# 全景图 CRUD
# ──────────────────────────────────────────────────────────────

async def create_panorama(db: AsyncSession, data: dict) -> VRPanorama:
    """创建全景图记录。"""
    # initial_view: dict → JSON 字符串
    initial_view = data.pop("initial_view", None)
    if isinstance(initial_view, dict):
        data["initial_view"] = json.dumps(initial_view, ensure_ascii=False)

    panorama = VRPanorama(**data)
    db.add(panorama)
    await db.commit()
    await db.refresh(panorama)
    return panorama


async def get_panorama(db: AsyncSession, panorama_id: str) -> VRPanorama | None:
    result = await db.execute(select(VRPanorama).where(VRPanorama.id == panorama_id))
    return result.scalar_one_or_none()


async def list_panoramas(
    db: AsyncSession,
    project_id: str,
    status_filter: str | None = None,
) -> list[VRPanorama]:
    stmt = (
        select(VRPanorama)
        .where(VRPanorama.project_id == project_id)
        .order_by(VRPanorama.created_at.desc())
    )
    if status_filter:
        stmt = stmt.where(VRPanorama.status == status_filter)
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def delete_panorama(db: AsyncSession, panorama_id: str) -> bool:
    result = await db.execute(select(VRPanorama).where(VRPanorama.id == panorama_id))
    panorama = result.scalar_one_or_none()
    if not panorama:
        return False
    await db.delete(panorama)
    await db.commit()
    return True


# ──────────────────────────────────────────────────────────────
# 渲染 (mock 实现)
# ──────────────────────────────────────────────────────────────

# 渲染质量 → 分辨率/预估耗时/文件大小
RENDER_QUALITY_PROFILE = {
    "draft":    {"resolution_multiplier": 0.5, "duration_sec": 30,  "file_size_mb": 8.0},
    "standard": {"resolution_multiplier": 1.0, "duration_sec": 90,  "file_size_mb": 24.0},
    "high":     {"resolution_multiplier": 2.0, "duration_sec": 240, "file_size_mb": 96.0},
}


def generate_equirectangular(floorplan_data: dict) -> dict:
    """生成等距柱状全景图 (基于户型数据的 mock 实现)。

    实际实现需调用渲染集群 (Blender headless / Unreal Engine),
    本函数返回结构化的元数据,供调用方记录和测试。

    Args:
        floorplan_data: 户型数据 {rooms, walls, materials, ...}
    Returns:
        {image_url, thumbnail_url, resolution_width, resolution_height, render_metadata}
    """
    rooms = floorplan_data.get("rooms", []) if isinstance(floorplan_data, dict) else []
    room_name = rooms[0].get("name", "未命名房间") if rooms else "未命名房间"

    # mock 渲染输出 URL (实际由渲染集群上传到 OSS)
    render_id = uuid.uuid4().hex[:12]
    image_url = f"https://cdn.i-home.life/vr/{render_id}_equirectangular.jpg"
    thumbnail_url = f"https://cdn.i-home.life/vr/{render_id}_thumb.jpg"

    # 等距柱状投影标准比例 2:1
    # 4K = 4096x2048,8K = 8192x4096
    return {
        "image_url": image_url,
        "thumbnail_url": thumbnail_url,
        "resolution_width": 4096,
        "resolution_height": 2048,
        "render_metadata": {
            "projection": "equirectangular",
            "room_name": room_name,
            "rooms_count": len(rooms),
            "renderer": "blender-3.6-mock",
        },
    }


async def render_panorama(
    db: AsyncSession,
    panorama_id: str,
    floorplan_data: dict | None = None,
    quality: str = "standard",
) -> VRPanorama | None:
    """触发全景图渲染 (mock 实现:更新状态,生成占位 URL,记录耗时)。

    实际实现需通过任务队列 (Celery/RQ) 异步调用渲染集群,
    本函数同步 mock 渲染过程,模拟状态流转:queued → rendering → completed。
    """
    result = await db.execute(select(VRPanorama).where(VRPanorama.id == panorama_id))
    panorama = result.scalar_one_or_none()
    if not panorama:
        return None

    # 1. 进入渲染中
    panorama.status = "rendering"
    await db.commit()

    # 2. 生成全景图 (mock)
    profile = RENDER_QUALITY_PROFILE.get(quality, RENDER_QUALITY_PROFILE["standard"])
    render_result = generate_equirectangular(floorplan_data or {})

    # 3. 写回渲染结果
    panorama.image_url = render_result["image_url"]
    panorama.thumbnail_url = render_result["thumbnail_url"]
    panorama.render_quality = quality
    panorama.file_size_mb = profile["file_size_mb"]
    panorama.render_duration_sec = profile["duration_sec"]
    panorama.status = "completed"
    panorama.completed_at = datetime.now(timezone.utc).replace(tzinfo=None)
    await db.commit()
    await db.refresh(panorama)
    return panorama


# ──────────────────────────────────────────────────────────────
# 热点管理 (热点存储在 panorama.hotspots JSON 字段中)
# ──────────────────────────────────────────────────────────────

async def add_hotspot(db: AsyncSession, panorama_id: str, hotspot_data: dict) -> VRPanorama | None:
    """添加热点 (跳转其他房间/户型/外部链接)。"""
    result = await db.execute(select(VRPanorama).where(VRPanorama.id == panorama_id))
    panorama = result.scalar_one_or_none()
    if not panorama:
        return None

    hotspots = panorama.hotspot_list
    # 为热点分配 id (便于通过索引删除)
    hotspot_data["id"] = hotspot_data.get("id") or str(uuid.uuid4())
    hotspots.append(hotspot_data)
    panorama.hotspot_list = hotspots
    await db.commit()
    await db.refresh(panorama)
    return panorama


async def list_hotspots(db: AsyncSession, panorama_id: str) -> list[dict]:
    """列出全景图的所有热点。"""
    result = await db.execute(select(VRPanorama).where(VRPanorama.id == panorama_id))
    panorama = result.scalar_one_or_none()
    if not panorama:
        return []
    return panorama.hotspot_list


async def delete_hotspot(db: AsyncSession, panorama_id: str, hotspot_index: int) -> VRPanorama | None:
    """通过索引删除热点 (hotspot 是 panorama.hotspots JSON 字段中的元素)。"""
    result = await db.execute(select(VRPanorama).where(VRPanorama.id == panorama_id))
    panorama = result.scalar_one_or_none()
    if not panorama:
        return None

    hotspots = panorama.hotspot_list
    if hotspot_index < 0 or hotspot_index >= len(hotspots):
        return None
    hotspots.pop(hotspot_index)
    panorama.hotspot_list = hotspots
    await db.commit()
    await db.refresh(panorama)
    return panorama


# ──────────────────────────────────────────────────────────────
# VR 场景 (多个全景图按顺序组合)
# ──────────────────────────────────────────────────────────────

async def create_scene(db: AsyncSession, data: dict) -> VRScene:
    """创建 VR 场景 (多个全景图按顺序组合,支持漫游)。"""
    panorama_ids = data.pop("panorama_ids", None)
    if isinstance(panorama_ids, list):
        data["panorama_ids"] = json.dumps(panorama_ids, ensure_ascii=False)

    # 默认全景图:第一个
    if not data.get("default_panorama_id") and panorama_ids:
        data["default_panorama_id"] = panorama_ids[0]

    scene = VRScene(**data)
    db.add(scene)
    await db.commit()
    await db.refresh(scene)
    return scene


async def get_scene(db: AsyncSession, scene_id: str) -> VRScene | None:
    result = await db.execute(select(VRScene).where(VRScene.id == scene_id))
    return result.scalar_one_or_none()


async def list_scenes(
    db: AsyncSession,
    project_id: str,
    status_filter: str | None = None,
) -> list[VRScene]:
    stmt = (
        select(VRScene)
        .where(VRScene.project_id == project_id)
        .order_by(VRScene.created_at.desc())
    )
    if status_filter:
        stmt = stmt.where(VRScene.status == status_filter)
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def update_scene(db: AsyncSession, scene_id: str, data: dict) -> VRScene | None:
    """更新场景 (添加/删除 panorama,修改过渡效果等)。"""
    result = await db.execute(select(VRScene).where(VRScene.id == scene_id))
    scene = result.scalar_one_or_none()
    if not scene:
        return None

    for key, value in data.items():
        if key == "panorama_ids" and isinstance(value, list):
            scene.panorama_id_list = value
        elif hasattr(scene, key):
            setattr(scene, key, value)
    await db.commit()
    await db.refresh(scene)
    return scene


async def delete_scene(db: AsyncSession, scene_id: str) -> bool:
    result = await db.execute(select(VRScene).where(VRScene.id == scene_id))
    scene = result.scalar_one_or_none()
    if not scene:
        return False
    await db.delete(scene)
    await db.commit()
    return True


# ──────────────────────────────────────────────────────────────
# 场景时长估算
# ──────────────────────────────────────────────────────────────

# 每个房间浏览时间 (秒)
DEFAULT_VIEW_TIME_PER_PANORAMA = 30
# 过渡时间 (秒)
TRANSITION_DURATION = {
    "fade": 1.5,
    "warp": 0.8,
    "none": 0.0,
}


def compute_scene_duration(scene: VRScene) -> float:
    """计算场景总时长 (按热点数量和过渡时间估算)。

    估算公式:
        总时长 = Σ (每个全景浏览时间 + 每个热点交互时间) + 过渡时间 × (全景数 - 1)

    Args:
        scene: VRScene 实例
    Returns:
        总时长 (秒)
    """
    panorama_ids = scene.panorama_id_list
    if not panorama_ids:
        return 0.0

    # 过渡时间: 全景数 - 1 次切换
    transition_per = TRANSITION_DURATION.get(scene.transition_type, 1.0)
    transition_total = transition_per * max(len(panorama_ids) - 1, 0)

    # 浏览时间: 假设每个房间固定浏览时间 + 热点交互时间 (mock 估算)
    # 由于热点存储在 panorama 中而非 scene 中,这里按平均 2 个热点估算
    avg_hotspot_count = 2
    hotspot_interaction_sec = 5  # 每个热点 5 秒交互
    view_total = len(panorama_ids) * (DEFAULT_VIEW_TIME_PER_PANORAMA + avg_hotspot_count * hotspot_interaction_sec)

    return round(view_total + transition_total, 2)

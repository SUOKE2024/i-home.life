"""工程量计算路由 — F9"""

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from app.models.user import User
from app.auth import get_current_user
from app.services import takeoff_service

router = APIRouter(prefix="/takeoff", tags=["工程量计算"])


class WallTakeoffRequest(BaseModel):
    length: float = Field(gt=0, description="墙体长度(m)")
    height: float = Field(gt=0, description="墙体高度(m)")
    thickness: float = Field(default=0.24, gt=0, description="墙体厚度(m)")
    openings_area: float = Field(default=0, ge=0, description="门窗洞口面积(m²)")
    brick_type: str = Field(default="standard_brick")


class SlabTakeoffRequest(BaseModel):
    area: float = Field(gt=0, description="楼板面积(m²)")
    thickness: float = Field(default=0.12, gt=0)
    concrete_grade: str = Field(default="c25")


class FloorTakeoffRequest(BaseModel):
    area: float = Field(gt=0, description="地面面积(m²)")
    tile_size: str = Field(default="600x600")


class PaintTakeoffRequest(BaseModel):
    area: float = Field(gt=0, description="涂刷面积(m²)")
    coats: int = Field(default=3, ge=1, le=10)


class ProjectTakeoffRequest(BaseModel):
    walls: list[WallTakeoffRequest] = []
    slabs: list[SlabTakeoffRequest] = []
    floors: list[FloorTakeoffRequest] = []


@router.post("/wall")
async def wall_takeoff(
    data: WallTakeoffRequest,
    current_user: User = Depends(get_current_user),
):
    """墙体工程量计算（砖数/砂浆/涂料面积）"""
    result = takeoff_service.calc_wall_takeoff(
        length=data.length,
        height=data.height,
        thickness=data.thickness,
        openings_area=data.openings_area,
        brick_type=data.brick_type,
    )
    return result.__dict__


@router.post("/slab")
async def slab_takeoff(
    data: SlabTakeoffRequest,
    current_user: User = Depends(get_current_user),
):
    """楼板工程量计算（混凝土/钢筋/模板）"""
    result = takeoff_service.calc_slab_takeoff(
        area=data.area,
        thickness=data.thickness,
        concrete_grade=data.concrete_grade,
    )
    return result.__dict__


@router.post("/floor")
async def floor_takeoff(
    data: FloorTakeoffRequest,
    current_user: User = Depends(get_current_user),
):
    """地面工程量计算（瓷砖数/砂浆/砖缝）"""
    result = takeoff_service.calc_floor_takeoff(area=data.area, tile_size=data.tile_size)
    return result.__dict__


@router.post("/paint")
async def paint_takeoff(
    data: PaintTakeoffRequest,
    current_user: User = Depends(get_current_user),
):
    """涂料工程量计算（漆量/桶数）"""
    result = takeoff_service.calc_paint_takeoff(area=data.area, coats=data.coats)
    return result.__dict__


@router.post("/project")
async def project_takeoff(
    data: ProjectTakeoffRequest,
    current_user: User = Depends(get_current_user),
):
    """项目级工程量汇总（墙体/楼板/地面）"""
    return takeoff_service.calc_project_takeoff(
        walls=[w.model_dump() for w in data.walls],
        slabs=[s.model_dump() for s in data.slabs],
        floors=[f.model_dump() for f in data.floors],
    )

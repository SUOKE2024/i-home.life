"""工程量计算服务 — F9 墙体体积→砖/砂浆；楼板面积→混凝土/钢筋；模板面积→周转材料"""

from dataclasses import dataclass


# 标准材料参数（每立方米）
BRICK_PARAMS = {
    "standard_brick": {  # 240×115×53mm 标准砖
        "brick_per_m3": 512,  # 每立方米砖数（含砂浆）
        "mortar_ratio": 0.225,  # 砂浆占比
        "brick_size": "240×115×53mm",
    },
    "aerated_block": {  # 加气混凝土砌块 600×200×200mm
        "brick_per_m3": 41.7,
        "mortar_ratio": 0.10,
        "brick_size": "600×200×200mm",
    },
    "hollow_block": {  # 空心砖 390×190×190mm
        "brick_per_m3": 71.4,
        "mortar_ratio": 0.15,
        "brick_size": "390×190×190mm",
    },
}

# 混凝土参数（每立方米）
CONCRETE_PARAMS = {
    "c20": {"cement": 280, "sand": 660, "gravel": 1280, "water": 180},  # kg/m³
    "c25": {"cement": 320, "sand": 640, "gravel": 1280, "water": 180},
    "c30": {"cement": 360, "sand": 620, "gravel": 1280, "water": 180},
}

# 钢筋含量参考（kg/m³）
REBAR_CONTENT = {
    "slab": 80,  # 楼板
    "beam": 150,  # 梁
    "column": 200,  # 柱
    "wall": 60,  # 墙
    "foundation": 100,  # 基础
}

# 损耗系数
LOSS_FACTORS = {
    "brick": 1.03,
    "mortar": 1.05,
    "concrete": 1.02,
    "rebar": 1.05,
    "formwork": 1.08,
}


@dataclass
class WallTakeoff:
    """墙体工程量计算结果"""
    length: float  # m
    height: float  # m
    thickness: float  # m
    volume: float  # m³
    area: float  # m² (单面)
    brick_type: str
    brick_count: int
    mortar_volume: float  # m³
    paint_area: float  # m² (双面刷漆)


def calc_wall_takeoff(
    length: float,
    height: float,
    thickness: float = 0.24,
    openings_area: float = 0.0,
    brick_type: str = "standard_brick",
) -> WallTakeoff:
    """墙体工程量计算（F9）

    Args:
        length: 墙体长度 (m)
        height: 墙体高度 (m)
        thickness: 墙体厚度 (m)，默认 240mm
        openings_area: 门窗洞口面积 (m²)
        brick_type: 砖块类型
    """
    gross_area = length * height
    net_area = max(0, gross_area - openings_area)
    volume = net_area * thickness

    params = BRICK_PARAMS.get(brick_type, BRICK_PARAMS["standard_brick"])
    loss = LOSS_FACTORS["brick"]
    mortar_loss = LOSS_FACTORS["mortar"]

    brick_count = int(volume * params["brick_per_m3"] * loss)
    mortar_volume = round(volume * params["mortar_ratio"] * mortar_loss, 3)

    # 双面刷漆面积
    paint_area = net_area * 2

    return WallTakeoff(
        length=round(length, 2),
        height=round(height, 2),
        thickness=round(thickness, 3),
        volume=round(volume, 3),
        area=round(net_area, 2),
        brick_type=brick_type,
        brick_count=brick_count,
        mortar_volume=mortar_volume,
        paint_area=round(paint_area, 2),
    )


@dataclass
class SlabTakeoff:
    """楼板工程量计算结果"""
    area: float  # m²
    thickness: float  # m
    volume: float  # m³
    concrete_grade: str
    cement: float  # kg
    sand: float  # kg
    gravel: float  # kg
    water: float  # kg
    rebar_weight: float  # kg
    formwork_area: float  # m²


def calc_slab_takeoff(
    area: float,
    thickness: float = 0.12,
    concrete_grade: str = "c25",
) -> SlabTakeoff:
    """楼板工程量计算（F9）"""
    volume = area * thickness
    params = CONCRETE_PARAMS.get(concrete_grade, CONCRETE_PARAMS["c25"])
    loss_c = LOSS_FACTORS["concrete"]
    loss_r = LOSS_FACTORS["rebar"]
    loss_f = LOSS_FACTORS["formwork"]

    rebar_per_m3 = REBAR_CONTENT["slab"]
    rebar_weight = volume * rebar_per_m3 * loss_r
    formwork = area * loss_f

    return SlabTakeoff(
        area=round(area, 2),
        thickness=round(thickness, 3),
        volume=round(volume, 3),
        concrete_grade=concrete_grade,
        cement=round(volume * params["cement"] * loss_c, 2),
        sand=round(volume * params["sand"] * loss_c, 2),
        gravel=round(volume * params["gravel"] * loss_c, 2),
        water=round(volume * params["water"] * loss_c, 2),
        rebar_weight=round(rebar_weight, 2),
        formwork_area=round(formwork, 2),
    )


@dataclass
class FloorTakeoff:
    """地面工程量计算"""
    area: float  # m²
    tile_count_600x600: int  # 600×600 砖数
    tile_count_800x800: int  # 800×800 砖数
    tile_count_750x1500: int  # 750×1500 大板砖数
    mortar_volume: float  # m³ (结合层)
    joint_length: float  # m (砖缝长度)


def calc_floor_takeoff(area: float, tile_size: str = "600x600") -> FloorTakeoff:
    """地面工程量计算（F9）

    Args:
        area: 地面面积 (m²)
        tile_size: 砖尺寸规格
    """
    loss = LOSS_FACTORS["brick"]
    sizes = {
        "600x600": (0.6, 0.6),
        "800x800": (0.8, 0.8),
        "750x1500": (0.75, 1.5),
    }
    w, h = sizes.get(tile_size, sizes["600x600"])
    tile_area = w * h
    tile_count = int(area / tile_area * loss)

    # 结合层砂浆（3cm 厚）
    mortar_volume = round(area * 0.03 * LOSS_FACTORS["mortar"], 3)

    # 砖缝长度（按 2mm 缝）
    joint_length = (tile_count * (w + h)) if tile_count > 0 else 0

    return FloorTakeoff(
        area=round(area, 2),
        tile_count_600x600=tile_count if tile_size == "600x600" else 0,
        tile_count_800x800=tile_count if tile_size == "800x800" else 0,
        tile_count_750x1500=tile_count if tile_size == "750x1500" else 0,
        mortar_volume=mortar_volume,
        joint_length=round(joint_length, 2),
    )


@dataclass
class PaintTakeoff:
    """涂料工程量计算"""
    area: float  # m²
    primer_count: int  # 底漆桶数 (18L/桶)
    finish_count: int  # 面漆桶数 (18L/桶)
    total_paint_liters: float  # 总升数


def calc_paint_takeoff(area: float, coats: int = 3) -> PaintTakeoff:
    """涂料工程量计算（F9）

    Args:
        area: 涂刷面积 (m²)
        coats: 涂刷遍数（1底2面=3）
    """
    # 标准涂布率：8-12 m²/L，按 10 m²/L 计算
    coverage_per_liter = 10.0
    total_liters = area * coats / coverage_per_liter * LOSS_FACTORS["mortar"]

    # 18L/桶
    primer = int(area * 1 / coverage_per_liter * LOSS_FACTORS["mortar"] / 18) + 1
    finish = int(area * (coats - 1) / coverage_per_liter * LOSS_FACTORS["mortar"] / 18) + 1

    return PaintTakeoff(
        area=round(area, 2),
        primer_count=primer,
        finish_count=finish,
        total_paint_liters=round(total_liters, 2),
    )


def calc_project_takeoff(walls: list[dict], slabs: list[dict], floors: list[dict]) -> dict:
    """项目级工程量汇总"""
    wall_results = [calc_wall_takeoff(**w) for w in walls]
    slab_results = [calc_slab_takeoff(**s) for s in slabs]
    floor_results = [calc_floor_takeoff(**f) for f in floors]

    total_brick = sum(w.brick_count for w in wall_results)
    total_mortar = round(sum(w.mortar_volume for w in wall_results) + sum(s.volume * 0.03 for s in slab_results), 3)
    total_concrete = round(sum(s.volume for s in slab_results), 3)
    total_rebar = round(sum(s.rebar_weight for s in slab_results), 2)
    total_formwork = round(sum(s.formwork_area for s in slab_results), 2)
    total_tile = sum(f.tile_count_600x600 + f.tile_count_800x800 + f.tile_count_750x1500 for f in floor_results)
    total_paint_area = round(sum(w.paint_area for w in wall_results), 2)

    return {
        "walls": [w.__dict__ for w in wall_results],
        "slabs": [s.__dict__ for s in slab_results],
        "floors": [f.__dict__ for f in floor_results],
        "summary": {
            "total_brick_count": total_brick,
            "total_mortar_m3": total_mortar,
            "total_concrete_m3": total_concrete,
            "total_rebar_kg": total_rebar,
            "total_formwork_m2": total_formwork,
            "total_tile_count": total_tile,
            "total_paint_area_m2": total_paint_area,
        },
        "reply": (
            f"工程量汇总：砖 {total_brick} 块 / 砂浆 {total_mortar} m³ / "
            f"混凝土 {total_concrete} m³ / 钢筋 {total_rebar} kg / "
            f"模板 {total_formwork} m² / 瓷砖 {total_tile} 块 / 涂料面积 {total_paint_area} m²"
        ),
    }

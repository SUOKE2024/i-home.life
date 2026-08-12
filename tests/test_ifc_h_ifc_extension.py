"""H-IFC 扩展属性测试（v1.3.0 P4-1）

对标湖北招标投标 BIM 应用导则附录 C：H-IFC 在标准 IFC4 之上扩展
视点(Viewpoints)/漫游(Walkthrough)/地理位置(GeographicLocation)。

覆盖：
- build_h_ifc_extension_metadata: 元数据结构 + DMS 经纬度转换
- _validate_placement_range: 坐标范围合法性校验（脏数据警告，不阻断导出）
- _attach_pset_h_ifc_extension: Pset_HIFCExtension 属性集附加（需 ifcopenshell）
- 配置 flag: ifc_h_ifc_extension_enabled 默认关闭
"""

import pytest

from app.config import get_settings
from app.services.ifc_export_service import (
    _IFCOPENSHELL_AVAILABLE,
    _PLACEMENT_RANGE_MM,
    _validate_placement_range,
    build_h_ifc_extension_metadata,
)


# === build_h_ifc_extension_metadata 元数据结构 ===


def test_h_ifc_metadata_structure():
    """H-IFC 元数据含 standard/geographic_location/viewpoints/walkthrough/compliance"""
    meta = build_h_ifc_extension_metadata(project_name="测试项目")
    assert "H-IFC" in meta["standard"]
    assert "geographic_location" in meta
    assert "viewpoints" in meta
    assert "walkthrough" in meta
    assert "compliance" in meta
    # 默认武汉坐标
    geo = meta["geographic_location"]
    assert geo["latitude_deg"] == pytest.approx(30.5928)
    assert geo["longitude_deg"] == pytest.approx(114.3055)


def test_h_ifc_metadata_dms_conversion():
    """IFC RefLatitude/RefLongitude 为 [度, 分, 秒, 百万分秒] 整数列表"""
    meta = build_h_ifc_extension_metadata(latitude_deg=30.5928, longitude_deg=114.3055)
    lat_dms = meta["geographic_location"]["latitude_dms"]
    lon_dms = meta["geographic_location"]["longitude_dms"]
    # DMS 为 4 元素整数列表
    assert len(lat_dms) == 4
    assert len(lon_dms) == 4
    assert all(isinstance(v, int) for v in lat_dms)
    assert all(isinstance(v, int) for v in lon_dms)
    # 武汉纬度 30° → 度分量应为 30
    assert lat_dms[0] == 30
    # 武汉经度 114° → 度分量应为 114
    assert lon_dms[0] == 114


def test_h_ifc_metadata_dms_zero_degree():
    """DMS 转换：0 度边界值"""
    meta = build_h_ifc_extension_metadata(latitude_deg=0.0, longitude_deg=0.0)
    assert meta["geographic_location"]["latitude_dms"] == [0, 0, 0, 0]
    assert meta["geographic_location"]["longitude_dms"] == [0, 0, 0, 0]


def test_h_ifc_metadata_custom_location():
    """H-IFC 元数据支持自定义经纬度（真实接入时从项目地址派生）"""
    meta = build_h_ifc_extension_metadata(
        project_name="北京项目", latitude_deg=39.9042, longitude_deg=116.4074
    )
    geo = meta["geographic_location"]
    assert geo["latitude_deg"] == pytest.approx(39.9042)
    assert geo["longitude_deg"] == pytest.approx(116.4074)
    assert geo["latitude_dms"][0] == 39
    assert geo["longitude_dms"][0] == 116


def test_h_ifc_metadata_viewpoints_placeholder():
    """viewpoints 为占位列表（真实接入时从 BCF/相机位派生）"""
    meta = build_h_ifc_extension_metadata()
    assert isinstance(meta["viewpoints"], list)
    assert len(meta["viewpoints"]) == 0  # 占位阶段为空


def test_h_ifc_metadata_walkthrough_contract_phase():
    """walkthrough 在合同阶段不可用（available=False）"""
    meta = build_h_ifc_extension_metadata()
    assert meta["walkthrough"]["available"] is False
    assert "reason" in meta["walkthrough"]


def test_h_ifc_metadata_compliance_declaration():
    """compliance 字段声明对标湖北 BIM 应用导则附录 C"""
    meta = build_h_ifc_extension_metadata()
    assert "湖北" in meta["compliance"]
    assert "附录 C" in meta["compliance"]


# === _validate_placement_range 坐标范围校验 ===


def test_placement_range_threshold_is_1km():
    """坐标合理范围阈值 ±1,000,000mm（±1km，住宅合理范围）"""
    assert _PLACEMENT_RANGE_MM == 1_000_000.0


def test_validate_placement_range_in_range_no_exception(caplog):
    """合法坐标范围内不抛异常"""
    import logging
    caplog.set_level(logging.WARNING)
    # 1km 内的坐标合法
    _validate_placement_range(500_000.0, -500_000.0, "wall-1")
    # 不应有 warning
    assert not any("ifc_placement_out_of_range" in r.message for r in caplog.records)


def test_validate_placement_range_out_of_range_logs_warning(caplog):
    """坐标超范围记录警告，不抛异常（避免阻断导出）"""
    import logging
    caplog.set_level(logging.WARNING)
    # 超过 ±1km 的脏数据
    _validate_placement_range(2_000_000.0, 0.0, "dirty-wall")
    # 应有 warning 日志
    assert any("ifc_placement_out_of_range" in r.message for r in caplog.records)


def test_validate_placement_range_does_not_raise_on_dirty_data():
    """脏数据不阻断导出（核心：不抛异常）"""
    # 即使坐标极大也不抛异常
    _validate_placement_range(1e15, -1e15, "extreme-dirty")
    _validate_placement_range(0.0, 1_000_001.0, "over-y")


# === 配置 flag ===


def test_ifc_h_ifc_extension_flag_default_on():
    """ifc_h_ifc_extension_enabled v1.13.2 起默认开启（H-IFC 元数据为纯内部实现）"""
    assert get_settings().ifc_h_ifc_extension_enabled is True


def test_construction_drawing_mep_flag_default_on():
    """construction_drawing_mep_enabled v1.13.5 起默认开启

    SVG 为纯 Python 字符串生成（从 floorplan 几何派生，厨/卫湿区规则标注），
    零外部依赖；SVG 内含「占位示意」标注，不伪装真实 MEP 模型数据。
    """
    assert get_settings().construction_drawing_mep_enabled is True


def test_construction_drawing_mep_flag_disable_degrades(monkeypatch):
    """flag 显式关闭时降级为空串（诚实降级语义保留）"""
    monkeypatch.setattr(get_settings(), "construction_drawing_mep_enabled", False)
    assert get_settings().construction_drawing_mep_enabled is False


# === _attach_pset_h_ifc_extension（需 ifcopenshell）===


@pytest.mark.skipif(
    not _IFCOPENSHELL_AVAILABLE,
    reason="ifcopenshell 未安装（含 C 扩展，CI 环境常缺）",
)
def test_attach_pset_h_ifc_extension_writes_property_set():
    """Pset_HIFCExtension 属性集附加到 IfcSite（需 ifcopenshell）"""
    import ifcopenshell

    from app.services.ifc_export_service import _attach_pset_h_ifc_extension

    f = ifcopenshell.file()
    site = f.createIfcSite(
        GlobalId=ifcopenshell.guid.compress("1" * 32),
        Name="Test Site",
    )
    meta = build_h_ifc_extension_metadata(project_name="测试")
    _attach_pset_h_ifc_extension(f, site, meta)

    # 验证 Pset_HIFCExtension 已附加
    psets = [r.RelatingPropertyDefinition for r in f.by_type("IfcRelDefinesByProperties")]
    pset_names = [p.Name for p in psets if hasattr(p, "Name")]
    assert "Pset_HIFCExtension" in pset_names


# === _wall_placement_point 集成校验（真实坐标路径）===


def test_wall_placement_point_validates_range(monkeypatch, caplog):
    """_wall_placement_point 在 real_placement 模式下校验坐标范围"""
    import logging
    from app.services.ifc_export_service import _wall_placement_point

    monkeypatch.setattr(get_settings(), "ifc_real_placement_enabled", True)
    caplog.set_level(logging.WARNING)

    # 脏数据坐标
    wall = {"name": "dirty-wall", "start": {"x": 2_000_000, "y": 0}}
    point = _wall_placement_point(wall, index=0)
    # 仍返回坐标（不阻断），但记录警告
    assert point == (2_000_000.0, 0.0, 0.0)
    assert any("ifc_placement_out_of_range" in r.message for r in caplog.records)


def test_wall_placement_point_valid_coords_no_warning(monkeypatch, caplog):
    """_wall_placement_point 合法坐标不告警"""
    import logging
    from app.services.ifc_export_service import _wall_placement_point

    monkeypatch.setattr(get_settings(), "ifc_real_placement_enabled", True)
    caplog.set_level(logging.WARNING)

    wall = {"name": "ok-wall", "start": {"x": 1000, "y": 2000}}
    point = _wall_placement_point(wall, index=0)
    assert point == (1000.0, 2000.0, 0.0)
    assert not any("ifc_placement_out_of_range" in r.message for r in caplog.records)

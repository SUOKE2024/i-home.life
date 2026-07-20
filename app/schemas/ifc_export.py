"""BIM IFC 导出 Schema"""

from pydantic import BaseModel


class IFCExportRequest(BaseModel):
    """IFC 导出请求"""
    include_furniture: bool = False
    lod_level: str = "LOD300"  # LOD200 / LOD300 / LOD350


class IFCExportResponse(BaseModel):
    """IFC 导出结果"""
    file_url: str
    file_size: int
    element_count: int
    format_version: str

"""CAD 文件导入 API — 支持 DXF 解析（ezdxf）和 DWG 转换提示

PRD §7.1: DWG/DXF 文件导入
- DXF: 使用 ezdxf 库解析 LINE/LWPOLYLINE/CIRCLE/ARC/TEXT 实体，返回结构化 JSON
- DWG: 闭源二进制格式，尝试调用系统 dwg2dxf 命令（LibreDWG）转换后解析；
       未安装时返回 422 + 转换指引
"""
import logging
import shutil
import subprocess
import tempfile
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, status
from pydantic import BaseModel

from app.auth import get_current_user
from app.models.user import User

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/cad-import", tags=["CAD 导入"])

# 允许的实体类型
SUPPORTED_ENTITIES = {"LINE", "LWPOLYLINE", "CIRCLE", "ARC", "TEXT", "POINT"}


class CADImportResult(BaseModel):
    """CAD 文件解析结果"""
    file_type: str  # dxf | dwg
    entity_count: int
    lines: list[dict]  # [{x1,y1,x2,y2}]
    polylines: list[list[dict]]  # [[{x,y},...]]
    circles: list[dict]  # [{x,y,r}]
    arcs: list[dict]  # [{x,y,r,start_angle,end_angle}]
    texts: list[dict]  # [{x,y,text,height}]
    bounds: dict | None  # {min_x, min_y, max_x, max_y}
    converted_from_dwg: bool = False  # DWG 是否已成功转换


def _parse_dxf_bytes(content: bytes) -> CADImportResult:  # noqa: C901
    """使用 ezdxf 解析 DXF 文件内容，返回结构化 JSON

    ezdxf 1.4.x 的 read() 期望文本流，对 BytesIO 兼容性差；
    这里写入临时文件后用 readfile()，自动识别 ASCII / 二进制 DXF。
    """
    try:
        import ezdxf
    except ImportError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"服务端未安装 ezdxf 库: {e}",
        )

    with tempfile.NamedTemporaryFile(suffix=".dxf", delete=False) as tmp:
        tmp.write(content)
        tmp_path = tmp.name
    try:
        try:
            doc = ezdxf.readfile(tmp_path)
        except Exception as e:
            raise HTTPException(
                status_code=422,
                detail=f"DXF 解析失败: {e}",
            )

        msp = doc.modelspace()
        lines, polylines, circles, arcs, texts = [], [], [], [], []
        min_x = min_y = float("inf")
        max_x = max_y = float("-inf")

        def _update_bounds(x, y):
            nonlocal min_x, min_y, max_x, max_y
            min_x = min(min_x, x)
            min_y = min(min_y, y)
            max_x = max(max_x, x)
            max_y = max(max_y, y)

        for ent in msp:
            dxftype = ent.dxftype()
            if dxftype == "LINE":
                s, e = ent.dxf.start, ent.dxf.end
                lines.append({"x1": s.x, "y1": s.y, "x2": e.x, "y2": e.y})
                _update_bounds(s.x, s.y)
                _update_bounds(e.x, e.y)
            elif dxftype == "LWPOLYLINE":
                pts = [{"x": p[0], "y": p[1]} for p in ent.get_points()]
                if len(pts) >= 2:
                    polylines.append(pts)
                    for p in pts:
                        _update_bounds(p["x"], p["y"])
            elif dxftype == "CIRCLE":
                c, r = ent.dxf.center, ent.dxf.radius
                circles.append({"x": c.x, "y": c.y, "r": r})
                _update_bounds(c.x - r, c.y - r)
                _update_bounds(c.x + r, c.y + r)
            elif dxftype == "ARC":
                c, r = ent.dxf.center, ent.dxf.radius
                arcs.append({
                    "x": c.x, "y": c.y, "r": r,
                    "start_angle": ent.dxf.start_angle,
                    "end_angle": ent.dxf.end_angle,
                })
                _update_bounds(c.x - r, c.y - r)
                _update_bounds(c.x + r, c.y + r)
            elif dxftype == "TEXT":
                p = ent.dxf.insert
                texts.append({
                    "x": p.x, "y": p.y,
                    "text": ent.dxf.text or "",
                    "height": ent.dxf.height if hasattr(ent.dxf, "height") else 0,
                })
                _update_bounds(p.x, p.y)

        bounds = None
        if min_x != float("inf"):
            bounds = {
                "min_x": round(min_x, 4), "min_y": round(min_y, 4),
                "max_x": round(max_x, 4), "max_y": round(max_y, 4),
                "width": round(max_x - min_x, 4),
                "height": round(max_y - min_y, 4),
            }

        return CADImportResult(
            file_type="dxf",
            entity_count=len(lines) + len(polylines) + len(circles) + len(arcs) + len(texts),
            lines=lines, polylines=polylines, circles=circles, arcs=arcs, texts=texts,
            bounds=bounds,
        )
    finally:
        Path(tmp_path).unlink(missing_ok=True)


def _try_convert_dwg(content: bytes) -> bytes:
    """尝试使用系统 dwg2dxf 命令（LibreDWG）将 DWG 转换为 DXF

    返回 DXF 文件内容；转换失败抛出 HTTPException 含转换指引。
    """
    dwg2dxf = shutil.which("dwg2dxf")
    if not dwg2dxf:
        raise HTTPException(
            status_code=422,
            detail=(
                "DWG 为 AutoCAD 闭源二进制格式，服务端未安装转换器。请选择以下方案之一：\n"
                "1. 安装 LibreDWG：brew install libredwg（macOS）\n"
                "2. 使用 ODA File Converter（免费）：https://www.opendesign.com/guestfiles/oda_file_converter\n"
                "3. 在 AutoCAD / BricsCAD 中另存为 DXF 后再上传\n"
                "4. 直接上传 DXF 文件"
            ),
        )

    with tempfile.NamedTemporaryFile(suffix=".dwg", delete=False) as dwg_tmp:
        dwg_tmp.write(content)
        dwg_path = dwg_tmp.name
    dxf_path = dwg_path.replace(".dwg", ".dxf")

    try:
        result = subprocess.run(
            [dwg2dxf, dwg_path, "-o", dxf_path],
            capture_output=True, text=True, timeout=30,
        )
        if result.returncode != 0 or not Path(dxf_path).exists():
            raise HTTPException(
                status_code=422,
                detail=f"DWG 转换失败（dwg2dxf 退出码 {result.returncode}）: {result.stderr[:200]}",
            )
        with open(dxf_path, "rb") as f:
            return f.read()
    except subprocess.TimeoutExpired:
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail="DWG 转换超时（30s），文件可能过大或损坏",
        )
    finally:
        for p in (dwg_path, dxf_path):
            try:
                Path(p).unlink(missing_ok=True)
            except Exception:
                pass


@router.post("/dxf", response_model=CADImportResult)
async def import_dxf_file(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
):
    """上传 DXF 文件，服务端用 ezdxf 解析返回结构化 JSON

    支持实体：LINE / LWPOLYLINE / CIRCLE / ARC / TEXT
    返回结果包含所有实体的几何数据 + 整体边界框
    """
    if not file.filename:
        raise HTTPException(status_code=400, detail="缺少文件名")
    name = file.filename.lower()
    content = await file.read()

    if name.endswith(".dxf"):
        return _parse_dxf_bytes(content)

    if name.endswith(".dwg"):
        # 尝试用 LibreDWG 转换为 DXF 后解析
        dxf_content = _try_convert_dwg(content)
        result = _parse_dxf_bytes(dxf_content)
        result.file_type = "dwg"
        result.converted_from_dwg = True
        return result

    raise HTTPException(
        status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
        detail="仅支持 .dxf 或 .dwg 文件",
    )

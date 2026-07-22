"""i-home.life 设计渲染微服务 — FC 3.0 handler

负责 CAD 导入（DXF/DWG）、户型图生成、草图转 3D、VR 全景、AI 渲染（2D/3D/换搭）、IFC 导出。
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="i-home.life Design Render", version="1.1.28")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── 路由挂载 ──
from app.api import cad_import
from app.api import floorplans
from app.api import sketch_to_3d
from app.api import vr_panorama
from app.api import ai_render
from app.api import ifc_export

app.include_router(cad_import.router, prefix="/api")
app.include_router(floorplans.router, prefix="/api")
app.include_router(sketch_to_3d.router, prefix="/api")
app.include_router(vr_panorama.router, prefix="/api")
app.include_router(ai_render.router, prefix="/api")
app.include_router(ifc_export.router, prefix="/api")


@app.get("/health")
async def health():
    return {"status": "ok", "service": "design-render", "version": "1.1.28"}

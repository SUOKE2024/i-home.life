"""i-home.life 商城微服务 — FC 3.0 handler

负责支付、商品、商品批次、积分、摄像头扫描、增强采购、家具品类目录。
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="i-home.life Commerce", version="1.1.28")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── 路由挂载 ──
from app.api import payments
from app.api import products
from app.api import product_batch
from app.api import points
from app.api import camera_scan
from app.api import procurement_enhanced
from app.api import furniture_catalog

app.include_router(payments.router, prefix="/api")
app.include_router(product_batch.router, prefix="/api")
app.include_router(camera_scan.router, prefix="/api")
app.include_router(products.router, prefix="/api")
app.include_router(points.router, prefix="/api")
app.include_router(procurement_enhanced.router, prefix="/api")
app.include_router(furniture_catalog.router, prefix="/api")


@app.get("/health")
async def health():
    return {"status": "ok", "service": "commerce", "version": "1.1.28"}

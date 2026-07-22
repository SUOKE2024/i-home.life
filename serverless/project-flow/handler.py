"""i-home.life 项目流程微服务 — FC 3.0 handler

负责项目 CRUD、户型图、材料、预算、采购、施工、结算、变更单、施工队、工人、质量巡检。
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="i-home.life Project Flow", version="1.1.28")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── 路由挂载 ──
from app.api import projects
from app.api import materials
from app.api import budgets
from app.api import procurement
from app.api import construction
from app.api import settlements
from app.api import change_orders
from app.api import crews
from app.api import workers
from app.api import surveys
from app.api import takeoff
from app.api import tasks

app.include_router(projects.router, prefix="/api")
app.include_router(materials.router, prefix="/api")
app.include_router(budgets.router, prefix="/api")
app.include_router(procurement.router, prefix="/api")
app.include_router(construction.router, prefix="/api")
app.include_router(settlements.router, prefix="/api")
app.include_router(change_orders.router, prefix="/api")
app.include_router(crews.router, prefix="/api")
app.include_router(workers.router, prefix="/api")
app.include_router(surveys.router, prefix="/api")
app.include_router(takeoff.router, prefix="/api")
app.include_router(tasks.router, prefix="/api")


@app.get("/health")
async def health():
    return {"status": "ok", "service": "project-flow", "version": "1.1.28"}

import os
from contextlib import asynccontextmanager

from fastapi import APIRouter, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.config import get_settings
from app.database import init_db
from app.api import auth, projects, materials, budgets, procurement, construction, settlements, floorplans, voice, files, agents, surveys, location, change_orders, takeoff, mep, payments, chat, crews, workers, lighting, kitchen, bathroom, custom_furniture, soft_furnishing, vr_panorama, ai_image, kitchen_bath_mep, hard_decoration, door_window_waterproof, furniture_catalog, smart_home, scene_automation, procurement_enhanced

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    yield


app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    lifespan=lifespan,
    # 将 docs/openapi 路径置于 /api/ 前缀下，避免被根路径 StaticFiles 拦截
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/api/openapi.json",
)

# CORS: 生产环境从 .env 读取白名单; DEBUG 模式下放开以方便本地联调
_cors_origins = (
    ["*"] if settings.debug else (settings.cors_origins or ["http://localhost:3000"])
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── API 路由（统一 /api 前缀，与前端 JS 中 `const API = '/api'` 对齐） ──
api_router = APIRouter(prefix="/api")
api_router.include_router(auth.router)          # /api/auth/*
api_router.include_router(projects.router)      # /api/projects/*
api_router.include_router(materials.router)     # /api/materials/*
api_router.include_router(budgets.router)       # /api/budgets/*
api_router.include_router(procurement.router)   # /api/procurement/*
api_router.include_router(construction.router)  # /api/construction/*
api_router.include_router(settlements.router)   # /api/settlements/*
api_router.include_router(floorplans.router)    # /api/floorplans/*
api_router.include_router(voice.router)         # /api/voice/*
api_router.include_router(files.router)         # /api/files/*
api_router.include_router(agents.router)        # /api/agents/*
api_router.include_router(surveys.router)       # /api/surveys/*
api_router.include_router(location.router)      # /api/location/*
api_router.include_router(change_orders.router) # /api/change-orders/*
api_router.include_router(takeoff.router)       # /api/takeoff/*
api_router.include_router(mep.router)           # /api/mep/*
api_router.include_router(payments.router)      # /api/payments/*
api_router.include_router(chat.router)          # /api/chat/*
api_router.include_router(crews.router)         # /api/crews/*
api_router.include_router(workers.router)       # /api/workers/*
api_router.include_router(lighting.router)     # /api/lighting/*
api_router.include_router(kitchen.router)      # /api/kitchen/*
api_router.include_router(bathroom.router)     # /api/bathroom/*
api_router.include_router(custom_furniture.router)  # /api/custom-furniture/*
api_router.include_router(soft_furnishing.router)   # /api/soft-furnishing/*
api_router.include_router(vr_panorama.router)  # /api/vr/*
api_router.include_router(ai_image.router)     # /api/ai-image/*
api_router.include_router(kitchen_bath_mep.router)        # /api/mep-kb/* (F18)
api_router.include_router(hard_decoration.router)         # /api/hard-decoration/* (F21)
api_router.include_router(door_window_waterproof.router)  # /api/door-window-waterproof/* (F23)
api_router.include_router(furniture_catalog.router)       # /api/furniture-catalog/* (F26)
api_router.include_router(smart_home.router)              # /api/smart-home/* (F31)
api_router.include_router(scene_automation.router)        # /api/scene-automation/* (F32)
api_router.include_router(procurement_enhanced.router)    # /api/procurement-enhanced/* (F33/F34)
app.include_router(api_router)


@app.get("/health")
async def health_check():
    return {"status": "ok", "app": settings.app_name, "version": settings.app_version}


@app.websocket("/ws/{project_id}")
async def websocket_endpoint(websocket, project_id: str):
    from app.ws import ws_manager
    await ws_manager.connect(websocket, project_id)
    try:
        while True:
            data = await websocket.receive_text()
            import json
            try:
                msg = json.loads(data)
                event = msg.get("event", "message")
                payload = msg.get("data", {})
                await ws_manager.broadcast_to_project(project_id, event, payload)
            except Exception:
                await ws_manager.send_to(websocket, "error", {"message": "Invalid message format"})
    except Exception:
        pass
    finally:
        ws_manager.disconnect(websocket)


# ── 站点静态文件（挂载在根路径，确保 index.html / studio.html 直接可访问） ──
web_dir = os.path.join(os.path.dirname(__file__), "..", "web")
if os.path.isdir(web_dir):
    app.mount("/", StaticFiles(directory=web_dir, html=True), name="web")

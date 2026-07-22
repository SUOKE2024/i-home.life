"""i-home.life 实时通信微服务 — FC 3.0 handler

负责语音（TTS/ASR）、实时语音（Qwen-Audio WebSocket）、WebSocket 聊天、通知推送、位置服务。
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="i-home.life Realtime", version="1.1.28")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── 路由挂载 ──
from app.api import voice
from app.api import voice_realtime
from app.api import notifications
from app.api import location

app.include_router(voice.router, prefix="/api")
app.include_router(voice_realtime.router, prefix="/api")
app.include_router(notifications.router, prefix="/api")
app.include_router(location.router, prefix="/api")


@app.get("/health")
async def health():
    return {"status": "ok", "service": "realtime", "version": "1.1.28"}

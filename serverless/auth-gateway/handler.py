"""i-home.life 认证网关微服务 — FC 3.0 handler

负责 PASETO 令牌签发/验证、用户注册登录、WebAuthn/Passkey、身份认证。
"""

import os
import sys

# 将项目根目录加入 sys.path，确保可以导入 app 模块
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="i-home.life Auth Gateway", version="1.1.28")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── 路由挂载 ──
from app.api import auth
from app.api import identity

app.include_router(auth.router, prefix="/api")
app.include_router(identity.router, prefix="/api")


@app.get("/health")
async def health():
    return {"status": "ok", "service": "auth-gateway", "version": "1.1.28"}

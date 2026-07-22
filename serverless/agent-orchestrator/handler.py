"""i-home.life Agent 编排微服务 — FC 3.0 handler

负责 22 个 Agent 编排、聊天端点、Harness、MCP Server、Eval 框架、模型规范辩驳。
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="i-home.life Agent Orchestrator", version="1.1.28")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── 路由挂载 ──
from app.api import agents
from app.api import chat
from app.api import mcp as mcp_api
from app.api import eval as eval_api
from app.api import a2a as a2a_api
from app.api import harness_api

app.include_router(agents.router, prefix="/api")
app.include_router(chat.router, prefix="/api")
app.include_router(mcp_api.router, prefix="/api")
app.include_router(eval_api.router, prefix="/api")
app.include_router(a2a_api.router, prefix="/api")
app.include_router(harness_api.router, prefix="/api")

# A2A 公开路由（无认证）
app.include_router(a2a_api.public_router)


@app.get("/health")
async def health():
    return {"status": "ok", "service": "agent-orchestrator", "version": "1.1.28"}

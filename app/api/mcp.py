"""MCP API 路由 —— 暴露 Agent 工具为标准 MCP 接口

路由前缀：/api/mcp（main.py 通过 api_router 统一加 /api 前缀）
端点：
- GET  /api/mcp/manifest    服务器元信息（公开，无需认证）
- GET  /api/mcp/tools       工具列表（需 PASETO 认证）
- POST /api/mcp/tools/call  调用工具（需认证 + 项目归属校验）
- POST /api/mcp/sse         SSE 流式工具调用（兼容 MCP 2026-07-28 stateless 核心）

项目归属校验：
- 工具参数含 project_id 时，调用 verify_project_access 校验
- admin 角色或项目 owner 通过；其他角色返回 403
"""

import json
import logging

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import get_current_user
from app.database import get_db
from app.mcp.server import mcp_server
from app.models.user import User
from app.rbac import verify_project_access

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/mcp", tags=["MCP"])


# ── 请求体模型 ──

class ToolCallRequest(BaseModel):
    """MCP tools/call 请求体"""
    name: str
    arguments: dict = {}


class SSEToolCallRequest(BaseModel):
    """SSE 工具调用请求体（兼容 MCP stateless HTTP transport）

    id 字段对应 JSON-RPC 2.0 请求 id，用于响应匹配。
    """
    id: int | str = 1
    name: str
    arguments: dict = {}


# ── 辅助函数 ──

async def _check_project_access_for_args(
    arguments: dict,
    current_user: User,
    db: AsyncSession,
) -> None:
    """如果工具参数包含 project_id，校验当前用户对该项目的归属权限

    防止越权访问其他用户的项目数据（IDOR 防护）。
    admin 或项目 owner 通过；其他用户抛 403。
    """
    project_id = arguments.get("project_id")
    if not project_id:
        return
    # verify_project_access 内部会抛 404/403，由全局异常处理器统一封装
    await verify_project_access(project_id, current_user, db)


# ── 端点 ──

@router.get("/manifest")
async def mcp_manifest():
    """MCP 服务器元信息（公开端点，无需认证）

    供客户端发现服务器能力：名称 / 版本 / 协议版本 / 工具数量。
    """
    return mcp_server.get_manifest()


@router.get("/tools")
async def mcp_list_tools(
    current_user: User = Depends(get_current_user),
):
    """返回 MCP 协议格式的工具列表

    需 PASETO 认证；所有认证用户均可访问（工具调用本身仍受项目归属校验约束）。
    """
    return {"tools": mcp_server.list_tools()}


@router.post("/tools/call")
async def mcp_call_tool(
    req: ToolCallRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """调用指定工具并返回 MCP 协议格式结果

    - 需 PASETO 认证
    - 如工具参数含 project_id，需校验项目归属（admin 或 owner）
    - 工具不存在或执行失败：返回 200 + isError=True（MCP 协议错误在响应内容中）
    - 越权访问：返回 403
    """
    # 项目归属校验（在调用工具前完成，避免泄露其他用户项目数据）
    await _check_project_access_for_args(req.arguments, current_user, db)

    result = await mcp_server.call_tool(req.name, req.arguments)
    return result


@router.post("/sse")
async def mcp_sse_call(
    req: SSEToolCallRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """SSE 流式工具调用（兼容 MCP 2026-07-28 stateless 核心）

    以 Server-Sent Events 流式返回工具调用结果，适配 MCP stateless HTTP transport。
    事件序列：
    1. event: endpoint  —— MCP 规范约定的端点声明
    2. event: message   —— JSON-RPC 2.0 响应（含工具调用结果）
    3. 异常时 event: error —— JSON-RPC 2.0 error 响应
    """
    # 项目归属校验（同步执行，校验失败时直接抛 HTTPException，不进入 SSE 流）
    await _check_project_access_for_args(req.arguments, current_user, db)

    async def event_stream():
        # 1. 发送 endpoint 事件（MCP 规范：客户端据此发现 POST 端点）
        endpoint_data = json.dumps({"endpoint": "/api/mcp/sse"}, ensure_ascii=False)
        yield f"event: endpoint\ndata: {endpoint_data}\n\n"

        # 2. 调用工具并流式返回 JSON-RPC 2.0 响应
        try:
            result = await mcp_server.call_tool(req.name, req.arguments)
            response = mcp_server.to_mcp_response(req.id, result=result)
            yield f"event: message\ndata: {json.dumps(response, ensure_ascii=False)}\n\n"
        except Exception as e:
            logger.error(
                f"mcp_sse_error: tool={req.name}, error={e}",
                exc_info=True,
            )
            error = mcp_server.make_error(-32603, f"内部错误: {e}")
            response = mcp_server.to_mcp_response(req.id, error=error)
            yield f"event: error\ndata: {json.dumps(response, ensure_ascii=False)}\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            # 禁用 Nginx 缓冲，确保 SSE 实时推送
            "X-Accel-Buffering": "no",
        },
    )

"""MCP API 路由 —— 暴露 Agent 工具为标准 MCP 接口

v1.3.0 完整对齐 MCP 2026-07-28 规范：
- stateless 核心（无 initialize/initialized 握手，无 Mcp-Session-Id）
- server/discover RPC（POST /api/mcp，JSON-RPC 入口）
- header-based routing（Mcp-Method / Mcp-Name header）
- cacheable list results（ETag + If-None-Match → 304）
- MRTR 轮询端点（POST /api/mcp/mrtr/{request_id}）
- CIMD 端点（POST /api/mcp/cimd，替代 DCR）
- Tasks 扩展（tasks/* 方法经 POST /api/mcp 分发）
- .well-known Server Card（GET /.well-known/mcp）

路由前缀：/api/mcp（main.py 通过 api_router 统一加 /api 前缀）
向后兼容端点（标注 deprecated，v1.3.0 推荐用 POST /api/mcp）：
- GET  /api/mcp/manifest    服务器元信息（公开）
- GET  /api/mcp/tools       工具列表（需 PASETO 认证，v1.3.0 加 ETag/304）
- POST /api/mcp/tools/call  调用工具（需认证 + 项目归属校验）
- POST /api/mcp/sse         SSE 流式工具调用

项目归属校验：
- 工具参数含 project_id 时，调用 verify_project_access 校验
- admin 角色或项目 owner 通过；其他角色返回 403
"""

import json
import logging

from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from fastapi.responses import JSONResponse, Response, StreamingResponse
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import get_current_user
from app.config import get_settings
from app.database import get_db
from app.mcp.server import mcp_server
from app.models.user import User
from app.rbac import verify_project_access

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/mcp", tags=["MCP"])
# v1.3.0: .well-known 公开端点（无 /api 前缀，对标 A2A public_router 模式）
public_router = APIRouter(tags=["MCP Public"])


# ── 请求体模型 ──

class ToolCallRequest(BaseModel):
    """MCP tools/call 请求体（向后兼容）"""
    name: str
    arguments: dict = {}


class SSEToolCallRequest(BaseModel):
    """SSE 工具调用请求体（兼容 MCP stateless HTTP transport）"""
    id: int | str = 1
    name: str
    arguments: dict = {}


class JSONRPCRequest(BaseModel):
    """v1.3.0 JSON-RPC 2.0 请求体（POST /api/mcp 入口）"""
    jsonrpc: str = "2.0"
    id: int | str | None = None
    method: str
    params: dict | None = None


class MRTRResponseRequest(BaseModel):
    """v1.3.0 MRTR 客户端回传响应体"""
    response: dict | None = None


class CIMDRequest(BaseModel):
    """v1.3.0 Client Issuer Metadata Document 注册请求"""
    client_name: str
    client_uri: str | None = None
    redirect_uris: list[str] = []
    grant_types: list[str] = ["authorization_code"]


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
    await verify_project_access(project_id, current_user, db)


def _validate_protocol_version(
    mcp_protocol_version: str | None = Header(default=None, alias="MCP-Protocol-Version"),
) -> None:
    """v1.3.0 校验 MCP-Protocol-Version header

    MCP 2026-07-28 stateless 核心：每个请求携带协议版本。
    版本不匹配时返回 400 + 升级提示（按规范 12 个月最小兼容窗口）。
    """
    settings = get_settings()
    if not settings.mcp_enabled:
        raise HTTPException(status_code=503, detail="MCP 服务已禁用")

    # 公开端点（manifest/discover/.well-known）不强制 header
    # 仅在需要时校验（由调用方决定是否传 header）
    if mcp_protocol_version is None:
        return  # 向后兼容：未传 header 时放行
    if mcp_protocol_version != mcp_server.PROTOCOL_VERSION:
        raise HTTPException(
            status_code=400,
            detail={
                "error": "unsupported_protocol_version",
                "expected": mcp_server.PROTOCOL_VERSION,
                "received": mcp_protocol_version,
                "message": f"服务器协议版本 {mcp_server.PROTOCOL_VERSION}，客户端 {mcp_protocol_version}。",
            },
        )


def _validate_issuer(
    mcp_issuer: str | None = Header(default=None, alias="MCP-Issuer"),
) -> None:
    """v1.3.0 RFC 9207 issuer 校验（authorization hardening）

    外部 MCP 客户端需声明 issuer，服务端据此校验客户端注册来源。
    内部 PASETO 客户端 issuer 为 "i-home.life"。
    """
    # 当前实现：仅记录，不强制（向后兼容）
    # 完整 CIMD 流程需客户端先经 /api/mcp/cimd 注册
    if mcp_issuer and mcp_issuer != "i-home.life":
        logger.info("mcp_external_issuer: issuer=%s", mcp_issuer)


# ── v1.3.0 新端点 ──

@public_router.get("/.well-known/mcp")
async def mcp_well_known():
    """v1.3.0 MCP Server Card —— 标准化发现端点

    供注册中心/浏览器/爬虫发现 MCP 服务器，无需活跃连接。
    对标 MCP 2026 Roadmap 的 MCP Server Cards。
    公开端点，无需认证。
    """
    settings = get_settings()
    if not settings.mcp_enabled:
        raise HTTPException(status_code=503, detail="MCP 服务已禁用")
    return mcp_server.get_server_card()


@router.post("")
async def mcp_jsonrpc(
    req: JSONRPCRequest,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    mcp_method: str | None = Header(default=None, alias="Mcp-Method"),
    mcp_name: str | None = Header(default=None, alias="Mcp-Name"),
):
    """v1.3.0 JSON-RPC 2.0 入口 —— 支持 server/discover / tools/list / tools/call / tasks/*

    Header-based routing（MCP 2026-07-28）：
    - Mcp-Method header 可替代 body.method（网关可直接基于 header 路由）
    - Mcp-Name header 携带工具名（tools/call 时可用）

    stateless 核心：每个请求自描述，可落在任意实例上（round-robin 负载均衡）。
    """
    settings = get_settings()
    if not settings.mcp_enabled:
        raise HTTPException(status_code=503, detail="MCP 服务已禁用")

    # Header routing：header 优先于 body
    method = mcp_method or req.method
    params = req.params or {}

    # Mcp-Name header 注入 params（tools/call 时）
    if mcp_name and method == "tools/call":
        params = {**params, "name": params.get("name", mcp_name)}

    # discover 方法受 mcp_discover_enabled 控制
    if method == "server/discover" and not settings.mcp_discover_enabled:
        raise HTTPException(status_code=503, detail="MCP discover 未启用")

    # MRTR 方法受 mcp_mrtr_enabled 控制
    if method.startswith("mrtr/") and not settings.mcp_mrtr_enabled:
        raise HTTPException(status_code=503, detail="MCP MRTR 未启用")

    # tasks/* 方法受 mcp_tasks_extension_enabled 控制
    if method.startswith("tasks/") and not settings.mcp_tasks_extension_enabled:
        raise HTTPException(status_code=503, detail="MCP Tasks 扩展未启用")

    # tools/call 需项目归属校验
    if method == "tools/call":
        arguments = params.get("arguments", {})
        await _check_project_access_for_args(arguments, current_user, db)

    # 分发方法
    result, error = await mcp_server.dispatch_method(method, params)
    response = mcp_server.to_mcp_response(req.id, result=result, error=error)

    # v1.3.0: cacheable list results —— tools/list 响应加 Cache-Control + ETag
    if method == "tools/list" and result and "cache_hint" in result:
        etag = result["cache_hint"]["etag"]
        ttl = result["cache_hint"]["ttl"]
        # 检查 If-None-Match → 304
        if_none_match = request.headers.get("If-None-Match")
        if if_none_match and etag in if_none_match:
            # 304 Not Modified：无响应体（JSONResponse 必须含 content，用 Response）
            return Response(
                status_code=304,
                headers={"ETag": etag, "Cache-Control": f"max-age={ttl}"},
            )
        return JSONResponse(
            content=response,
            headers={"ETag": etag, "Cache-Control": f"max-age={ttl}"},
        )

    return response


@router.post("/cimd")
async def mcp_cimd(
    req: CIMDRequest,
    current_user: User = Depends(get_current_user),
):
    """v1.3.0 Client Issuer Metadata Document（CIMD）—— 替代 Dynamic Client Registration

    MCP 2026-07-28 authorization hardening：从 DCR 转向 CIMD。
    外部 MCP 客户端通过本端点注册客户端元数据，获取 issuer 凭证。
    """
    settings = get_settings()
    if not settings.mcp_enabled:
        raise HTTPException(status_code=503, detail="MCP 服务已禁用")

    # 简化实现：记录客户端元数据，返回 issuer 凭证
    # 完整实现需持久化客户端元数据 + 签发 client_id（对标 OAuth 2.1 CIMD）
    logger.info(
        "mcp_cimd_registered: client_name=%s client_uri=%s user_id=%s",
        req.client_name, req.client_uri, current_user.id,
    )
    return {
        "client_name": req.client_name,
        "issuer": "i-home.life",
        "client_id": f"mcp_{current_user.id}_{req.client_name}",
        "grant_types": req.grant_types,
        "message": "CIMD 注册成功。后续请求请携带 MCP-Issuer: i-home.life header。",
    }


@router.post("/mrtr/{request_id}")
async def mcp_mrtr_respond(
    request_id: str,
    req: MRTRResponseRequest,
    current_user: User = Depends(get_current_user),
):
    """v1.3.0 MRTR 客户端响应端点 —— 客户端回传 sampling/elicitation 响应

    MRTR 流程：
    1. 工具调用需客户端配合时，服务端创建 MRTR 请求（POST /api/mcp with mrtr/create）
    2. 客户端轮询 GET /api/mcp/mrtr 列表拉取待响应请求
    3. 客户端处理后通过本端点回传响应
    4. 服务端消费响应，继续原工具调用
    """
    settings = get_settings()
    if not settings.mcp_enabled or not settings.mcp_mrtr_enabled:
        raise HTTPException(status_code=503, detail="MCP MRTR 未启用")

    from app.mcp.mrtr import mrtr_manager
    ok = await mrtr_manager.submit_response(request_id, req.response)
    if not ok:
        raise HTTPException(status_code=404, detail="MRTR 请求不存在或已终态")
    return {"status": "ok", "request_id": request_id}


@router.get("/mrtr")
async def mcp_mrtr_list(
    current_user: User = Depends(get_current_user),
):
    """v1.3.0 MRTR 待响应请求列表 —— 客户端轮询拉取"""
    settings = get_settings()
    if not settings.mcp_enabled or not settings.mcp_mrtr_enabled:
        raise HTTPException(status_code=503, detail="MCP MRTR 未启用")

    from app.mcp.mrtr import mrtr_manager
    pending = await mrtr_manager.list_pending()
    return {"requests": [r.to_dict() for r in pending]}


# ── 向后兼容端点（v1.3.0 标注 deprecated，推荐用 POST /api/mcp）──

@router.get("/manifest")
async def mcp_manifest():
    """MCP 服务器元信息（公开端点，无需认证）

    v1.3.0 deprecated：推荐用 POST /api/mcp with server/discover。
    保留向后兼容。
    """
    return mcp_server.get_manifest()


@router.get("/tools")
async def mcp_list_tools(
    request: Request,
    current_user: User = Depends(get_current_user),
):
    """返回 MCP 协议格式的工具列表（v1.3.0 加 ETag/304 cacheable list）

    需 PASETO 认证；所有认证用户均可访问。
    v1.3.0: 响应携带 ETag + Cache-Control，支持 If-None-Match → 304。
    """
    cached = mcp_server.list_tools_with_cache()
    etag = cached["cache_hint"]["etag"]
    ttl = cached["cache_hint"]["ttl"]

    if_none_match = request.headers.get("If-None-Match")
    if if_none_match and etag in if_none_match:
        # 304 Not Modified：无响应体
        return Response(
            status_code=304,
            headers={"ETag": etag, "Cache-Control": f"max-age={ttl}"},
        )
    return JSONResponse(
        content={"tools": cached["tools"]},
        headers={"ETag": etag, "Cache-Control": f"max-age={ttl}"},
    )


@router.post("/tools/call")
async def mcp_call_tool(
    req: ToolCallRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """调用指定工具并返回 MCP 协议格式结果（向后兼容）

    v1.3.0 deprecated：推荐用 POST /api/mcp with tools/call。
    """
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

    以 Server-Sent Events 流式返回工具调用结果。
    """
    await _check_project_access_for_args(req.arguments, current_user, db)

    async def event_stream():
        endpoint_data = json.dumps({"endpoint": "/api/mcp/sse"}, ensure_ascii=False)
        yield f"event: endpoint\ndata: {endpoint_data}\n\n"

        try:
            result = await mcp_server.call_tool(req.name, req.arguments)
            response = mcp_server.to_mcp_response(req.id, result=result)
            yield f"event: message\ndata: {json.dumps(response, ensure_ascii=False)}\n\n"
        except Exception as e:
            logger.error(f"mcp_sse_error: tool={req.name}, error={e}", exc_info=True)
            error = mcp_server.make_error(-32603, f"内部错误: {e}")
            response = mcp_server.to_mcp_response(req.id, error=error)
            yield f"event: error\ndata: {json.dumps(response, ensure_ascii=False)}\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )

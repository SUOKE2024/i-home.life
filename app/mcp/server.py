"""MCP Server 核心实现 —— 纯 Python dict 实现 MCP 协议，不依赖第三方 SDK

参考: MCP 2026-07-28 spec
- 工具格式 : {name, description, inputSchema(=JSON Schema object)}
- 调用结果 : {content: [{type: "text", text: "..."}], isError: bool}
- 响应封装 : JSON-RPC 2.0 {jsonrpc: "2.0", id, result|error}

v1.3.0 完整对齐 MCP 2026-07-28 规范：
- stateless 核心（无 initialize/initialized 握手，无 Mcp-Session-Id）
- server/discover RPC（替代旧 manifest 端点，标准化能力发现）
- cacheable list results（list_tools 响应携带 cache_hint + etag + 确定性排序）
- extensions framework + Tasks 扩展
- Server Card（.well-known 标准化元数据）

复用 app/services/agent_tool_registry.py 的 tool_registry 单例，
将项目内 Agent 工具统一暴露为 MCP 协议兼容接口。
"""

import hashlib
import json
import logging
import secrets
import time
from typing import Any, cast

from app.config import get_settings
from app.services.agent_tool_registry import tool_registry

logger = logging.getLogger(__name__)


def build_trace_meta(
    traceparent: str | None = None,
    tracestate: str | None = None,
    baggage: str | None = None,
) -> dict:
    """MCP 2026-07-28 SEP-414: W3C Trace Context 嵌入 JSON-RPC 响应 `_meta`。

    客户端请求头携带 traceparent/tracestate/baggage 时透传；
    未提供 traceparent 时生成服务端根 span（version=00 / 128-bit trace-id /
    64-bit span-id / flags=01），并附 trace_id/span_id 便于与对象存储/日志关联。

    返回恒非空 dict（至少含 traceparent）。
    """
    meta: dict = {}
    if not traceparent:
        trace_id = secrets.token_hex(16)
        span_id = secrets.token_hex(8)
        traceparent = f"00-{trace_id}-{span_id}-01"
        meta["trace_id"] = trace_id
        meta["span_id"] = span_id
    meta["traceparent"] = traceparent
    if tracestate:
        meta["tracestate"] = tracestate
    if baggage:
        meta["baggage"] = baggage
    return meta


class MCPServer:
    """MCP Server —— 封装工具列表/调用/JSON-RPC 2.0 响应

    职责：
    1. 将 tool_registry 中的 AgentTool 转换为 MCP 协议格式（list_tools）
    2. 调用工具并包装结果为 MCP content 格式（call_tool）
    3. 生成 JSON-RPC 2.0 兼容响应（to_mcp_response）
    4. 暴露服务器元信息（get_manifest / discover / get_server_card）
    5. v1.3.0: list_tools 支持 cache_hint + etag（cacheable list results）
    6. v1.3.0: extensions 注册 + Tasks 扩展
    """

    # ── 服务器元信息常量 ──
    SERVER_NAME = "i-home.life MCP Server"
    SERVER_VERSION = "1.15.0"
    # MCP 2026-07-28 stateless 核心
    PROTOCOL_VERSION = "2026-07-28"
    # v1.3.0: list 结果缓存 TTL（秒），客户端可据此缓存工具目录
    LIST_CACHE_TTL = 300

    def __init__(self):
        self._registry = tool_registry
        # v1.3.0: 扩展注册表（延迟初始化，避免循环导入）
        self._extensions: dict[str, Any] = {}
        self._extensions_loaded = False

    # ── 扩展注册（v1.3.0）──

    def _load_extensions(self) -> None:
        """延迟加载扩展（避免启动时循环导入）。"""
        if self._extensions_loaded:
            return
        self._extensions_loaded = True
        settings = get_settings()
        # Tasks 扩展
        if settings.mcp_tasks_extension_enabled:
            try:
                from app.mcp.extensions.tasks import TasksExtension
                self._extensions["tasks"] = TasksExtension()
                logger.info("mcp_extension_loaded: extension=tasks")
            except Exception as e:
                logger.warning("mcp_extension_load_failed: extension=tasks error=%s", e)
        # Enterprise 扩展（MCP 2026 Roadmap Enterprise Readiness：审计/SSO/网关）
        if settings.mcp_enterprise_extension_enabled:
            try:
                from app.mcp.extensions.enterprise import EnterpriseExtension
                self._extensions["enterprise"] = EnterpriseExtension()
                logger.info("mcp_extension_loaded: extension=enterprise")
            except Exception as e:
                logger.warning("mcp_extension_load_failed: extension=enterprise error=%s", e)

    def list_extensions(self) -> list[dict]:
        """返回已注册扩展的元信息。"""
        self._load_extensions()
        return [
            {"name": name, "version": getattr(ext, "VERSION", "1.0.0")}
            for name, ext in self._extensions.items()
        ]

    def get_extension(self, name: str) -> Any | None:
        """获取指定扩展实例。"""
        self._load_extensions()
        return self._extensions.get(name)

    # ── 元信息 / 发现 ──

    def get_manifest(self) -> dict:
        """返回服务器元信息（向后兼容，v1.3.0 标注 deprecated，推荐用 discover）"""
        return {
            "name": self.SERVER_NAME,
            "version": self.SERVER_VERSION,
            "protocol_version": self.PROTOCOL_VERSION,
            "tools_count": self._registry.tool_count,
            "capabilities": {
                "tools": {"listChanged": False},
                "resources": {},
                "prompts": {},
            },
            "deprecated": "v1.3.0 起推荐使用 POST /api/mcp with server/discover",
        }

    def discover(self) -> dict:
        """v1.3.0 server/discover RPC —— 标准化能力发现（替代旧 manifest）

        返回服务器能力清单，客户端据此决定是否发起后续请求。
        每个请求自描述，discover 可选（任何请求可落在任意实例上）。
        """
        self._load_extensions()
        return {
            "protocol_version": self.PROTOCOL_VERSION,
            "server": {
                "name": self.SERVER_NAME,
                "version": self.SERVER_VERSION,
            },
            "capabilities": {
                "tools": {"listChanged": False, "cacheable": True},
                "resources": {"listChanged": False, "cacheable": True},
                "prompts": {"listChanged": False, "cacheable": True},
                # v1.3.0: 声明支持的扩展
                "extensions": {name: {} for name in self._extensions},
            },
            "extensions": self.list_extensions(),
            # v1.3.0: 授权信息（RFC 9207 issuer）
            "authorization": {
                "issuer": "i-home.life",
                "schemes": ["bearer"],
                "cimd_supported": True,  # Client Issuer Metadata Document
            },
        }

    def get_server_card(self) -> dict:
        """v1.3.0 Server Card —— .well-known 标准化元数据

        供注册中心/浏览器/爬虫发现 MCP 服务器，无需活跃连接。
        对标 MCP 2026 Roadmap 的 MCP Server Cards。
        """
        return {
            "mcp_version": self.PROTOCOL_VERSION,
            "server": {
                "name": self.SERVER_NAME,
                "version": self.SERVER_VERSION,
                "description": "索克家居 AI 智能装修平台 Agent 工具 MCP 服务器",
            },
            "transport": {
                "type": "streamable_http",
                "endpoint": "/api/mcp",
                "stateless": True,  # v1.3.0: stateless 核心，支持 round-robin 负载均衡
            },
            "capabilities": {
                "tools": True,
                "resources": False,  # 暂未实现 resources 原语
                "prompts": False,    # 暂未实现 prompts 原语
                "extensions": [e["name"] for e in self.list_extensions()],
            },
            "authorization": {
                "scheme": "bearer",
                "issuer": "i-home.life",
                "cimd_endpoint": "/api/mcp/cimd",
            },
            "discovered_at": int(time.time()),
        }

    # ── 工具列表（cacheable）──

    def list_tools(self) -> list[dict]:
        """返回 MCP 协议格式的工具列表（确定性排序，按 name 字典序）

        MCP 工具字段：
        - name        : 工具唯一标识
        - description : 工具描述（供 LLM 选择工具）
        - inputSchema : JSON Schema object，描述参数
        - annotations : 可选元数据（category 等扩展信息）
        """
        tools: list[dict] = []
        for tool in self._registry.list_tools():
            properties = tool.parameters or {}
            tools.append({
                "name": tool.name,
                "description": tool.description,
                "inputSchema": {
                    "type": "object",
                    "properties": properties,
                    "required": list(properties.keys()),
                },
                "annotations": {
                    "category": tool.category,
                },
            })
        # v1.3.0: 确定性排序（按 name 字典序），保证 cacheable list 稳定
        tools.sort(key=lambda t: t["name"])
        return tools

    def list_tools_with_cache(self) -> dict:
        """v1.3.0 cacheable list results —— 返回工具列表 + cache_hint + etag

        客户端可基于 etag 走 If-None-Match → 304，减少重复传输。
        """
        tools = self.list_tools()
        # 基于工具内容计算 etag（内容不变则 etag 不变）
        tools_json = json.dumps(tools, sort_keys=True, ensure_ascii=False)
        etag = hashlib.md5(tools_json.encode("utf-8")).hexdigest()[:16]
        return {
            "tools": tools,
            "cache_hint": {
                "ttl": self.LIST_CACHE_TTL,
                "etag": etag,
                "sortable": True,  # 确定性排序
            },
        }

    # ── 工具调用 ──

    async def call_tool(self, name: str, arguments: dict) -> dict:
        """调用工具并返回 MCP 协议格式的结果

        返回结构：
        - 成功 : {content: [{type:"text", text:"<json>"}], isError: False, tool: name}
        - 失败 : {content: [{type:"text", text:"<err_msg>"}], isError: True,  tool: name}

        注意：工具执行失败属于业务错误，不应抛 HTTP 异常，而是通过 isError=True 上报。
        """
        tool = self._registry.get(name)
        if tool is None:
            logger.warning(f"mcp_tool_not_found: {name}")
            return {
                "content": [{"type": "text", "text": f"工具不存在: {name}"}],
                "isError": True,
                "tool": name,
            }

        try:
            result = await tool.execute(**arguments)
            text = json.dumps(result, ensure_ascii=False, default=str)
            return {
                "content": [{"type": "text", "text": text}],
                "isError": False,
                "tool": name,
            }
        except Exception as e:
            logger.error(
                f"mcp_call_tool_error: tool={name}, error={e}",
                exc_info=True,
            )
            return {
                "content": [{"type": "text", "text": f"工具执行失败: {e}"}],
                "isError": True,
                "tool": name,
            }

    # ── JSON-RPC 2.0 响应封装 ──

    def to_mcp_response(
        self,
        id: Any,
        result: dict | None = None,
        error: dict | None = None,
    ) -> dict:
        """生成 MCP 兼容的 JSON-RPC 2.0 响应

        - id     : 请求 id（int/str/null）
        - result : 成功结果对象（与 error 互斥）
        - error  : 错误对象 {code, message, data?}（与 result 互斥）
        """
        resp: dict = {"jsonrpc": "2.0", "id": id}
        if error is not None:
            resp["error"] = error
        else:
            resp["result"] = result if result is not None else {}
        return resp

    def make_error(
        self,
        code: int,
        message: str,
        data: Any = None,
    ) -> dict:
        """构造 JSON-RPC 2.0 错误对象

        常用 code（JSON-RPC 2.0 + MCP 扩展）：
        - -32600 : 无效请求
        - -32601 : 方法不存在
        - -32602 : 参数无效
        - -32603 : 内部错误
        """
        err: dict = {"code": code, "message": message}
        if data is not None:
            err["data"] = data
        return err

    # ── v1.3.0 JSON-RPC 方法分发 ──

    async def dispatch_method(
        self, method: str, params: dict | None = None, db: Any = None,
    ) -> tuple[dict | None, dict | None]:
        """分发 JSON-RPC 方法（server/discover / tools/list / tools/call 等）

        Args:
            method: JSON-RPC 方法名
            params: 方法参数
            db: 可选数据库会话（透传给需要持久化的扩展，如 enterprise/audit）

        Returns:
            (result, error) —— 成功时 result 非 None，失败时 error 非 None
        """
        params = params or {}

        if method == "server/discover":
            return self.discover(), None

        if method == "tools/list":
            return self.list_tools_with_cache(), None

        if method == "tools/call":
            name = params.get("name")
            arguments = params.get("arguments", {})
            if not name:
                return None, self.make_error(-32602, "缺少参数: name")
            result = await self.call_tool(name, arguments)
            return result, None

        if method == "resources/list":
            return {"resources": []}, None  # 暂未实现 resources 原语

        if method == "prompts/list":
            return {"prompts": []}, None  # 暂未实现 prompts 原语

        # v1.3.0: Tasks 扩展方法分发
        if method.startswith("tasks/"):
            tasks_ext = self.get_extension("tasks")
            if tasks_ext is None:
                return None, self.make_error(-32601, f"Tasks 扩展未启用: {method}")
            result = await tasks_ext.dispatch(method, params)
            return cast(tuple[dict | None, dict | None], result)

        # Enterprise 扩展方法分发（MCP 2026 Roadmap Enterprise Readiness）
        if method.startswith("enterprise/"):
            ent_ext = self.get_extension("enterprise")
            if ent_ext is None:
                return None, self.make_error(-32601, f"Enterprise 扩展未启用: {method}")
            result = await ent_ext.dispatch(method, params, db=db)
            return cast(tuple[dict | None, dict | None], result)

        return None, self.make_error(-32601, f"方法不存在: {method}")


# 模块级单例，路由层直接复用
mcp_server = MCPServer()

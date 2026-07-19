"""MCP Server 核心实现 —— 纯 Python dict 实现 MCP 协议，不依赖第三方 SDK

参考: MCP 2026-07-28 spec
- 工具格式 : {name, description, inputSchema(=JSON Schema object)}
- 调用结果 : {content: [{type: "text", text: "..."}], isError: bool}
- 响应封装 : JSON-RPC 2.0 {jsonrpc: "2.0", id, result|error}

复用 app/services/agent_tool_registry.py 的 tool_registry 单例，
将项目内 Agent 工具统一暴露为 MCP 协议兼容接口。
"""

import json
import logging
from typing import Any

from app.services.agent_tool_registry import tool_registry

logger = logging.getLogger(__name__)


class MCPServer:
    """MCP Server —— 封装工具列表/调用/JSON-RPC 2.0 响应

    职责：
    1. 将 tool_registry 中的 AgentTool 转换为 MCP 协议格式（list_tools）
    2. 调用工具并包装结果为 MCP content 格式（call_tool）
    3. 生成 JSON-RPC 2.0 兼容响应（to_mcp_response）
    4. 暴露服务器元信息（get_manifest）
    """

    # ── 服务器元信息常量 ──
    SERVER_NAME = "i-home.life MCP Server"
    SERVER_VERSION = "1.0.0"
    # MCP 2026-07-28 stateless 核心
    PROTOCOL_VERSION = "2026-07-28"

    def __init__(self):
        self._registry = tool_registry

    # ── 元信息 ──

    def get_manifest(self) -> dict:
        """返回服务器元信息（name/version/tools count/protocol_version）"""
        return {
            "name": self.SERVER_NAME,
            "version": self.SERVER_VERSION,
            "protocol_version": self.PROTOCOL_VERSION,
            "tools_count": self._registry.tool_count,
            "capabilities": {
                # 仅声明 tools 能力，不启用 listChanged 增量推送
                "tools": {"listChanged": False},
                "resources": {},
                "prompts": {},
            },
        }

    # ── 工具列表 ──

    def list_tools(self) -> list[dict]:
        """返回 MCP 协议格式的工具列表

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
                # MCP annotations 用于附加工具元信息（不影响协议兼容性）
                "annotations": {
                    "category": tool.category,
                },
            })
        return tools

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
            # 将 dict 结果序列化为文本，符合 MCP content[].text 字段类型约束
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


# 模块级单例，路由层直接复用
mcp_server = MCPServer()

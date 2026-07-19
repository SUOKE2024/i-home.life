"""MCP (Model Context Protocol) Server —— 将 Agent 工具暴露为标准 MCP 接口

供外部 AI 客户端（Claude Desktop / Cursor / 小艺）通过统一协议调用
项目内已有的 Agent 工具集（预算 / 设计 / 物料 / 施工 / 质检）。

模块结构：
- server.py  : MCPServer 核心类（纯 Python dict 实现 MCP 协议，无第三方 SDK 依赖）
- 路由层位于 app/api/mcp.py
"""

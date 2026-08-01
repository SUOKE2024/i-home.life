"""MCP Tasks 扩展（v1.3.0 对齐 MCP 2026-07-28 Tasks extension）

MCP 2026-07-28 规范将 Tasks 提升为正式扩展，用于异步任务管理。
与 A2A Task Machine 互补：
- A2A Tasks: 跨 Agent 任务委托（不同框架/厂商的 Agent 协作）
- MCP Tasks: 单 Agent 异步任务（Agent 通过 MCP 工具发起的长任务）

本实现采用内存存储 + TTL 清理（24h），适合单实例部署。
多实例部署需替换为 Redis/DB 共享存储（TODO: 多 worker 支持）。

方法：
- tasks/create: 创建异步任务
- tasks/update: 更新任务状态
- tasks/get: 查询任务详情
- tasks/list: 列出任务
- tasks/cancel: 取消任务
"""

import asyncio
import time
import uuid
from typing import Any

from app.mcp.extensions import Extension

_TASK_TTL_SECONDS = 24 * 3600  # 24h 自动清理


class TaskState:
    """任务状态枚举（对标 A2A TaskState）"""
    SUBMITTED = "submitted"
    WORKING = "working"
    COMPLETED = "completed"
    CANCELED = "canceled"
    FAILED = "failed"


class _Task:
    """内存任务对象"""

    __slots__ = ("id", "name", "arguments", "state", "result", "error", "created_at", "updated_at", "metadata")

    def __init__(self, name: str, arguments: dict, metadata: dict | None = None):
        self.id = str(uuid.uuid4())
        self.name = name
        self.arguments = arguments
        self.state = TaskState.SUBMITTED
        self.result: Any = None
        self.error: str | None = None
        self.created_at = time.time()
        self.updated_at = time.time()
        self.metadata = metadata or {}

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "arguments": self.arguments,
            "state": self.state,
            "result": self.result,
            "error": self.error,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "metadata": self.metadata,
        }


class TasksExtension(Extension):
    """MCP Tasks 扩展"""

    NAME = "tasks"
    VERSION = "1.0.0"

    def __init__(self):
        self._tasks: dict[str, _Task] = {}
        self._lock = asyncio.Lock()

    async def _cleanup_expired(self) -> None:
        """清理过期任务（24h TTL）"""
        now = time.time()
        expired = [tid for tid, t in self._tasks.items() if now - t.updated_at > _TASK_TTL_SECONDS]
        for tid in expired:
            del self._tasks[tid]

    async def dispatch(self, method: str, params: dict | None = None) -> tuple[dict | None, dict | None]:
        params = params or {}
        await self._cleanup_expired()

        if method == "tasks/create":
            return await self.create_task(params)
        if method == "tasks/update":
            return await self.update_task(params)
        if method == "tasks/get":
            return await self.get_task(params)
        if method == "tasks/list":
            return await self.list_tasks(params)
        if method == "tasks/cancel":
            return await self.cancel_task(params)

        return None, {"code": -32601, "message": f"Tasks 方法不存在: {method}"}

    async def create_task(self, params: dict) -> tuple[dict | None, dict | None]:
        name = params.get("name")
        if not name:
            return None, {"code": -32602, "message": "缺少参数: name"}
        arguments = params.get("arguments", {})
        metadata = params.get("metadata", {})
        async with self._lock:
            task = _Task(name, arguments, metadata)
            self._tasks[task.id] = task
        return {"task": task.to_dict()}, None

    async def update_task(self, params: dict) -> tuple[dict | None, dict | None]:
        task_id = params.get("id")
        if not task_id:
            return None, {"code": -32602, "message": "缺少参数: id"}
        async with self._lock:
            task = self._tasks.get(task_id)
            if task is None:
                return None, {"code": -32602, "message": f"任务不存在: {task_id}"}
            if "state" in params:
                task.state = params["state"]
            if "result" in params:
                task.result = params["result"]
            if "error" in params:
                task.error = params["error"]
            if "metadata" in params:
                task.metadata.update(params["metadata"])
            task.updated_at = time.time()
            return {"task": task.to_dict()}, None

    async def get_task(self, params: dict) -> tuple[dict | None, dict | None]:
        task_id = params.get("id")
        if not task_id:
            return None, {"code": -32602, "message": "缺少参数: id"}
        task = self._tasks.get(task_id)
        if task is None:
            return None, {"code": -32602, "message": f"任务不存在: {task_id}"}
        return {"task": task.to_dict()}, None

    async def list_tasks(self, params: dict) -> tuple[dict | None, dict | None]:
        state_filter = params.get("state")
        limit = min(params.get("limit", 100), 500)  # 上限 500 防滥用
        tasks = list(self._tasks.values())
        if state_filter:
            tasks = [t for t in tasks if t.state == state_filter]
        tasks.sort(key=lambda t: t.updated_at, reverse=True)
        return {"tasks": [t.to_dict() for t in tasks[:limit]]}, None

    async def cancel_task(self, params: dict) -> tuple[dict | None, dict | None]:
        task_id = params.get("id")
        if not task_id:
            return None, {"code": -32602, "message": "缺少参数: id"}
        async with self._lock:
            task = self._tasks.get(task_id)
            if task is None:
                return None, {"code": -32602, "message": f"任务不存在: {task_id}"}
            if task.state in (TaskState.COMPLETED, TaskState.FAILED, TaskState.CANCELED):
                return None, {"code": -32602, "message": f"任务已终态，不可取消: {task.state}"}
            task.state = TaskState.CANCELED
            task.updated_at = time.time()
            return {"task": task.to_dict()}, None

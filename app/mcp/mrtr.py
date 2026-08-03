"""MCP Multi Round-Trip Requests (MRTR) 管理器（v1.3.0 对齐 MCP 2026-07-28）

MCP 2026-07-28 规范将服务端→客户端请求（sampling/elicitation）重新设计为
Multi Round-Trip Requests (MRTR)，移除常开双向流的需求。

本实现采用轮询式 MRTR：
1. 服务端需要客户端配合时（如 sampling），创建 MRTR 请求
2. 客户端轮询 POST /api/mcp/mrtr/{request_id} 拉取请求
3. 客户端处理后回传响应
4. 服务端消费响应，继续原工具调用

内存存储 + TTL 清理（5 分钟），适合单实例。
多实例部署需替换为 Redis/DB 共享存储。

受 settings.mcp_mrtr_enabled feature flag 控制。
"""

import asyncio
import time
import uuid
from typing import Any

_MRTR_TTL_SECONDS = 300  # 5 分钟超时


class MRTRState:
    PENDING = "pending"      # 等待客户端响应
    COMPLETED = "completed"  # 客户端已回传响应
    TIMED_OUT = "timed_out"
    CANCELED = "canceled"


class _MRTRRequest:
    """MRTR 请求对象（服务端→客户端）"""

    __slots__ = ("id", "method", "params", "state", "response", "created_at", "expires_at")

    def __init__(self, method: str, params: dict):
        self.id = str(uuid.uuid4())
        self.method = method  # "sampling" | "elicitation"
        self.params = params
        self.state = MRTRState.PENDING
        self.response: Any = None
        self.created_at = time.time()
        self.expires_at = time.time() + _MRTR_TTL_SECONDS

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "method": self.method,
            "params": self.params,
            "state": self.state,
            "created_at": self.created_at,
            "expires_at": self.expires_at,
        }


class MRTRManager:
    """MRTR 请求管理器（单例）"""

    def __init__(self):
        self._requests: dict[str, _MRTRRequest] = {}
        self._lock = asyncio.Lock()
        # 等待响应的 Future（工具调用方阻塞等待）
        self._waiters: dict[str, asyncio.Future] = {}

    async def create_request(self, method: str, params: dict) -> _MRTRRequest:
        """服务端创建 MRTR 请求（如工具需要客户端 sampling）"""
        async with self._lock:
            req = _MRTRRequest(method, params)
            self._requests[req.id] = req
            self._waiters[req.id] = asyncio.get_event_loop().create_future()
        return req

    async def wait_for_response(self, request_id: str, timeout: float = _MRTR_TTL_SECONDS) -> Any:
        """工具调用方阻塞等待客户端响应"""
        future = self._waiters.get(request_id)
        if future is None:
            raise KeyError(f"MRTR 请求不存在或已完成: {request_id}")
        try:
            return await asyncio.wait_for(future, timeout=timeout)
        except asyncio.TimeoutError:
            async with self._lock:
                req = self._requests.get(request_id)
                if req:
                    req.state = MRTRState.TIMED_OUT
            raise

    async def submit_response(self, request_id: str, response: Any) -> bool:
        """客户端回传 MRTR 响应"""
        async with self._lock:
            req = self._requests.get(request_id)
            if req is None or req.state != MRTRState.PENDING:
                return False
            if req.expires_at < time.time():
                req.state = MRTRState.TIMED_OUT
                return False
            req.state = MRTRState.COMPLETED
            req.response = response
            future = self._waiters.get(request_id)
            if future and not future.done():
                future.set_result(response)
            return True

    async def get_request(self, request_id: str) -> _MRTRRequest | None:
        """查询 MRTR 请求状态"""
        return self._requests.get(request_id)

    async def cancel_request(self, request_id: str) -> bool:
        """取消 MRTR 请求"""
        async with self._lock:
            req = self._requests.get(request_id)
            if req is None or req.state != MRTRState.PENDING:
                return False
            req.state = MRTRState.CANCELED
            future = self._waiters.get(request_id)
            if future and not future.done():
                future.cancel()
            return True

    async def list_pending(self) -> list[_MRTRRequest]:
        """列出待响应的 MRTR 请求（客户端轮询用）"""
        await self._cleanup_expired()
        return [r for r in self._requests.values() if r.state == MRTRState.PENDING]

    async def _cleanup_expired(self) -> None:
        now = time.time()
        expired = [rid for rid, r in self._requests.items() if r.expires_at < now and r.state == MRTRState.PENDING]
        for rid in expired:
            r = self._requests[rid]
            r.state = MRTRState.TIMED_OUT
            future = self._waiters.get(rid)
            if future and not future.done():
                future.cancel()


# 模块级单例
mrtr_manager = MRTRManager()

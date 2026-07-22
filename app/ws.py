"""WebSocket 实时同步管理器

为 i-home.life 平台提供跨端实时数据同步能力。
支持按项目（project_id）分组，实现设计台、业主端、施工端的数据实时推送。

v1.1.1 新增心跳机制：
- 客户端发送 {"event":"ping"} → 服务端自动回复 {"event":"pong"}
- 服务端 receive 超时（RECEIVE_TIMEOUT 秒）后发送 ping 探测
- 探测后 PONG_TIMEOUT 秒内无回复则断开僵尸连接

v1.1.12 性能优化：
- broadcast_to_project 改为 asyncio.gather 并发发送，N 个连接的广播延迟从 N×RTT 降至 1×RTT
"""

import asyncio
import json
import logging
from datetime import datetime, date
from typing import Any

from fastapi import WebSocket

logger = logging.getLogger(__name__)


def _json_serialize(obj):
    """自定义 JSON 序列化，处理 datetime / date 类型"""
    if isinstance(obj, (datetime, date)):
        return obj.isoformat()
    raise TypeError(f"Object of type {type(obj).__name__} is not JSON serializable")


# 心跳配置
RECEIVE_TIMEOUT = 300  # 无活动 5 分钟后发送 ping 探测
PONG_TIMEOUT = 30  # ping 探测后 30 秒无回复则断开


class ConnectionManager:
    """WebSocket 连接管理器，按项目房间分组管理连接"""

    def __init__(self):
        # project_id -> set of WebSocket connections
        self._connections: dict[str, set[WebSocket]] = {}
        # WebSocket -> project_id 反向映射
        self._ws_to_project: dict[WebSocket, str] = {}

    async def connect(self, websocket: WebSocket, project_id: str):
        await websocket.accept()
        if project_id not in self._connections:
            self._connections[project_id] = set()
        self._connections[project_id].add(websocket)
        self._ws_to_project[websocket] = project_id
        # v1.1.26: 更新 Prometheus WS 连接数指标
        try:
            from app.metrics import ws_connections
            ws_connections.inc()
        except Exception:
            pass
        logger.info(f"WebSocket 连接: project={project_id}, total={len(self._connections[project_id])}")

    def disconnect(self, websocket: WebSocket):
        project_id = self._ws_to_project.pop(websocket, None)
        if project_id and project_id in self._connections:
            self._connections[project_id].discard(websocket)
            if not self._connections[project_id]:
                del self._connections[project_id]
            # v1.1.26: 更新 Prometheus WS 连接数指标
            try:
                from app.metrics import ws_connections
                ws_connections.dec()
            except Exception:
                pass
            logger.info(f"WebSocket 断开: project={project_id}")

    async def broadcast_to_project(self, project_id: str, event: str, data: dict[str, Any]):
        """向指定项目的所有连接并发广播消息

        v1.1.12: 使用 asyncio.gather 并发发送，所有连接的广播延迟降至 1×RTT。
        失败的连接会被收集并统一清理。
        """
        if project_id not in self._connections:
            return
        message = json.dumps({"event": event, "data": data}, ensure_ascii=False, default=_json_serialize)
        targets = list(self._connections[project_id])
        if not targets:
            return

        async def _safe_send(ws: WebSocket) -> bool:
            try:
                await ws.send_text(message)
                return True
            except Exception:
                return False

        # 并发发送所有连接
        results = await asyncio.gather(*[_safe_send(ws) for ws in targets], return_exceptions=False)
        # 清理失败的连接
        for ws, ok in zip(targets, results):
            if not ok:
                self.disconnect(ws)

    async def send_to(self, websocket: WebSocket, event: str, data: dict[str, Any]):
        """向单个连接发送消息"""
        message = json.dumps({"event": event, "data": data}, ensure_ascii=False, default=_json_serialize)
        try:
            await websocket.send_text(message)
        except Exception:
            self.disconnect(websocket)

    async def send_ping(self, websocket: WebSocket):
        """发送心跳探测（v1.1.1）"""
        try:
            await websocket.send_text(json.dumps({"event": "ping", "data": {}}))
        except Exception:
            self.disconnect(websocket)

    @property
    def active_projects(self) -> list[str]:
        return list(self._connections.keys())

    @property
    def active_connections(self) -> int:
        return len(self._ws_to_project)


ws_manager = ConnectionManager()

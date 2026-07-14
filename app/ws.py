"""WebSocket 实时同步管理器

为 i-home.life 平台提供跨端实时数据同步能力。
支持按项目（project_id）分组，实现设计台、业主端、施工端的数据实时推送。
"""

import json
import logging
from typing import Any

from fastapi import WebSocket

logger = logging.getLogger(__name__)


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
        logger.info(f"WebSocket 连接: project={project_id}, total={len(self._connections[project_id])}")

    def disconnect(self, websocket: WebSocket):
        project_id = self._ws_to_project.pop(websocket, None)
        if project_id and project_id in self._connections:
            self._connections[project_id].discard(websocket)
            if not self._connections[project_id]:
                del self._connections[project_id]
            logger.info(f"WebSocket 断开: project={project_id}")

    async def broadcast_to_project(self, project_id: str, event: str, data: dict[str, Any]):
        """向指定项目的所有连接广播消息"""
        if project_id not in self._connections:
            return
        message = json.dumps({"event": event, "data": data}, ensure_ascii=False)
        stale = set()
        for ws in self._connections[project_id]:
            try:
                await ws.send_text(message)
            except Exception:
                stale.add(ws)
        for ws in stale:
            self.disconnect(ws)

    async def send_to(self, websocket: WebSocket, event: str, data: dict[str, Any]):
        """向单个连接发送消息"""
        message = json.dumps({"event": event, "data": data}, ensure_ascii=False)
        try:
            await websocket.send_text(message)
        except Exception:
            self.disconnect(websocket)

    @property
    def active_projects(self) -> list[str]:
        return list(self._connections.keys())

    @property
    def active_connections(self) -> int:
        return len(self._ws_to_project)


ws_manager = ConnectionManager()

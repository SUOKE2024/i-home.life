"""语音智能体编排服务 — 语音作为 Agent 调度入口

借鉴 GPT Voice / Claude Voice (2026-07) 的 agent orchestration 范式：
- 一句话启动后台 Agent 任务，长任务不阻塞语音对话
- 连接词切分多意图，并行协调多个 Agent（"同时/另外/再帮我"）
- 语音任务生命周期控制（查询进度 / 取消任务 / 任务列表）

受 settings.voice_agent_orchestration_enabled feature flag 控制。
"""

from __future__ import annotations

import asyncio
import logging
import re
import time
import uuid
from collections.abc import Coroutine
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class VoiceTask:
    """一个由语音指令启动的后台 Agent 任务。"""

    task_id: str
    seq: int
    intent: str
    command: str
    status: str = "running"  # running | done | failed | cancelled
    reply: str = ""
    error: str = ""
    created_at: float = field(default_factory=time.time)
    finished_at: float | None = None
    asyncio_task: asyncio.Task | None = field(default=None, repr=False)

    def to_dict(self) -> dict[str, Any]:
        return {
            "task_id": self.task_id,
            "seq": self.seq,
            "intent": self.intent,
            "command": self.command,
            "status": self.status,
            "reply": self.reply,
            "error": self.error,
            "created_at": self.created_at,
            "finished_at": self.finished_at,
        }


class VoiceTaskRegistry:
    """进程内语音任务注册表。

    项目为模块化单体（阿里云 FC 单实例），进程内注册表即可满足当前部署；
    多实例扩展时应迁移到 Redis（复用 app/services/cache_service.py）。
    """

    def __init__(self) -> None:
        self._tasks: dict[str, list[VoiceTask]] = {}  # user_id → [VoiceTask]
        self._lock = asyncio.Lock()

    async def launch(
        self,
        user_id: str,
        intent: str,
        command: str,
        coro: Coroutine[Any, Any, str],
    ) -> VoiceTask:
        """注册并后台执行一个语音任务。"""
        async with self._lock:
            seq = len(self._tasks.get(user_id, [])) + 1
        task = VoiceTask(task_id=uuid.uuid4().hex[:8], seq=seq, intent=intent, command=command)

        async def _runner() -> None:
            try:
                task.reply = await coro
                task.status = "done"
            except asyncio.CancelledError:
                task.status = "cancelled"
                raise
            except Exception as e:  # noqa: BLE001 — 后台任务必须兜底，禁止泄漏到事件循环
                logger.warning("voice_task_failed: task=%s intent=%s error=%s", task.task_id, intent, e)
                task.status = "failed"
                task.error = str(e)
            finally:
                task.finished_at = time.time()
                logger.info(
                    "voice_task_finished: task=%s intent=%s status=%s elapsed=%.2fs",
                    task.task_id, intent, task.status, task.finished_at - task.created_at,
                )

        task.asyncio_task = asyncio.create_task(_runner())
        async with self._lock:
            self._tasks.setdefault(user_id, []).append(task)
        logger.info("voice_task_launched: user=%s task=%s intent=%s", user_id, task.task_id, intent)
        return task

    async def list(self, user_id: str) -> list[VoiceTask]:
        async with self._lock:
            return list(self._tasks.get(user_id, []))

    async def resolve(self, user_id: str, task_ref: str | None) -> VoiceTask | None:
        """按引用定位任务：None=最近一个；数字=序号(seq)；否则按 task_id 前缀匹配。"""
        tasks = await self.list(user_id)
        if not tasks:
            return None
        if task_ref is None:
            return tasks[-1]
        if task_ref.isdigit():
            return next((t for t in tasks if t.seq == int(task_ref)), None)
        return next((t for t in tasks if t.task_id.startswith(task_ref)), None)

    async def cancel(self, user_id: str, task_ref: str | None) -> VoiceTask | None:
        task = await self.resolve(user_id, task_ref)
        if task is None or task.status != "running":
            return task
        # 立即标记，避免事件循环尚未调度 runner 的 CancelledError 处理器时
        # 调用方读到旧的 running 状态；runner 侧的兜底赋值与之幂等
        task.status = "cancelled"
        task.finished_at = time.time()
        if task.asyncio_task and not task.asyncio_task.done():
            task.asyncio_task.cancel()
        return task


voice_task_registry = VoiceTaskRegistry()


# ── 多意图切分 ────────────────────────────────────────────────

_CONNECTOR_RE = re.compile(r"(?:同时|并且|另外|还有|再帮我|然后再|然后|接着|顺便|；|;)")


def split_multi_intent(text: str) -> list[str]:
    """把一句话按连接词切分为多个可独立执行的指令段。"""
    parts = [p.strip(" ，,。") for p in _CONNECTOR_RE.split(text)]
    return [p for p in parts if len(p) >= 2]


# ── 任务控制命令解析 ──────────────────────────────────────────

_TASK_NOUN_RE = re.compile(r"任务")
_CANCEL_VERB_RE = re.compile(r"取消|停下|停止|终止|别做|不用做")
_STATUS_VERB_RE = re.compile(r"进度|状态|怎么样|跑得如何|做完了吗|做好了吗|好了吗|结果如何|完成了吗")
_LIST_RE = re.compile(r"任务列表|所有任务|哪些任务|几个任务|在跑什么")
_SEQ_RE = re.compile(r"(?:第\s*(\d+)\s*个)?任务\s*(?:编号)?\s*(\d+)?")
_ID_RE = re.compile(r"任务\s*([0-9a-f]{6,})")


def parse_task_command(text: str) -> dict[str, Any] | None:
    """识别语音任务控制指令；非任务控制返回 None。

    保守识别：必须显式提及"任务"（列表类句式除外），
    避免劫持"施工进度"等正常业务意图。
    """
    if _LIST_RE.search(text):
        return {"action": "list", "task_ref": None}

    if not _TASK_NOUN_RE.search(text):
        return None

    task_ref: str | None = None
    id_match = _ID_RE.search(text)
    seq_match = _SEQ_RE.search(text)
    if id_match:
        task_ref = id_match.group(1)
    elif seq_match:
        task_ref = seq_match.group(1) or seq_match.group(2)

    if _CANCEL_VERB_RE.search(text):
        return {"action": "cancel", "task_ref": task_ref}
    if _STATUS_VERB_RE.search(text):
        return {"action": "status", "task_ref": task_ref}
    return None

"""
SSE 流管理器

管理 SSE 客户端连接和事件广播。
每个 thread_id 可对应多个监听客户端，使用 asyncio.Queue 实现生产-消费模型。
"""

import asyncio
import logging
from datetime import datetime
from typing import Dict, List, Optional

from adcast_agent.api.schemas import SSEEvent

logger = logging.getLogger(__name__)


class SSEManager:
    """SSE 流管理器

    管理 SSE 客户端连接和事件广播：
    - 每个 thread_id 可对应多个监听客户端
    - 使用 asyncio.Queue(maxsize=100) 实现生产-消费模型
    - 队列满时静默丢弃事件，防止广播阻塞
    - 自动清理死亡队列
    """

    def __init__(self):
        self._clients: Dict[str, List[asyncio.Queue]] = {}
        self._cleanup_task: Optional[asyncio.Task] = None

    async def connect(self, thread_id: str) -> asyncio.Queue:
        """新客户端连接，返回一个 Queue 用于接收事件。"""
        queue = asyncio.Queue(maxsize=100)
        if thread_id not in self._clients:
            self._clients[thread_id] = []
        self._clients[thread_id].append(queue)
        logger.debug(f"SSE client connected: thread={thread_id}, total={len(self._clients[thread_id])}")
        return queue

    def disconnect(self, thread_id: str, queue: asyncio.Queue) -> None:
        """客户端断开连接，清理 Queue。"""
        clients = self._clients.get(thread_id, [])
        if queue in clients:
            clients.remove(queue)
            logger.debug(f"SSE client disconnected: thread={thread_id}, remaining={len(clients)}")
        if not clients and thread_id in self._clients:
            del self._clients[thread_id]

    async def emit(self, thread_id: str, event: SSEEvent) -> None:
        """向指定 thread 的所有客户端广播事件。"""
        clients = self._clients.get(thread_id, [])
        dead_queues = []
        for queue in clients:
            try:
                queue.put_nowait(event)
            except asyncio.QueueFull:
                dead_queues.append(queue)
            except Exception:
                dead_queues.append(queue)
        # 清理死亡队列
        for dq in dead_queues:
            self.disconnect(thread_id, dq)

    async def emit_to_all(self, event: SSEEvent) -> None:
        """广播给所有客户端。"""
        for thread_id in list(self._clients.keys()):
            await self.emit(thread_id, event)

    async def heartbeat_loop(self, thread_id: str, interval: float = 15.0) -> None:
        """定时发送心跳保持连接。无客户端时自动退出。"""
        while True:
            await asyncio.sleep(interval)
            clients = self._clients.get(thread_id, [])
            if not clients:
                break
            await self.emit(
                thread_id,
                SSEEvent(
                    event="heartbeat",
                    data={},
                    timestamp=datetime.utcnow().isoformat(),
                ),
            )

    def get_client_count(self, thread_id: str) -> int:
        """获取指定 thread 的客户端数量。"""
        return len(self._clients.get(thread_id, []))

    def shutdown(self) -> None:
        """关闭所有连接。"""
        self._clients.clear()
        logger.info("SSE manager shutdown")


# 全局单例
sse_manager = SSEManager()

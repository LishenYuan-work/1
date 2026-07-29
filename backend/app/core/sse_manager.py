"""
SSE 连接管理器

维护 {debate_id: [asyncio.Queue]} 映射，支持：
- 多个客户端同时观看同一场辩论
- 辩论结束后自动清理
- 断线重连（客户端重连时回放已缓存的事件）
"""

import asyncio
import json
from collections import defaultdict


class SSEManager:
    """管理所有辩论的 SSE 广播"""

    def __init__(self):
        # debate_id -> list of asyncio.Queue
        self._subscribers: dict[str, list[asyncio.Queue]] = defaultdict(list)
        # debate_id -> list of past events (for replay on reconnect)
        self._event_log: dict[str, list[str]] = defaultdict(list)
        # debate_id -> bool (是否已完成)
        self._completed: dict[str, bool] = {}
        # 流式状态：debate_id -> {agent_name: current_text, round_num, agent_name}
        self._streaming: dict[str, dict] = {}

    async def subscribe(self, debate_id: str) -> asyncio.Queue:
        """客户端订阅某个辩论的 SSE 流，返回专属队列"""
        queue: asyncio.Queue = asyncio.Queue()
        self._subscribers[debate_id].append(queue)

        # 回放已有事件（断线重连场景）
        for event_str in self._event_log.get(debate_id, []):
            await queue.put(event_str)

        # 如果已结束，发送 done 信号
        if self._completed.get(debate_id):
            await queue.put(self._format_sse("done", {"status": "completed"}))

        return queue

    def unsubscribe(self, debate_id: str, queue: asyncio.Queue):
        """客户端断开连接"""
        subs = self._subscribers.get(debate_id, [])
        if queue in subs:
            subs.remove(queue)
        if not subs and debate_id in self._completed:
            # 清理已完成且无观众的辩论
            self._subscribers.pop(debate_id, None)
            self._event_log.pop(debate_id, None)
            self._completed.pop(debate_id, None)

    async def broadcast(self, debate_id: str, event_type: str, data: dict):
        """向所有订阅者广播事件"""
        event_str = self._format_sse(event_type, data)
        self._event_log[debate_id].append(event_str)

        # 清理断开的队列
        dead_queues = []
        for q in self._subscribers.get(debate_id, []):
            try:
                await q.put(event_str)
            except Exception:
                dead_queues.append(q)

        for q in dead_queues:
            self.unsubscribe(debate_id, q)

        # 更新流式状态
        if event_type == "agent_start":
            self._streaming[debate_id] = {
                "agent_name": data.get("agent", ""),
                "round_num": data.get("round", 1),
                "text": "",
            }
        elif event_type == "chunk":
            if debate_id in self._streaming:
                self._streaming[debate_id]["text"] += data.get("text", "")
        elif event_type == "agent_end":
            if debate_id in self._streaming:
                self._streaming[debate_id]["text"] = data.get("full_text", "")

        if event_type == "done":
            self._completed[debate_id] = True
            self._streaming.pop(debate_id, None)

    def get_streaming_state(self, debate_id: str) -> dict | None:
        """获取某个辩论当前正在输入的文字（供轮询端点使用）"""
        return self._streaming.get(debate_id)

    @staticmethod
    def _format_sse(event_type: str, data: dict) -> str:
        """格式化为 SSE text/event-stream 格式"""
        payload = json.dumps(data, ensure_ascii=False)
        return f"event: {event_type}\ndata: {payload}\n\n"


# 全局单例
sse_manager = SSEManager()

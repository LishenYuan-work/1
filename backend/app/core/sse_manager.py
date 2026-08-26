"""In-memory broadcast manager; durable replay is stored in review_events."""
import asyncio
import json
from collections import defaultdict

class SSEManager:
    def __init__(self):
        self._subscribers: dict[str, list[asyncio.Queue]] = defaultdict(list)
        self._event_log: dict[str, list[str]] = defaultdict(list)
        self._completed: dict[str, bool] = {}
    async def subscribe(self, session_id: str, after: int = 0) -> asyncio.Queue:
        queue: asyncio.Queue = asyncio.Queue()
        self._subscribers[session_id].append(queue)
        for event in self._event_log.get(session_id, []):
            event_id = next((line[4:] for line in event.splitlines() if line.startswith("id: ")), "0")
            if int(event_id or 0) > after:
                await queue.put(event)
        return queue
    def unsubscribe(self, session_id: str, queue: asyncio.Queue):
        subscribers = self._subscribers.get(session_id, [])
        if queue in subscribers: subscribers.remove(queue)
        if not subscribers and self._completed.get(session_id):
            self._subscribers.pop(session_id, None); self._event_log.pop(session_id, None); self._completed.pop(session_id, None)
    async def broadcast(self, session_id: str, event_type: str, data: dict):
        event = self._format_sse(event_type, data); self._event_log[session_id].append(event)
        for queue in list(self._subscribers.get(session_id, [])):
            try: await queue.put(event)
            except Exception: self.unsubscribe(session_id, queue)
        if event_type == "done": self._completed[session_id] = True
        if event_type == "done" and not self._subscribers.get(session_id):
            self._event_log.pop(session_id, None)
    @staticmethod
    def _format_sse(event_type: str, data: dict) -> str:
        payload = json.dumps(data, ensure_ascii=False)
        event_id = f"id: {data.get('sequence')}\n" if data.get("sequence") else ""
        return f"{event_id}event: {event_type}\ndata: {payload}\n\n"

sse_manager = SSEManager()

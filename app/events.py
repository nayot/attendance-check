"""In-process publish/subscribe for live display updates (Server-Sent Events).

State lives in one process, so run a single worker (the default in the
Docker image).
"""

import asyncio
from collections import defaultdict


class Broker:
    def __init__(self):
        self._subs: dict[int, set[asyncio.Queue]] = defaultdict(set)
        self._loop: asyncio.AbstractEventLoop | None = None

    def bind(self, loop: asyncio.AbstractEventLoop) -> None:
        self._loop = loop

    def subscribe(self, session_id: int) -> asyncio.Queue:
        q: asyncio.Queue = asyncio.Queue(maxsize=500)
        self._subs[session_id].add(q)
        return q

    def unsubscribe(self, session_id: int, q: asyncio.Queue) -> None:
        self._subs[session_id].discard(q)
        if not self._subs[session_id]:
            del self._subs[session_id]

    def publish(self, session_id: int, event: str, data: dict) -> None:
        """Safe to call from request threads as well as the event loop."""
        if self._loop is None:
            return
        for q in list(self._subs.get(session_id, ())):
            self._loop.call_soon_threadsafe(self._put, q, (event, data))

    @staticmethod
    def _put(q: asyncio.Queue, item) -> None:
        try:
            q.put_nowait(item)
        except asyncio.QueueFull:
            pass

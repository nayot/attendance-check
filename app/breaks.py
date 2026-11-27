"""Break timer shown on the class screen.

Held in memory only, like live questions (see live.py): a restart clears it.
The server keeps the end time, so every screen showing the session counts down
to the same moment and a reload picks up where it was.
"""

import threading
import time
from dataclasses import dataclass

MIN_MINUTES = 1
MAX_MINUTES = 120


@dataclass
class Break:
    started_at: float
    ends_at: float

    def view(self) -> dict:
        return {"started_at": self.started_at, "ends_at": self.ends_at, "now": time.time()}


class BreakStore:
    def __init__(self):
        self._lock = threading.Lock()
        self._breaks: dict[int, Break] = {}

    def get(self, session_id: int) -> dict | None:
        with self._lock:
            b = self._breaks.get(session_id)
            return b.view() if b else None

    def start(self, session_id: int, minutes: int) -> dict:
        if not MIN_MINUTES <= minutes <= MAX_MINUTES:
            raise ValueError("A break is 1 to 120 minutes long.")
        now = time.time()
        with self._lock:
            b = self._breaks[session_id] = Break(now, now + minutes * 60)
            return b.view()

    def adjust(self, session_id: int, minutes: int) -> dict | None:
        """Add (or with a negative number, take off) minutes. Never ends before now."""
        now = time.time()
        with self._lock:
            b = self._breaks.get(session_id)
            if b is None:
                return None
            # Adding time after the break ran out counts from now, not from the old end.
            base = max(b.ends_at, now) if minutes > 0 else b.ends_at
            b.ends_at = min(max(now, base + minutes * 60), now + MAX_MINUTES * 60)
            return b.view()

    def end(self, session_id: int) -> None:
        with self._lock:
            self._breaks.pop(session_id, None)

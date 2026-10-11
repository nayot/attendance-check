"""Rotating QR tokens.

A token is an HMAC over (phase id, time window). The display shows the
current window's token; the server also accepts the previous window so a
code scanned just before it rotates still works.
"""

import base64
import hashlib
import hmac
import time


class TokenSigner:
    def __init__(self, secret: str):
        self._key = hashlib.sha256(("qr:" + secret).encode()).digest()

    @staticmethod
    def window(interval: int, now: float | None = None) -> int:
        return int((time.time() if now is None else now) // interval)

    def token(self, phase_id: int, window: int) -> str:
        mac = hmac.new(self._key, f"{phase_id}:{window}".encode(), hashlib.sha256).digest()
        return base64.urlsafe_b64encode(mac[:12]).decode().rstrip("=")

    def current(self, phase_id: int, interval: int, now: float | None = None) -> tuple[str, int]:
        w = self.window(interval, now)
        return self.token(phase_id, w), w

    def verify(self, phase_id: int, token: str, interval: int, now: float | None = None) -> bool:
        w = self.window(interval, now)
        return any(hmac.compare_digest(self.token(phase_id, x), token) for x in (w, w - 1))

"""Send mail from a teacher's own Gmail / Google Workspace account.

Teachers grant the `gmail.send` scope once (Dashboard → Connect Gmail). The
refresh token is stored encrypted with a key derived from SECRET_KEY.
"""

import base64
import hashlib
import logging
import threading
import time
from datetime import datetime
from email.message import EmailMessage

import httpx
from cryptography.fernet import Fernet, InvalidToken
from sqlalchemy import String, Text
from sqlalchemy.orm import Mapped, mapped_column

from .db import AwareDateTime, Base, Database, utcnow

log = logging.getLogger("attendance.gmail")

SCOPE = "https://www.googleapis.com/auth/gmail.send"
TOKEN_URL = "https://oauth2.googleapis.com/token"
SEND_URL = "https://gmail.googleapis.com/gmail/v1/users/me/messages/send"


class GmailToken(Base):
    __tablename__ = "gmail_tokens"
    email: Mapped[str] = mapped_column(String(320), primary_key=True)
    refresh_token: Mapped[str] = mapped_column(Text)  # Fernet-encrypted
    updated_at: Mapped[datetime] = mapped_column(AwareDateTime, default=utcnow)


class GmailSender:
    def __init__(self, db: Database, secret_key: str, client_id: str, client_secret: str):
        GmailToken.__table__.create(db.engine, checkfirst=True)
        self.db = db
        self.client_id = client_id
        self.client_secret = client_secret
        key = base64.urlsafe_b64encode(hashlib.sha256(("gmail:" + secret_key).encode()).digest())
        self._fernet = Fernet(key)
        self._access: dict[str, tuple[str, float]] = {}
        self._lock = threading.Lock()

    def save(self, email: str, refresh_token: str) -> None:
        enc = self._fernet.encrypt(refresh_token.encode()).decode()
        with self.db.session() as s:
            row = s.get(GmailToken, email)
            if row is None:
                s.add(GmailToken(email=email, refresh_token=enc))
            else:
                row.refresh_token = enc
                row.updated_at = utcnow()
            s.commit()
        with self._lock:
            self._access.pop(email, None)

    def forget(self, email: str) -> None:
        with self.db.session() as s:
            row = s.get(GmailToken, email)
            if row is not None:
                s.delete(row)
                s.commit()
        with self._lock:
            self._access.pop(email, None)

    def connected(self, email: str | None) -> bool:
        if not email:
            return False
        with self.db.session() as s:
            return s.get(GmailToken, email.lower()) is not None

    def _access_token(self, email: str) -> str | None:
        with self._lock:
            cached = self._access.get(email)
            if cached and cached[1] > time.time() + 60:
                return cached[0]
        with self.db.session() as s:
            row = s.get(GmailToken, email)
            enc = row.refresh_token if row else None
        if enc is None:
            return None
        try:
            refresh = self._fernet.decrypt(enc.encode()).decode()
        except InvalidToken:
            log.error("Stored Gmail token for %s cannot be decrypted (SECRET_KEY changed?)", email)
            return None
        r = httpx.post(TOKEN_URL, data={
            "client_id": self.client_id, "client_secret": self.client_secret,
            "refresh_token": refresh, "grant_type": "refresh_token",
        }, timeout=30)
        if r.status_code == 400 and r.json().get("error") == "invalid_grant":
            log.warning("Gmail access for %s was revoked; the teacher must reconnect", email)
            self.forget(email)
            return None
        r.raise_for_status()
        data = r.json()
        with self._lock:
            self._access[email] = (data["access_token"], time.time() + int(data.get("expires_in", 3600)))
        return data["access_token"]

    def send(self, email: str, msg: EmailMessage) -> bool:
        """Send `msg` as `email`. Returns False if that account isn't connected."""
        token = self._access_token(email)
        if token is None:
            return False
        raw = base64.urlsafe_b64encode(msg.as_bytes()).decode()
        r = httpx.post(SEND_URL, json={"raw": raw}, headers={"Authorization": f"Bearer {token}"}, timeout=60)
        if r.status_code == 401:
            with self._lock:
                self._access.pop(email, None)
        r.raise_for_status()
        return True

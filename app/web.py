"""Shared request helpers: services, templates, auth guards and CSRF."""

import secrets
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from urllib.parse import quote

from fastapi import HTTPException, Request
from fastapi.templating import Jinja2Templates

from . import settings as settings_mod
from .config import Config
from .db import Database
from .events import Broker
from .mailer import Mailer
from .tokens import TokenSigner

TEMPLATES = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))


@dataclass
class Services:
    config: Config
    db: Database
    mailer: Mailer
    broker: Broker
    signer: TokenSigner

    def settings(self) -> settings_mod.Settings:
        return settings_mod.load(self.db)

    def url(self, path: str = "/") -> str:
        """Path under the app's base path, for links and redirects."""
        return self.config.base_path + path

    def absolute(self, path: str = "/") -> str:
        """Full external URL, for QR codes, OIDC callbacks and emails."""
        return self.config.public_url + path

    def is_admin(self, email: str | None) -> bool:
        return bool(email) and email.lower() in self.config.admin_emails

    def is_teacher(self, email: str | None, st: settings_mod.Settings | None = None) -> bool:
        if not email:
            return False
        email = email.lower()
        if self.is_admin(email):
            return True
        st = st or self.settings()
        return email in st.teacher_emails or settings_mod.domain_allowed(email, st.teacher_domains)


class Redirect(Exception):
    """Raised by guards to send the browser elsewhere (e.g. to the login page)."""

    def __init__(self, location: str):
        self.location = location


def svc(request: Request) -> Services:
    return request.app.state.svc


def current_user(request: Request) -> dict | None:
    return request.session.get("user")


def csrf_token(request: Request) -> str:
    token = request.session.get("csrf")
    if not token:
        token = secrets.token_urlsafe(24)
        request.session["csrf"] = token
    return token


async def check_csrf(request: Request) -> None:
    expected = request.session.get("csrf")
    sent = request.headers.get("x-csrf-token")
    if sent is None:
        form = await request.form()
        sent = form.get("csrf")
    if not expected or not sent or not secrets.compare_digest(str(sent), expected):
        raise HTTPException(403, "Invalid or missing CSRF token. Reload the page and try again.")


def login_url(request: Request, target: str | None = None) -> str:
    if target is None:
        target = request.url.path
        if request.url.query:
            target += "?" + request.url.query
    return svc(request).url("/login?next=" + quote(target))


def require_user(request: Request) -> dict:
    user = current_user(request)
    if not user:
        raise Redirect(login_url(request))
    return user


def require_teacher(request: Request) -> dict:
    user = require_user(request)
    if not svc(request).is_teacher(user["email"]):
        raise HTTPException(403, "This page is for teachers. Ask an administrator to add your account.")
    return user


def require_admin(request: Request) -> dict:
    user = require_user(request)
    if not svc(request).is_admin(user["email"]):
        raise HTTPException(403, "Only administrators can change settings.")
    return user


def safe_next(request: Request, value: str | None) -> str:
    s = svc(request)
    base = s.config.base_path + "/"
    if value and value.startswith(base) and not value.startswith("//") and "\\" not in value:
        return value
    return s.url("/")


def render(request: Request, name: str, status_code: int = 200, **context):
    s = svc(request)
    st = s.settings()
    user = current_user(request)
    context.update(
        request=request,
        st=st,
        user=user,
        is_teacher=s.is_teacher(user["email"], st) if user else False,
        is_admin=s.is_admin(user["email"]) if user else False,
        csrf=csrf_token(request),
        url=s.url,
        local=lambda dt, fmt="%H:%M:%S": format_local(dt, st, fmt),
    )
    return TEMPLATES.TemplateResponse(request, name, context, status_code=status_code)


def format_local(dt: datetime | None, st: settings_mod.Settings, fmt: str = "%H:%M:%S") -> str:
    if dt is None:
        return ""
    return dt.astimezone(st.tz).strftime(fmt)

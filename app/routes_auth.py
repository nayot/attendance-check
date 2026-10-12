"""Sign-in: OIDC providers (Google, Microsoft, any OIDC) and one-time email codes."""

import hashlib
import hmac
import logging
import re
import secrets
import time
from datetime import timedelta
from urllib.parse import quote

from authlib.integrations.starlette_client import OAuth, OAuthError
from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse

from .db import LoginCode, Phase, User, utcnow
from .gmail import SCOPE as GMAIL_SCOPE
from .web import check_csrf, current_user, render, require_teacher, safe_next, svc

log = logging.getLogger("attendance.auth")
router = APIRouter()

# A QR scan stays valid this long while the student signs in.
PENDING_TTL = 180
CODE_TTL = timedelta(minutes=10)
CODE_RESEND = timedelta(seconds=60)
CODE_ATTEMPTS = 5
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def build_oauth(config) -> OAuth:
    oauth = OAuth()
    for p in config.providers:
        oauth.register(
            name=p.name,
            client_id=p.client_id,
            client_secret=p.client_secret,
            server_metadata_url=p.metadata_url,
            client_kwargs={"scope": "openid email profile"},
        )
    return oauth


def pending_teacher(request: Request) -> str | None:
    """Teacher of the class a signed-out student just scanned, if any.

    Their connected Gmail can then send the student's sign-in code.
    """
    pending = request.session.get("pending")
    if not pending:
        return None
    with svc(request).db.session() as db:
        phase = db.get(Phase, pending.get("phase"))
        return phase.session.teacher_email if phase else None


def may_sign_in(request: Request, email: str) -> bool:
    s = svc(request)
    st = s.settings()
    return s.is_teacher(email, st) or st.student_allowed(email)


def finish_login(request: Request, email: str, name: str) -> RedirectResponse:
    s = svc(request)
    email = email.strip().lower()
    with s.db.session() as db:
        user = db.get(User, email)
        if user is None:
            user = User(email=email, name=name.strip())
            db.add(user)
        elif name.strip() and not user.name:
            user.name = name.strip()
        user.last_login_at = utcnow()
        db.commit()
        name = user.name
    request.session.pop("csrf", None)
    request.session["user"] = {"email": email, "name": name}
    target = safe_next(request, request.session.pop("next", None))
    pending = request.session.get("pending")
    if pending and time.time() - pending.get("at", 0) <= PENDING_TTL:
        # A QR scan is waiting for this login; finish it whatever the next page was.
        target = s.url("/checkin")
    else:
        request.session.pop("pending", None)
    if not name:
        return RedirectResponse(s.url("/profile?next=" + quote(target)), status_code=303)
    return RedirectResponse(target, status_code=303)


@router.get("/login")
def login_page(request: Request, next: str | None = None):
    s = svc(request)
    request.session["next"] = safe_next(request, next)
    if current_user(request):
        return RedirectResponse(request.session.pop("next"), status_code=303)
    return render(
        request,
        "login.html",
        providers=s.config.providers,
        otp_enabled=s.config.otp_enabled,
        pending=bool(request.session.get("pending")),
    )


@router.get("/login/{provider}")
async def login_provider(request: Request, provider: str):
    s = svc(request)
    client = request.app.state.oauth.create_client(provider)
    if client is None:
        return render(request, "message.html", 404, title="Unknown sign-in method")
    redirect_uri = s.absolute(f"/auth/{provider}")
    return await client.authorize_redirect(request, redirect_uri, prompt="select_account")


@router.get("/auth/{provider}")
async def auth_callback(request: Request, provider: str):
    client = request.app.state.oauth.create_client(provider)
    if client is None:
        return render(request, "message.html", 404, title="Unknown sign-in method")
    connecting = request.session.pop("gmail_connect", False)
    try:
        token = await client.authorize_access_token(request)
    except OAuthError as exc:
        log.warning("OIDC error from %s: %s", provider, exc)
        return render(request, "message.html", 400, title="Sign-in failed", text=str(exc.description or exc.error))
    info = token.get("userinfo") or {}
    email = (info.get("email") or info.get("preferred_username") or "").lower()
    if connecting:
        return finish_gmail_connect(request, email, token)
    if not EMAIL_RE.match(email) or info.get("email_verified") is False:
        return render(request, "message.html", 400, title="Sign-in failed",
                      text="Your account did not provide a verified email address.")
    if not may_sign_in(request, email):
        return render(request, "message.html", 403, title="Account not allowed",
                      text=f"{email} is not in an allowed email domain. Sign in with your institution account.")
    return finish_login(request, email, info.get("name") or "")


@router.get("/gmail/connect")
async def gmail_connect(request: Request, user: dict = Depends(require_teacher)):
    """Ask the teacher's Google account for permission to send mail as them."""
    s = svc(request)
    if s.mailer.gmail is None:
        return render(request, "message.html", 404, title="Gmail sending is not enabled")
    request.session["gmail_connect"] = True
    client = request.app.state.oauth.create_client("google")
    return await client.authorize_redirect(
        request, s.absolute("/auth/google"),
        scope="openid email " + GMAIL_SCOPE,
        access_type="offline", prompt="consent", include_granted_scopes="true",
        login_hint=user["email"],
    )


def finish_gmail_connect(request: Request, email: str, token: dict):
    s = svc(request)
    user = current_user(request)
    if not user or email != user["email"]:
        return render(request, "message.html", 400, title="Wrong Google account",
                      text=f"Choose {user['email'] if user else 'your own account'} when Google asks.")
    if GMAIL_SCOPE not in token.get("scope", "").split() or not token.get("refresh_token"):
        return render(request, "message.html", 400, title="Gmail not connected",
                      text="Google did not grant permission to send email. Try again and tick the Gmail box.")
    s.mailer.gmail.save(email, token["refresh_token"])
    return RedirectResponse(s.url("/?gmail=connected"), status_code=303)


@router.post("/gmail/disconnect", dependencies=[Depends(check_csrf)])
def gmail_disconnect(request: Request, user: dict = Depends(require_teacher)):
    s = svc(request)
    if s.mailer.gmail is not None:
        s.mailer.gmail.forget(user["email"])
    return RedirectResponse(s.url("/"), status_code=303)


def _hash_code(request: Request, email: str, code: str) -> str:
    key = svc(request).config.secret_key.encode()
    return hmac.new(key, f"otp:{email}:{code}".encode(), hashlib.sha256).hexdigest()


@router.post("/login/code", dependencies=[Depends(check_csrf)])
def send_code(request: Request, email: str = Form(...)):
    s = svc(request)
    if not s.config.otp_enabled:
        return render(request, "message.html", 404, title="Email codes are disabled")
    email = email.strip().lower()
    if not EMAIL_RE.match(email):
        return render(request, "login.html", 400, providers=s.config.providers, otp_enabled=True,
                      error="Enter a valid email address.", email=email)
    if not may_sign_in(request, email):
        st = s.settings()
        return render(request, "login.html", 403, providers=s.config.providers, otp_enabled=True,
                      error="Use your institution email (" + ", ".join(st.student_domains) + ").", email=email)
    now = utcnow()
    with s.db.session() as db:
        row = db.get(LoginCode, email)
        if row is not None and now - row.sent_at < CODE_RESEND:
            # Don't resend straight away; reuse the code already on its way.
            request.session["otp_email"] = email
            return render(request, "code.html", email=email, info="A code was sent a moment ago. Check your inbox.")
        code = f"{secrets.randbelow(1_000_000):06d}"
        if row is None:
            row = LoginCode(email=email)
            db.add(row)
        row.code_hash = _hash_code(request, email, code)
        row.expires_at = now + CODE_TTL
        row.sent_at = now
        row.attempts = 0
        db.commit()
    st = s.settings()
    sender = st.institution_name or st.app_title
    s.mailer.send(
        email,
        f"{code} is your {st.app_title} sign-in code",
        f"Your sign-in code is {code}\n\nIt expires in 10 minutes. If you did not ask for it, ignore this email.\n\n{sender}",
        sender_name=sender,
        from_email=pending_teacher(request),
    )
    request.session["otp_email"] = email
    return render(request, "code.html", email=email)


@router.post("/login/verify", dependencies=[Depends(check_csrf)])
def verify_code(request: Request, code: str = Form(...)):
    s = svc(request)
    email = request.session.get("otp_email")
    if not email:
        return RedirectResponse(s.url("/login"), status_code=303)
    code = re.sub(r"\D", "", code)
    now = utcnow()
    with s.db.session() as db:
        row = db.get(LoginCode, email)
        if row is None or row.expires_at < now or row.attempts >= CODE_ATTEMPTS:
            if row is not None:
                db.delete(row)
                db.commit()
            return render(request, "login.html", 400, providers=s.config.providers, otp_enabled=True,
                          email=email, error="That code has expired. Request a new one.")
        if not hmac.compare_digest(row.code_hash, _hash_code(request, email, code)):
            row.attempts += 1
            db.commit()
            return render(request, "code.html", 400, email=email, error="Wrong code. Try again.")
        db.delete(row)
        db.commit()
    request.session.pop("otp_email", None)
    return finish_login(request, email, "")


@router.get("/profile")
def profile_page(request: Request, next: str | None = None):
    user = current_user(request)
    if not user:
        return RedirectResponse(svc(request).url("/login"), status_code=303)
    return render(request, "profile.html", next=safe_next(request, next))


@router.post("/profile", dependencies=[Depends(check_csrf)])
def profile_save(request: Request, name: str = Form(...), next: str = Form("")):
    s = svc(request)
    user = current_user(request)
    if not user:
        return RedirectResponse(s.url("/login"), status_code=303)
    name = " ".join(name.split())[:200]
    if not name:
        return render(request, "profile.html", 400, next=safe_next(request, next), error="Please enter your name.")
    with s.db.session() as db:
        row = db.get(User, user["email"])
        row.name = name
        db.commit()
    request.session["user"] = {"email": user["email"], "name": name}
    return RedirectResponse(safe_next(request, next), status_code=303)


@router.get("/logout")
def logout(request: Request):
    request.session.clear()
    return RedirectResponse(svc(request).url("/"), status_code=303)

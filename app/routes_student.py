"""Student check-in via the rotating QR code."""

import time

from fastapi import APIRouter, Request
from fastapi.responses import RedirectResponse

from . import attendance as att
from .db import Phase
from .routes_auth import PENDING_TTL
from .web import current_user, language, login_url, render, svc

router = APIRouter()


def _result(request: Request, r: att.CheckInResult, status_code: int = 200):
    return render(request, "checkin_result.html", status_code, r=r,
                  title=att.session_title(r.session, language(request)) if r.session else "")


@router.get("/c/{phase_id}/{token}")
def scan(request: Request, phase_id: int, token: str):
    s = svc(request)
    st = s.settings()
    if not s.signer.verify(phase_id, token, st.qr_interval):
        return render(request, "message.html", 410, title="QR code expired",
                      text="This code has changed. Scan the code on the screen again.")
    user = current_user(request)
    if not user:
        request.session["pending"] = {"phase": phase_id, "at": time.time()}
        return RedirectResponse(login_url(request, s.url("/checkin")), status_code=303)
    r = att.check_in(s, st, phase_id, user["email"], user["name"])
    return _result(request, r, 200 if r.ok else 409)


@router.get("/checkin")
def complete_pending(request: Request):
    """Finish a check-in that started before the student signed in."""
    s = svc(request)
    user = current_user(request)
    pending = request.session.pop("pending", None)
    if not user:
        return RedirectResponse(s.url("/login"), status_code=303)
    if not pending or time.time() - pending.get("at", 0) > PENDING_TTL:
        return render(request, "message.html", 410, title="Please scan again",
                      text="Signing in took too long. Scan the code on the screen again.")
    with s.db.session() as db:
        if db.get(Phase, pending["phase"]) is None:
            return render(request, "message.html", 404, title="QR code not valid")
    r = att.check_in(s, s.settings(), pending["phase"], user["email"], user["name"])
    return _result(request, r, 200 if r.ok else 409)

"""Teacher pages: dashboard, live display, phase controls and reports."""

import asyncio
import io
import json
import time

import qrcode
import qrcode.image.svg
from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import JSONResponse, RedirectResponse, Response, StreamingResponse
from sqlalchemy import select

from . import attendance as att
from .db import ClassSession
from .routes_auth import EMAIL_RE
from .web import check_csrf, render, require_teacher, svc

router = APIRouter()


def own_session(request: Request, session_id: int, user: dict) -> ClassSession:
    s = svc(request)
    sess = att.load_session(s, session_id)
    if sess is None or (sess.teacher_email != user["email"] and not s.is_admin(user["email"])):
        raise HTTPException(404, "Session not found.")
    return sess


@router.get("/")
def home(request: Request):
    s = svc(request)
    user = request.session.get("user")
    if not user:
        return render(request, "welcome.html")
    if not s.is_teacher(user["email"]):
        return render(request, "student_home.html")
    with s.db.session() as db:
        sessions = db.scalars(
            select(ClassSession)
            .where(ClassSession.teacher_email == user["email"])
            .order_by(ClassSession.created_at.desc())
            .limit(50)
        ).all()
        for sess in sessions:
            sess.counts = [len(p.checkins) for p in sess.phases]
    names = sorted({x.class_name for x in sessions if x.class_name})
    gmail = s.mailer.gmail
    return render(request, "dashboard.html", sessions=sessions, class_names=names,
                  gmail_enabled=gmail is not None, smtp_configured=s.config.smtp_configured, gmail_connected=bool(gmail and gmail.connected(user["email"])))


@router.post("/sessions", dependencies=[Depends(check_csrf)])
def new_session(
    request: Request,
    class_name: str = Form(""),
    mid_checks: int = Form(0),
    checkout: bool = Form(False),
    email_report: bool = Form(False),
    email_students: bool = Form(False),
    user: dict = Depends(require_teacher),
):
    s = svc(request)
    sid = att.create_session(
        s, user["email"], class_name, max(0, min(5, mid_checks)), checkout, email_report, email_students
    )
    return RedirectResponse(s.url(f"/sessions/{sid}"), status_code=303)


@router.get("/sessions/{session_id}")
def display(request: Request, session_id: int, user: dict = Depends(require_teacher)):
    sess = own_session(request, session_id, user)
    if sess.is_closed:
        return RedirectResponse(svc(request).url(f"/sessions/{session_id}/report"), status_code=303)
    return render(request, "display.html", sess=sess, title=att.session_title(sess))


@router.get("/sessions/{session_id}/state")
def state(request: Request, session_id: int, user: dict = Depends(require_teacher)):
    s = svc(request)
    sess = own_session(request, session_id, user)
    return JSONResponse(att.session_state(s, sess, s.settings()))


def qr_payload(request: Request, phase_id: int, interval: int) -> dict:
    s = svc(request)
    token, window = s.signer.current(phase_id, interval)
    url = s.absolute(f"/c/{phase_id}/{token}")
    img = qrcode.make(url, image_factory=qrcode.image.svg.SvgPathImage, box_size=10, border=2)
    buf = io.BytesIO()
    img.save(buf)
    return {"phase_id": phase_id, "svg": buf.getvalue().decode(), "url": url, "interval": interval,
            "expires_in": (window + 1) * interval - time.time()}


@router.get("/sessions/{session_id}/events")
async def events(request: Request, session_id: int, user: dict = Depends(require_teacher)):
    s = svc(request)
    own_session(request, session_id, user)
    queue = s.broker.subscribe(session_id)

    def current_phase():
        sess = att.load_session(s, session_id)
        phase = sess.active_phase if sess else None
        return phase.id if phase and phase.state == "open" else None

    async def stream():
        last = None
        phase_id = await asyncio.to_thread(current_phase)
        interval = s.settings().qr_interval
        try:
            yield "retry: 2000\n\n"
            while True:
                if await request.is_disconnected():
                    break
                key = (phase_id, s.signer.window(interval)) if phase_id else None
                if key != last:
                    last = key
                    data = qr_payload(request, phase_id, interval) if phase_id else {"phase_id": None}
                    yield f"event: qr\ndata: {json.dumps(data)}\n\n"
                try:
                    event, data = await asyncio.wait_for(queue.get(), timeout=1.0)
                except asyncio.TimeoutError:
                    yield ": keepalive\n\n"
                    continue
                if event == "state":
                    phase_id = await asyncio.to_thread(current_phase)
                    interval = s.settings().qr_interval
                yield f"event: {event}\ndata: {json.dumps(data)}\n\n"
        finally:
            s.broker.unsubscribe(session_id, queue)

    headers = {"Cache-Control": "no-cache", "X-Accel-Buffering": "no"}
    return StreamingResponse(stream(), media_type="text/event-stream", headers=headers)


@router.post("/sessions/{session_id}/phases/{phase_id}/{action}", dependencies=[Depends(check_csrf)])
def phase_action(request: Request, session_id: int, phase_id: int, action: str,
                 user: dict = Depends(require_teacher)):
    if action not in ("open", "pause", "resume", "close"):
        raise HTTPException(404)
    own_session(request, session_id, user)
    try:
        att.set_phase_state(svc(request), session_id, phase_id, action)
    except ValueError as exc:
        raise HTTPException(400, str(exc))
    return {"ok": True}


@router.post("/sessions/{session_id}/phases", dependencies=[Depends(check_csrf)])
def phase_add(request: Request, session_id: int, kind: str = Form(...), open_now: bool = Form(False),
              user: dict = Depends(require_teacher)):
    if kind not in ("mid", "checkout"):
        raise HTTPException(400, "Unknown phase type.")
    sess = own_session(request, session_id, user)
    if sess.is_closed:
        raise HTTPException(400, "This session is closed.")
    try:
        att.add_phase(svc(request), session_id, kind, open_now)
    except ValueError as exc:
        raise HTTPException(400, str(exc))
    return {"ok": True}


@router.post("/sessions/{session_id}/close", dependencies=[Depends(check_csrf)])
def session_close(request: Request, session_id: int, user: dict = Depends(require_teacher)):
    own_session(request, session_id, user)
    att.close_session(svc(request), session_id)
    return RedirectResponse(svc(request).url(f"/sessions/{session_id}/report"), status_code=303)


@router.get("/sessions/{session_id}/report")
def report(request: Request, session_id: int, user: dict = Depends(require_teacher)):
    sess = own_session(request, session_id, user)
    phases, rows = att.roster(sess)
    return render(request, "report.html", sess=sess, title=att.session_title(sess), phases=phases,
                  rows=rows, all_phases=sess.phases)


@router.get("/sessions/{session_id}/report.csv")
def report_csv(request: Request, session_id: int, user: dict = Depends(require_teacher)):
    s = svc(request)
    st = s.settings()
    sess = own_session(request, session_id, user)
    return Response(
        att.report_csv(sess, st), media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{att.report_filename(sess, st)}"'},
    )


@router.post("/sessions/{session_id}/report/email", dependencies=[Depends(check_csrf)])
def report_email(request: Request, session_id: int, user: dict = Depends(require_teacher)):
    own_session(request, session_id, user)
    att.send_report_email(svc(request), session_id, user["email"])
    return RedirectResponse(svc(request).url(f"/sessions/{session_id}/report?sent=1"), status_code=303)


@router.post("/sessions/{session_id}/checkins", dependencies=[Depends(check_csrf)])
def manual_add(request: Request, session_id: int, phase_id: int = Form(...), email: str = Form(...),
               name: str = Form(""), user: dict = Depends(require_teacher)):
    s = svc(request)
    sess = own_session(request, session_id, user)
    if phase_id not in {p.id for p in sess.phases}:
        raise HTTPException(400, "Unknown phase.")
    if not EMAIL_RE.match(email.strip()):
        raise HTTPException(400, "Enter a valid email address.")
    att.check_in(s, s.settings(), phase_id, email, name, manual=True)
    return RedirectResponse(s.url(f"/sessions/{session_id}/report"), status_code=303)


@router.post("/sessions/{session_id}/checkins/{checkin_id}/delete", dependencies=[Depends(check_csrf)])
def manual_remove(request: Request, session_id: int, checkin_id: int, user: dict = Depends(require_teacher)):
    own_session(request, session_id, user)
    att.remove_checkin(svc(request), session_id, checkin_id)
    if request.headers.get("x-csrf-token"):
        return {"ok": True}
    return RedirectResponse(svc(request).url(f"/sessions/{session_id}/report"), status_code=303)

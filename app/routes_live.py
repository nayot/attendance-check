"""Live votes and short answers: teacher controls and the student answer page.

Nothing is recorded; see live.py.
"""

import io

import qrcode
import qrcode.image.svg
from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import JSONResponse, RedirectResponse

from . import attendance as att
from . import i18n
from .routes_teacher import own_session
from .web import check_csrf, current_user, language, login_url, render, require_teacher, svc

router = APIRouter()


def join_path(request: Request, session_id: int) -> str:
    return f"/live/{session_id}/{svc(request).signer.live_token(session_id)}"


def _publish(request: Request, session_id: int, results: dict | None) -> dict:
    svc(request).broker.publish(session_id, "live", {"activity": results})
    return {"activity": results}


def _error(request: Request, exc: ValueError) -> HTTPException:
    return HTTPException(400, i18n.gettext(language(request), str(exc)))


# --- Teacher --------------------------------------------------------------

@router.get("/sessions/{session_id}/live")
def live_state(request: Request, session_id: int, user: dict = Depends(require_teacher)):
    s = svc(request)
    own_session(request, session_id, user)
    url = s.absolute(join_path(request, session_id))
    img = qrcode.make(url, image_factory=qrcode.image.svg.SvgPathImage, box_size=10, border=1)
    buf = io.BytesIO()
    img.save(buf)
    return JSONResponse({"activity": s.live.results(session_id), "join_url": url, "join_qr": buf.getvalue().decode()})


@router.post("/sessions/{session_id}/live", dependencies=[Depends(check_csrf)])
async def live_start(request: Request, session_id: int, user: dict = Depends(require_teacher)):
    form = await request.form()
    sess = own_session(request, session_id, user)
    if sess.is_closed:
        raise HTTPException(400, "This session is closed.")
    try:
        results = svc(request).live.start(
            session_id, str(form.get("kind", "")), str(form.get("question", "")),
            [str(o) for o in form.getlist("option")], str(form.get("chart", "bar")),
        )
    except ValueError as exc:
        raise _error(request, exc)
    return _publish(request, session_id, results)


@router.post("/sessions/{session_id}/live/{action}", dependencies=[Depends(check_csrf)])
def live_action(request: Request, session_id: int, action: str, user: dict = Depends(require_teacher)):
    own_session(request, session_id, user)
    store = svc(request).live
    if action == "stop":
        store.stop(session_id)
        return _publish(request, session_id, None)
    changes = {"open": {"open": True}, "close": {"open": False},
               "bar": {"chart": "bar"}, "pie": {"chart": "pie"}}.get(action)
    if changes is None:
        raise HTTPException(404)
    return _publish(request, session_id, store.update(session_id, **changes))


# --- Students -------------------------------------------------------------

def _student(request: Request, session_id: int, token: str) -> dict | None:
    if not svc(request).signer.verify_live(session_id, token):
        raise HTTPException(404, "This link is not valid.")
    return current_user(request)


def _allowed(request: Request, email: str) -> bool:
    s = svc(request)
    st = s.settings()
    return st.student_allowed(email) or s.is_teacher(email, st)


@router.get("/live/{session_id}/{token}")
def live_page(request: Request, session_id: int, token: str):
    s = svc(request)
    user = _student(request, session_id, token)
    if not user:
        return RedirectResponse(login_url(request), status_code=303)
    if not _allowed(request, user["email"]):
        raise HTTPException(403, i18n.gettext(language(request), "{email} is not in an allowed email domain.",
                                              email=user["email"]))
    sess = att.load_session(s, session_id)
    if sess is None:
        raise HTTPException(404, "This link is not valid.")
    return render(request, "live.html", title=att.session_title(sess, language(request)),
                  ended=sess.is_closed, live_strings=i18n.LIVE_STRINGS,
                  join=s.url(join_path(request, session_id)))


@router.get("/live/{session_id}/{token}/poll")
def live_poll(request: Request, session_id: int, token: str):
    """Polled by every student's phone, so it reads memory only."""
    user = _student(request, session_id, token)
    if not user:
        raise HTTPException(401, "Please sign in again.")
    return JSONResponse(svc(request).live.for_student(session_id, user["email"]),
                        headers={"Cache-Control": "no-store"})


@router.post("/live/{session_id}/{token}/vote", dependencies=[Depends(check_csrf)])
def live_vote(request: Request, session_id: int, token: str, activity: int = Form(...), option: int = Form(...)):
    user = _student(request, session_id, token)
    if not user or not _allowed(request, user["email"]):
        raise HTTPException(403, "Please sign in again.")
    try:
        results = svc(request).live.vote(session_id, activity, user["email"], option)
    except ValueError as exc:
        raise _error(request, exc)
    _publish(request, session_id, results)
    return svc(request).live.for_student(session_id, user["email"])


@router.post("/live/{session_id}/{token}/answer", dependencies=[Depends(check_csrf)])
def live_answer(request: Request, session_id: int, token: str, activity: int = Form(...), text: str = Form(...)):
    user = _student(request, session_id, token)
    if not user or not _allowed(request, user["email"]):
        raise HTTPException(403, "Please sign in again.")
    try:
        results = svc(request).live.answer(session_id, activity, user["email"], text)
    except ValueError as exc:
        raise _error(request, exc)
    _publish(request, session_id, results)
    return svc(request).live.for_student(session_id, user["email"])


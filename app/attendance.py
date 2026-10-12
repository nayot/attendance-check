"""Attendance logic: sessions, phases, check-ins, reports and their emails."""

import csv
import io
import mimetypes
from dataclasses import dataclass, field
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import selectinload

from . import COPYRIGHT, i18n
from .db import CheckIn, ClassSession, Phase, User, utcnow
from .settings import Settings
from .web import Services, format_local

# Plain-text emails must not be HTML-escaped, so they get their own environment.
EMAILS = Environment(
    loader=FileSystemLoader(Path(__file__).parent / "templates"),
    autoescape=select_autoescape(["html"]),
)

PHASE_LABELS = {"checkin": "Check-in", "mid": "Mid-class check", "checkout": "Check-out"}


def load_session(svc: Services, session_id: int) -> ClassSession | None:
    with svc.db.session() as db:
        return db.scalar(
            select(ClassSession)
            .where(ClassSession.id == session_id)
            .options(selectinload(ClassSession.phases).selectinload(Phase.checkins))
        )


def create_session(
    svc: Services, teacher: str, class_name: str, mid_checks: int, checkout: bool,
    email_report: bool, email_students: bool,
) -> int:
    now = utcnow()
    with svc.db.session() as db:
        sess = ClassSession(
            teacher_email=teacher, class_name=class_name.strip()[:200],
            email_report=email_report, email_students=email_students, created_at=now,
        )
        sess.phases.append(Phase(kind="checkin", label="Check-in", position=0, state="open", opened_at=now))
        for i in range(mid_checks):
            sess.phases.append(Phase(kind="mid", label=f"Mid-class check {i + 1}", position=i + 1))
        if checkout:
            sess.phases.append(Phase(kind="checkout", label="Check-out", position=mid_checks + 1))
        db.add(sess)
        db.commit()
        return sess.id


def add_phase(svc: Services, session_id: int, kind: str, open_now: bool) -> None:
    with svc.db.session() as db:
        sess = db.get(ClassSession, session_id)
        phases = list(sess.phases)
        if kind == "checkout" and any(p.kind == "checkout" for p in phases):
            raise ValueError("This session already has a check-out.")
        if kind == "mid":
            n = sum(1 for p in phases if p.kind == "mid") + 1
            label = f"Mid-class check {n}"
            # Keep check-out last.
            position = max([p.position for p in phases if p.kind != "checkout"], default=0) + 1
            for p in phases:
                if p.kind == "checkout":
                    p.position = position + 1
        else:
            label = PHASE_LABELS[kind]
            position = max(p.position for p in phases) + 1
        phase = Phase(kind=kind, label=label, position=position)
        sess.phases.append(phase)
        db.flush()
        if open_now:
            _open(sess, phase)
        db.commit()
    svc.broker.publish(session_id, "state", {})


def _open(sess: ClassSession, phase: Phase) -> None:
    now = utcnow()
    for p in sess.phases:
        if p.id != phase.id and p.state in ("open", "paused"):
            p.state = "closed"
            p.closed_at = now
    phase.state = "open"
    phase.opened_at = phase.opened_at or now
    phase.closed_at = None


def set_phase_state(svc: Services, session_id: int, phase_id: int, action: str) -> None:
    with svc.db.session() as db:
        sess = db.get(ClassSession, session_id)
        phase = db.get(Phase, phase_id)
        if sess is None or phase is None or phase.session_id != session_id or sess.is_closed:
            raise ValueError("Phase not found.")
        if action == "open":
            _open(sess, phase)
        elif action == "pause" and phase.state == "open":
            phase.state = "paused"
        elif action == "resume" and phase.state == "paused":
            phase.state = "open"
        elif action == "close" and phase.state in ("open", "paused"):
            phase.state = "closed"
            phase.closed_at = utcnow()
        db.commit()
    svc.broker.publish(session_id, "state", {})


def close_session(svc: Services, session_id: int) -> None:
    now = utcnow()
    with svc.db.session() as db:
        sess = db.get(ClassSession, session_id)
        if sess.is_closed:
            return
        for p in sess.phases:
            if p.state in ("open", "paused"):
                p.closed_at = now
            p.state = "closed"
        sess.closed_at = now
        db.commit()
        send_report = sess.email_report
        teacher = sess.teacher_email
    svc.broker.publish(session_id, "state", {})
    if send_report:
        send_report_email(svc, session_id, teacher)


def manage_session(svc: Services, session_id: int, action: str) -> bool:
    """Archive, unarchive or delete. Returns whether the session was archived before."""
    with svc.db.session() as db:
        sess = db.get(ClassSession, session_id)
        was_archived = sess.archived_at is not None
        if action == "delete":
            db.delete(sess)
        elif action == "archive":
            if not sess.is_closed:
                # Archiving a running session ends it, without the report email.
                now = utcnow()
                for p in sess.phases:
                    if p.state in ("open", "paused"):
                        p.closed_at = now
                    p.state = "closed"
                sess.closed_at = now
            sess.archived_at = utcnow()
        elif action == "unarchive":
            sess.archived_at = None
        db.commit()
    svc.broker.publish(session_id, "state", {})
    return was_archived


@dataclass
class CheckInResult:
    ok: bool
    message: str
    checkin: CheckIn | None = None
    phase: Phase | None = None
    session: ClassSession | None = None
    duplicate: bool = False
    params: dict = field(default_factory=dict)  # for formatting the translated message


def check_in(svc: Services, st: Settings, phase_id: int, email: str, name: str,
             allow_paused: bool = False, manual: bool = False) -> CheckInResult:
    """Record a check-in. `manual` is a teacher adding someone by hand."""
    email = email.strip().lower()
    with svc.db.session() as db:
        phase = db.get(Phase, phase_id)
        if phase is None:
            return CheckInResult(False, "This QR code is not valid.")
        sess = phase.session
        allowed = ("open", "paused") if allow_paused else ("open",)
        if not manual and (sess.is_closed or phase.state not in allowed):
            msg = "Check-in is paused. Wait for your teacher to resume it." if phase.state == "paused" \
                else "This check-in is closed."
            return CheckInResult(False, msg, phase=phase, session=sess)
        if not manual and not st.student_allowed(email):
            return CheckInResult(False, "{email} is not in an allowed email domain.", phase=phase, session=sess,
                                 params={"email": email})
        existing = db.scalar(select(CheckIn).where(CheckIn.phase_id == phase_id, CheckIn.email == email))
        if existing is not None:
            return CheckInResult(True, "You have already checked in.", existing, phase, sess, duplicate=True)
        if not name.strip():
            known = db.get(User, email)
            name = known.name if known else ""
        row = CheckIn(phase_id=phase_id, email=email, name=name.strip()[:200])
        db.add(row)
        try:
            db.commit()
        except IntegrityError:  # two scans racing each other
            db.rollback()
            existing = db.scalar(select(CheckIn).where(CheckIn.phase_id == phase_id, CheckIn.email == email))
            return CheckInResult(True, "You have already checked in.", existing, phase, sess, duplicate=True)
        db.refresh(row)
        session_id, email_students = sess.id, sess.email_students
        result = CheckInResult(True, "Checked in.", row, phase, sess)
    svc.broker.publish(session_id, "checkin", checkin_json(row, st))
    if email_students and not manual:
        send_student_email(svc, st, result)
    return result


def remove_checkin(svc: Services, session_id: int, checkin_id: int) -> None:
    with svc.db.session() as db:
        row = db.get(CheckIn, checkin_id)
        if row is not None and row.phase.session_id == session_id:
            db.delete(row)
            db.commit()
    svc.broker.publish(session_id, "state", {})


def checkin_json(c: CheckIn, st: Settings) -> dict:
    return {"id": c.id, "phase_id": c.phase_id, "email": c.email, "name": c.name,
            "time": format_local(c.created_at, st)}


def session_title(sess: ClassSession, lang: str = "en") -> str:
    return sess.class_name or i18n.gettext(lang, "Class session")


def session_state(svc: Services, sess: ClassSession, st: Settings, lang: str = "en") -> dict:
    active = sess.active_phase
    return {
        "id": sess.id,
        "title": session_title(sess, lang),
        "closed": sess.is_closed,
        "active_phase": active.id if active else None,
        "phases": [
            {
                "id": p.id, "kind": p.kind, "label": i18n.phase_label(p.label, lang), "state": p.state,
                "count": len(p.checkins),
                "checkins": [checkin_json(c, st) for c in reversed(p.checkins)],
            }
            for p in sess.phases
        ],
    }


def roster(sess: ClassSession) -> tuple[list[Phase], list[dict]]:
    """One row per student with their check-in time in each phase."""
    phases = [p for p in sess.phases if p.state != "pending" or p.checkins]
    people: dict[str, dict] = {}
    for p in phases:
        for c in p.checkins:
            row = people.setdefault(c.email, {"email": c.email, "name": c.name, "times": {}})
            row["name"] = row["name"] or c.name
            row["times"][p.id] = c.created_at
    rows = sorted(people.values(), key=lambda r: min(r["times"].values()))
    return phases, rows


def report_csv(sess: ClassSession, st: Settings) -> str:
    phases, rows = roster(sess)
    out = io.StringIO()
    w = csv.writer(out)
    _ = i18n.translator(st.default_language)
    w.writerow(["No.", _("Name"), _("Email")] + [i18n.phase_label(p.label, st.default_language) for p in phases])
    date_fmt = "%Y-%m-%d %H:%M:%S"
    for i, r in enumerate(rows, 1):
        w.writerow([i, r["name"], r["email"]] + [format_local(r["times"].get(p.id), st, date_fmt) for p in phases])
    return "﻿" + out.getvalue()  # BOM so Excel opens UTF-8 (e.g. Thai names) correctly


def report_filename(sess: ClassSession, st: Settings) -> str:
    stamp = format_local(sess.created_at, st, "%Y%m%d-%H%M")
    name = "".join(ch if ch.isalnum() or ch in "-_" else "-" for ch in sess.class_name).strip("-")[:60]
    return f"attendance-{name + '-' if name else ''}{stamp}.csv"


def _logo(svc: Services, st: Settings) -> tuple[str, bytes] | None:
    for name in st.logos:
        mime = mimetypes.guess_type(name)[0] or ""
        path = svc.config.upload_dir / name
        if mime in ("image/png", "image/jpeg", "image/gif") and path.is_file():
            return mime, path.read_bytes()
    return None


def _email(svc: Services, st: Settings, to: str, subject: str, template: str, attachments=(),
           teacher: str | None = None, **ctx) -> None:
    logo = _logo(svc, st)
    lang = st.default_language
    ctx.update(st=st, has_logo=logo is not None, app_url=svc.absolute("/"), lang=lang, copyright=COPYRIGHT,
               _=i18n.translator(lang), phase_label=lambda label: i18n.phase_label(label, lang))
    html = EMAILS.get_template(f"emails/{template}.html").render(**ctx)
    text = EMAILS.get_template(f"emails/{template}.txt").render(**ctx)
    sender_name = st.institution_name or st.app_title
    if teacher and svc.mailer.gmail and svc.mailer.gmail.connected(teacher):
        sender_name = teacher_name(svc, teacher) or sender_name
    svc.mailer.send(to, subject, text, html, sender_name=sender_name, attachments=attachments,
                    inline_logo=logo, from_email=teacher)


def teacher_name(svc: Services, email: str) -> str:
    with svc.db.session() as db:
        user = db.get(User, email)
        return user.name if user else ""


def send_student_email(svc: Services, st: Settings, r: CheckInResult) -> None:
    lang = st.default_language
    title = session_title(r.session, lang)
    phase = i18n.phase_label(r.phase.label, lang)
    _email(
        svc, st, r.checkin.email, i18n.gettext(lang, "{phase} confirmed: {title}", phase=phase, title=title), "student",
        teacher=r.session.teacher_email,
        name=r.checkin.name, title=title, phase=phase,
        time=format_local(r.checkin.created_at, st, "%d %b %Y, %H:%M:%S", lang),
        timezone=st.timezone,
    )


def send_report_email(svc: Services, session_id: int, to: str) -> None:
    st = svc.settings()
    sess = load_session(svc, session_id)
    phases, rows = roster(sess)
    lang = st.default_language
    title = session_title(sess, lang)
    date = format_local(sess.created_at, st, "%d %b %Y", lang)
    _email(
        svc, st, to, i18n.gettext(lang, "Attendance report: {title} ({date})", title=title, date=date), "report",
        teacher=sess.teacher_email,
        title=title, sess=sess, phases=phases, rows=rows,
        date=format_local(sess.created_at, st, "%d %b %Y, %H:%M", lang),
        local=lambda dt: format_local(dt, st, "%H:%M:%S"),
        report_url=svc.absolute(f"/sessions/{sess.id}/report"),
    )

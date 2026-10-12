import base64
import json
import re
import sqlite3
import time
from email import message_from_bytes

import pytest
from fastapi.testclient import TestClient

from app import config as config_mod
from app.main import create_app

TEACHER = "teacher@uni.example"
STUDENT = "6501@students.uni.example"


@pytest.fixture
def app(tmp_path):
    cfg = config_mod.load({
        "PUBLIC_URL": "http://testserver/attendance",
        "SECRET_KEY": "x" * 40,
        "DATA_DIR": str(tmp_path),
        "ADMIN_EMAILS": TEACHER,
        "STUDENT_DOMAINS": "students.uni.example",
        "INSTITUTION_NAME": "Example University",
        "TIMEZONE": "Asia/Bangkok",
    })
    return create_app(cfg)


def client(app):
    return TestClient(app, follow_redirects=True)


def csrf(c, path="/attendance/login"):
    html = c.get(path).text
    return re.search(r'name="csrf" value="([^"]+)"', html).group(1)


def login(app, c, email, name="Somchai Jaidee", outbox=None):
    mailer = app.state.svc.mailer
    outbox = mailer.sent if outbox is None else outbox
    before = len(outbox)
    r = c.post("/attendance/login/code", data={"email": email, "csrf": csrf(c)})
    assert r.status_code == 200, r.text
    deadline = time.time() + 5
    while len(outbox) <= before and time.time() < deadline:
        time.sleep(0.05)
    msg = outbox[before]
    code = re.search(r"\b(\d{6})\b", msg["Subject"]).group(1)
    token = re.search(r'name="csrf" value="([^"]+)"', r.text).group(1)
    r = c.post("/attendance/login/verify", data={"code": code, "csrf": token})
    if 'name="name"' in r.text:
        nxt = re.search(r'name="next" value="([^"]+)"', r.text).group(1)
        token = re.search(r'name="csrf" value="([^"]+)"', r.text).group(1)
        r = c.post("/attendance/profile", data={"name": name, "next": nxt, "csrf": token})
    return r


def start_session(app, c, **opts):
    data = {"class_name": "Circuits 101", "mid_checks": "1", "checkout": "true",
            "email_report": "true", "email_students": "true", "csrf": csrf(c, "/attendance/")}
    data.update(opts)
    r = c.post("/attendance/sessions", data=data)
    assert r.status_code == 200
    sid = int(re.search(r"/sessions/(\d+)$", str(r.url)).group(1))
    state = c.get(f"/attendance/sessions/{sid}/state").json()
    return sid, state


def qr_url(app, phase_id):
    svc = app.state.svc
    token, _ = svc.signer.current(phase_id, svc.settings().qr_interval)
    return f"/attendance/c/{phase_id}/{token}"


def test_branding_and_redirect(app):
    c = client(app)
    r = c.get("/")
    assert r.url.path == "/attendance/"
    assert "Example University" in r.text


def test_disallowed_domain_cannot_request_code(app):
    c = client(app)
    r = c.post("/attendance/login/code", data={"email": "x@gmail.com", "csrf": csrf(c)})
    assert r.status_code == 403
    assert not app.state.svc.mailer.sent


def test_csrf_required(app):
    c = client(app)
    r = c.post("/attendance/login/code", data={"email": STUDENT})
    assert r.status_code == 403


def test_full_flow(app):
    with client(app) as t:
        assert "Start a class session" in login(app, t, TEACHER, "Dr Teacher").text
        sid, state = start_session(app, t)
        kinds = [p["kind"] for p in state["phases"]]
        assert kinds == ["checkin", "mid", "checkout"]
        checkin = state["phases"][0]
        assert checkin["state"] == "open"
        url = qr_url(app, checkin["id"])

        with client(app) as s:
            # Scan before signing in: the scan is remembered through login.
            r = s.get(url)
            assert "Sign in" in r.text
            r = login(app, s, STUDENT)
            assert "Check-in recorded" in r.text
            # Second scan is a duplicate, not an error.
            r = s.get(url)
            assert "Already checked in" in r.text

            confirmations = [m for m in app.state.svc.mailer.sent if m["To"] == STUDENT and "confirmed" in m["Subject"]]
            assert len(confirmations) == 1

            # Pause blocks check-in.
            h = {"X-CSRF-Token": csrf(t, "/attendance/")}
            mid = state["phases"][1]
            assert t.post(f"/attendance/sessions/{sid}/phases/{mid['id']}/open", headers=h).status_code == 200
            assert t.post(f"/attendance/sessions/{sid}/phases/{mid['id']}/pause", headers=h).status_code == 200
            r = s.get(qr_url(app, mid["id"]))
            assert r.status_code == 409 and "paused" in r.text
            t.post(f"/attendance/sessions/{sid}/phases/{mid['id']}/resume", headers=h)
            assert "Mid-class check 1 recorded" in s.get(qr_url(app, mid["id"])).text

            # Opening the mid check closed the first check-in.
            r = s.get(url)
            assert r.status_code == 409 and "closed" in r.text

            # Add a second mid check on the fly; check-out stays last.
            t.post(f"/attendance/sessions/{sid}/phases", data={"kind": "mid"}, headers=h)
            labels = [p["label"] for p in t.get(f"/attendance/sessions/{sid}/state").json()["phases"]]
            assert labels == ["Check-in", "Mid-class check 1", "Mid-class check 2", "Check-out"]

        csv = t.get(f"/attendance/sessions/{sid}/report.csv").text
        assert STUDENT in csv and "Somchai Jaidee" in csv

        r = t.post(f"/attendance/sessions/{sid}/close", data={"csrf": csrf(t, "/attendance/")})
        assert "Circuits 101" in r.text
        report = [m for m in app.state.svc.mailer.sent if m["To"] == TEACHER and "Attendance report" in m["Subject"]]
        assert len(report) == 1
        assert any(part.get_filename(" ").endswith(".csv") for part in report[0].iter_attachments())


def test_expired_and_forged_tokens(app):
    with client(app) as t:
        login(app, t, TEACHER)
        _, state = start_session(app, t)
        pid = state["phases"][0]["id"]
        svc = app.state.svc
        interval = svc.settings().qr_interval
        old = svc.signer.token(pid, svc.signer.window(interval, time.time() - 3 * interval))
        assert t.get(f"/attendance/c/{pid}/{old}").status_code == 410
        assert t.get(f"/attendance/c/{pid}/forged").status_code == 410
        # Previous window still accepted.
        prev = svc.signer.token(pid, svc.signer.window(interval) - 1)
        assert t.get(f"/attendance/c/{pid}/{prev}").status_code != 410


def test_student_cannot_open_teacher_pages(app):
    with client(app) as s:
        login(app, s, STUDENT)
        assert s.get("/attendance/admin/settings").status_code == 403
        r = s.post("/attendance/sessions", data={"csrf": csrf(s, "/attendance/profile")})
        assert r.status_code == 403


def test_settings_and_logo(app):
    with client(app) as t:
        login(app, t, TEACHER)
        token = csrf(t, "/attendance/admin/settings")
        r = t.post("/attendance/admin/settings", data={
            "csrf": token, "institution_name": "Another Institute", "app_title": "Roll Call",
            "student_domains": "@a.example\n*.b.example", "timezone": "Europe/Berlin", "qr_interval": "10",
            "accent_color": "#123456",
        })
        assert "Another Institute" in r.text and "Roll Call" in r.text
        png = bytes.fromhex("89504e470d0a1a0a0000000d4948445200000001000000010806000000"
                            "1f15c4890000000d49444154789c6360000002000154a24f5d0000000049454e44ae426082")
        r = t.post("/attendance/admin/logos", data={"csrf": token}, files={"file": ("l.png", png, "image/png")})
        assert r.status_code == 200
        logo = app.state.svc.settings().logos[0]
        assert t.get(f"/attendance/media/{logo}").content == png
        st = app.state.svc.settings()
        assert st.student_allowed("x@a.example") and st.student_allowed("x@cs.b.example")
        assert not st.student_allowed("x@b.example.com")


def test_unknown_route_uses_message_page(app):
    r = client(app).get("/attendance/nope")
    assert r.status_code == 404 and "Not found" in r.text


def test_stale_pending_scan_is_ignored(app, monkeypatch):
    with client(app) as t:
        login(app, t, TEACHER)
        _, state = start_session(app, t)
        url = qr_url(app, state["phases"][0]["id"])
    with client(app) as s:
        s.get(url)  # scan while signed out: remembered as pending
        monkeypatch.setattr("app.routes_auth.PENDING_TTL", -1)  # scan has expired
        r = login(app, s, STUDENT)
        assert "signed in" in r.text and "Check-in recorded" not in r.text


def test_mail_sent_from_teacher_gmail(tmp_path, monkeypatch):
    cfg = config_mod.load({
        "PUBLIC_URL": "http://testserver/attendance", "SECRET_KEY": "y" * 40, "DATA_DIR": str(tmp_path),
        "ADMIN_EMAILS": TEACHER, "STUDENT_DOMAINS": "students.uni.example",
        "OIDC_PROVIDERS": "google", "OIDC_GOOGLE_CLIENT_ID": "cid", "OIDC_GOOGLE_CLIENT_SECRET": "cs",
        "GMAIL_SEND": "true",
    })
    app = create_app(cfg)
    calls = []
    gmail_out = []

    class Resp:
        def __init__(self, data, code=200):
            self.status_code, self._data = code, data

        def json(self):
            return self._data

        def raise_for_status(self):
            pass

    def fake_post(url, data=None, json=None, headers=None, timeout=None):
        calls.append((url, data or json, headers))
        if "messages/send" in url:
            gmail_out.append(message_from_bytes(base64.urlsafe_b64decode(json["raw"])))
        if "token" in url:
            return Resp({"access_token": "at", "expires_in": 3600})
        return Resp({"id": "m1"})

    monkeypatch.setattr("app.gmail.httpx.post", fake_post)
    gmail = app.state.svc.mailer.gmail
    gmail.save(TEACHER, "refresh-1")
    # Stored encrypted, not in clear text.
    raw = sqlite3.connect(tmp_path / "attendance.db").execute("select refresh_token from gmail_tokens").fetchone()[0]
    assert "refresh-1" not in raw

    with client(app) as t:
        login(app, t, TEACHER, "Dr Teacher")  # OTP via log: teacher has no pending scan
        _, state = start_session(app, t)
        url = qr_url(app, state["phases"][0]["id"])
        with client(app) as s:
            s.get(url)
            login(app, s, STUDENT, outbox=gmail_out)  # sign-in code goes out via the teacher's Gmail
        deadline = time.time() + 5
        while len([c for c in calls if "messages/send" in c[0]]) < 2 and time.time() < deadline:
            time.sleep(0.05)
    sends = [c for c in calls if "messages/send" in c[0]]
    assert len(sends) == 2  # sign-in code + confirmation
    msg = gmail_out[1]
    assert TEACHER in msg["From"] and msg["To"] == STUDENT
    assert sends[1][2]["Authorization"] == "Bearer at"
    assert sum(1 for c in calls if "token" in c[0]) == 1  # access token cached


def test_thai_language(app):
    with client(app) as t:
        login(app, t, TEACHER, "Dr Teacher")
        r = t.get("/attendance/lang/th?next=/attendance/")
        assert "เริ่มคาบเรียน" in r.text and 'lang="th"' in r.text
        sid, _ = start_session(app, t)
        r = t.get(f"/attendance/sessions/{sid}")
        assert "สแกนด้วยกล้องโทรศัพท์" in r.text
        i18n_json = re.search(r"window.I18N = (\{.*?\});", r.text, re.S).group(1)
        assert json.loads(re.sub(r",\s*}", "}", i18n_json))["Pause"] == "หยุดชั่วคราว"
        labels = [p["label"] for p in t.get(f"/attendance/sessions/{sid}/state").json()["phases"]]
        assert labels == ["เช็คชื่อเข้าเรียน", "เช็คชื่อระหว่างคาบ 1", "เช็คชื่อออก"]
        r = t.get(f"/attendance/sessions/{sid}/report")
        assert "2569" in r.text  # Buddhist-era year
        # Switching back works, and an unknown language falls back to English.
        assert "Start a class session" in t.get("/attendance/lang/xx?next=/attendance/").text


def test_emails_follow_default_language(app):
    from app import settings as S
    S.save(app.state.svc.db, {"default_language": "th"})
    with client(app) as t:
        login(app, t, TEACHER, "Dr Teacher")
        _, state = start_session(app, t)
        with client(app) as s:
            s.get(qr_url(app, state["phases"][0]["id"]))
            r = login(app, s, STUDENT)
            assert "บันทึกเช็คชื่อเข้าเรียนแล้ว" in r.text  # new visitors see the default language
    msg = [m for m in app.state.svc.mailer.sent if m["To"] == STUDENT][-1]
    assert msg["Subject"].startswith("ยืนยันเช็คชื่อเข้าเรียน")
    assert "เรียน Somchai Jaidee" in msg.get_body(("plain",)).get_content()

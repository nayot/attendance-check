"""Administrator settings: branding, logos, allowed domains, defaults."""

import json
import re
import secrets
from zoneinfo import available_timezones

from fastapi import APIRouter, Depends, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, RedirectResponse

from . import settings as settings_mod
from .web import check_csrf, render, require_admin, svc

router = APIRouter()

MAX_LOGOS = 4
MAX_LOGO_BYTES = 2 * 1024 * 1024
LOGO_TYPES = {"image/png": ".png", "image/jpeg": ".jpg", "image/gif": ".gif",
              "image/webp": ".webp", "image/svg+xml": ".svg"}
LOGO_NAME = re.compile(r"^logo-[A-Za-z0-9_-]+\.(png|jpg|gif|webp|svg)$")
COLOR = re.compile(r"^#[0-9a-fA-F]{6}$")


@router.get("/admin/settings")
def settings_page(request: Request, user: dict = Depends(require_admin), saved: int = 0):
    return render(request, "settings.html", timezones=sorted(available_timezones()), saved=saved,
                  config=svc(request).config)


@router.post("/admin/settings", dependencies=[Depends(check_csrf)])
def settings_save(
    request: Request,
    user: dict = Depends(require_admin),
    institution_name: str = Form(""),
    app_title: str = Form(""),
    student_domains: str = Form(""),
    teacher_domains: str = Form(""),
    teacher_emails: str = Form(""),
    timezone: str = Form("UTC"),
    qr_interval: int = Form(15),
    accent_color: str = Form("#1f5fbf"),
    student_emails_default: bool = Form(False),
    report_email_default: bool = Form(False),
):
    if timezone not in available_timezones():
        raise HTTPException(400, "Unknown time zone.")
    settings_mod.save(svc(request).db, {
        "institution_name": institution_name.strip()[:200],
        "app_title": app_title.strip()[:100] or "Attendance Check",
        "student_domains": ", ".join(settings_mod.parse_list(student_domains)),
        "teacher_domains": ", ".join(settings_mod.parse_list(teacher_domains)),
        "teacher_emails": ", ".join(settings_mod.parse_list(teacher_emails)),
        "timezone": timezone,
        "qr_interval": str(max(5, min(120, qr_interval))),
        "accent_color": accent_color if COLOR.match(accent_color) else "#1f5fbf",
        "student_emails_default": "1" if student_emails_default else "0",
        "report_email_default": "1" if report_email_default else "0",
    })
    return RedirectResponse(svc(request).url("/admin/settings?saved=1"), status_code=303)


@router.post("/admin/logos", dependencies=[Depends(check_csrf)])
async def logo_upload(request: Request, file: UploadFile, user: dict = Depends(require_admin)):
    s = svc(request)
    st = s.settings()
    if len(st.logos) >= MAX_LOGOS:
        raise HTTPException(400, f"At most {MAX_LOGOS} logos. Remove one first.")
    ext = LOGO_TYPES.get(file.content_type or "")
    if ext is None:
        raise HTTPException(400, "Logos must be PNG, JPEG, GIF, WebP or SVG images.")
    data = await file.read(MAX_LOGO_BYTES + 1)
    if len(data) > MAX_LOGO_BYTES:
        raise HTTPException(400, "Logo files must be 2 MB or smaller.")
    s.config.upload_dir.mkdir(parents=True, exist_ok=True)
    name = f"logo-{secrets.token_urlsafe(8)}{ext}"
    (s.config.upload_dir / name).write_bytes(data)
    settings_mod.save(s.db, {"logos": json.dumps(st.logos + [name])})
    return RedirectResponse(s.url("/admin/settings?saved=1"), status_code=303)


@router.post("/admin/logos/{name}/{action}", dependencies=[Depends(check_csrf)])
def logo_action(request: Request, name: str, action: str, user: dict = Depends(require_admin)):
    s = svc(request)
    logos = s.settings().logos
    if name not in logos:
        raise HTTPException(404)
    i = logos.index(name)
    if action == "delete":
        logos.pop(i)
        (s.config.upload_dir / name).unlink(missing_ok=True)
    elif action == "up" and i > 0:
        logos[i - 1], logos[i] = logos[i], logos[i - 1]
    elif action == "down" and i < len(logos) - 1:
        logos[i + 1], logos[i] = logos[i], logos[i + 1]
    settings_mod.save(s.db, {"logos": json.dumps(logos)})
    return RedirectResponse(s.url("/admin/settings"), status_code=303)


@router.get("/media/{name}")
def media(request: Request, name: str):
    s = svc(request)
    path = s.config.upload_dir / name
    if not LOGO_NAME.match(name) or not path.is_file():
        raise HTTPException(404)
    return FileResponse(path, headers={
        "Cache-Control": "public, max-age=86400",
        "X-Content-Type-Options": "nosniff",
        "Content-Security-Policy": "default-src 'none'; style-src 'unsafe-inline'; sandbox",
    })

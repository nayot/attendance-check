"""Admin-editable settings stored in the database."""

import json
from dataclasses import dataclass, field
from zoneinfo import ZoneInfo, available_timezones

from .db import Database, Setting

DEFAULTS = {
    "institution_name": "",
    "app_title": "Attendance Check",
    "logos": "[]",
    "student_domains": "",
    "teacher_domains": "",
    "teacher_emails": "",
    "timezone": "UTC",
    "qr_interval": "15",
    "student_emails_default": "1",
    "report_email_default": "1",
    "accent_color": "#1f5fbf",
}


def parse_list(value: str) -> list[str]:
    return [v.strip().lower().lstrip("@") for v in value.replace(";", ",").replace("\n", ",").split(",") if v.strip()]


def domain_allowed(email: str, domains: list[str]) -> bool:
    """`*.example.edu` matches any subdomain; a bare domain matches exactly."""
    domain = email.rsplit("@", 1)[-1].lower()
    for d in domains:
        if d.startswith("*."):
            if domain.endswith(d[1:]):
                return True
        elif domain == d:
            return True
    return False


@dataclass
class Settings:
    institution_name: str = ""
    app_title: str = "Attendance Check"
    logos: list[str] = field(default_factory=list)
    student_domains: list[str] = field(default_factory=list)
    teacher_domains: list[str] = field(default_factory=list)
    teacher_emails: list[str] = field(default_factory=list)
    timezone: str = "UTC"
    qr_interval: int = 15
    student_emails_default: bool = True
    report_email_default: bool = True
    accent_color: str = "#1f5fbf"

    @property
    def tz(self) -> ZoneInfo:
        try:
            return ZoneInfo(self.timezone)
        except Exception:
            return ZoneInfo("UTC")

    def student_allowed(self, email: str) -> bool:
        # No domains configured means any verified email may check in.
        return not self.student_domains or domain_allowed(email, self.student_domains)


def load(db: Database) -> Settings:
    with db.session() as s:
        raw = dict(DEFAULTS)
        raw.update({row.key: row.value for row in s.query(Setting).all()})
    try:
        logos = [str(x) for x in json.loads(raw["logos"])]
    except ValueError:
        logos = []
    try:
        interval = max(5, min(120, int(raw["qr_interval"])))
    except ValueError:
        interval = 15
    return Settings(
        institution_name=raw["institution_name"],
        app_title=raw["app_title"] or "Attendance Check",
        logos=logos,
        student_domains=parse_list(raw["student_domains"]),
        teacher_domains=parse_list(raw["teacher_domains"]),
        teacher_emails=parse_list(raw["teacher_emails"]),
        timezone=raw["timezone"] if raw["timezone"] in available_timezones() else "UTC",
        qr_interval=interval,
        student_emails_default=raw["student_emails_default"] == "1",
        report_email_default=raw["report_email_default"] == "1",
        accent_color=raw["accent_color"] or "#1f5fbf",
    )


def save(db: Database, values: dict[str, str]) -> None:
    with db.session() as s:
        for key, value in values.items():
            if key not in DEFAULTS:
                raise KeyError(key)
            row = s.get(Setting, key)
            if row is None:
                s.add(Setting(key=key, value=value))
            else:
                row.value = value
        s.commit()

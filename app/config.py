"""Deployment configuration, read once from environment variables.

Everything an admin may want to change at runtime (institution name, logos,
allowed domains, ...) lives in the database instead; see settings.py.
"""

import os
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import urlparse


def _list(value: str) -> list[str]:
    return [v.strip().lower() for v in value.replace(";", ",").split(",") if v.strip()]


def _bool(value: str, default: bool = False) -> bool:
    if value == "":
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


# Well-known OIDC discovery URLs, so most deployments only need an id and secret.
KNOWN_PROVIDERS = {
    "google": (
        "Google",
        "https://accounts.google.com/.well-known/openid-configuration",
    ),
    "microsoft": (
        "Microsoft",
        "https://login.microsoftonline.com/{tenant}/v2.0/.well-known/openid-configuration",
    ),
}


SEED_VARS = {
    "institution_name": "INSTITUTION_NAME",
    "student_domains": "STUDENT_DOMAINS",
    "teacher_domains": "TEACHER_DOMAINS",
    "teacher_emails": "TEACHER_EMAILS",
    "timezone": "TIMEZONE",
    "default_language": "DEFAULT_LANGUAGE",
}


@dataclass
class OIDCProvider:
    name: str
    label: str
    client_id: str
    client_secret: str
    metadata_url: str


@dataclass
class Config:
    public_url: str
    base_path: str
    secret_key: str
    data_dir: Path
    admin_emails: list[str]
    smtp_host: str
    smtp_port: int
    smtp_user: str
    smtp_password: str
    smtp_from: str
    smtp_starttls: bool
    smtp_ssl: bool
    otp_enabled: bool
    gmail_send: bool
    providers: list[OIDCProvider] = field(default_factory=list)
    cookie_secure: bool = True
    # Initial values for admin settings, applied only while a setting is unset.
    seed_settings: dict[str, str] = field(default_factory=dict)

    @property
    def db_path(self) -> Path:
        return self.data_dir / "attendance.db"

    @property
    def upload_dir(self) -> Path:
        return self.data_dir / "uploads"

    @property
    def smtp_configured(self) -> bool:
        return bool(self.smtp_host)

    @property
    def google(self) -> "OIDCProvider | None":
        return next((p for p in self.providers if p.name == "google"), None)


def _providers(env) -> list[OIDCProvider]:
    providers = []
    for name in _list(env.get("OIDC_PROVIDERS", "")):
        key = f"OIDC_{name.upper()}_"
        client_id = env.get(key + "CLIENT_ID", "")
        client_secret = env.get(key + "CLIENT_SECRET", "")
        if not client_id:
            continue
        label, metadata = KNOWN_PROVIDERS.get(name, (name.title(), ""))
        metadata = env.get(key + "METADATA_URL", metadata)
        metadata = metadata.replace("{tenant}", env.get(key + "TENANT", "organizations"))
        if not metadata:
            raise RuntimeError(f"{key}METADATA_URL is required for provider '{name}'")
        providers.append(
            OIDCProvider(
                name=name,
                label=env.get(key + "LABEL", label),
                client_id=client_id,
                client_secret=client_secret,
                metadata_url=metadata,
            )
        )
    return providers


def load(env=None) -> Config:
    env = os.environ if env is None else env
    public_url = env.get("PUBLIC_URL", "http://localhost:8000").rstrip("/")
    # The app is served under PUBLIC_URL's path, e.g. https://host/attendance.
    base_path = urlparse(public_url).path.rstrip("/")
    secret = env.get("SECRET_KEY", "")
    if len(secret) < 32:
        raise RuntimeError("SECRET_KEY must be set to at least 32 random characters")
    return Config(
        public_url=public_url,
        base_path=base_path,
        secret_key=secret,
        data_dir=Path(env.get("DATA_DIR", "./data")).resolve(),
        admin_emails=_list(env.get("ADMIN_EMAILS", "")),
        smtp_host=env.get("SMTP_HOST", ""),
        smtp_port=int(env.get("SMTP_PORT", "587")),
        smtp_user=env.get("SMTP_USER", ""),
        smtp_password=env.get("SMTP_PASSWORD", ""),
        smtp_from=env.get("SMTP_FROM", env.get("SMTP_USER", "")),
        smtp_starttls=_bool(env.get("SMTP_STARTTLS", ""), True),
        smtp_ssl=_bool(env.get("SMTP_SSL", ""), False),
        otp_enabled=_bool(env.get("OTP_LOGIN", ""), True),
        gmail_send=_bool(env.get("GMAIL_SEND", ""), False),
        providers=_providers(env),
        cookie_secure=public_url.startswith("https://"),
        seed_settings={
            key: env[var]
            for key, var in SEED_VARS.items()
            if env.get(var, "").strip()
        },
    )

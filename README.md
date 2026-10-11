# Attendance Check

A small self-hosted web app that lets teachers take class attendance with a rotating QR code.

- A teacher signs in, starts a session (class name optional) and shows the QR code on the classroom screen.
- Students scan it with their phone and sign in with their institution account. Their name, email and
  time appear on the screen straight away.
- The QR code changes every few seconds, so a photo sent to a friend outside the room soon stops working.
- **Pause** stops check-in instantly. The QR code is hidden, and codes already scanned are rejected.
- Add **mid-class checks** and a **check-out** when you set up the session or while class is running.
- Each student gets a confirmation email. When the session closes, the teacher gets the list by email with a
  CSV file attached. The list can also be downloaded or corrected by hand.
- Settings for the institution name, logos, accent colour, allowed student email domains, teacher allowlist,
  time zone and QR interval. Nothing is tied to one institution.

## How students prove who they are

Check-in records the email of a **signed-in** account. Students can't type someone else's address.

- **SSO (recommended):** Google, Microsoft or any OpenID Connect provider. Students sign in once, and later
  check-ins are a single scan.
- **Email code:** a 6-digit code sent to the student's email. This needs SMTP and works without any SSO setup.

Only addresses in the allowed student domains can check in or request a code.

## Quick start (Docker)

```sh
git clone https://github.com/<you>/attendance-check.git
cd attendance-check
cp .env.example .env
# edit .env: PUBLIC_URL, SECRET_KEY, ADMIN_EMAILS, STUDENT_DOMAINS, SMTP_*, OIDC_*
docker compose up -d --build
```

Open `PUBLIC_URL`, sign in with an address listed in `ADMIN_EMAILS`, then go to **Settings** to add the
institution name, logos and allowed domains.

Data (an SQLite database and uploaded logos) lives in the `attendance-data` Docker volume.

### Running under a sub-path

Set `PUBLIC_URL` to the full address, for example `https://apps.example.edu/attendance`. The app serves
everything under `/attendance`. Proxy that path to the container **without stripping the prefix**:

```nginx
location /attendance/ {
    proxy_pass http://127.0.0.1:8000;
    proxy_set_header Host $host;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;
    client_max_body_size 5m;

    # Live updates on the QR display use Server-Sent Events.
    proxy_buffering off;
    proxy_cache off;
    proxy_read_timeout 1h;
}
location = /attendance { return 301 /attendance/; }
```

The app must be served over HTTPS in production. Session cookies are marked `Secure` whenever
`PUBLIC_URL` starts with `https://`.

## Setting up SSO

Register a web application with your identity provider. Use this redirect URI:

```
<PUBLIC_URL>/auth/<provider name>      e.g. https://apps.example.edu/attendance/auth/google
```

**Google Workspace:** in Google Cloud Console → *APIs & Services → Credentials*, create an *OAuth client ID*
(type *Web application*). Set the consent screen to *Internal* to limit sign-in to your organisation.

```env
OIDC_PROVIDERS=google
OIDC_GOOGLE_CLIENT_ID=...apps.googleusercontent.com
OIDC_GOOGLE_CLIENT_SECRET=...
```

**Microsoft 365 / Entra ID:** register an app under *App registrations*, add a *Web* redirect URI and create a
client secret.

```env
OIDC_PROVIDERS=microsoft
OIDC_MICROSOFT_CLIENT_ID=...
OIDC_MICROSOFT_CLIENT_SECRET=...
OIDC_MICROSOFT_TENANT=<your tenant id>
```

**Any other OIDC provider** (Keycloak, Okta, Authentik, ...): pick a name and set `OIDC_<NAME>_METADATA_URL`
to its `.well-known/openid-configuration` URL. See `.env.example`.

Several providers can be enabled at once (`OIDC_PROVIDERS=google,microsoft`).

## Configuration

Deployment settings come from environment variables (see [`.env.example`](.env.example)). Everything else is
edited on the **Settings** page by an administrator:

| Setting | Notes |
| --- | --- |
| Institution name, app title, accent colour | Shown on every page, the QR display and emails |
| Logos | Up to 4 images. The first PNG/JPEG is also embedded in emails |
| Student email domains | e.g. `students.example.edu, *.example.edu`. Empty allows any verified email |
| Teacher domains / emails | Who may start sessions. Admins always can |
| Time zone | Used for every time shown, emailed or exported |
| QR interval | Seconds between code changes (5–120). A scanned code is accepted for up to two intervals |
| Email defaults | Whether new sessions email students and the teacher |

`INSTITUTION_NAME`, `STUDENT_DOMAINS`, `TEACHER_DOMAINS`, `TEACHER_EMAILS` and `TIMEZONE` in the environment
set the starting values on first run.

## Using it in class

1. **Start a class session** and choose how many mid-class checks you want and whether to have a check-out.
2. The QR display opens. Put it on the projector (**Full screen** or press `f`).
3. Students scan the code. Each one appears at the top of the list with their name, email and time.
4. **Pause** (or press the space bar) stops check-in. **Resume** starts it again.
5. Click a check in the row at the top, or use **+ Mid-class check** / **+ Check-out**, to open the next check.
   Opening one closes the one before it.
6. **Close session** ends it and, if you chose that option, emails you the list.

On the report page you can download the CSV, email it to yourself again, add a student by hand or remove a
mistaken check-in.

## Development

```sh
python3 -m venv .venv && .venv/bin/pip install -r requirements-dev.txt
export SECRET_KEY=$(python3 -c "import secrets; print(secrets.token_urlsafe(48))")
export PUBLIC_URL=http://localhost:8000 ADMIN_EMAILS=you@example.edu
.venv/bin/uvicorn app.main:app --reload
.venv/bin/pytest
```

Without `SMTP_HOST` no email is sent. Messages, including sign-in codes in the subject line, are written to the
log instead.

The app runs as **one process**: live updates and the mail queue are kept in memory. One instance easily
handles a whole faculty. Don't start it with several workers.

## License

[MIT](LICENSE)

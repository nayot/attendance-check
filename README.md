# Attendance Check

A small self-hosted web app that lets teachers take class attendance with a rotating QR code.

- A teacher signs in, starts a session (class name optional) and shows the QR code on the classroom screen.
- Students scan it with their phone and sign in with their institution account. Their name, email and
  time appear on the screen straight away.
- The QR code changes every few seconds, so a photo sent to a friend outside the room soon stops working.
- **Pause** stops check-in instantly. The QR code is hidden, and codes already scanned are rejected.
- Add **mid-class checks** and a **check-out** when you set up the session or while class is running.
- Each student gets a confirmation email, sent from the teacher's own Gmail / Google Workspace address
  (or from a shared SMTP account). When the session closes, the teacher gets the list by email with a
  CSV file attached. The list can also be downloaded or corrected by hand.
- English and Thai interface. Everyone can switch language in the header, and the admin picks the default,
  which is also used for emails.
- English and Thai user interface: everyone can switch language in the header, and an admin picks the default
  language, which is also used for emails. Thai dates use Thai month names and Buddhist-era years.
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
# edit .env: PUBLIC_URL, SECRET_KEY, ADMIN_EMAILS, STUDENT_DOMAINS, SMTP_*, OIDC_*,
# and HOST_PORT if port 8000 is already in use on the host
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

### Sending email from the teacher's Google account

Set `GMAIL_SEND=true` (requires the `google` provider). In the same Google Cloud project, enable the
**Gmail API** and add the `https://www.googleapis.com/auth/gmail.send` scope to the consent screen. Each teacher
then clicks **Connect Gmail** on their dashboard once. Student confirmations, sign-in codes for that class and
attendance reports are sent from the teacher's own address. The refresh token is stored encrypted with a key
derived from `SECRET_KEY`. Changing `SECRET_KEY` means teachers have to reconnect.

`gmail.send` is a restricted scope. With an **Internal** consent screen (Google Workspace) no review is needed.
An **External** app works without review for sign-in scopes, but teachers see an "unverified app" notice when
connecting Gmail until Google verifies the app.

## Configuration

Deployment settings come from environment variables (see [`.env.example`](.env.example)). Everything else is
edited on the **Settings** page by an administrator:

| Setting | Notes |
| --- | --- |
| Institution name, app title, accent colour | Shown on every page, the QR display and emails |
| Logos | Up to 4 images. The first PNG/JPEG is also embedded in emails |
| Student email domains | e.g. `students.example.edu, *.example.edu`. Empty allows any verified email |
| Teacher domains / emails | Who may start sessions. Admins always can |
| Default language | English or Thai, for new visitors and for emails. Thai dates use Buddhist-era years |
| Default language | English or Thai, for new visitors and for all emails |
| Time zone | Used for every time shown, emailed or exported |
| QR interval | Seconds between code changes (5–120). A scanned code is accepted for up to two intervals |
| Email defaults | Whether new sessions email students and the teacher |

`INSTITUTION_NAME`, `STUDENT_DOMAINS`, `TEACHER_DOMAINS`, `TEACHER_EMAILS`, `TIMEZONE` and `DEFAULT_LANGUAGE` in the environment
set the starting values on first run.

## Using it in class

1. **Start a class session** and choose how many mid-class checks you want and whether to have a check-out.
2. The QR display opens. Put it on the projector (**Full screen** or press `f`).
3. Students scan the code. Each one appears at the top of the list with their name, email and time.
4. **Pause** (or press the space bar) stops check-in. **Resume** starts it again.
5. Click a check in the row at the top, or use **+ Mid-class check** / **+ Check-out**, to open the next check.
   Opening one closes the one before it.
6. **Close session** ends it and, if you chose that option, emails you the list.

Use the **…** menu next to a session on the dashboard to **archive** it (hidden from the list, kept in
**Archived**) or **delete** it with all its check-ins.

On the report page you can download the CSV, email it to yourself again, add a student by hand or remove a
mistaken check-in.

## Adding a language

Interface text is written in English and translated through the catalogs in [`app/i18n.py`](app/i18n.py).
To add a language, copy the `TH` dictionary, translate the values and register it in `CATALOGS` and `LANGUAGES`.
`tests/test_i18n.py` checks that every string shown in the UI has a translation.

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

## Adding a language

UI strings are written in English and translated in [`app/i18n.py`](app/i18n.py). Copy the `TH` catalog, translate
it, and register it in `CATALOGS` and `LANGUAGES`. `tests/test_i18n.py` fails if a string the UI shows has no
Thai translation, so run it after adding text.

## License

[MIT](LICENSE). © 2026 Nayot Kurukitkoson, Faculty of Engineering, Burapha University.

# Changelog

## 0.1.2 — 2026-10-12

- Attendance tables (report email, report page and CSV) have one column per check held (check-in, each
  mid-class check, check-out) plus a **Checks** column such as `2/3`, highlighted when a student missed one.
  Checks that were planned but never opened get no column.

## 0.1.1 — 2026-10-12

- The attendance report email has the list as a table in the message body (HTML table plus a plain-text
  Markdown-style table), so it can be read or pasted directly, including by AI assistants. The CSV attachment is
  gone; CSV download stays on the report page.

## 0.1.0 — 2026-10-12

First release.

- Teachers start a class session (class name optional) and show a rotating, HMAC-signed QR code.
- Students sign in with Google, Microsoft or any OpenID Connect provider, or with a one-time email code, limited
  to allowed email domains, and check in with one scan.
- Live display with the running list (name, email, time), pause/resume, full screen and keyboard shortcuts.
- Mid-class checks and check-out, planned at setup or added during class.
- Confirmation email to each student and an attendance report to the teacher on close with a CSV attachment, sent from the
  teacher's own Gmail through the Gmail API, or via SMTP.
- Attendance list with CSV download, re-send by email, and corrections (add by hand, remove).
- Archive, unarchive and delete sessions.
- Admin settings: institution name, logos, accent colour, default language, student domains, teacher domains or
  individual teachers, time zone, QR interval, email defaults.
- English and Thai interface and emails, with Thai dates in the Buddhist era.
- Built-in teacher's manual (Help), in English and Thai.
- Single Docker container with SQLite, served under a URL sub-path behind a reverse proxy.

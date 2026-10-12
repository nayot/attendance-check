"""Outgoing mail, sent from a background thread so requests never wait on it.

A message with a `from_email` whose owner has connected Gmail is sent through
the Gmail API from that account. Anything else goes through SMTP, or, without
SMTP_HOST, is only written to the log (handy for local development).
"""

import logging
import queue
import smtplib
import ssl
import threading
from email.message import EmailMessage
from email.utils import formataddr, make_msgid

from .config import Config
from .gmail import GmailSender

log = logging.getLogger("attendance.mail")


class Mailer:
    def __init__(self, config: Config, gmail: GmailSender | None = None):
        self.config = config
        self.gmail = gmail
        self._queue: queue.Queue[tuple[EmailMessage, str | None] | None] = queue.Queue()
        self._thread: threading.Thread | None = None
        self.sent: list[EmailMessage] = []  # kept when SMTP is off; used by tests

    def start(self) -> None:
        if self._thread is None:
            self._thread = threading.Thread(target=self._run, name="mailer", daemon=True)
            self._thread.start()

    def stop(self) -> None:
        if self._thread is not None:
            self._queue.put(None)
            self._thread.join(timeout=10)
            self._thread = None

    def send(
        self,
        to: str,
        subject: str,
        text: str,
        html: str | None = None,
        sender_name: str = "",
        attachments: list[tuple[str, str, bytes]] = (),
        inline_logo: tuple[str, bytes] | None = None,
        from_email: str | None = None,
    ) -> None:
        """Queue a message. `attachments` holds (filename, mime type, data).

        `from_email` is the teacher the message is sent on behalf of.
        """
        msg = EmailMessage()
        msg["Subject"] = subject
        msg["To"] = to
        via_gmail = bool(from_email and self.gmail and self.gmail.connected(from_email))
        if via_gmail:
            msg["From"] = formataddr((sender_name, from_email))
        else:
            msg["From"] = formataddr((sender_name, self.config.smtp_from or "attendance@localhost"))
            if from_email:
                msg["Reply-To"] = from_email
        msg.set_content(text)
        if html is not None:
            if inline_logo is not None:
                cid = make_msgid()
                html = html.replace("cid:logo", "cid:" + cid[1:-1])
            msg.add_alternative(html, subtype="html")
            if inline_logo is not None:
                mime, data = inline_logo
                maintype, subtype = mime.split("/", 1)
                msg.get_payload()[1].add_related(data, maintype, subtype, cid=cid)
        for filename, mime, data in attachments:
            maintype, subtype = mime.split("/", 1)
            msg.add_attachment(data, maintype=maintype, subtype=subtype, filename=filename)
        sender = from_email if via_gmail else None
        if self._thread is None or not (via_gmail or self.config.smtp_configured):
            self._deliver(msg, sender)  # nothing slow to wait on
        else:
            self._queue.put((msg, sender))

    def _run(self) -> None:
        while True:
            item = self._queue.get()
            if item is None:
                return
            msg, sender = item
            try:
                self._deliver(msg, sender)
            except Exception:
                log.exception("Failed to send mail to %s", msg["To"])

    def _deliver(self, msg: EmailMessage, gmail_sender: str | None = None) -> None:
        c = self.config
        if gmail_sender and self.gmail.send(gmail_sender, msg):
            log.info("Sent mail via Gmail as %s to %s: %s", gmail_sender, msg["To"], msg["Subject"])
            return
        if gmail_sender:
            # Access was revoked after the message was queued; fall back.
            del msg["From"]
            msg["From"] = formataddr(("", c.smtp_from or "attendance@localhost"))
            msg["Reply-To"] = gmail_sender
        if not c.smtp_configured:
            self.sent.append(msg)
            log.info("SMTP not configured; would send to %s: %s", msg["To"], msg["Subject"])
            return
        context = ssl.create_default_context()
        if c.smtp_ssl:
            server = smtplib.SMTP_SSL(c.smtp_host, c.smtp_port, context=context, timeout=30)
        else:
            server = smtplib.SMTP(c.smtp_host, c.smtp_port, timeout=30)
        with server:
            if c.smtp_starttls and not c.smtp_ssl:
                server.starttls(context=context)
            if c.smtp_user:
                server.login(c.smtp_user, c.smtp_password)
            server.send_message(msg)
        log.info("Sent mail to %s: %s", msg["To"], msg["Subject"])

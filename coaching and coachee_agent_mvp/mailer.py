"""Optional outgoing email for self-service password resets, over SMTP.

Configure with SMTP_HOST, SMTP_PORT (587 for STARTTLS, 465 for SSL), SMTP_USERNAME, SMTP_PASSWORD and
SMTP_FROM. Without SMTP_HOST, resets stay admin-issued links.
"""

from __future__ import annotations

from email.message import EmailMessage
import smtplib
import ssl
from typing import Callable


def smtp_sender(env: dict[str, str]) -> Callable[[str, str, str], None] | None:
    host = env.get("SMTP_HOST", "").strip()
    if not host:
        return None
    port = int(env.get("SMTP_PORT", "").strip() or 587)
    username = env.get("SMTP_USERNAME", "").strip()
    password = env.get("SMTP_PASSWORD", "")
    sender = env.get("SMTP_FROM", "").strip() or username

    def send(to: str, subject: str, body: str) -> None:
        message = EmailMessage()
        message["From"] = sender
        message["To"] = to
        message["Subject"] = subject
        message.set_content(body)
        context = ssl.create_default_context()
        if port == 465:
            with smtplib.SMTP_SSL(host, port, context=context, timeout=20) as smtp:
                if username:
                    smtp.login(username, password)
                smtp.send_message(message)
        else:
            with smtplib.SMTP(host, port, timeout=20) as smtp:
                smtp.starttls(context=context)
                if username:
                    smtp.login(username, password)
                smtp.send_message(message)

    return send

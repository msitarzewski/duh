"""Transactional email sender using stdlib SMTP."""

from __future__ import annotations

import logging
import smtplib
import ssl
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from duh.config.schema import MailConfig

logger = logging.getLogger(__name__)


def send_email(
    config: MailConfig,
    to: str,
    subject: str,
    body_html: str,
    body_text: str | None = None,
) -> None:
    """Send a transactional email via SMTP.

    Raises smtplib.SMTPException on failure.
    """
    if not config.host:
        msg = "Mail not configured (no SMTP host). Set DUH_MAIL_HOST."
        raise smtplib.SMTPException(msg)

    message = MIMEMultipart("alternative")
    message["Subject"] = subject
    message["From"] = (
        f"{config.from_name} <{config.from_address}>"
        if config.from_name
        else config.from_address
    )
    message["To"] = to

    if body_text:
        message.attach(MIMEText(body_text, "plain"))
    message.attach(MIMEText(body_html, "html"))

    if config.encryption == "ssl":
        ctx = ssl.create_default_context()
        with smtplib.SMTP_SSL(config.host, config.port, context=ctx) as server:
            if config.username:
                server.login(config.username, config.password)
            server.sendmail(config.from_address, to, message.as_string())
    else:
        with smtplib.SMTP(config.host, config.port) as server:
            if config.encryption == "tls":
                ctx = ssl.create_default_context()
                server.starttls(context=ctx)
            if config.username:
                server.login(config.username, config.password)
            server.sendmail(config.from_address, to, message.as_string())

    logger.info("Sent email to %s: %s", to, subject)

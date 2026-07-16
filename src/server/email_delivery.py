"""One-time-passcode email delivery.

In development mode (``DEV=TRUE``) the code is logged instead of emailed so
the login flow is testable without an SMTP account.
"""

from __future__ import annotations

import logging
from email.message import EmailMessage

import aiosmtplib

from settings import get_portal_settings

logger = logging.getLogger(__name__)


async def send_one_time_passcode_email(recipient_email: str, code: str) -> None:
    settings = get_portal_settings()
    if settings.dev_mode_enabled or not settings.smtp_host:
        logger.warning(
            "DEV mode one-time passcode for %s: %s (not emailed)", recipient_email, code
        )
        return

    message = EmailMessage()
    message["From"] = settings.smtp_from_address or settings.smtp_username
    message["To"] = recipient_email
    message["Subject"] = "Your Neural Nexus sign-in code"
    message.set_content(
        f"Your Neural Nexus customer portal sign-in code is: {code}\n\n"
        "The code expires in 10 minutes. If you did not request this code, "
        "you can ignore this email."
    )
    await aiosmtplib.send(
        message,
        hostname=settings.smtp_host,
        port=settings.smtp_port,
        username=settings.smtp_username or None,
        password=settings.smtp_password or None,
        start_tls=settings.smtp_port == 587,
        use_tls=settings.smtp_port == 465,
    )

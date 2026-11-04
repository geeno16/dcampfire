import os
from email.message import EmailMessage

import aiosmtplib

from src.common.config import EMAIL_CODE_TTL


def _require(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise RuntimeError(f"Environment variable {name} is not set")
    return value


_SMTP_HOST = _require("SMTP_HOST")
_SMTP_PORT = int(_require("SMTP_PORT"))
_SMTP_USER = _require("SMTP_USER")
_SMTP_PASSWORD = _require("SMTP_PASSWORD")
_SMTP_FROM = _require("SMTP_FROM")


async def send_verification_code(email: str, code: str) -> None:
    minutes = int(EMAIL_CODE_TTL.total_seconds() // 60)

    message = EmailMessage()
    message["From"] = _SMTP_FROM
    message["To"] = email
    message["Subject"] = "Костёр: подтверждение почты"
    message.set_content(
        f"Код для подтверждения почты: {code}\n"
        f"Код действует {minutes} минут."
    )

    await aiosmtplib.send(
        message,
        hostname=_SMTP_HOST,
        port=_SMTP_PORT,
        username=_SMTP_USER,
        password=_SMTP_PASSWORD,
        start_tls=True,
    )

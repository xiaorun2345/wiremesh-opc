"""Deliver high-priority lead notifications through configured channels."""
from __future__ import annotations

import asyncio
import smtplib
from email.message import EmailMessage

from config.settings import settings


async def notify_wecom(title: str, body: str, url: str = "") -> bool:
    if not settings.WECOM_WEBHOOK_URL:
        return False
    import httpx
    quoted_body = body.replace("\n", "\n> ")
    content = f"### {title}\n> {quoted_body}"
    if url:
        content += f"\n> [打开平台查看]({url})"
    async with httpx.AsyncClient(timeout=10) as client:
        response = await client.post(settings.WECOM_WEBHOOK_URL, json={"msgtype": "markdown", "markdown": {"content": content}})
        response.raise_for_status()
        return response.json().get("errcode") == 0


def _send_email_sync(subject: str, body: str) -> bool:
    recipients = [item.strip() for item in settings.NOTIFY_EMAILS.split(",") if item.strip()]
    if not settings.SMTP_HOST or not recipients:
        return False
    message = EmailMessage()
    message["Subject"] = subject
    message["From"] = settings.SMTP_FROM or settings.SMTP_USERNAME
    message["To"] = ", ".join(recipients)
    message.set_content(body)
    with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT, timeout=20) as smtp:
        if settings.SMTP_STARTTLS:
            smtp.starttls()
        if settings.SMTP_USERNAME:
            smtp.login(settings.SMTP_USERNAME, settings.SMTP_PASSWORD)
        smtp.send_message(message)
    return True


async def notify_email(subject: str, body: str) -> bool:
    return await asyncio.to_thread(_send_email_sync, subject, body)

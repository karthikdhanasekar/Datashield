"""
DataShield OSINT - Notification Service
Email, SMS, and push notification delivery
"""
import asyncio
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Optional
from structlog import get_logger

from app.core.config import settings

logger = get_logger(__name__)


async def send_email(
    to_email: str,
    subject: str,
    body: str,
    html_body: Optional[str] = None,
    reply_to: Optional[str] = None,
) -> bool:
    """Send an email via SMTP. Returns True on success."""
    if not settings.SMTP_USERNAME or not settings.SMTP_PASSWORD:
        logger.warning("Email not configured — skipping send", to=to_email, subject=subject)
        return False

    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = f"{settings.EMAIL_FROM_NAME} <{settings.EMAIL_FROM}>"
        msg["To"] = to_email
        if reply_to:
            msg["Reply-To"] = reply_to

        msg.attach(MIMEText(body, "plain"))
        if html_body:
            msg.attach(MIMEText(html_body, "html"))

        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, _send_smtp, msg, to_email)
        logger.info("Email sent", to=to_email, subject=subject)
        return True

    except Exception as e:
        logger.error("Email send failed", error=str(e), to=to_email)
        return False


def _send_smtp(msg: MIMEMultipart, to_email: str):
    """Blocking SMTP send (run in executor)."""
    with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT) as server:
        server.ehlo()
        server.starttls()
        server.login(settings.SMTP_USERNAME, settings.SMTP_PASSWORD)
        server.sendmail(settings.EMAIL_FROM, to_email, msg.as_string())


async def send_verification_email(email: str, name: str, token: str) -> bool:
    """Send email verification link."""
    verify_url = f"{settings.FRONTEND_URL}/verify-email?token={token}"
    
    html_body = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <style>
            body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
            .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
            .header {{ background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 30px; text-align: center; border-radius: 10px 10px 0 0; }}
            .content {{ background: #f9f9f9; padding: 30px; border-radius: 0 0 10px 10px; }}
            .button {{ display: inline-block; background: #667eea; color: white; padding: 12px 30px; text-decoration: none; border-radius: 5px; margin: 20px 0; }}
            .footer {{ text-align: center; margin-top: 20px; color: #666; font-size: 12px; }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>🛡️ Welcome to DataShield OSINT!</h1>
            </div>
            <div class="content">
                <p>Hi <strong>{name}</strong>,</p>
                <p>Thank you for registering with DataShield OSINT! Please verify your email address to activate your account and start protecting your privacy.</p>
                <p style="text-align: center;">
                    <a href="{verify_url}" class="button">Verify Email Address</a>
                </p>
                <p>Or copy and paste this link into your browser:</p>
                <p style="word-break: break-all; background: #fff; padding: 10px; border-radius: 5px;">{verify_url}</p>
                <p><strong>This link expires in 24 hours.</strong></p>
                <p>If you did not create this account, please ignore this email.</p>
            </div>
            <div class="footer">
                <p>© 2024 DataShield OSINT. All rights reserved.</p>
            </div>
        </div>
    </body>
    </html>
    """
    
    body = f"""Hi {name},

Welcome to DataShield OSINT! Please verify your email address to get started.

Click here to verify: {verify_url}

This link expires in 24 hours.

If you did not create this account, please ignore this email.

— The DataShield OSINT Team
"""
    return await send_email(
        to_email=email,
        subject="✅ Verify your DataShield OSINT account",
        body=body,
        html_body=html_body,
    )


async def send_password_reset_email(email: str, name: str, token: str) -> bool:
    """Send password reset link."""
    reset_url = f"{settings.FRONTEND_URL}/reset-password?token={token}"
    
    html_body = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <style>
            body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
            .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
            .header {{ background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 30px; text-align: center; border-radius: 10px 10px 0 0; }}
            .content {{ background: #f9f9f9; padding: 30px; border-radius: 0 0 10px 10px; }}
            .button {{ display: inline-block; background: #667eea; color: white; padding: 12px 30px; text-decoration: none; border-radius: 5px; margin: 20px 0; }}
            .warning {{ background: #fff3cd; border-left: 4px solid #ffc107; padding: 15px; margin: 20px 0; }}
            .footer {{ text-align: center; margin-top: 20px; color: #666; font-size: 12px; }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>🔐 Password Reset Request</h1>
            </div>
            <div class="content">
                <p>Hi <strong>{name}</strong>,</p>
                <p>A password reset was requested for your DataShield OSINT account.</p>
                <p style="text-align: center;">
                    <a href="{reset_url}" class="button">Reset Password</a>
                </p>
                <p>Or copy and paste this link into your browser:</p>
                <p style="word-break: break-all; background: #fff; padding: 10px; border-radius: 5px;">{reset_url}</p>
                <div class="warning">
                    <strong>⚠️ Security Notice:</strong><br>
                    This link expires in 1 hour. If you did not request a password reset, please ignore this email and ensure your account is secure.
                </div>
            </div>
            <div class="footer">
                <p>© 2024 DataShield OSINT. All rights reserved.</p>
            </div>
        </div>
    </body>
    </html>
    """
    
    body = f"""Hi {name},

A password reset was requested for your DataShield OSINT account.

Click here to reset your password: {reset_url}

This link expires in 1 hour.

If you did not request a reset, please ignore this email and ensure your account is secure.

— The DataShield OSINT Team
"""
    return await send_email(
        to_email=email,
        subject="🔐 Reset your DataShield OSINT password",
        body=body,
        html_body=html_body,
    )


async def send_sms(phone_number: str, message: str) -> bool:
    """Send an SMS via Twilio."""
    if not settings.TWILIO_ACCOUNT_SID or not settings.TWILIO_AUTH_TOKEN:
        logger.warning("Twilio not configured — skipping SMS", phone=phone_number)
        return False

    try:
        from twilio.rest import Client
        client = Client(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN)
        client.messages.create(
            body=message,
            from_=settings.TWILIO_PHONE_NUMBER,
            to=phone_number,
        )
        logger.info("SMS sent", phone=phone_number)
        return True
    except Exception as e:
        logger.error("SMS send failed", error=str(e))
        return False


async def send_telegram(chat_id: str, message: str) -> bool:
    """
    Send a Telegram notification via Bot API.

    Setup:
      1. Create a bot via @BotFather on Telegram → get TELEGRAM_BOT_TOKEN
      2. Start a chat with your bot and get your chat_id from
         https://api.telegram.org/bot<TOKEN>/getUpdates
      3. Add to .env:  TELEGRAM_BOT_TOKEN=<token>
      4. Store user's chat_id in their profile (or use the one from settings)

    Falls back silently if not configured.
    """
    token = getattr(settings, "TELEGRAM_BOT_TOKEN", "")
    if not token:
        logger.debug("Telegram not configured — skipping notification")
        return False

    import httpx
    url = f"https://api.telegram.org/bot{token}/sendMessage"

    # Format with Markdown
    formatted = f"🛡️ *DataShield OSINT*\n\n{message}"

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(url, json={
                "chat_id":    chat_id,
                "text":       formatted,
                "parse_mode": "Markdown",
            })
            resp.raise_for_status()
        logger.info("Telegram message sent", chat_id=chat_id)
        return True
    except Exception as e:
        logger.error("Telegram send failed", error=str(e), chat_id=chat_id)
        return False


async def send_breach_alert_telegram(
    chat_id: str,
    email: str,
    finding_count: int,
    critical: int,
    high: int,
    scan_id: str,
) -> bool:
    """
    Send a formatted Telegram breach alert when a scan finds critical/high findings.
    """
    if not chat_id:
        return False

    risk_emoji = "🔴" if critical > 0 else "🟠" if high > 0 else "🟡"
    lines = [
        f"{risk_emoji} *New Exposures Detected*",
        f"",
        f"📧 Scan target: `{email}`",
        f"⚠️ Findings: {finding_count} total",
    ]
    if critical > 0:
        lines.append(f"🔴 Critical: {critical}")
    if high > 0:
        lines.append(f"🟠 High: {high}")
    lines += [
        f"",
        f"View findings: http://localhost:3000/dashboard/scan/{scan_id}",
    ]

    return await send_telegram(chat_id, "\n".join(lines))

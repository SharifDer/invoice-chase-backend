from twilio.rest import Client
from config import settings
import resend
from database import Database
from logger import get_logger
from config import settings
from .utils import fetch_business_info
from .dbUtils import set_msgs_sent_count, fetch_user_currency
from Utils.rules import can_send_email, can_send_sms
import asyncio
from datetime import datetime
from typing import Tuple


resend.api_key = settings.resend_api_key
logger = get_logger(__name__)
# ---------- Twilio SMS Sender ----------
async def send_sms(to_number: str, body: str, from_number: str = None):
    """
    Sends an SMS using Twilio.
    """
    try:
        client = Client(settings.twilio_account_sid, settings.twilio_auth_token)
        message = client.messages.create(
            body=body,
            from_=from_number or settings.twilio_number,
            to=to_number
        )
        return message.sid
    except Exception as e:
        print(f"❌ SMS send failed: {e}")
        return None

async def send_email(to_email: str, subject: str, html_content: str, text_content: str,
                     from_email: str = settings.EMAIL_FROM_SYSTEM,
                     reply_to: str = None):
    """
    Sends an email using the Resend API, with HTML + plain-text.
    """
    try:
        params = {
            "from": from_email,
            "to": [to_email],
            "subject": subject,
            "html": html_content,
            "text": text_content  # critical for deliverability
        }
        if reply_to:
            params["reply_to"] = reply_to
        loop = asyncio.get_running_loop()
        response = await loop.run_in_executor(None, resend.Emails.send, params)
        logger.info(f"✅ Email notification sent to {to_email}")
        return response
    except Exception as e:
        print(f"❌ Email send failed: {e}")
        return None


def generate_welcome_email(
    business_name: str,
    client_name: str,
    login_link: str = "https://pursuepayments.com"
) -> Tuple[str, str, str]:
    """
    Generates a professional, spam-friendly HTML and plain-text welcome email
    that encourages the user to start creating invoices and recording payments.
    Returns (subject, html_content, text_content)
    """
    subject = f"Welcome to {business_name}, {client_name}! Let's get started"

    html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{subject}</title>
<style>
body {{ margin:0; padding:0; font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,Arial,'Helvetica Neue',sans-serif; background:#f3f4f6; }}
.container {{ max-width:600px; margin:24px auto; background:#ffffff; border-radius:8px; overflow:hidden; border:1px solid #e6edf3; }}
.header {{ background:linear-gradient(90deg,#3b82f6,#1e40af); padding:20px; color:#fff; text-align:center; }}
.header h1 {{ margin:0; font-size:20px; font-weight:700; }}
.content {{ padding:28px; color:#0f172a; line-height:1.5; }}
.btn {{ display:inline-block; padding:12px 20px; border-radius:6px; text-decoration:none; font-weight:600; margin-top:18px; background:#3b82f6; color:#fff; }}
.footer {{ padding:24px; background:#f8fafc; color:#64748b; font-size:12px; text-align:center; line-height:1.5; }}
</style>
</head>
<body>
<div class="container">
<div class="header"><h1>Welcome to {business_name}, {client_name}!</h1></div>
<div class="content">
<p>Hi {client_name},</p>
<p>We're excited to have you on board! {business_name} makes it easy to manage your finances, track payments, and stay on top of your business.</p>
<p>Here’s what you can do next:</p>
<ul>
<li>Create your first invoice in seconds</li>
<li>Record payments and monitor cash flow effortlessly</li>
<li>Explore your dashboard for insights and reports</li>
</ul>
<p>Getting started is quick—just click the button below to log in and take control of your business finances:</p>
<a href="{login_link}" class="btn">Get Started</a>
<p>If you have any questions or need assistance, our support team is always ready to help.</p>
<p>- The {business_name} Team</p>
</div>
<div class="footer">
<p>Sent via {business_name}</p>
<p>123 Main St, Riyadh, Saudi Arabia</p>
<p>&copy; {datetime.now().year} {business_name}</p>
</div>
</div>
</body>
</html>"""

    text_content = f"""Welcome to {business_name}, {client_name}!

Hi {client_name},

We're excited to have you on board! {business_name} makes it easy to manage your finances, track payments, and stay on top of your business.

Here’s what you can do next:
- Create your first invoice in seconds
- Record payments and monitor cash flow effortlessly
- Explore your dashboard for insights and reports

Get started now: {login_link}

If you have any questions or need assistance, our support team is always ready to help.

- The {business_name} Team
Sent via {business_name}
123 Main St, Riyadh, Saudi Arabia
© {datetime.now().year} {business_name}
"""

    return subject, html_content, text_content

def generate_transaction_email(
    business_name: str,
    client_name: str,
    transaction_type: str,
    amount: float,
    currency: str = "$"
):
    """
    Returns subject, html_content, text_content.
    Uses only existing parameters. Plain-text added. Professional styling for deliverability.
    """
    pretty_type = "Payment" if transaction_type == "payment" else "Invoice"
    
    # Subject: clear and specific, no ALL CAPS, no spammy punctuation
    subject = f"New {pretty_type} ({currency}{amount:,.2f}) from {business_name}"
    
    # Fallback link for CTA (safe default for MVP)
    cta_link = "https://pursuepayments.com"  # points to your app home/login
    
    # HTML content
    html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{subject}</title>
<style>
body {{ margin:0; padding:0; font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,Arial,'Helvetica Neue',sans-serif; background:#f3f4f6; }}
.container {{ max-width:600px; margin:24px auto; background:#ffffff; border-radius:8px; overflow:hidden; border:1px solid #e6edf3; }}
.header {{ background:linear-gradient(90deg,#10b981,#059669); padding:20px; color:#fff; text-align:center; }}
.header h1 {{ margin:0; font-size:20px; font-weight:700; }}
.content {{ padding:28px; color:#0f172a; line-height:1.5; }}
.btn {{ display:inline-block; padding:12px 20px; border-radius:6px; text-decoration:none; font-weight:600; margin-top:18px; background:#10b981; color:#fff; }}
.footer {{ padding:24px; background:#f8fafc; color:#64748b; font-size:12px; text-align:center; line-height:1.5; }}
</style>
</head>
<body>
<div class="container">
<div class="header"><h1>New {pretty_type} Notification</h1></div>
<div class="content">
<p>Dear {client_name},</p>
<p>A new <strong>{pretty_type.lower()}</strong> has been recorded for <strong>{currency}{amount:,.2f}</strong>.</p>
<p>Click below to view your details:</p>
<a href="{cta_link}" class="btn">View {pretty_type} Details</a>
<p>If you have questions, reply directly to this email.</p>
<p>- Pursue Payments Team</p>
</div>
<div class="footer">
  <p>Sent via Pursue Payments</p>
  <p>123 Main St, Riyadh, Saudi Arabia</p> <!-- default website owner address -->
  <p>&copy; {datetime.now().year} {business_name}</p>
</div>
</div>
</body>
</html>"""

    # Plain-text content (mirrors HTML)
    text_content = f"""New {pretty_type} ({currency}{amount:,.2f}) from {business_name}

Dear {client_name},

A new {pretty_type.lower()} has been recorded for {currency}{amount:,.2f}.

View {pretty_type} Details: {cta_link}

If you have questions, reply directly to this email.

Sent via Pursue Payments
123 Main St, Riyadh, Saudi Arabia
© 2025 {business_name}
"""
    return subject, html_content, text_content


def generate_reminder_email(
    business_name: str,
    client_name: str,
    balance: float,
    currency: str = "$",
    urgent: bool = False
) -> Tuple[str, str, str]:
    """
    Generates professional, spam-friendly HTML and plain-text reminder email.
    Uses only existing parameters. Returns (subject, html_content, text_content)
    """
    # Subject: clear, concise, avoids spammy ALL CAPS / punctuation
    subject = f"{'Urgent' if urgent else 'Payment'} Reminder: {currency}{balance:,.2f} Outstanding"

    # Intro and action phrasing
    intro_text = (
        f"It has been some time since we received your payment. Your account with {business_name} shows an outstanding balance of <strong>{currency}{balance:,.2f}</strong>."
        if urgent
        else f"This is an <strong>automated balance reminder</strong> from <strong>{business_name}</strong>."
    )

    action_text = (
        f"We kindly remind you that your account currently has an outstanding balance of <strong>{currency}{balance:,.2f}</strong>. Your prompt attention to this matter is appreciated."
        if urgent
        else f"We wanted to inform you that your account currently reflects a balance of <strong>{currency}{balance:,.2f}</strong>. Please review at your convenience."
    )

    # Fallback link for CTA (safe, points to your app)
    cta_link = "https://pursuepayments.com"  # MVP-safe link to app login/home

    # HTML version (pro layout)
    html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{subject}</title>
<style>
body {{ margin:0; padding:0; font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,Arial,'Helvetica Neue',sans-serif; background:#f3f4f6; }}
.container {{ max-width:600px; margin:24px auto; background:#ffffff; border-radius:8px; overflow:hidden; border:1px solid #e6edf3; }}
.header {{ background:linear-gradient(90deg,#{'ef4444' if urgent else '3b82f6'},#{'b91c1c' if urgent else '1e40af'}); padding:20px; color:#fff; text-align:center; }}
.header h1 {{ margin:0; font-size:20px; font-weight:700; }}
.content {{ padding:28px; color:#0f172a; line-height:1.5; }}
.btn {{ display:inline-block; padding:12px 20px; border-radius:6px; text-decoration:none; font-weight:600; margin-top:18px; background:{'#ef4444' if urgent else '#3b82f6'}; color:#fff; }}
.footer {{ padding:24px; background:#f8fafc; color:#64748b; font-size:12px; text-align:center; line-height:1.5; }}
</style>
</head>
<body>
<div class="container">
<div class="header">
<h1>{'Urgent Payment Reminder' if urgent else 'Automated Balance Reminder'}</h1>
</div>

<div class="content">
<p>Dear {client_name},</p>
<p>{intro_text}</p>
<p>{action_text}</p>
<div style="text-align:center;">
<a href="{cta_link}" class="btn">{'Pay Now' if urgent else 'View Account'}</a>
</div>
<p style="margin-top:20px;">Thank you for your time!</p>
<p>— Pursue Payments Team</p>
</div>
<div class="footer">
<p>Sent via Pursue Payments</p>
<p>&copy; {datetime.now().year} {business_name}</p>
</div>
</div>
</body>
</html>"""

    # Plain-text version (mirrors HTML)
    text_content = f"""{'Urgent' if urgent else 'Payment'} Reminder: {currency}{balance:,.2f} Outstanding

Dear {client_name},

{intro_text.replace('<strong>', '').replace('</strong>', '')}

{action_text.replace('<strong>', '').replace('</strong>', '')}

View account details: {cta_link}

Thank you for your time!

— The {business_name} Team
Sent via Pursue Payments
© {datetime.now().year} {business_name}
"""

    return subject, html_content, text_content



def generate_reminder_sms(business_name: str, client_name: str, balance: float, currency: str = "$", urgent: bool = False) -> str:
    """
    Generate professional SMS text for a balance reminder.
    """
    if urgent:
        # Gentle professional notification
        sms_text = (
            f"Dear {client_name}, this is a reminder from {business_name} that your account shows an outstanding balance of "
            f"{currency}{balance:,.2f}. Thank you for your attention."
        )
    else:
        # Standard automated reminder
        sms_text = (
            f"Hello {client_name}, {business_name} would like to inform you that your account currently reflects a balance of "
            f"{currency}{balance:,.2f}."
        )
    
    return sms_text


def generate_transaction_sms(business_name: str, client_name: str, transaction_type: str, amount: float, currency: str = "$") -> str:
    """
    Generate professional SMS text for a transaction notification,
    indicating that the amount has been added to the account/balance.
    """
    if transaction_type.lower() == "payment":
        sms_text = (
            f"Hello {client_name}, a payment of {amount:,.2f} {currency} has been received and added to your account with {business_name}."
        )
    else:  # invoice
        sms_text = (
            f"Hello {client_name}, a new invoice of {amount:,.2f} {currency} has been issued and recorded in your account with {business_name}."
        )
    
    return sms_text

# utils/notifications.py




async def notify_transaction_creation(
    user_data : dict,
    client_id: int,
    client_name: str,
    transaction_type: str,
    amount: float,
    client_email: str = None,
    client_phone: str = None,
):
    """
    Check notification settings and send transaction notification (email or SMS).
    """
    user_id = user_data["user_id"]
    user_email = user_data["email"]
    email_from = settings.EMAIL_FROM_INVOICE if transaction_type == 'invoice' else settings.EMAIL_FROM_RECEIPT 
    currency_data = await fetch_user_currency(user_id)
    currency = currency_data["currency_name"] if currency_data else "USD"

    business_name = "Unknown Business"
    business_info = await fetch_business_info(user_id)
    if business_info and business_info.get("business_name"):
        business_name = business_info["business_name"]
    else:
        row = await Database.fetch_one("SELECT name FROM users WHERE id=?", (user_id,))
        if row and row.get("name"):
            business_name = row["name"]
    # 1️⃣ Fetch client-specific settings (if any)
    client_settings = await Database.fetch_one(
        "SELECT * FROM client_settings WHERE user_id=? AND client_id=?",
        (user_id, client_id),
    )

    # 2️⃣ Fallback to user settings if client settings not found
    if client_settings:
        send_notifications = client_settings["send_transaction_notifications"]
        communication_method = client_settings["communication_method"]
    else:
        user_settings = await Database.fetch_one(
            "SELECT * FROM user_settings WHERE user_id=?",
            (user_id,),
        )
        if not user_settings:
            # logger.info(f"No notification settings found for user {user_id}")
            return  # No settings at all → skip notification
        send_notifications = user_settings["send_transaction_notifications"]
        communication_method = user_settings["communication_method"]

    # 3️⃣ Check if notifications are enabled
    if not send_notifications:
        logger.info(f"Transaction notifications disabled for client {client_id}")
        return

    # 4️⃣ Send according to communication method
    try:
        if communication_method == "sms":
            if not await can_send_sms(user_id , user_data["plan_type"]):
                logger.info(f"SMS limit reached for user {user_id}, skipping SMS.")
            if not client_phone:
                logger.warning(f"Skipping SMS — no phone number for client {client_name}")
                return

            body = generate_transaction_sms(
                business_name, client_name, transaction_type, amount, currency
            )
            await send_sms(to_number=client_phone, body=body)
            logger.info(f"✅ SMS notification sent to {client_phone} for {transaction_type}")

        else:  # email
            if not await can_send_email(user_id , user_data["plan_type"]):
                logger.info(f"Email limit reached for user {user_id}, skipping email.")
            if not client_email:
                logger.warning(f"Skipping Email — no email for client {client_name}")
                return

            subject, html, email_text = generate_transaction_email(
                business_name, client_name, transaction_type, amount, currency
            )
            await send_email(to_email=client_email, subject=subject, html_content=html ,
                              text_content=email_text,
                              from_email=email_from, reply_to=user_email)
            # logger.info(f"✅ Email notification sent to {client_email} for {transaction_type}")
        await set_msgs_sent_count(user_id , communication_method , msg_type="notification")
    except Exception as e:
        logger.error(f"❌ Failed to send transaction notification: {e}")

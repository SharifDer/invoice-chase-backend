from twilio.rest import Client
from config import settings
import resend
from database import Database
from logger import get_logger
from config import settings
from .utils import fetch_business_info
from .dbUtils import set_msgs_sent_count, fetch_user_currency
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

async def send_email(to_email: str, subject: str, html_content: str, from_email: str = "onboarding@resend.dev"):
    """
    Sends an email using the Resend API.
    """
    resend.api_key = settings.resend_api_key
    try:
        params = {
            "from": from_email,
            "to": [to_email],
            "subject": subject,
            "html": html_content,
        }
        response = resend.Emails.send(params)
        return response
    except Exception as e:
        print(f"❌ Email send failed: {e}")
        return None


def generate_transaction_email(business_name: str, client_name : str , transaction_type: str, amount: float , currency : str = "$"):
    pretty_type = "Payment" if transaction_type == "payment" else "Invoice"
    subject = f"New {pretty_type} Recorded — {amount:,.2f} {currency} {('Received' if transaction_type == 'payment' else 'Issued')}"
    html = f"""
    <div style="font-family: 'Segoe UI', Arial, sans-serif; padding: 24px; background-color: #f9fafb;">
        <div style="max-width: 600px; margin: 0 auto; background: #ffffff; border-radius: 10px; box-shadow: 0 2px 6px rgba(0,0,0,0.05); overflow: hidden;">
            <div style="background: linear-gradient(90deg, #16a34a, #15803d); color: white; padding: 20px 30px;">
                <h2 style="margin: 0;">{business_name}</h2>
                <p style="margin: 4px 0 0;">Automated Transaction Notification</p>
            </div>
            <div style="padding: 30px; color: #374151;">
                <p>Dear {client_name},</p>
                <p>This is an <strong>automated update</strong> from <strong>{business_name}</strong>.</p>
                <p>A new <strong>{pretty_type.lower()}</strong> has been recorded for <strong>{currency}{amount:,.2f}</strong>.</p>
                <p style="margin-top: 20px;">Please review your account for full details.</p>
            </div>
        </div>
    </div>
    """
    return subject, html

def generate_reminder_email(business_name: str, client_name : str ,  balance: float, currency: str = "$", urgent: bool = False):
    # Subject line
    subject = f"{'Urgent Payment Reminder ' if urgent else 'Automated Balance Reminder — Outstanding'} {currency}{balance:,.2f}"

    # Intro and action text depending on urgency
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

    # HTML email template
    html = f"""
    <div style="font-family: 'Segoe UI', Arial, sans-serif; padding: 24px; background-color: #f9fafb;">
        <div style="max-width: 600px; margin: 0 auto; background: #ffffff; border-radius: 10px; box-shadow: 0 2px 6px rgba(0,0,0,0.05); overflow: hidden;">
            <div style="background: linear-gradient(90deg, #2563eb, #1e40af); color: white; padding: 20px 30px;">
                <h2 style="margin: 0;">{business_name}</h2>
                <p style="margin: 4px 0 0;">{'Urgent Payment Reminder' if urgent else 'Automated Payment Reminder'}</p>
            </div>
            <div style="padding: 30px; color: #374151;">
                <p>Dear {client_name},</p>
                <p>{intro_text}</p>
                <p>{action_text}</p>
                <p style="margin-top: 20px;">Thank you for your time!</p>
            </div>
        </div>
    </div>
    """
    return subject, html



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
    user_id: int,
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
            if not client_phone:
                logger.warning(f"Skipping SMS — no phone number for client {client_name}")
                return

            body = generate_transaction_sms(
                business_name, client_name, transaction_type, amount, currency
            )
            await send_sms(to_number=client_phone, body=body)
            logger.info(f"✅ SMS notification sent to {client_phone} for {transaction_type}")

        else:  # email
            if not client_email:
                logger.warning(f"Skipping Email — no email for client {client_name}")
                return

            subject, html = generate_transaction_email(
                business_name, client_name, transaction_type, amount, currency
            )
            await send_email(to_email=client_email, subject=subject, html_content=html)
            logger.info(f"✅ Email notification sent to {client_email} for {transaction_type}")
        set_msgs_sent_count(communication_method , user_id)
    except Exception as e:
        logger.error(f"❌ Failed to send transaction notification: {e}")

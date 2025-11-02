from database import Database
from datetime import datetime, timezone
from fastapi import HTTPException, status
from logger import get_logger
from schemas.responses import MonthlyUsageStats
from config import settings

logger = get_logger(__name__)

async def get_client_communication_method(user_id: int, client: dict):
    """
    Returns the effective communication method and contact for a client.
    Output:
        - method: 'email' or 'sms'
        - contact: email address or phone number
        - reason: (optional) string if no valid contact is found
    """
    # Fetch settings
    client_settings = await Database.fetch_one(
        "SELECT communication_method FROM client_settings WHERE user_id = ? AND client_id = ?",
        (user_id, client["id"])
    )
    user_settings = await Database.fetch_one(
        "SELECT communication_method FROM user_settings WHERE user_id = ?",
        (user_id,)
    )

    # Determine effective method
    method = (
        client_settings.get("communication_method")
        if client_settings and client_settings.get("communication_method")
        else (user_settings.get("communication_method") if user_settings else "email")
    )

    # Determine contact
    contact = None
    if method == "email":
        contact = client.get("email")
        if not contact:
            return None, None, "Client has no email"
    elif method == "sms":
        contact = client.get("phone")
        if not contact:
            return None, None, "Client has no phone"

    return method, contact, None

async def get_client_effective_settings(user_id: int, client: dict):
    """
    Determine if reminders are enabled for this client and which method to use.
    Returns:
        - enabled (bool)
        - method ('email' or 'sms')
        - contact (email or phone)
        - reason (str, if skipped)
    """
    # Fetch client-specific settings
    client_settings = await Database.fetch_one(
        "SELECT * FROM client_settings WHERE user_id = ? AND client_id = ?", 
        (user_id, client["id"])
    )

    # Fetch user-level defaults
    user_settings = await Database.fetch_one(
        "SELECT * FROM user_settings WHERE user_id = ?", 
        (user_id,)
    )

    # Determine if reminders enabled
    enabled = True
    if client_settings and client_settings.get("send_automated_reminders") is not None:
        enabled = client_settings["send_automated_reminders"]
    elif user_settings:
        enabled = user_settings.get("send_automated_reminders", True)
    
    if not enabled:
        return False, None, None, "Reminders disabled"

    # Determine communication method
    method = (client_settings.get("communication_method") 
              if client_settings and client_settings.get("communication_method")
              else user_settings.get("communication_method", "email"))

    # Determine contact info
    contact = None
    if method == "email":
        contact = client.get("email")
        if not contact:
            return False, method, None, "Client has no email"
    elif method == "sms":
        contact = client.get("phone")
        if not contact:
            return False, method, None, "Client has no phone"

    return True, method, contact, None

# utils/client_helpers.py





async def check_existing_client(user_id: int, email: str):
    """Check if a client with the same email already exists for this user"""
    if not email:
        return None
    existing_client = await Database.fetch_one(
        "SELECT id FROM clients WHERE user_id=? AND email=?",
        (user_id, email)
    )
    if existing_client:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Client with this email already exists"
        )
    return None


async def insert_client_record(user_id: int, name: str, email: str, phone: str, company: str):
    """Insert a new client and return the created client record"""
    query = """
        INSERT INTO clients (user_id, name, email, phone, company)
        VALUES (?, ?, ?, ?, ?)
    """
    await Database.execute(query, (user_id, name, email, phone, company))

    # Fetch the just-created client (same logic as before)
    created_client = await Database.fetch_one(
        "SELECT * FROM clients WHERE user_id=? AND name=? ORDER BY created_at DESC LIMIT 1",
        (user_id, name)
    )
    logger.info(f"Client created: {name} for user {user_id}")
    return created_client


async def apply_custom_client_settings(user_id: int, client_id: int, ns):
    """Insert custom client notification settings (only if user unchecked apply_user_settings)"""
    await Database.execute(
        """
        INSERT INTO client_settings (
            user_id, client_id, communication_method,
            send_transaction_notifications, send_automated_reminders,
            reminder_frequency_days, reminder_minimum_balance, reminder_next_date
        )
        VALUES (?, ?, ?, ?, ?, ?, ? , CASE WHEN ? IS NOT NULL 
     THEN DATETIME(STRFTIME('%Y-%m-%d %H:00:00', DATETIME('now', '+' || ? || ' days')))
     ELSE NULL END)
        """,
        (
            user_id,
            client_id,
            ns.communication_method,
            ns.send_transaction_notifications,
            ns.send_automated_reminders,
            ns.reminder_frequency_days,
            ns.reminder_minimum_balance,
            ns.reminder_frequency_days,
            ns.reminder_frequency_days
       
        ),
    )



async def set_msgs_sent_count(user_id: int, communication_method: str, msg_type: str):
    """
    Increment the user's SMS/email count for the current month using UPSERT.
    
    :param user_id: ID of the user
    :param communication_method: "email" or "sms"
    :param msg_type: "reminder" or "notification"
    """
    now = datetime.now(timezone.utc)  # timezone-aware UTC datetime
    year = now.year
    month = now.month

    # Determine which column to increment
    if communication_method == "email":
        if msg_type == "reminder":
            column = "email_reminders_sent_count"
        elif msg_type == "notification":
            column = "email_notifications_sent_count"
        else:
            raise ValueError("Invalid msg_type for email")
    elif communication_method == "sms":
        if msg_type == "reminder":
            column = "sms_reminders_sent_count"
        elif msg_type == "notification":
            column = "sms_notifications_sent_count"
        else:
            raise ValueError("Invalid msg_type for sms")
    else:
        raise ValueError("Invalid communication_method")

    # UPSERT: insert if not exists, else increment counter
    await Database.execute(
        f"""
        INSERT INTO user_monthly_usage (user_id, year, month, {column})
        VALUES (?, ?, ?, 1)
        ON CONFLICT(user_id, year, month)
        DO UPDATE SET {column} = {column} + 1
        """,
        (user_id, year, month)
    )


async def fetch_user_currency(user_id : int):
    currency = await Database.fetch_one(
        "SELECT currency,currency_symobl FROM users WHERE id = ?",
        (user_id,)
    )
    return {
         "currency_symbol" : currency["currency_symobl"],
         "currency_name" : currency["currency"]
    }





async def get_user_monthly_usage(user_id: int , user_data : dict) -> MonthlyUsageStats:

    now = datetime.now(timezone.utc)
    year, month = now.year, now.month

    # Get usage record for this month
    sql = """
        SELECT 
            sms_reminders_sent_count + sms_notifications_sent_count AS total_sms_sent,
            email_reminders_sent_count + email_notifications_sent_count AS total_email_sent,
            sms_reminders_sent_count, sms_notifications_sent_count,
            email_reminders_sent_count, email_notifications_sent_count
        FROM user_monthly_usage
        WHERE user_id = ? AND year = ? AND month = ?;
    """
    row = await Database.fetch_one(sql, (user_id, year, month))
    if not row:
        # No record means 0 usage
        row = {
            "total_sms_sent": 0,
            "total_email_sent": 0,
            "sms_reminders_sent_count": 0,
            "sms_notifications_sent_count": 0,
            "email_reminders_sent_count": 0,
            "email_notifications_sent_count": 0
        }

    plan = user_data["plan_type"]
    sms_limits = settings.sms_limits

    sms_limit = sms_limits.get(plan.lower(), 0)

    return MonthlyUsageStats(
    reminders_sent_this_month=row["sms_reminders_sent_count"] + row["email_reminders_sent_count"],
    sms_reminders_sent_this_month = row["sms_reminders_sent_count"] ,
    email_reminders_sent_this_month = row["email_reminders_sent_count"],
    notifications_sent_this_month=row["sms_notifications_sent_count"] + row["email_notifications_sent_count"],
    sms_notifications_sent_this_month = row["sms_notifications_sent_count"] ,
    email_notifications_sent_this_month = row["email_notifications_sent_count"],
    emails_sent=row["total_email_sent"],
    sms_sent=row["total_sms_sent"],
    sms_limit=sms_limit,
    sms_left=max(0, sms_limit - row["total_sms_sent"]),
)
     

async def get_user_data_by_id(user_id : int):
    user_info = await Database.fetch_one(
        "SELECT * FROM users WHERE id = ?",
        (user_id,))
    return {
        "user_id" : user_info["id"],
        "firebase_id": user_info["uid"],
        "name": user_info.get("name", user_info.get("email", "")),
        "email": user_info.get("email", None),
        "currency" : user_info["currency"],
        "currency_symobl" : user_info["currency_symobl"],
        "plan_type" : user_info["plan_type"],
        "trial_end_date" : user_info["trial_end_date"],

    }


async def get_users_data_by_ids(user_ids: list[int]) -> dict[int, dict]:
    """
    Fetch multiple users' data in one query.
    Returns a dictionary keyed by user_id.
    """
    if not user_ids:
        return {}

    placeholders = ",".join(["?"] * len(user_ids))
    query = f"SELECT * FROM users WHERE id IN ({placeholders})"
    rows = await Database.fetch_all(query, tuple(user_ids))

    user_map = {}
    for user_info in rows:
        user_map[user_info["id"]] = {
            "user_id": user_info["id"],
            "firebase_id": user_info.get("firebase_uid"),
            "name": user_info.get("name") or user_info.get("email", ""),
            "email": user_info.get("email"),
            "currency": user_info.get("currency"),
            "currency_symobl": user_info.get("currency_symobl"),
            "plan_type": user_info.get("plan_type"),
            "trial_end_date": user_info.get("trial_end_date"),
        }

    return user_map


async def get_business_names_by_user_ids(user_ids: list[int]) -> dict[int, str]:
    """
    Fetch business names for multiple users in one query.
    Returns a dict mapping user_id -> business_name (or None if missing).
    """
    if not user_ids:
        return {}

    placeholders = ",".join(["?"] * len(user_ids))
    query = f"SELECT user_id, business_name FROM business_info WHERE user_id IN ({placeholders})"
    rows = await Database.fetch_all(query, tuple(user_ids))

    business_map = {row["user_id"]: row.get("business_name") for row in rows}
    return business_map
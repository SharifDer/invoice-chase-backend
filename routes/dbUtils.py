from database import Database

from fastapi import HTTPException, status
from logger import get_logger

logger = get_logger(__name__)
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


async def set_msgs_sent_count(communication_method : str , user_id : int):
    
    if communication_method == "email" :
         await Database.execute(
                    "UPDATE users SET email_sent_count = email_sent_count + 1 WHERE id = ?",
                    (user_id,)
                )
    elif communication_method == "sms":
        await Database.execute(
            "UPDATE users SET sms_sent_count = sms_sent_count + 1 WHERE id = ?",
            (user_id,)
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
      

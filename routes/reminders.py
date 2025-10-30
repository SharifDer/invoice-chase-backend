
from config import settings
from fastapi import APIRouter, Depends
from schemas.responses import TestReminderRes
from schemas.requests import EmailSendReq, UrgentReminderReq
from auth import get_current_user
from .utils import (
    get_clients_balance, get_user_business_info)
from .remindersUtils import (send_sms, send_email, generate_transaction_email,
                             generate_reminder_email , generate_reminder_sms , generate_transaction_sms)

from .dbUtils import get_client_effective_settings, set_msgs_sent_count, get_client_communication_method
from datetime import datetime, timedelta
from database import Database

router = APIRouter()


async def send_reminder_for_client(client: dict, user_id: int, urgent=False):
    """
    Sends a single urgent reminder (email or SMS) for a client.
    Returns a dict suitable for results list.
    """
    success = False
    method = None
    contact = None
    if urgent:
      method, contact, _ = await get_client_communication_method(user_id=user_id , client=client)
    
    else :
        enabled, method, contact, reason = await get_client_effective_settings(user_id, client)

        if not enabled:
            return {
                "client_id": client["id"],
                "success": False,
                "method": method,
                "sent_to": None,
                "message": reason
            }

    # Generate message
    if method == "email":
        subject, html_content, email_text = generate_reminder_email(
            business_name=client['business_name'],
            client_name=client["name"],
            balance=client["balance"],
            currency=client['currency'],
            urgent=urgent
        )
        user_email = await Database.fetch_one(
        "SELECT email FROM users WHERE id = ?",
        (user_id,)
    )
        success = bool(await send_email(to_email=contact, subject=subject,
                                         html_content=html_content,text_content=email_text,
                                        from_email=settings.EMAIL_FROM_REMINDER
                                         ,reply_to=user_email["email"]))

        if success :
                await Database.execute(
                    "UPDATE users SET email_sent_count = email_sent_count + 1 WHERE id = ?",
                    (user_id,)
                )
    elif method == "sms":
        body = generate_reminder_sms(
            business_name=client['business_name'],
            client_name=client["name"],
            balance=client["balance"],
            currency=client['currency'],
            urgent=urgent
        )
        success = bool(await send_sms(to_number=contact, body=body))
        if success :
               await Database.execute(
                    "UPDATE users SET sms_sent_count = sms_sent_count + 1 WHERE id = ?",
                    (user_id,)
                )
    else :
        return {
            "client_id": client["id"],
            "success": False,
            "method": method,
            "sent_to": None,
            "message": f"Unknown communication method: {method}"
        }


    return {
        "client_id": client["id"],
        "success": success,
        "method": method,
        "sent_to": contact if success else None,
        "message": None if success else "Failed to send"
    }




@router.post("/Send_test_email", response_model=TestReminderRes)
async def send_test_email(
    request: EmailSendReq,
    current_user: dict = Depends(get_current_user)
):
    # user_id = 1 
    user_id = current_user["user_id"]
    user_info = await get_user_business_info(user_id)

    if not user_info:
        return TestReminderRes(
            status="Failed",
            message="User not found",
            sent_to=None
        )

    if request.type == "reminder":
        subject, html_content = generate_reminder_email(
            user_info["business_name"],
            user_info["name"],
            balance=350.75,
            currency=user_info["currency"]
        )
        html_content += "<p style='text-align:center; color:#9ca3af; font-size:13px;'>This is a <strong>test reminder email</strong> for preview purposes only.</p>"

    else:
        subject, html_content, email_text = generate_transaction_email(
            user_info["business_name"],
            user_info["name"],
            transaction_type="payment",
            amount=150.25,
            currency=user_info["currency"]
        )
        html_content += "<p style='text-align:center; color:#9ca3af; font-size:13px;'>This is a <strong>test transaction notification</strong> for preview purposes only.</p>"

    email_from = settings.EMAIL_FROM_SYSTEM

    response = await send_email(
        to_email=user_info["email"],
        subject=subject,
        html_content=html_content,
        text_content=email_text,
        from_email=email_from
    )
    if response :
        await Database.execute(
            "UPDATE users SET email_sent_count = email_sent_count + 1 WHERE id = ?",
            (user_id,)
                )
    return TestReminderRes(
        status="Success" if response else "Failed",
        message="Test email sent successfully" if response else "Failed to send test email",
        sent_to=user_info["email"]
    )





# ---------- Test SMS Endpoint ----------
@router.post("/Send_test_sms", response_model=TestReminderRes)
async def send_test_sms(request: EmailSendReq,
                        current_user : dict = Depends(get_current_user)
                        ):
    # user_id = 1
    user_id = current_user["user_id"]
    user_info = await get_user_business_info(user_id)

    if not user_info or not user_info.get("phone"):
        return TestReminderRes(
            status="Failed",
            message="User has no phone number",
            sent_to=None
        )

    if request.type == "reminder":
        body = generate_reminder_sms(
            business_name=user_info["business_name"],
            client_name=user_info["name"],
            balance=350.75,
            urgent=False
        )
        body += " [This is a test reminder SMS for preview purposes only.]"
    else:
        body = generate_transaction_sms(
            business_name=user_info["business_name"],
            client_name=user_info["name"],
            transaction_type="payment",
            amount=150.25
        )
        body += " [This is a test transaction SMS for preview purposes only.]"

    sid = await send_sms(
        to_number=user_info["phone"],
        body=body
    )
    if sid :
        await Database.execute(
            "UPDATE users SET sms_sent_count = sms_sent_count + 1 WHERE id = ?",
            (user_id,)
            )

    return TestReminderRes(
        status="Success" if sid else "Failed",
        message="Test SMS sent successfully" if sid else "Failed to send test SMS",
        sent_to=user_info["phone"] if sid else None
    )

@router.post("/Send_urgent_reminders")
async def send_urgent_reminders(request: UrgentReminderReq,
                                current_user = Depends(get_current_user)
                                ):
    user_id = current_user['user_id']
    # user_id = 1 
    clients = await get_clients_balance(user_id, request.client_ids)

    results = []
    for client in clients:
        result = await send_reminder_for_client(client, user_id, urgent=True)
        results.append(result)

    return {
        "success": True,
        "results": results,
        "message": "Urgent reminders processed"
    }







async def _fetch_candidates_due(grace_minutes: int = 10):
    """
    Fetch candidate clients whose reminder_next_date is due (client_settings or user_settings fallback).
    """
    now = datetime.utcnow()
    hour_fragment = now.strftime("%Y-%m-%dT%H")
    cutoff = (now + timedelta(minutes=grace_minutes)).isoformat()

    # Select all clients + their related settings (if any)
    query = """
        SELECT
            c.id AS id,
            c.user_id AS user_id,
            c.name AS name,
            c.email AS email,
            c.phone AS phone,
            cs.reminder_next_date AS client_next,
            us.reminder_next_date AS user_next,
            IFNULL(SUM(CASE WHEN t.type = 'invoice' THEN t.amount ELSE 0 END), 0)
              - IFNULL(SUM(CASE WHEN t.type = 'payment' THEN t.amount ELSE 0 END), 0) AS balance
        FROM clients c
        LEFT JOIN client_settings cs ON cs.client_id = c.id AND cs.user_id = c.user_id
        LEFT JOIN user_settings us ON us.user_id = c.user_id
        LEFT JOIN transactions t ON t.client_id = c.id
        WHERE
            (
              (cs.reminder_next_date IS NOT NULL AND 
               (substr(cs.reminder_next_date, 1, 13) = ? OR DATETIME(cs.reminder_next_date) <= DATETIME(?)))
              OR
              (cs.reminder_next_date IS NULL AND us.reminder_next_date IS NOT NULL AND
               (substr(us.reminder_next_date, 1, 13) = ? OR DATETIME(us.reminder_next_date) <= DATETIME(?)))
            )
        GROUP BY c.id
    """
    rows = await Database.fetch_all(query, (hour_fragment, cutoff, hour_fragment, cutoff))
    return rows


async def _get_effective_interval_days(user_id: int, client_id: int) -> int:
    """
    Determine interval days to add after successful send:
    client_settings.reminder_frequency_days -> user_settings.reminder_frequency_days -> default 7
    """
    row = await Database.fetch_one(
        "SELECT reminder_frequency_days FROM client_settings WHERE user_id = ? AND client_id = ?",
        (user_id, client_id)
    )
    if row and row.get("reminder_frequency_days"):
        return int(row["reminder_frequency_days"])

    row = await Database.fetch_one(
        "SELECT reminder_frequency_days FROM user_settings WHERE user_id = ?",
        (user_id,)
    )
    if row and row.get("reminder_frequency_days"):
        return int(row["reminder_frequency_days"])

    return 7


@router.post("/send_automated_reminders")
async def send_automated_reminders(grace_minutes: int = 10):
    """
    Runs periodically (e.g. hourly). Finds clients due for reminder (same hour or within grace window).
    Respects user/client settings, increments counts, and updates appropriate next_date.
    """
    now = datetime.utcnow()
    results = []
    candidates = await _fetch_candidates_due(grace_minutes=grace_minutes)

    for c in candidates:
        user_id = c["user_id"]

        # Get user's minimum balance
        # Determine effective minimum balance (client -> user fallback)
        client_min_row = await Database.fetch_one(
            "SELECT reminder_minimum_balance FROM client_settings WHERE user_id = ? AND client_id = ?",
            (user_id, c["id"])
        )
        if client_min_row and client_min_row.get("reminder_minimum_balance") is not None:
            min_balance = float(client_min_row["reminder_minimum_balance"])
        else:
            user_row = await Database.fetch_one(
                "SELECT reminder_minimum_balance FROM user_settings WHERE user_id = ?",
                (user_id,)
            )
            min_balance = float(user_row["reminder_minimum_balance"]) if user_row else 0.0

        # Skip if below threshold
        if float(c.get("balance", 0)) < min_balance:
            results.append({
                "client_id": c["id"],
                "success": False,
                "method": None,
                "sent_to": None,
                "message": f"Balance below minimum ({min_balance})"
            })
            continue

        # Determine effective reminder settings (client overrides -> user fallback)
        enabled, method, contact, reason = await get_client_effective_settings(user_id, c)

        if not enabled:
            results.append({
                "client_id": c["id"],
                "success": False,
                "method": method,
                "sent_to": None,
                "message": reason or "Reminders disabled"
            })
            continue

        if not method:
            results.append({
                "client_id": c["id"],
                "success": False,
                "method": None,
                "sent_to": None,
                "message": "No communication method configured (client/user)"
            })
            continue

        # Send reminder using existing shared function
        send_result = await send_reminder_for_client(c, user_id, urgent=False)

        if send_result.get("success"):
            # Update reminder_last_sent in clients table
            await Database.execute(
                "UPDATE clients SET reminder_last_sent = DATETIME('now') WHERE id = ?",
                (c["id"],)
            )

            # Update user's sent count
            await set_msgs_sent_count(communication_method=method , user_id=user_id)
            # Compute new reminder_next_date
            interval_days = await _get_effective_interval_days(user_id, c["id"])
            next_dt = (datetime.utcnow() + timedelta(days=interval_days)).replace(minute=0, second=0, microsecond=0)

            # Determine which table to update (client_settings if exists, else user_settings)
            client_has_settings = await Database.fetch_one(
                "SELECT id FROM client_settings WHERE user_id = ? AND client_id = ?",
                (user_id, c["id"])
            )

            if client_has_settings:
                await Database.execute(
                    "UPDATE client_settings SET reminder_next_date = ? WHERE user_id = ? AND client_id = ?",
                    (next_dt.isoformat(), user_id, c["id"])
                )
            else:
                await Database.execute(
                    "UPDATE user_settings SET reminder_next_date = ? WHERE user_id = ?",
                    (next_dt.isoformat(), user_id)
                )

        results.append(send_result)

    return {"success": True, "results": results, "message": "Automated reminders processed"}

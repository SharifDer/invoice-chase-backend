
from datetime import datetime, timezone
from database import Database
from config import settings

async def can_send_sms(user_id: int , plan_type : str) -> bool:

    now = now = datetime.now(timezone.utc)
    year, month = now.year, now.month

    plan = plan_type.lower()

    sms_limits = settings.sms_limits

    limit = sms_limits.get(plan)
    usage_sql = """
        SELECT sms_reminders_sent_count + sms_notifications_sent_count AS total_sms
        FROM user_monthly_usage
        WHERE user_id = ? AND year = ? AND month = ?;
    """
    usage = await Database.fetch_one(usage_sql, (user_id, year, month))
    total_sms = usage["total_sms"] if usage else 0

    return total_sms < limit



async def can_send_email(user_id: int , plan_type : str) -> bool:

    now = datetime.now(timezone.utc)
    year, month = now.year, now.month

    plan = plan_type.lower()

    email_limits = settings.email_limits

    limit = email_limits.get(plan)
    usage_sql = """
        SELECT email_reminders_sent_count + email_notifications_sent_count AS total_email
        FROM user_monthly_usage
        WHERE user_id = ? AND year = ? AND month = ?;
    """
    usage = await Database.fetch_one(usage_sql, (user_id, year, month))
    total_email = usage["total_email"] if usage else 0

    return total_email < limit


async def can_create_transaction_today(user_id: int , plan_type : str) -> bool:

    plan = plan_type.lower()

    daily_limits = settings.transactions_daily_limits

    limit = daily_limits.get(plan)
    if limit is None:
        return True

    today_sql = """
        SELECT COUNT(*) as tx_today
        FROM transactions
        WHERE user_id = ? AND DATE(created_at) = DATE('now', 'localtime');
    """
    result = await Database.fetch_one(today_sql, (user_id,))
    tx_today = result["tx_today"]

    return tx_today < limit

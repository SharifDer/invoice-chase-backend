from fastapi import APIRouter, Depends, HTTPException
from typing import Optional
from database import Database
from auth import get_current_user
from logger import get_logger
from schemas.responses import (BusinessDataRes, NotificationSettings)
from .utils import fetch_business_info
logger = get_logger(__name__)
router = APIRouter( tags=["Settings"])



# --- BUSINESS INFO CRUD --- #
@router.get("/business", response_model=BusinessDataRes)
async def get_business_info(
    current_user: dict = Depends(get_current_user)
    ):
    user_id = current_user["user_id"]
    record = await fetch_business_info(user_id)
    if not record:
        raise HTTPException(status_code=404, detail="Business info not found")
    return record

# Create new business info
@router.post("/business/create", response_model=BusinessDataRes)
async def create_business_info_record(data: BusinessDataRes,
                                      current_user : dict = Depends(get_current_user)
                                      ):
    # user_id = 1  # replace with current_user["user_id"]
    user_id = current_user["user_id"]
    existing = await Database.fetch_one("SELECT id FROM business_info WHERE user_id = ?", (user_id,))
    if existing:
        raise HTTPException(status_code=400, detail="Business info already exists")
    
    await Database.execute(
        """
        INSERT INTO business_info (user_id, business_name, business_email, phone, website, address, logo_url)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (user_id, data.business_name, data.business_email, data.phone, data.website, data.address, data.logo_url)
    )
    return await fetch_business_info(user_id)

# Update existing business info
@router.put("/business/update", response_model=BusinessDataRes)
async def update_business_info_record(data: BusinessDataRes,
                                      current_user : dict = Depends(get_current_user)
                                      ):
    # user_id = 1  # replace with current_user["user_id"]
    user_id = current_user["user_id"]
    existing = await Database.fetch_one("SELECT id FROM business_info WHERE user_id = ?", (user_id,))
    if not existing:
        raise HTTPException(status_code=404, detail="Business info not found")
    
    await Database.execute(
        """
        UPDATE business_info
        SET business_name = ?, business_email = ?, phone = ?, website = ?, address = ?, logo_url = ?, updated_at = CURRENT_TIMESTAMP
        WHERE user_id = ?
        """,
        (data.business_name, data.business_email, data.phone, data.website, data.address, data.logo_url, user_id)
    )
    return await fetch_business_info(user_id)

# --- NOTIFICATION SETTINGS CRUD --- #
@router.get("/notifications", response_model=NotificationSettings)
async def get_notification_settings(current_user : dict = Depends(get_current_user)):
    user_id = current_user["user_id"]
    record = await fetch_notification_settings(user_id)
    if not record:
        raise HTTPException(status_code=404, detail="Notification settings not found")
    return record

@router.put("/notifications", response_model=NotificationSettings)
async def update_notification_settings(data: NotificationSettings,
                                       current_user : dict = Depends(get_current_user)
                                       ):
    
    user_id = current_user["user_id"]
    existing = await Database.fetch_one(
        "SELECT id FROM user_settings WHERE user_id = ?", (user_id,)
    )

    if existing:
        # build dynamic update
        update_fields = []
        values = []

        for field, value in data.dict(exclude_unset=True).items():
            if field == "reminder_frequency_days":
                update_fields.append(
                    "reminder_next_date = DATETIME(STRFTIME('%Y-%m-%d %H:00:00', DATETIME('now', '+' || ? || ' days')))"
                )
                values.append(value)
            update_fields.append(f"{field} = ?")
            values.append(value)

        if update_fields:
            update_fields.append("updated_at = CURRENT_TIMESTAMP")
            sql = f"UPDATE user_settings SET {', '.join(update_fields)} WHERE user_id = ?"
            values.append(user_id)
            await Database.execute(sql, tuple(values))
    else:
        await Database.execute(
            """
            INSERT INTO user_settings (
                user_id, communication_method, 
                send_automated_reminders, reminder_frequency_days, reminder_minimum_balance, 
                send_transaction_notifications, reminder_next_date
            )
            VALUES (?, ?, ?, ?, ?, ?, 
                    CASE WHEN ? IS NOT NULL 
                    THEN DATETIME(STRFTIME('%Y-%m-%d %H:00:00', DATETIME('now', '+' || ? || ' days'))) 
                    ELSE NULL END)
            """,
            (
                user_id,
                data.communication_method,
                data.send_automated_reminders,
                data.reminder_frequency_days,
                data.reminder_minimum_balance,
                data.send_transaction_notifications,
                data.reminder_frequency_days,
                data.reminder_frequency_days,
            ),
        )

    return await fetch_notification_settings(user_id)

async def fetch_notification_settings(user_id) :
    record = await Database.fetch_one("SELECT * FROM user_settings WHERE user_id = ?", (user_id,))
    settings = {k: v for k, v in record.items() if v is not None}
    return settings
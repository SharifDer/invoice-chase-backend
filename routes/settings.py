from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr
from typing import Optional
from database import Database
from auth import get_current_user
from logger import get_logger
from schemas.responses import (BusinessDataRes, NotificationSettings)
logger = get_logger(__name__)
router = APIRouter( tags=["Settings"])



# --- BUSINESS INFO CRUD --- #
@router.get("/business", response_model=BusinessDataRes)
async def get_business_info(
    # current_user: dict = Depends(get_current_user)
    ):
    # user_id = current_user["user_id"]
    user_id = 1
    record = await Database.fetch_one(
        "SELECT * FROM business_info WHERE user_id = ?", (user_id,)
    )
    if not record:
        raise HTTPException(status_code=404, detail="Business info not found")
    return record

# Create new business info
@router.post("/business/create", response_model=BusinessDataRes)
async def create_business_info_record(data: BusinessDataRes):
    user_id = 1  # replace with current_user["user_id"]
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
    return await get_business_info()

# Update existing business info
@router.put("/business/update", response_model=BusinessDataRes)
async def update_business_info_record(data: BusinessDataRes):
    user_id = 1  # replace with current_user["user_id"]
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
    return await get_business_info()

# --- NOTIFICATION SETTINGS CRUD --- #
@router.get("/notifications", response_model=NotificationSettings)
async def get_notification_settings(
    # current_user: dict = Depends(get_current_user)
                                    ):
    # user_id = current_user["user_id"]
    user_id = 1
    record = await Database.fetch_one("SELECT * FROM user_settings WHERE user_id = ?", (user_id,))
    if not record:
        # Return defaults if not set
        raise HTTPException(status_code=404, detail="Notification settings not found")
    return record

@router.put("/notifications", response_model=NotificationSettings)
async def update_notification_settings(data: NotificationSettings, 
                                    #    current_user: dict = Depends(get_current_user)
                                       ):
    # user_id = current_user["user_id"]
    user_id = 1
    comm_type = data.communication_method  # email | sms | both

    existing = await Database.fetch_one("SELECT id FROM user_settings WHERE user_id = ?", (user_id,))
    if existing:
        await Database.execute(
            """
            UPDATE user_settings
            SET reminder_type = ?, transaction_notification_type = ?, 
                send_automated_reminders = ?, reminder_frequency_days = ?, 
                reminder_minimum_balance = ?, send_transaction_notifications = ?,
                reminder_template = ?, notification_template = ?, updated_at = CURRENT_TIMESTAMP
            WHERE user_id = ?
            """,
            (
                comm_type,
                comm_type,
                data.send_automated_reminders,
                data.reminder_frequency_days,
                data.reminder_minimum_balance,
                data.send_transaction_notifications,
                data.reminder_template,
                data.notification_template,
                user_id
            )
        )
    else:
        await Database.execute(
            """
            INSERT INTO user_settings (user_id, reminder_type, transaction_notification_type, 
                send_automated_reminders, reminder_frequency_days, reminder_minimum_balance, send_transaction_notifications,
                reminder_template, notification_template)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                user_id,
                comm_type,
                comm_type,
                data.send_automated_reminders,
                data.reminder_frequency_days,
                data.reminder_minimum_balance,
                data.send_transaction_notifications,
                data.reminder_template,
                data.notification_template
            )
        )
    return await get_notification_settings()
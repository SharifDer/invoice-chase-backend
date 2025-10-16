from pydantic import BaseModel, EmailStr, Field
from typing import Optional, Dict, Any, Literal
from datetime import date
from decimal import Decimal
from fastapi import Query
# ======================
# Authentication Requests
# ======================

# Backend / Admin user creation (Swagger/testing)
class CreateUserRequest(BaseModel):
    email: EmailStr
    name: str = Field(..., min_length=1)
    password: str = Field(..., min_length=8)  # only for backend creation

# Frontend Firebase login/signup
class FirebaseLoginRequest(BaseModel):
    firebase_token: str
    email: Optional[EmailStr] = None  # optional, for storing in DB
    name: str = Field(..., min_length=1)

class GoogleAuthRequest(BaseModel):
    firebase_token: str
    email: Optional[EmailStr] = None
    name: str = Field(..., min_length=1)

# ======================
# Client Requests
# ======================

class ClientCreateRequest(BaseModel):
    name: str = Field(..., min_length=1)
    email: Optional[EmailStr] = None
    phone: Optional[str] = None
    company: Optional[str] = None

class ClientUpdateRequest(BaseModel):
    name: Optional[str] = None
    email: Optional[EmailStr] = None
    phone: Optional[str] = None
    company: Optional[str] = None
    communication_method : Optional[str] = None
    trans_notification : Optional[bool] = None
    payment_reminders : Optional[bool] = None
    reminds_every_n_days : Optional[int] = None
    min_balance_to_remind : Optional[float] = None

# ======================
# Invoice Requests
# ======================

class InvoiceCreateRequest(BaseModel):
    client_id: int
    type : str = Literal['payment', 'invoice']
    amount: Decimal = Field(..., gt=0)
    description: Optional[str] = None
    status: Optional[str] = Field("Draft", pattern="^(Draft|Pending|Paid|Overdue)$")


class InvoiceCreateRequestNewClient(BaseModel):
    type : str = Literal['payment', 'invoice']
    amount: Decimal = Field(..., gt=0)
    description: Optional[str] = None
    status: Optional[str] = Field("Draft", pattern="^(Draft|Pending|Paid|Overdue)$")
   

class TransactionUpdateRequest(BaseModel):
    # client_id: Optional[int] = None
    # trans_num: Optional[str] = None
    amount: Optional[Decimal] = Field(None, gt=0)
    description: Optional[str] = None
    type : Optional[str] = None
    created_at : Optional[date] = None
    # status: Optional[str] = Field(None, pattern="^(Draft|Pending|Paid|Overdue)$")

class InvoiceFilterRequest(BaseModel):
    status: Optional[str] = None
    client_id: Optional[int] = None
    due_date_from: Optional[date] = None
    due_date_to: Optional[date] = None
    page: int = Field(1, ge=1)
    limit: int = Field(10, ge=1, le=100)

# ======================
# Settings Requests
# ======================

class CompanySettingsRequest(BaseModel):
    company_logo_url: Optional[str] = None
    reminder_settings: Optional[Dict[str, Any]] = None
    payment_settings: Optional[Dict[str, Any]] = None

class ReminderSettingsRequest(BaseModel):
    enabled: bool = True
    gentle_reminder_days: int = Field(3, ge=1, le=30)
    firm_reminder_days: int = Field(7, ge=1, le=30)
    final_reminder_days: int = Field(14, ge=1, le=60)
    email_template: Optional[str] = None
    sms_enabled: bool = False

class PaymentSettingsRequest(BaseModel):
    stripe_enabled: bool = False
    stripe_publishable_key: Optional[str] = None
    paypal_enabled: bool = False
    paypal_client_id: Optional[str] = None
    default_currency: str = Field("USD", min_length=3, max_length=3)



class ReqUserLogin(BaseModel):
    email: str
    password: str

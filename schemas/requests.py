from pydantic import BaseModel, EmailStr, Field,model_validator
from typing import Optional,Literal, List
from datetime import date, datetime
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
    # email: Optional[EmailStr] = None  # optional, for storing in DB
    # name: str = Field(..., min_length=1)

class GoogleAuthRequest(BaseModel):
    firebase_token: str
    email: Optional[EmailStr] = None
    name: str = Field(..., min_length=1)
class ReqUserLogin(BaseModel):
    email: str
    password: str
# ======================
# Client Requests
# ======================
class ClientNotificationSettings(BaseModel):
    communication_method: str = Field(..., pattern="^(email|sms)$")
    send_transaction_notifications: bool = True
    send_automated_reminders: bool = True
    reminder_frequency_days: int = 7
    reminder_minimum_balance: float = 0.0

class ClientCreateRequest(BaseModel):
    name: str = Field(..., min_length=1)
    email: Optional[EmailStr] = None
    phone: Optional[str] = None
    company: Optional[str] = None
    apply_user_settings : bool = True
    notification_settings: Optional[ClientNotificationSettings] = None
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
# Transactions Requests
# ======================

class TransactionCreateRequest(BaseModel):
    client_id: Optional[int] = None  # optional here
    type: Literal['payment', 'invoice']
    amount: Decimal = Field(..., gt=0)
    description: Optional[str] = None
    created_date : date

   
class UnifiedTransactionRequest(BaseModel):
    is_new_client: bool
    transaction: TransactionCreateRequest
    client: Optional[ClientCreateRequest] = None
    @model_validator(mode="after")
    def validate_client_fields(cls, values):
        is_new = values.is_new_client
        transaction = values.transaction
        client = getattr(values, "client", None) 

        if is_new:
            if not client:
                raise ValueError("Client data is required for new client transactions")
        else:
            if not transaction.client_id:
                raise ValueError("client_id is required for existing client transactions")
        return values
class TransactionUpdateRequest(BaseModel):
    amount: Optional[Decimal] = Field(None, gt=0)
    description: Optional[str] = None
    type : Optional[str] = None
    created_at : Optional[date] = None

# ======================
# Reminders Requests
# ======================

class EmailSendReq(BaseModel):
    type: Literal["reminder", "notification"]        #balance reminder or transaction notifcation creation so the filed either reminder or notification

class UrgentReminderReq(BaseModel):
    client_ids: List[int]  



class BusinessNameCurrency(BaseModel):
    business_name : str
    currency : str
    currency_symbol : str
    plan_type : str

class UpdateUserPlan(BaseModel):
    plan_type : str
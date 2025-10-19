from pydantic import BaseModel, EmailStr, Field
from typing import Optional,Literal, List
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
class ReqUserLogin(BaseModel):
    email: str
    password: str
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

# ======================
# Reminders Requests
# ======================

class EmailSendReq(BaseModel):
    type : str        #balance reminder or transaction notifcation creation

class UrgentReminderReq(BaseModel):
    client_ids: List[int]  

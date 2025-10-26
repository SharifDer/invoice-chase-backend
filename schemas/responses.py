from pydantic import BaseModel, EmailStr
from typing import Optional, List, Dict, Any, Literal
from datetime import date, datetime
from decimal import Decimal


# Base Response Models
class BaseResponse(BaseModel):
    success: bool = True
    message: Optional[str] = None


# Authentication Responses
class UserResponse(BaseModel):
    id: int
    email: EmailStr
    name: str
    created_at: datetime


class AuthResponse(BaseResponse):
    user: UserResponse
 

# Client Responses
class ClientResponse(BaseModel):
    id: int
    name: str
    email: Optional[EmailStr] = None
    phone: Optional[str] = None
    company: Optional[str] = None
    created_at: datetime
    updated_at: datetime


class ClientSummaryResponse(BaseModel):
    id: int
    name: str
    email: Optional[EmailStr] = None
    phone: Optional[str] = None
    company: Optional[str] = None
    total_invoiced: float
    total_paid: float
    net_balance: float
    created_at: datetime
    updated_at: datetime


class ClientListResponse(BaseResponse):
    clients: List[ClientSummaryResponse]
    total: int
    page: int
    limit: int
    total_pages: int


class ClientTransaction(BaseModel):
    id: int
    type: str               # 'invoice' or 'payment'
    description: Optional[str]
    amount: float
    date: date
    transaction_number: Optional[str]
class BusinessProfile(BaseModel):
    business_name: Optional[str] = None
    business_logo: Optional[str] = None
    business_phone: Optional[str] = None
    business_website: Optional[str] = None
    business_address: Optional[str] = None
class ClientReportResponse(BaseModel):
    client_id: int
    client_name: str
    client_email: Optional[EmailStr] = None
    client_phone: Optional[str] = None
    client_company: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    total_invoiced: float
    total_paid: float
    outstanding: float
    transactions: List[ClientTransaction]
    page: int
    limit: int
    total_transactions: int
    total_pages: int
    business_profile: Optional[BusinessProfile] = None 
class ClientSettingsResponse(BaseModel):
    communicationMethod : str
    transactionNotificationEnabled : bool
    reminderEnabled : bool
    reminderIntervalDays : int
    reminderMinimumAmount : float
# Invoice Responses
class TransactionResponse(BaseModel):
  message : str
  status : str


class TransCreationResponse(BaseModel):
    message : str
    status : str

class TransactionDetailsResponse(BaseModel):
    client_company: Optional[str] = None
    client_email: Optional[str] = None
    Description: Optional[str] = None

class TransactionResponse(BaseModel):
    transaction_number: str        ##transaction number not db id 
    client_id: int
    client_name: str
    type: str               # "invoice" | "payment"
    amount: float
    created_date: date
    description: Optional[str]


class TransactionListResponse(BaseModel):
    transactions: List[TransactionResponse]
    total: int
    page: int
    limit: int
    total_pages: int
    message: str


# Dashboard Responses

class TransactionSummary(BaseModel):
    id: int        ##this is the id for the system
    trans_id : str  ## this is the id of this transaction for the user, this is what appears int the frontend
    type: str  # 'payment' or 'invoice'
    client_name : str
    clientId : int
    amount: Decimal
    created_at: str

class TodayMomentum(BaseModel):
    todayInvoices: int
    todayPayments: int
    todayInvoicesAmount: float
    todayPaymentsAmount: float
    dailyAvgInvoices: float
    dailyAvgPayments: float
    thisWeekInvoices: int
    thisWeekPayments: int
    lastWeekInvoices: int
    lastWeekPayments: int

class DashboardStatsResponse(BaseModel):
    total_invoices: int
    invoiced_amount: float
    num_of_receipts: int
    total_receipts_amount: float
    todayMomentum: TodayMomentum
    recent_transactions: List[TransactionSummary]

class CurrencyResponse(BaseModel):
    currency_symbol : str 
    currency_name : str
# Analytics Response Models
class TotalClientBalancesData(BaseModel):
    current: float
    trend: float
    trendDirection: Literal["up", "down"]


class PaymentsCollectedData(BaseModel):
    amount: float
    count: int


class InvoicesIssuedData(BaseModel):
    amount: float
    count: int


class WeeklyCashFlowData(BaseModel):
    week: str
    invoiced: float
    paid: float


class TopClientByBalanceData(BaseModel):
    client_id : int
    name: str
    company: str
    balance: float


class AgingBalanceClientData(BaseModel):
    name: str
    company: str
    balance: float
    daysSincePayment: int


class AgingBalancesData(BaseModel):
    count: int
    clients: List[AgingBalanceClientData]


class NetCashChangeData(BaseModel):
    amount: float
    isPositive: bool


class AnalyticsResponse(BaseModel):
    totalClientBalances: TotalClientBalancesData
    paymentsCollected: PaymentsCollectedData
    invoicesIssued: InvoicesIssuedData
    weeklyCashFlow: List[WeeklyCashFlowData]
    topClientsByBalance: List[TopClientByBalanceData]
    agingBalances: AgingBalancesData
    netCashChange: NetCashChangeData
# Settings Responses
# --- MODELS --- #
class BusinessDataRes(BaseModel):
    business_name: str
    business_email: Optional[EmailStr] = None
    phone: Optional[str] = None
    website: Optional[str] = None
    address: Optional[str] = None  ##Business address in frontend
    logo_url: Optional[str] = None
    
class NotificationSettings(BaseModel):
    communication_method: Optional[str] = None
    send_automated_reminders: Optional[bool] = None
    reminder_frequency_days: Optional[int] = None
    reminder_minimum_balance: Optional[float] = None
    send_transaction_notifications: Optional[bool] = None
### Reminders responses 
class TestReminderRes(BaseModel):
    status : str 
    message : str
    sent_to : Optional[str]
# Health Check Response
class HealthCheckResponse(BaseModel):
    status: str
    database: str
    timestamp: datetime = datetime.utcnow()

from fastapi import APIRouter, Depends, HTTPException, status, Query
from datetime import datetime, timedelta, date
from decimal import Decimal
from typing import List, Literal, Optional

from database import Database
from auth import get_current_user
from schemas.responses import (
    AnalyticsResponse,
    TotalClientBalancesData,
    PaymentsCollectedData,
    InvoicesIssuedData,
    WeeklyCashFlowData,
    TopClientByBalanceData,
    AgingBalancesData,
    AgingBalanceClientData,
    NetCashChangeData
)
from logger import get_logger

logger = get_logger(__name__)
router = APIRouter()


@router.get("/", response_model=AnalyticsResponse)
async def get_analytics(
    period: Literal["7days", "30days"] = Query(default="7days"),
    # current_user: dict = Depends(get_current_user)
):
    """
    Get analytics data for the dashboard
    
    Query Parameters:
    - period: Time period for metrics ("7days" or "30days", defaults to "7days")
    
    Returns comprehensive analytics including:
    - Total client balances with trend
    - Payments collected in period
    - Invoices issued in period
    - Weekly cash flow comparison
    - Top clients by outstanding balance
    - Clients with aging balances (no payment in 30+ days)
    - Net cash change for period
    """

    # user_id = current_user['user_id']
    user_id = 1
    days = 7 if period == "7days" else 30
    
    logger.info(f"Fetching analytics for user {user_id}, period: {period}")
    
    # Get all analytics data
    total_client_balances = await _get_total_client_balances(user_id, days)
    payments_collected = await _get_payments_collected(user_id, days)
    invoices_issued = await _get_invoices_issued(user_id, days)
    if period == "7days":
         weekly_cash_flow = await _get_daily_cash_flow(user_id, days)
    else:
        weekly_cash_flow = await _get_weekly_cash_flow(user_id)
    # weekly_cash_flow = await _get_weekly_cash_flow(user_id)
    top_clients_by_balance = await _get_top_clients_by_balance(user_id)
    aging_balances = await _get_aging_balances(user_id)
    net_cash_change = await _get_net_cash_change(user_id, days)
    
    logger.info(f"Analytics data retrieved successfully for user {user_id}")
    
    return AnalyticsResponse(
        totalClientBalances=total_client_balances,
        paymentsCollected=payments_collected,
        invoicesIssued=invoices_issued,
        weeklyCashFlow=weekly_cash_flow,
        topClientsByBalance=top_clients_by_balance,
        agingBalances=aging_balances,
        netCashChange=net_cash_change
    )


async def _get_daily_cash_flow(user_id: int, days: int) -> List[WeeklyCashFlowData]:
    """
    Get daily cash flow data for the last N days (default: 7 days)
    Returns list with { day: str, invoiced: float, paid: float }
    """
    try:
        daily_data = []

        for i in range(days - 1, -1, -1):
            query = """
            SELECT 
                COALESCE(SUM(CASE WHEN type = 'invoice' THEN amount ELSE 0 END), 0) as invoiced,
                COALESCE(SUM(CASE WHEN type = 'payment' THEN amount ELSE 0 END), 0) as paid
            FROM transactions
            WHERE user_id = ?
            AND created_date = date('now', '-' || ? || ' days')
            """
            result = await Database.fetch_one(query, (user_id, i))

            day_label = (date.today() - timedelta(days=i)).strftime("%a")  # e.g., Mon, Tue, etc.

            daily_data.append(WeeklyCashFlowData(
                week=day_label,   # same model field, just day label instead
                invoiced=float(result['invoiced']) if result else 0.0,
                paid=float(result['paid']) if result else 0.0
            ))

        return daily_data

    except Exception as e:
        logger.error(f"Error calculating daily cash flow: {e}")
        return []

async def _get_total_client_balances(user_id: int, days: int) -> TotalClientBalancesData:
    """
    Calculate total outstanding balances across all clients with trend
    """
    try:
        # Current total balance (sum of all net balances)
        current_query = """
        SELECT 
            COALESCE(SUM(
                COALESCE((SELECT SUM(amount) FROM transactions 
                          WHERE client_id = c.id AND type = 'invoice'), 0) -
                COALESCE((SELECT SUM(amount) FROM transactions 
                          WHERE client_id = c.id AND type = 'payment'), 0)
            ), 0) as total_balance
        FROM clients c
        WHERE c.user_id = ?
        """
        current_result = await Database.fetch_one(current_query, (user_id,))
        current_balance = Decimal(str(current_result['total_balance'])) if current_result else Decimal('0')
        
        # Previous period balance for trend calculation
        previous_query = """
        SELECT 
            COALESCE(SUM(
                COALESCE((SELECT SUM(amount) FROM transactions 
                          WHERE client_id = c.id AND type = 'invoice' 
                          AND created_date <= date('now', '-' || ? || ' days')), 0) -
                COALESCE((SELECT SUM(amount) FROM transactions 
                          WHERE client_id = c.id AND type = 'payment'
                          AND created_date <= date('now', '-' || ? || ' days')), 0)
            ), 0) as previous_balance
        FROM clients c
        WHERE c.user_id = ?
        """
        previous_result = await Database.fetch_one(previous_query, (days, days, user_id))
        previous_balance = Decimal(str(previous_result['previous_balance'])) if previous_result else Decimal('0')
        
        # Calculate trend percentage
        if previous_balance > 0:
            trend = float(((current_balance - previous_balance) / previous_balance) * 100)
        else:
            trend = 0.0
        
        return TotalClientBalancesData(
            current=float(current_balance),
            trend=round(trend, 1),
            trendDirection="up" if trend >= 0 else "down"
        )
    
    except Exception as e:
        logger.error(f"Error calculating total client balances: {e}")
        return TotalClientBalancesData(current=0.0, trend=0.0, trendDirection="up")


async def _get_payments_collected(user_id: int, days: int) -> PaymentsCollectedData:
    """
    Get total payments collected and count in the specified period
    """
    try:
        query = """
        SELECT 
            COALESCE(SUM(amount), 0) as total_amount,
            COUNT(*) as payment_count
        FROM transactions
        WHERE user_id = ? 
        AND type = 'payment'
        AND created_date >= date('now', '-' || ? || ' days')
        """
        result = await Database.fetch_one(query, (user_id, days))
        
        return PaymentsCollectedData(
            amount=float(result['total_amount']) if result else 0.0,
            count=result['payment_count'] if result else 0
        )
    
    except Exception as e:
        logger.error(f"Error calculating payments collected: {e}")
        return PaymentsCollectedData(amount=0.0, count=0)


async def _get_invoices_issued(user_id: int, days: int) -> InvoicesIssuedData:
    """
    Get total invoices issued and count in the specified period
    """
    try:
        query = """
        SELECT 
            COALESCE(SUM(amount), 0) as total_amount,
            COUNT(*) as invoice_count
        FROM transactions
        WHERE user_id = ? 
        AND type = 'invoice'
        AND created_date >= date('now', '-' || ? || ' days')
        """
        result = await Database.fetch_one(query, (user_id, days))
        
        return InvoicesIssuedData(
            amount=float(result['total_amount']) if result else 0.0,
            count=result['invoice_count'] if result else 0
        )
    
    except Exception as e:
        logger.error(f"Error calculating invoices issued: {e}")
        return InvoicesIssuedData(amount=0.0, count=0)


async def _get_weekly_cash_flow(user_id: int) -> List[WeeklyCashFlowData]:
    """
    Get cash flow data for the last 4 weeks showing invoiced vs paid
    """
    try:
        cash_flow_data = []
        
        for week_num in range(4, 0, -1):
            week_start_days = week_num * 7
            week_end_days = (week_num - 1) * 7
            
            query = """
            SELECT 
                COALESCE(SUM(CASE WHEN type = 'invoice' THEN amount ELSE 0 END), 0) as invoiced,
                COALESCE(SUM(CASE WHEN type = 'payment' THEN amount ELSE 0 END), 0) as paid
            FROM transactions
            WHERE user_id = ?
            AND created_date >= date('now', '-' || ? || ' days')
            AND created_date < date('now', '-' || ? || ' days')
            """
            result = await Database.fetch_one(query, (user_id, week_start_days, week_end_days))
            
            week_label = f"Week {5 - week_num}"
            
            cash_flow_data.append(WeeklyCashFlowData(
                week=week_label,
                invoiced=float(result['invoiced']) if result else 0.0,
                paid=float(result['paid']) if result else 0.0
            ))
        
        return cash_flow_data
    
    except Exception as e:
        logger.error(f"Error calculating weekly cash flow: {e}")
        return []


async def _get_top_clients_by_balance(user_id: int, limit: int = 5) -> List[TopClientByBalanceData]:
    """
    Get top clients with highest outstanding balances
    """

    query = """
    SELECT 
        c.name,
        c.company,
        (
            COALESCE((SELECT SUM(amount) FROM transactions 
                    WHERE client_id = c.id AND type = 'invoice'), 0) -
            COALESCE((SELECT SUM(amount) FROM transactions 
                    WHERE client_id = c.id AND type = 'payment'), 0)
        ) as balance
    FROM clients c
    WHERE c.user_id = ?
    AND balance > 0
    ORDER BY balance DESC
    LIMIT ?
    """
    results = await Database.fetch_all(query, (user_id, limit))
    print("results  sd" , results)
    top_clients = []
    for result in results:
        top_clients.append(TopClientByBalanceData(
            name=result['name'],
            company=result['company'] or "",
            balance=float(result['balance'])
        ))
    
    return top_clients



async def _get_aging_balances(user_id: int, days_threshold: int = 30) -> AgingBalancesData:
    """
    Get clients with aging balances (no payment in 30+ days and have outstanding balance)
    """
    try:
        query = """
        WITH client_balances AS (
            SELECT 
                c.id,
                c.name,
                c.company,
                (
                    COALESCE((SELECT SUM(amount) FROM transactions 
                              WHERE client_id = c.id AND type = 'invoice'), 0) -
                    COALESCE((SELECT SUM(amount) FROM transactions 
                              WHERE client_id = c.id AND type = 'payment'), 0)
                ) as balance,
                (
                    SELECT MAX(created_date) FROM transactions 
                    WHERE client_id = c.id AND type = 'payment'
                ) as last_payment_date
            FROM clients c
            WHERE c.user_id = ?
        )
        SELECT 
            name,
            company,
            balance,
            CASE 
                WHEN last_payment_date IS NULL THEN 999
                ELSE CAST(julianday('now') - julianday(last_payment_date) AS INTEGER)
            END as days_since_payment
        FROM client_balances
        WHERE balance > 0
        AND (
            last_payment_date IS NULL 
            OR julianday('now') - julianday(last_payment_date) >= ?
        )
        ORDER BY balance DESC
        """
        results = await Database.fetch_all(query, (user_id, days_threshold))
        
        clients = []
        total_amount = 0.0
        
        for result in results:
            balance = float(result['balance'])
            total_amount += balance
            
            clients.append(AgingBalanceClientData(
                name=result['name'],
                company=result['company'] or "",
                balance=balance,
                daysSincePayment=result['days_since_payment']
            ))
        
        return AgingBalancesData(
            count=len(clients),
            totalAmount=total_amount,
            clients=clients
        )
    
    except Exception as e:
        logger.error(f"Error fetching aging balances: {e}")
        return AgingBalancesData(count=0, totalAmount=0.0, clients=[])


async def _get_net_cash_change(user_id: int, days: int) -> NetCashChangeData:
    """
    Calculate net cash change (payments - invoices) for the period
    """
    try:
        query = """
        SELECT 
            COALESCE(SUM(CASE WHEN type = 'payment' THEN amount ELSE 0 END), 0) as total_payments,
            COALESCE(SUM(CASE WHEN type = 'invoice' THEN amount ELSE 0 END), 0) as total_invoices
        FROM transactions
        WHERE user_id = ?
        AND created_date >= date('now', '-' || ? || ' days')
        """
        result = await Database.fetch_one(query, (user_id, days))
        
        if result:
            total_payments = Decimal(str(result['total_payments']))
            total_invoices = Decimal(str(result['total_invoices']))
            net_change = total_payments - total_invoices
        else:
            net_change = Decimal('0')
        
        return NetCashChangeData(
            amount=float(net_change),
            isPositive=net_change >= 0
        )
    
    except Exception as e:
        logger.error(f"Error calculating net cash change: {e}")
        return NetCashChangeData(amount=0.0, isPositive=True)
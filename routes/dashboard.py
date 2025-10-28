from fastapi import APIRouter, Depends, HTTPException
from database import Database
from schemas.responses import (DashboardStatsResponse, TransactionSummary,
                               CurrencyResponse, TodayMomentum)
from datetime import date, timedelta
from .dbUtils import fetch_user_currency
from auth import get_current_user
from schemas.requests import BusinessNameCurrency
router = APIRouter()


# ----------------------------
# Helper Functions
# ----------------------------
async def get_total_stats(user_id: int):
    """Single-query optimized totals aggregation."""
    row = await Database.fetch_one(
        """
        SELECT 
            COUNT(CASE WHEN type = 'invoice' THEN 1 END) AS total_invoices,
            COALESCE(SUM(CASE WHEN type = 'invoice' THEN amount END), 0) AS invoiced_amount,
            COUNT(CASE WHEN type = 'payment' THEN 1 END) AS num_of_receipts,
            COALESCE(SUM(CASE WHEN type = 'payment' THEN amount END), 0) AS total_receipts_amount
        FROM transactions
        WHERE user_id = ?;
        """,
        (user_id,),
    )

    return {
        "total_invoices": row["total_invoices"],
        "invoiced_amount": row["invoiced_amount"],
        "num_of_receipts": row["num_of_receipts"],
        "total_receipts_amount": row["total_receipts_amount"],
    }


async def get_today_momentum(user_id: int):
    today = date.today()
    start_of_week = today - timedelta(days=today.weekday())
    last_week_start = start_of_week - timedelta(days=7)
    last_week_end = start_of_week - timedelta(days=1)

    # --- Today's invoices & payments ---
    today_data = await Database.fetch_one(
        """
        SELECT 
            SUM(CASE WHEN type='invoice' THEN amount ELSE 0 END) AS today_invoices_amount,
            SUM(CASE WHEN type='payment' THEN amount ELSE 0 END) AS today_payments_amount,
            COUNT(CASE WHEN type='invoice' THEN 1 END) AS today_invoices,
            COUNT(CASE WHEN type='payment' THEN 1 END) AS today_payments
        FROM transactions
        WHERE user_id = ? AND DATE(created_date) = DATE('now');
        """,
        (user_id,)
    )

    # --- This week ---
    this_week = await Database.fetch_one(
        """
        SELECT 
            COUNT(CASE WHEN type='invoice' THEN 1 END) AS this_week_invoices,
            COUNT(CASE WHEN type='payment' THEN 1 END) AS this_week_payments
        FROM transactions
        WHERE user_id = ? AND DATE(created_date) BETWEEN ? AND ?;
        """,
        (user_id, start_of_week.isoformat(), today.isoformat())
    )

    # --- Last week ---
    last_week = await Database.fetch_one(
        """
        SELECT 
            COUNT(CASE WHEN type='invoice' THEN 1 END) AS last_week_invoices,
            COUNT(CASE WHEN type='payment' THEN 1 END) AS last_week_payments
        FROM transactions
        WHERE user_id = ? AND DATE(created_date) BETWEEN ? AND ?;
        """,
        (user_id, last_week_start.isoformat(), last_week_end.isoformat())
    )

    # --- Daily averages (based on last 7 days) ---
    avg_data = await Database.fetch_one(
        """
        SELECT 
            AVG(invoice_count) AS daily_avg_invoices,
            AVG(payment_count) AS daily_avg_payments
        FROM (
            SELECT 
                DATE(created_date) AS day,
                COUNT(CASE WHEN type='invoice' THEN 1 END) AS invoice_count,
                COUNT(CASE WHEN type='payment' THEN 1 END) AS payment_count
            FROM transactions
            WHERE user_id = ? AND DATE(created_date) >= DATE('now', '-7 days')
            GROUP BY day
        );
        """,
        (user_id,)
    )

    return {
        "todayInvoices": today_data["today_invoices"] or 0,
        "todayPayments": today_data["today_payments"] or 0,
        "todayInvoicesAmount": today_data["today_invoices_amount"] or 0,
        "todayPaymentsAmount": today_data["today_payments_amount"] or 0,
        "dailyAvgInvoices": round(avg_data["daily_avg_invoices"] or 0, 2),
        "dailyAvgPayments": round(avg_data["daily_avg_payments"] or 0, 2),
        "thisWeekInvoices": this_week["this_week_invoices"] or 0,
        "thisWeekPayments": this_week["this_week_payments"] or 0,
        "lastWeekInvoices": last_week["last_week_invoices"] or 0,
        "lastWeekPayments": last_week["last_week_payments"] or 0
    }


async def get_recent_transactions(user_id: int, limit: int = 5)-> TransactionSummary:
    rows = await Database.fetch_all(
        "SELECT t.id, t.type, t.transaction_number, t.created_date AS created_at, t.amount, c.name AS client_name, "
        "t.client_id "  # <-- ADD THIS FIELD
        "FROM transactions t "
        "JOIN clients c ON t.client_id = c.id "
        "WHERE t.user_id = ? "
        "ORDER BY t.created_date DESC LIMIT ?;",
        (user_id, limit)
    )
    return [
        TransactionSummary(
            id=row["id"],
            trans_id=row["transaction_number"], # Use the column from your query
            type=row["type"],
            client_name=row["client_name"],
            clientId=row["client_id"],          # <-- ADD THE NEW FIELD
            created_at=row["created_at"],
            amount=row["amount"]
        )
        for row in rows
    ]
    
# ----------------------------
# Endpoint
# ----------------------------

@router.get("/stats", response_model=DashboardStatsResponse)
async def get_dashboard_stats(current_user: dict = Depends(get_current_user)):
    """
    Get dashboard statistics and overview data:
    - Totals
    - Today's momentum
    - Last 5 transactions
    """
    user_id = current_user["user_id"]
    totals = await get_total_stats(user_id)

    # --- Optimization (1): short-circuit for users with no transactions ---
    if (
        totals["total_invoices"] == 0
        and totals["total_receipts_amount"] == 0
    ):
        return DashboardStatsResponse(
            total_invoices=0,
            invoiced_amount=0.0,
            num_of_receipts=0,
            total_receipts_amount=0.0,
            todayMomentum=TodayMomentum(
                todayInvoices=0,
                todayPayments=0,
                todayInvoicesAmount=0.0,
                todayPaymentsAmount=0.0,
                dailyAvgInvoices=0.0,
                dailyAvgPayments=0.0,
                thisWeekInvoices=0,
                thisWeekPayments=0,
                lastWeekInvoices=0,
                lastWeekPayments=0,
            ),
            recent_transactions=[],
        )

    # --- Normal flow for existing users ---
    today_momentum = await get_today_momentum(user_id)
    recent_transactions = await get_recent_transactions(user_id)

    return DashboardStatsResponse(
        total_invoices=totals["total_invoices"],
        invoiced_amount=totals["invoiced_amount"],
        num_of_receipts=totals["num_of_receipts"],
        total_receipts_amount=totals["total_receipts_amount"],
        todayMomentum=today_momentum,
        recent_transactions=recent_transactions,
    )


@router.get("/get_currency", response_model=CurrencyResponse)
async def get_user_currency(current_user: dict = Depends(get_current_user)):
    user_id = current_user["user_id"]
    currency_data = await fetch_user_currency(user_id)

    # Handle missing or None values
    if not currency_data or not currency_data["currency_name"] or not currency_data["currency_symbol"]:
        raise HTTPException(
            status_code=404,
            detail="This user hasn't set a currency yet."
        )

    return currency_data



@router.post("/set_busname_currency")
async def set_business_name_currency(
    request: BusinessNameCurrency,
    current_user: dict = Depends(get_current_user)
):
    user_id = current_user["user_id"]

    # 1️⃣ Insert or update business name in business_info table
    insert_business_sql = """
        INSERT INTO business_info (
            user_id,
            business_name,
            created_at,
            updated_at
        )
        VALUES (?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
        ON CONFLICT(user_id) DO UPDATE SET
            business_name = excluded.business_name,
            updated_at = CURRENT_TIMESTAMP;
    """

    # 2️⃣ Update currency info in users table
    update_user_currency_sql = """
        UPDATE users
        SET 
            currency = ?,
            currency_symobl = ?,
            updated_at = CURRENT_TIMESTAMP
        WHERE id = ?;
    """

    await Database.execute(insert_business_sql, (user_id, request.business_name))
    await Database.execute(update_user_currency_sql, (request.currency, request.currency_symbol, user_id))

    return {"message": "Business name and currency updated successfully"}


from fastapi import APIRouter, Depends
from database import Database  # your Database class
from auth import get_current_user  # your existing auth dependency
from schemas.responses import DashboardStatsResponse, MonthlyCollection, TransactionSummary
router = APIRouter()



# ----------------------------
# Helper Functions
# ----------------------------
async def get_total_stats(user_id: int):
    # Totals for invoices
    invoice_row = await Database.fetch_one(
        "SELECT COUNT(*) AS total_invoices, COALESCE(SUM(amount),0) AS invoiced_amount "
        "FROM transactions WHERE user_id = ? AND type = 'invoice';",
        (user_id,)
    )
    # Totals for payments
    payment_row = await Database.fetch_one(
        "SELECT COUNT(*) AS num_of_receipts, COALESCE(SUM(amount),0) AS total_receipts_amount "
        "FROM transactions WHERE user_id = ? AND type = 'payment';",
        (user_id,)
    )
    return {
        "total_invoices": invoice_row["total_invoices"],
        "invoiced_amount": invoice_row["invoiced_amount"],
        "num_of_receipts": payment_row["num_of_receipts"],
        "total_receipts_amount": payment_row["total_receipts_amount"]
    }


async def get_monthly_collections(user_id: int):
    # Get payments grouped by month
    rows = await Database.fetch_all(
        "SELECT strftime('%Y-%m', created_date) AS month, COALESCE(SUM(amount),0) AS total_amount "
        "FROM transactions WHERE user_id = ? AND type = 'payment' "
        "GROUP BY month ORDER BY month ASC;",
        (user_id,)
    )
    return [MonthlyCollection(month=row["month"], total_amount=row["total_amount"]) for row in rows]


async def get_recent_transactions(user_id: int, limit: int = 5):
    rows = await Database.fetch_all(
        "SELECT t.id, t.type, t.created_date AS created_at, t.amount, c.name AS client_name "
        "FROM transactions t "
        "JOIN clients c ON t.client_id = c.id "
        "WHERE t.user_id = ? "
        "ORDER BY t.created_date DESC LIMIT ?;",
        (user_id, limit)
    )
    return [
        TransactionSummary(
            id=row["id"],
            type=row["type"],
            created_at=row["created_at"],
            amount=row["amount"],
            client_name=row["client_name"]
        )
        for row in rows
    ]


# ----------------------------
# Endpoint
# ----------------------------
@router.get("/stats", response_model=DashboardStatsResponse)
async def get_dashboard_stats():
    """
    Get dashboard statistics and overview data.
    Modular, clean, and maintainable:
    - Totals for invoices/payments
    - Monthly collections
    - Last 5 transactions
    """
    user_id = 1

    # 1. Totals
    totals = await get_total_stats(user_id)

    # 2. Monthly collections
    monthly_collections = await get_monthly_collections(user_id)

    # 3. Recent transactions
    recent_transactions = await get_recent_transactions(user_id)

    # 4. Return structured response
    return DashboardStatsResponse(
        total_invoices=totals["total_invoices"],
        invoiced_amount=totals["invoiced_amount"],
        num_of_receipts=totals["num_of_receipts"],
        total_receipts_amount=totals["total_receipts_amount"],
        monthly_collections=monthly_collections,
        recent_transactions=recent_transactions
    )

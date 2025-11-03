import math
from fastapi import HTTPException
from database import Database
from schemas.responses import (ClientReportResponse, ClientTransaction, 
                               BusinessProfile, BusinessDataRes)

from .remindersUtils import generate_welcome_email
from .reminders import send_email
from config import settings

async def get_client_report_data(user_id: int, client_id: int, page: int = 1, limit: int = 10) -> ClientReportResponse:

    """Fetch full client report data with business profile and transactions."""

    # --- 1. Fetch business profile ---
    business_query = """
    SELECT 
        business_name,
        logo_url AS business_logo,
        phone AS business_phone,
        website AS business_website,
        address AS business_address
    FROM business_info
    WHERE user_id = ?
    """
    business_info = await Database.fetch_one(business_query, (user_id,))

    # --- 2. Fetch client info and totals ---
    client_query = """
    SELECT
        c.id,
        c.name,
        c.email,
        c.phone,
        c.company,
        c.created_at,
        c.updated_at,
        COALESCE(SUM(CASE WHEN t.type = 'invoice' THEN t.amount END), 0) AS total_invoiced,
        COALESCE(SUM(CASE WHEN t.type = 'payment' THEN t.amount END), 0) AS total_paid
    FROM clients c
    LEFT JOIN transactions t ON c.id = t.client_id
    WHERE c.id = ? AND c.user_id = ?
    GROUP BY c.id
    """
    client_row = await Database.fetch_one(client_query, (client_id, user_id))
    if not client_row:
        raise HTTPException(status_code=404, detail="Client not found")

    # --- 3. Pagination info ---
    count_query = """
    SELECT COUNT(*) AS total
    FROM transactions
    WHERE client_id = ? AND user_id = ?
    """
    count_result = await Database.fetch_one(count_query, (client_id, user_id))
    total_transactions = count_result["total"] if count_result else 0
    total_pages = math.ceil(total_transactions / limit) if total_transactions > 0 else 0
    offset = (page - 1) * limit

    # --- 4. Fetch paginated transactions ---
    trans_query = """
    SELECT id, type, description, amount, created_date AS date, transaction_number
    FROM transactions
    WHERE client_id = ? AND user_id = ?
    ORDER BY created_date DESC
    LIMIT ? OFFSET ?
    """
    trans_rows = await Database.fetch_all(trans_query, (client_id, user_id, limit, offset))
    transactions = [
        ClientTransaction(
            id=row["id"],
            type="Invoice" if row["type"] == "invoice" else "Payment",
            description=row.get("description"),
            amount=float(row["amount"]),
            date=row["date"],
            transaction_number=row.get("transaction_number"),
        )
        for row in trans_rows
    ]

    # --- 5. Calculate financials ---
    total_invoiced = float(client_row["total_invoiced"])
    total_paid = float(client_row["total_paid"])
    outstanding = total_invoiced - total_paid

    # --- 6. Build and return the response model ---
    return ClientReportResponse(
        client_id=client_row["id"],
        client_name=client_row["name"],
        client_email=client_row["email"],
        client_phone=client_row["phone"],
        client_company=client_row["company"],
        created_at=client_row["created_at"],
        updated_at=client_row["updated_at"],
        total_invoiced=total_invoiced,
        total_paid=total_paid,
        outstanding=outstanding,
        transactions=transactions,
        page=page,
        limit=limit,
        total_transactions=total_transactions,
        total_pages=total_pages,
        business_profile=BusinessProfile(**business_info) if business_info else None
    )







async def get_clients_balance(user_data: dict, client_ids: list):
    """
    Fetch clients for a given user with their current balance (invoices - payments).
    Returns a list of client dicts ready to be used in your existing loop.
    """
    if not client_ids:
        return []

    # # Fetch user to get currency
    # user_data = await Database.fetch_one("SELECT * FROM users WHERE id = ?", (user_id,))
    # if not user_data:
    #     return []
    user_id = user_data["user_id"]
    currency = user_data["currency"]

    # Fetch business info
    business_info = await Database.fetch_one(
        "SELECT business_name FROM business_info WHERE user_id = ?", (user_id,)
    )
    business_name = business_info["business_name"] if business_info else user_data["name"]

    # Fetch clients and calculate true balance
    query = f"""
        SELECT
            c.id,
            c.name,
            c.email,
            IFNULL(SUM(CASE WHEN t.type = 'invoice' THEN t.amount ELSE 0 END), 0)
            - IFNULL(SUM(CASE WHEN t.type = 'payment' THEN t.amount ELSE 0 END), 0) AS balance
        FROM clients c
        LEFT JOIN transactions t
            ON t.client_id = c.id
        WHERE c.id IN ({','.join(['?']*len(client_ids))}) AND c.user_id = ?
        GROUP BY c.id
    """
    params = client_ids + [user_id]
    clients = await Database.fetch_all(query, tuple(params))

    # Attach business info and currency to each client for convenience (optional)
    for client in clients:
        client["currency"] = currency
        client["business_name"] = business_name

    return clients

async def get_user_business_info(user_id: int):
    """
    Fetch user information, business name, and currency for a given user_id.
    Returns a dict with: name, email, business_name, currency.
    """
    user_data = await Database.fetch_one(
        "SELECT * FROM users WHERE id = ?", (user_id,)
    )
    if not user_data:
        return None  # Or raise an exception if preferred

    user_name = user_data["name"]
    user_email = user_data["email"]
    currency = user_data.get("currency", "$")

    business_info = await Database.fetch_one(
        "SELECT * FROM business_info WHERE user_id = ?", (user_id,)
    )
    business_name = business_info["business_name"] if business_info else user_name
    phone = business_info["phone"] if business_info else None
    return {
        "name": user_name,
        "email": user_email,
        "phone" : phone,
        "business_name": business_name,
        "currency": currency
    }


async def fetch_business_info(user_id : int)->BusinessDataRes :
    record = await Database.fetch_one(
        "SELECT * FROM business_info WHERE user_id = ?", (user_id,)
    )
    return record




async def welcome_email_task(name , email):
    subject, html, text = generate_welcome_email(
        business_name="Pursue Payments",
        client_name=name
    )
    await send_email(
        to_email=email,
        subject=subject,
        html_content=html,
        text_content=text,
        from_email=settings.EMAIL_FROM_SYSTEM,
        reply_to=settings.EMAIL_SUPPORT_INBOX
    )
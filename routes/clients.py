from fastapi import APIRouter, Depends, HTTPException, status, Query
from datetime import datetime
from decimal import Decimal
import math
from database import Database
from auth import get_current_user
from schemas.requests import ClientCreateRequest, ClientUpdateRequest
from schemas.responses import (ClientResponse, ClientListResponse, 
                                BaseResponse, ClientTransaction,
                               ClientSummaryResponse, ClientReportResponse,
                               ClientSettingsResponse)
from logger import get_logger
from typing import List
logger = get_logger(__name__)
router = APIRouter()


@router.get("/get_clients", response_model=ClientListResponse)
async def get_clients(
    page: int = Query(1, ge=1),
    limit: int = Query(10, ge=1, le=100),
    # current_user: dict = Depends(get_current_user)
):
    """Get all clients for the current user with aggregated totals and pagination"""
    try:
        # user_id = current_user["user_id"]
        user_id = 1

        # Count total clients for pagination
        count_query = "SELECT COUNT(*) AS total FROM clients WHERE user_id = ?"
        count_result = await Database.fetch_one(count_query, (user_id,))
        total_clients = count_result["total"] if count_result else 0

        offset = (page - 1) * limit
        total_pages = math.ceil(total_clients / limit) if total_clients > 0 else 0

        # Fetch clients with aggregated invoice/payment data
        query = """
        SELECT 
            c.id,
            c.name,
            c.email,
            c.phone,
            c.company,
            c.created_at,
            c.updated_at,
            COALESCE(SUM(CASE WHEN t.type = 'invoice' THEN t.amount END), 0) AS total_invoiced,
            COALESCE(SUM(CASE WHEN t.type = 'payment' THEN t.amount END), 0) AS total_paid,
            (COALESCE(SUM(CASE WHEN t.type = 'invoice' THEN t.amount END), 0)
             - COALESCE(SUM(CASE WHEN t.type = 'payment' THEN t.amount END), 0)) AS net_balance
        FROM clients c
        LEFT JOIN transactions t ON c.id = t.client_id
        WHERE c.user_id = ?
        GROUP BY c.id
        ORDER BY c.created_at DESC
        LIMIT ? OFFSET ?;
        """

        clients = await Database.fetch_all(query, (user_id, limit, offset))

        client_responses = [ClientSummaryResponse(**client) for client in clients]

        logger.info(f"Retrieved {len(clients)} clients for user {user_id}")

        return ClientListResponse(
            clients=client_responses,
            total=total_clients,
            page=page,
            limit=limit,
            total_pages=total_pages,
            message="Clients retrieved successfully"
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Get clients error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch clients"
        )

@router.get("/clients/{client_id}/report", response_model=ClientReportResponse)
async def get_client_report(
    client_id: int,
    page: int = Query(1, ge=1),
    limit: int = Query(10, ge=1, le=100),
    # current_user: dict = Depends(get_current_user)
):
    """Get detailed report of a client with paginated transactions"""
    try:
        # user_id = current_user["user_id"]
        user_id = 1

        # --- 1. Fetch client info and financial totals ---
        query = """
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
        client_row = await Database.fetch_one(query, (client_id, user_id))
        if not client_row:
            raise HTTPException(status_code=404, detail="Client not found")

        # --- 2. Pagination calculations ---
        count_query = """
        SELECT COUNT(*) AS total
        FROM transactions
        WHERE client_id = ? AND user_id = ?
        """
        count_result = await Database.fetch_one(count_query, (client_id, user_id))
        total_transactions = count_result["total"] if count_result else 0
        total_pages = math.ceil(total_transactions / limit) if total_transactions > 0 else 0
        offset = (page - 1) * limit

        # --- 3. Fetch paginated transactions ---
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
                type=row["type"],
                description=row.get("description"),
                amount=float(row["amount"]),
                date=row["date"],
                transaction_number=row.get("transaction_number")
            )
            for row in trans_rows
        ]

        # --- 4. Return structured response ---
        total_invoiced = float(client_row["total_invoiced"])
        total_paid = float(client_row["total_paid"])
        outstanding = total_invoiced - total_paid

        return ClientReportResponse(
            id=client_row["id"],
            name=client_row["name"],
            email=client_row["email"],
            phone=client_row["phone"],
            company=client_row["company"],
            created_at=client_row["created_at"],
            updated_at=client_row["updated_at"],
            total_invoiced=total_invoiced,
            total_paid=total_paid,
            outstanding=outstanding,
            transactions=transactions,
            page=page,
            limit=limit,
            total_transactions=total_transactions,
            total_pages=total_pages
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Get client report error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve client report"
        )


@router.get("/get_client/{client_id}", response_model=ClientResponse)
async def get_client(client_id: int, current_user: dict = Depends(get_current_user)):
    """Get a specific client by ID"""
    try:
        user_id = current_user['id']
        
        query = "SELECT * FROM clients WHERE id = ? AND user_id = ?"
        client = await Database.fetch_one(query, (client_id, user_id))
        
        if not client:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Client not found"
            )
        
        return ClientResponse(**client)
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Get client error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve client"
        )


@router.post("/create_client", response_model=ClientResponse)
async def create_client(
    request: ClientCreateRequest,
    # current_user: dict = Depends(get_current_user)
):
    """Create a new client"""
    # user_id = current_user['user_id']
    user_id = 1
    # Check if client with same email already exists for this user
    if request.email:
        existing_client = await Database.fetch_one(
            "SELECT id FROM clients WHERE user_id = ? AND email = ?",
            (user_id, request.email)
        )
        if existing_client:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Client with this email already exists"
            )
    
    query = """
    INSERT INTO clients (user_id, name, email, phone, company)
    VALUES (?, ?, ?, ?, ?)
    """
    await Database.execute(query, (
        user_id,
        request.name,
        request.email,
        request.phone,
        request.company
    ))
    
    # Get the created client
    created_client = await Database.fetch_one(
        "SELECT * FROM clients WHERE user_id = ? AND name = ? ORDER BY created_at DESC LIMIT 1",
        (user_id, request.name)
    )
    
    logger.info(f"Client created: {request.name} for user {user_id}")
    
    return ClientResponse(**created_client)


@router.put("/update_client/{client_id}", response_model=ClientResponse)
async def update_client(
    client_id: int,
    request: ClientUpdateRequest,
    # current_user: dict = Depends(get_current_user)
):
    """Update an existing client"""
 
    # user_id = current_user['user_id']
    user_id = 1
    # Check if client exists and belongs to user
    existing_client = await Database.fetch_one(
        "SELECT * FROM clients WHERE id = ? AND user_id = ?",
        (client_id, user_id)
    )
    if not existing_client:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Client not found"
        )
    
    # Check if email is being updated and doesn't conflict with existing client
    if request.email and request.email != existing_client['email']:
        email_conflict = await Database.fetch_one(
            "SELECT id FROM clients WHERE user_id = ? AND email = ? AND id != ?",
            (user_id, request.email, client_id)
        )
        if email_conflict:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Client with this email already exists"
            )
    
    # Build update query dynamically based on provided fields
    update_fields = []
    params = []
    
    if request.name is not None:
        update_fields.append("name = ?")
        params.append(request.name)
    if request.email is not None:
        update_fields.append("email = ?")
        params.append(request.email)
    if request.phone is not None:
        update_fields.append("phone = ?")
        params.append(request.phone)
    if request.company is not None:
        update_fields.append("company = ?")
        params.append(request.company)
    
    
    
    update_fields.append("updated_at = ?")
    params.append(datetime.utcnow())
    params.extend([client_id, user_id])
    
    query = f"""
    UPDATE clients 
    SET {', '.join(update_fields)}
    WHERE id = ? AND user_id = ?
    """
    await Database.execute(query, tuple(params))
    

    settings_fields = {
        "reminder_type": request.communication_method,
        "transaction_notification_type": request.communication_method,
        "send_transaction_notifications": request.trans_notification,
        "send_automated_reminders": request.payment_reminders,
        "reminder_frequency_days": request.reminds_every_n_days,
        "reminder_minimum_balance": request.min_balance_to_remind
    }

    existing_settings = await Database.fetch_one(
        "SELECT * FROM client_settings WHERE client_id = ? AND user_id = ?",
        (client_id, user_id)
    )

    if existing_settings:
        set_clauses = []
        values = []
        for col, val in settings_fields.items():
            if val is not None:
                set_clauses.append(f"{col} = ?")
                values.append(val)

        if set_clauses:
            set_clauses.append("updated_at = ?")
            values.append(datetime.utcnow())
            values.extend([client_id, user_id])

            await Database.execute(
                f"""
                UPDATE client_settings
                SET {', '.join(set_clauses)}
                WHERE client_id = ? AND user_id = ?
                """,
                tuple(values)
            )

    else:
        provided = {k: v for k, v in settings_fields.items() if v is not None}
        if provided:
            cols = ", ".join(provided.keys())
            placeholders = ", ".join(["?"] * len(provided))
            values = list(provided.values())

            await Database.execute(
                f"""
                INSERT INTO client_settings (user_id, client_id, {cols})
                VALUES (?, ?, {placeholders})
                """,
                (user_id, client_id, *values)
            )
    # --------------------------------------------

    # Get updated client
    updated_client = await Database.fetch_one(
        "SELECT * FROM clients WHERE id = ? AND user_id = ?",
        (client_id, user_id)
    )
    
    logger.info(f"Client and settings updated: {client_id} for user {user_id}")

    return ClientResponse(**updated_client)
  
    
    # return ClientResponse(**updated_client)

@router.get("/get_client_settings/{client_id}", response_model=ClientSettingsResponse)
async def get_client_settings(client_id : int ,
                            #   current_user: dict = Depends(get_current_user)
                              ):
    # user_id = current_user['user_id']
    user_id = 1
    client_settings = await Database.fetch_one("SELECT * FROM client_settings WHERE client_id = ? AND user_id = ?",
        (client_id, user_id))
    if not client_settings :
        client_settings = await Database.fetch_one("SELECT * FROM user_settings WHERE user_id = ?",
        (user_id,))
    if not client_settings:
        # No settings found in either table
        raise HTTPException(status_code=404, detail="Settings not found for this client or user")

    print("client settings", client_settings)
    return ClientSettingsResponse(
        communicationMethod=client_settings["reminder_type"],
        transactionNotificationEnabled=client_settings["send_transaction_notifications"],
        reminderEnabled=client_settings["send_automated_reminders"],
        reminderIntervalDays=client_settings["reminder_frequency_days"],
        reminderMinimumAmount=client_settings["reminder_minimum_balance"]
    )

@router.delete("/delete_client/{client_id}", response_model=BaseResponse)
async def delete_client(client_id: int,
                        #  current_user: dict = Depends(get_current_user)
                        ):
    """Delete a client"""
  
    # user_id = current_user['user_id']
    user_id = 1
    # Check if client exists and belongs to user
    existing_client = await Database.fetch_one(
        "SELECT * FROM clients WHERE id = ? AND user_id = ?",
        (client_id, user_id)
    )
    if not existing_client:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Client not found"
        )
    
    # Check if client has associated invoices
    invoices_count = await Database.fetch_one(
        "SELECT COUNT(*) as count FROM transactions WHERE client_id = ?",
        (client_id,)
    )
    if invoices_count['count'] > 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot delete client with {invoices_count['count']} associated invoices. Delete invoices first."
        )
    
    # Delete client
    await Database.execute(
        "DELETE FROM clients WHERE id = ? AND user_id = ?",
        (client_id, user_id)
    )
    
    logger.info(f"Client deleted: {client_id} for user {user_id}")
    
    return BaseResponse(message="Client deleted successfully")

@router.get("/clients/search")
async def search_clients(q: str,
                        #  current_user: dict = Depends(get_current_user)
                         ):
    """
    Search clients by name, company, or email (min 2 characters).
    """
    if len(q) < 2:
        return {"clients": []}
    user_id = 1
    # user_id = current_user["user_id"]
    query = """
        SELECT id, name, email, phone, company
        FROM clients
        WHERE user_id = ?
          AND (name LIKE ? OR company LIKE ? OR email LIKE ?)
        LIMIT 10
    """
    like_q = f"%{q}%"
    clients = await Database.fetch_all(query, (user_id, like_q, like_q, like_q))
    return {"clients": clients}
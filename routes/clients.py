from fastapi import APIRouter, Depends, HTTPException, status, Query, Request
from datetime import datetime
from decimal import Decimal
import math
from database import Database
from auth import get_current_user
from schemas.requests import ClientCreateRequest, ClientUpdateRequest
from schemas.responses import (ClientResponse, ClientListResponse, 
                                BaseResponse,
                               ClientSummaryResponse, ClientReportResponse,
                               ClientSettingsResponse)
from logger import get_logger
import uuid
from datetime import datetime, timedelta
from .utils import get_client_report_data

from .dbUtils import (check_existing_client, insert_client_record,apply_custom_client_settings)
logger = get_logger(__name__)
router = APIRouter()


@router.get("/get_clients", response_model=ClientListResponse)
async def get_clients(
    page: int = Query(1, ge=1),
    limit: int = Query(10, ge=1, le=100),
    current_user: dict = Depends(get_current_user)
):
    """Get all clients for the current user with aggregated totals and pagination"""
    try:
        user_id = current_user["user_id"]
        # user_id = 1

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
    current_user: dict = Depends(get_current_user)
):
    """Get detailed report of a client with paginated transactions and business profile"""

    user_id = current_user["user_id"]
    return await get_client_report_data(user_id, client_id, page, limit)



@router.get("/get_client/{client_id}", response_model=ClientResponse)
async def get_client(client_id: int,
                      current_user: dict = Depends(get_current_user)
                    ):
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
    current_user: dict = Depends(get_current_user)
):
    """Create a new client"""
    user_id = current_user['user_id']

    # Check if client with same email already exists for this user
    await check_existing_client(user_id, request.email)
    created_client = await insert_client_record(
        user_id,
        request.name,
        request.email,
        request.phone,
        request.company
    )
    client_id = created_client["id"]
    # If user unchecked "Apply default settings", insert custom notification settings
    if not request.apply_user_settings and request.notification_settings:
        await apply_custom_client_settings(user_id, client_id, request.notification_settings)
    
    logger.info(f"Client created: {request.name} for user {user_id}")
    
    return ClientResponse(**created_client)


@router.put("/update_client/{client_id}", response_model=ClientResponse)
async def update_client(
    client_id: int,
    request: ClientUpdateRequest,
    current_user: dict = Depends(get_current_user)
):
    """Update an existing client"""
 
    user_id = current_user['user_id']
    # user_id = 1
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
        "communication_method": request.communication_method,
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

        # Add this to update reminder_next_date dynamically
        set_clauses.append(
            "reminder_next_date = strftime('%Y-%m-%d %H:00:00', DATETIME('now', '+' || ? || ' days'))"
        )
        values.append(settings_fields["reminder_frequency_days"])

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
            cols = ", ".join(provided.keys()) + ", reminder_next_date"
            placeholders = ", ".join(["?"] * len(provided)) + ", strftime('%Y-%m-%d %H:00:00', DATETIME('now', '+' || ? || ' days'))"
            values = list(provided.values())
            values.append(settings_fields["reminder_frequency_days"])  # for the ? in strftime

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
                              current_user: dict = Depends(get_current_user)
                              ):
    user_id = current_user['user_id']
    # user_id = 1
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
        communicationMethod=client_settings["communication_method"],
        transactionNotificationEnabled=client_settings["send_transaction_notifications"],
        reminderEnabled=client_settings["send_automated_reminders"],
        reminderIntervalDays=client_settings["reminder_frequency_days"],
        reminderMinimumAmount=client_settings["reminder_minimum_balance"]
    )

@router.delete("/delete_client/{client_id}", response_model=BaseResponse)
async def delete_client(client_id: int,
                         current_user: dict = Depends(get_current_user)
                        ):
    """Delete a client"""
  
    user_id = current_user['user_id']
    # user_id = 1
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
            detail=f"Cannot delete client with {invoices_count['count']} associated Transactions. Delete Transactions first."
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
                         current_user: dict = Depends(get_current_user)
                         ):
    """
    Search clients by name, company, or email (min 2 characters).
    """
    if len(q) < 2:
        return {"clients": []}
    # user_id = 1
    user_id = current_user["user_id"]
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



@router.post("/clients/{client_id}/share")
async def generate_client_report_token(client_id: int,
                                       request : Request,
                                       current_user: dict = Depends(get_current_user)
                                       ):
    user_id = current_user['user_id']
    token = str(uuid.uuid4())
    expires_at = datetime.utcnow() + timedelta(days=7)  # expires in 7 days

    insert_query = """
    INSERT INTO client_report_tokens (token, user_id, client_id, expires_at, is_active)
    VALUES (?, ?, ?, ?, 1)
    """
    await Database.execute(insert_query, (token, user_id, client_id, expires_at))
    base_url = str(request.base_url)
    share_url = f"{base_url}clients/report/view?token={token}"
    return {"success": True, "share_url": share_url, "expires_at": expires_at}


@router.get("/report/view", response_model=ClientReportResponse)
async def view_shared_client_report(token: str):
    # 1. Validate token
    token_query = """
    SELECT user_id, client_id, expires_at, is_active
    FROM client_report_tokens
    WHERE token = ?
    """
    token_row = await Database.fetch_one(token_query, (token,))
    if not token_row or not token_row["is_active"]:
        raise HTTPException(status_code=400, detail="Invalid or inactive token")

    expires_at = datetime.fromisoformat(token_row["expires_at"])
    if datetime.utcnow() > expires_at:
        raise HTTPException(status_code=410, detail="This shared link has expired")

    # 2. Update access time
    await Database.execute(
        "UPDATE client_report_tokens SET last_accessed_at = CURRENT_TIMESTAMP WHERE token = ?",
        (token,)
    )

    # 3. Fetch and return report data using utils
    return await get_client_report_data(
        user_id=token_row["user_id"],
        client_id=token_row["client_id"],
        page=1,
        limit=10
    )

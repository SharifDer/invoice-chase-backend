from fastapi import (APIRouter, Depends, 
                     HTTPException, status, Query,
                     BackgroundTasks)
from datetime import datetime, date
from decimal import Decimal
import math
import re
from database import Database
from auth import get_current_user
from schemas.requests import ( UnifiedTransactionRequest,
                              TransactionUpdateRequest
                              )
from schemas.responses import ( 
                             BaseResponse, TransactionListResponse,
                                TransactionResponse, TransCreationResponse,
                                TransactionDetailsResponse)
from logger import get_logger
from .dbUtils import (check_existing_client,insert_client_record,apply_custom_client_settings)
from .remindersUtils import notify_transaction_creation
logger = get_logger(__name__)
router = APIRouter()

@router.get("/get_transaction/{trans_id}", response_model=TransactionDetailsResponse)
async def get_transaction(
        trans_id: str,  # transaction_number
        current_user: dict = Depends(get_current_user)
    ):
    user_id = current_user["user_id"]
    # user_id = 1
    trans_id = trans_id.strip('"').strip("'")
    transaction = await Database.fetch_one(
        """
        SELECT 
            t.description AS Description,
            c.email AS client_email,
            c.company AS client_company
        FROM transactions t
        JOIN clients c ON t.client_id = c.id
        WHERE t.transaction_number = ? AND t.user_id = ?
        """,
        (trans_id, user_id)
    )
    if not transaction:
        raise HTTPException(
            status_code=404,
            detail="Transaction not found"
        )

    return TransactionDetailsResponse(**transaction)

    
@router.get("/get_transactions", response_model=TransactionListResponse)
async def get_transactions(
    type_filter: str | None = Query(None, alias="type"),          # 'invoice' or 'payment'   
    client_id: int | None = Query(None),
    date_from: date | None = Query(None),
    date_to: date | None = Query(None),
    page: int = Query(1, ge=1),
    limit: int = Query(10, ge=1, le=100),
    current_user: dict = Depends(get_current_user)
):
    """Get transactions for current user with filtering and pagination"""
    user_id = current_user["user_id"]
    # user_id = 1

    # --- 1. Build WHERE clause dynamically ---
    where_conditions = ["t.user_id = ?"]
    params = [user_id]

    if type_filter:
        where_conditions.append("t.type = ?")
        params.append(type_filter)

    if client_id:
        where_conditions.append("t.client_id = ?")
        params.append(client_id)

    if date_from:
        where_conditions.append("t.created_date >= ?")
        params.append(date_from)

    if date_to:
        where_conditions.append("t.created_date <= ?")
        params.append(date_to)

    where_clause = "WHERE " + " AND ".join(where_conditions)

    # --- 2. Count total records ---
    count_query = f"""
        SELECT COUNT(*) AS total
        FROM transactions t
        {where_clause};
    """
    total_result = await Database.fetch_one(count_query, tuple(params))
    total = total_result["total"] if total_result else 0

    # --- 3. Pagination ---
    offset = (page - 1) * limit
    total_pages = math.ceil(total / limit) if total > 0 else 0

    # --- 4. Main data query ---
    query = f"""
        SELECT 
             t.client_id, t.transaction_number, c.name AS client_name,
            t.type, t.amount,
            t.created_date, t.description
        FROM transactions t
        JOIN clients c ON t.client_id = c.id
        {where_clause}
        ORDER BY t.created_date DESC
        LIMIT ? OFFSET ?;
    """

    params.extend([limit, offset])
    rows = await Database.fetch_all(query, tuple(params))

    # --- 5. Format response list ---
    transactions = [
        TransactionResponse(
            transaction_number=row["transaction_number"],
            client_id=row["client_id"],
            client_name=row["client_name"],
            type=row["type"],
            amount=float(row["amount"]),
            created_date=row["created_date"],
            description=row["description"]
        )
        for row in rows
    ]

    logger.info(f"Retrieved {len(transactions)} transactions for user {user_id}")

    # --- 6. Return structured response ---
    return TransactionListResponse(
        transactions=transactions,
        total=total,
        page=page,
        limit=limit,
        total_pages=total_pages,
        message="Transactions retrieved successfully"
    )

@router.post("/create_transaction", response_model=TransCreationResponse)
async def create_transaction(request: UnifiedTransactionRequest,
                            background_tasks: BackgroundTasks
                             ,current_user: dict = Depends(get_current_user),
                        
                             ):
    user_id = current_user["user_id"]
    # user_id = 1  # replace with current_user['user_id']

    # try:
    if request.is_new_client:
        # Create new client first
        await check_existing_client(user_id, request.client.email)
        new_client = await insert_client_record(
            user_id,
            request.client.name,
            request.client.email,
            request.client.phone,
            request.client.company
        )
        client_id = new_client["id"]

        if not request.client.apply_user_settings and request.client.notification_settings:
            await apply_custom_client_settings(
                user_id, client_id, request.client.notification_settings
            )
    else:
        # Use existing client
        client = await Database.fetch_one(
            "SELECT * FROM clients WHERE id=? AND user_id=?",
            (request.transaction.client_id, user_id)
        )
        if not client:
            raise HTTPException(
                status_code=400, detail="Client not found or doesn't belong to you"
            )
        client_id = client["id"]
    if not request.transaction.description:
        if request.transaction.type.lower() == "invoice":
            description = "Invoice issued for and recorded"
        elif request.transaction.type.lower() == "payment":
            description = "Payment received and recorded"
        else:
            description = "Transaction recorded"
    else:
        description = request.transaction.description
    # Insert transaction
    await Database.execute("""
        INSERT INTO transactions (user_id, client_id, transaction_number, amount, type, description, created_date)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (
        user_id,
        client_id,
        "TEMP",
        float(request.transaction.amount),
        request.transaction.type,
        description,
        date.today()
    ))

    # Get new transaction ID
    last_inserted = await Database.fetch_one(
        "SELECT id FROM transactions WHERE user_id=? ORDER BY id DESC LIMIT 1",
        (user_id,)
    )
    trans_id = last_inserted["id"]
    trans_num = f"TXN-{str(trans_id).zfill(3)}"

    # Update transaction_number
    await Database.execute(
        "UPDATE transactions SET transaction_number=? WHERE id=?",
        (trans_num, trans_id)
    )

    # Send notification
    background_tasks.add_task(
        notify_transaction_creation,
        user_id=user_id,
        user_email=current_user["email"],
        client_id=client_id,
        client_name=request.client.name if request.is_new_client else client["name"],
        transaction_type=request.transaction.type,
        amount=float(request.transaction.amount),
        client_email=request.client.email if request.is_new_client else client["email"],
        client_phone=request.client.phone if request.is_new_client else client["phone"],
    )
    return TransCreationResponse(
        message="Transaction created successfully",
        status="Success"
    )

    # except HTTPException:
    #     raise
    # except Exception as e:
    #     logger.error(f"Create transaction error: {e}")
    #     raise HTTPException(500, "Failed to create transaction")


@router.put("/update_transaction/{trans_id}", response_model=TransactionResponse)
async def update_invoice(
    trans_id: str,
    request: TransactionUpdateRequest,
    current_user: dict = Depends(get_current_user)
):
    """Update an existing invoice"""
    # try:
    user_id = current_user['user_id']
    trans_id = trans_id.strip('"').strip("'")
    # Check if invoice exists and belongs to user
    existing_transaction = await Database.fetch_one(
        "SELECT * FROM transactions WHERE transaction_number = ? AND user_id = ?",
        (trans_id, user_id)
    )
    if not existing_transaction:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="transaction not found"
        )
    

    # Build update query dynamically based on provided fields
    update_fields = []
    params = []
    

   
    if request.amount is not None:
        update_fields.append("amount = ?")
        params.append(float(request.amount))
    if request.description is not None:
        update_fields.append("description = ?")
        params.append(request.description)
    if request.type is not None:
        update_fields.append("type = ?")
        params.append(request.type)
    if request.created_at is not None:
        update_fields.append("created_date = ?")
        params.append(request.created_at)


    if not update_fields:
        # No fields to update, return existing invoice with client name
        raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail="No field has been updated")
    
    update_fields.append("updated_at = ?")
    params.append(datetime.utcnow())
    params.extend([trans_id, user_id])
    
    query = f"""
    UPDATE transactions 
    SET {', '.join(update_fields)}
    WHERE transaction_number = ? AND user_id = ?
    """
    await Database.execute(query, tuple(params))
    
    # Get updated invoice with client information
    updated_invoice_query = """
    SELECT 
        i.id, i.transaction_number, i.client_id, i.amount, 
         i.created_date, i.description,
        i.created_at, i.updated_at, i.type,
        c.name as client_name
    FROM transactions i
    JOIN clients c ON i.client_id = c.id
    WHERE i.transaction_number = ? AND i.user_id = ?
    """
    updated_transaction = await Database.fetch_one(
        updated_invoice_query, (trans_id, user_id)
    )
    logger.info(f"Invoice updated: {trans_id} for user {user_id}")
    return TransactionResponse(
        transaction_number= updated_transaction["transaction_number"],
        client_id = updated_transaction['client_id'],
        client_name = updated_transaction['client_name'],
        type = updated_transaction['type']  ,      # "invoice" | "payment"
        amount = Decimal(str(updated_transaction['amount'])),
        created_date = updated_transaction['created_date'],
        description = updated_transaction['description']
    )



@router.delete("/delete_transaction/{trans_id}", response_model=BaseResponse)
async def delete_invoice(trans_id: str, 
                         current_user: dict = Depends(get_current_user)
                         ):
    """Delete transaction"""
    try:
        user_id = current_user['user_id']
        trans_id = trans_id.strip('"').strip("'")
        # Delete invoice
        await Database.execute(
            "DELETE FROM transactions WHERE transaction_number = ? AND user_id = ?",
            (trans_id, user_id)
        )
        
        logger.info(f"Transaction deleted: {trans_id} for user {user_id}")
        
        return BaseResponse(message="Transaction deleted successfully")
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Delete transaction error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete transaction"
        )

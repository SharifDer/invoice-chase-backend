from fastapi import APIRouter, HTTPException, Depends
from firebase_admin import auth as firebase_auth
from database import Database
from auth import AuthUtils, get_current_user, make_firebase_api_request
from schemas.requests import CreateUserRequest, FirebaseLoginRequest, ReqUserLogin
from schemas.responses import AuthResponse, UserResponse
from logger import get_logger
from config import settings
from datetime import datetime
from fastapi import HTTPException, status
from fastapi import BackgroundTasks
from .utils import generate_welcome_email
from .reminders import send_email

from firebase_admin import auth
logger = get_logger(__name__)
router = APIRouter()


async def _get_or_create_user(uid: str, email: str, 
                              name: str = None , 
                              email_verified: bool = False,
                              background : BackgroundTasks = None
                             ):
    """Fetch user from DB or create if missing."""
    user = await Database.fetch_one("SELECT * FROM users WHERE firebase_uid = ?", (uid,))
    if not user:
        query = """
        INSERT INTO users (firebase_uid, email, name, email_verified)
        VALUES (?, ?, ?, ?)
        """
        await Database.execute(query, (uid, email, name, email_verified))

        user = await Database.fetch_one("SELECT * FROM users WHERE firebase_uid = ?", (uid,))
        logger.info(f"New Firebase user created: {email}")

        if email_verified:
            background.add_task(welcome_email_task, name, email)
            logger.info(f"Welcome email is being sent to newly verified user: {email}")

    if user and user["email_verified"] != email_verified:
        await Database.execute(
            "UPDATE users SET email_verified = ? WHERE firebase_uid = ?",
            (email_verified, uid)
        )
        
        if email_verified:
            background.add_task(welcome_email_task, name, email)
            logger.info(f"Welcome email is being sent to this email : {email}")        
    return user


# =========================
# Backend/Admin Auth Functions
# =========================
# @router.post("/admin/create-user", response_model=AuthResponse)
# async def create_user(request: CreateUserRequest):
#     """Create a new Firebase user from backend (Swagger/admin testing)."""
#     try:
#         user_record = AuthUtils.create_user(
#             email=request.email,
#             password=request.password,
#             display_name=request.name
#         )
#         user = await _get_or_create_user(user_record.uid, user_record.email, user_record.name , email_verified=user_record.email_verified)
#         return AuthResponse(user=UserResponse(**user), message="User created successfully")
#     except Exception as e:
#         logger.error(f"Backend create user error: {e}")
#         raise HTTPException(status_code=400, detail="Failed to create user")

# @router.post("/admin/login")
# async def login_user(req: ReqUserLogin) -> dict:
#     payload = {
#         "email": req.email,
#         "password": req.password,
#         "returnSecureToken": True,
#     }

#     response = await make_firebase_api_request(
#         settings.firebase_signin_url + "?key=" + settings.FIREBASE_WEB_API_KEY, payload
#     )
#     response["created_at"] = datetime.now()

#     # Check if email is verified (Firebase returns this in response)
#     # if not response.get("emailVerified", False):
#     #     raise HTTPException(
#     #         status_code=status.HTTP_401_UNAUTHORIZED,
#     #         detail="Unverified Email",
#     #     )

#     # (Optional) Verify ID token with Admin SDK to keep same flow as your /login endpoint
#     decoded = auth.verify_id_token(response["idToken"])
#     print("decoded ", decoded)
#     user = await _get_or_create_user(
#         decoded["uid"],
#         decoded.get("email"),
#         decoded.get("name"),
#         decoded.get("email_verified")
#     )

#     return {
#         "token": response["idToken"],
#         "refresh_token": response["refreshToken"],
#         "expires_in": int(response["expiresIn"]),
#         "user": user,
#         "message": "Login successful",
#     }
# @router.delete("/admin/delete-user/{user_email}")
# async def delete_user(user_email: str):
#     """Delete a Firebase user and their data from backend."""
#     try:
#         # Get Firebase user by email
#         firebase_user = firebase_auth.get_user_by_email(user_email)
        
#         # Delete from database first
#         user = await Database.fetch_one("SELECT * FROM users WHERE firebase_uid = ?", (firebase_user.uid,))
#         if user:
#             # Delete user settings
#             await Database.execute("DELETE FROM settings WHERE user_id = ?", (user['id'],))
#             # Delete user invoices (if any)
#             await Database.execute("DELETE FROM invoices WHERE user_id = ?", (user['id'],))
#             # Delete user clients (if any) 
#             await Database.execute("DELETE FROM clients WHERE user_id = ?", (user['id'],))
#             # Delete user
#             await Database.execute("DELETE FROM users WHERE firebase_uid = ?", (firebase_user.uid,))
            
#         # Delete from Firebase
#         firebase_auth.delete_user(firebase_user.uid)
        
#         logger.info(f"User deleted: {user_email}")
#         return {"message": "User deleted successfully"}
#     except Exception as e:
#         logger.error(f"Delete user error: {e}")
#         raise HTTPException(status_code=400, detail="Failed to delete user")


# @router.put("/admin/change-password")
# async def change_user_password(user_email: str, new_password: str):
#     """Change user password from backend."""
#     try:
#         # Get Firebase user by email
#         firebase_user = firebase_auth.get_user_by_email(user_email)
        
#         # Update password in Firebase
#         firebase_auth.update_user(firebase_user.uid, password=new_password)
        
#         logger.info(f"Password changed for user: {user_email}")
#         return {"message": "Password changed successfully"}
#     except Exception as e:
#         logger.error(f"Change password error: {e}")
#         raise HTTPException(status_code=400, detail="Failed to change password")


# @router.put("/admin/update-user")
# async def update_user(user_email: str, new_name: str = None, new_email: str = None):
#     """Update user information from backend."""
#     try:
#         # Get Firebase user by email
#         firebase_user = firebase_auth.get_user_by_email(user_email)
        
#         # Update Firebase user
#         update_data = {}
#         if new_email:
#             update_data['email'] = new_email
#         if new_name:
#             update_data['display_name'] = new_name
            
#         if update_data:
#             firebase_auth.update_user(firebase_user.uid, **update_data)
        
#         # Update database
#         if new_name or new_email:
#             db_update_query = "UPDATE users SET "
#             params = []
#             updates = []
            
#             if new_name:
#                 updates.append("name = ?")
#                 params.append(new_name)
#             if new_email:
#                 updates.append("email = ?")
#                 params.append(new_email)
                
#             db_update_query += ", ".join(updates) + " WHERE firebase_uid = ?"
#             params.append(firebase_user.uid)
            
#             await Database.execute(db_update_query, tuple(params))
        
#         # Return updated user
#         user = await Database.fetch_one("SELECT * FROM users WHERE firebase_uid = ?", (firebase_user.uid,))
#         return AuthResponse(user=UserResponse(**user), message="User updated successfully")
#     except Exception as e:
#         logger.error(f"Update user error: {e}")
#         raise HTTPException(status_code=400, detail="Failed to update user")


# @router.get("/admin/list-users")
# async def list_all_users():
#     """List all users (for admin/testing purposes)."""
#     try:
#         users = await Database.fetch_all("SELECT * FROM users")
#         return {"users": [UserResponse(**user) for user in users]}
#     except Exception as e:
#         logger.error(f"List users error: {e}")
#         raise HTTPException(status_code=400, detail="Failed to fetch users")


# @router.get("/admin/user/{user_email}", response_model=AuthResponse)
# async def get_user_by_email(user_email: str):
#     """Get user by email (for admin/testing purposes)."""
#     try:
#         firebase_user = firebase_auth.get_user_by_email(user_email)
#         user = await Database.fetch_one("SELECT * FROM users WHERE firebase_uid = ?", (firebase_user.uid,))
#         if not user:
#             raise HTTPException(status_code=404, detail="User not found in database")
#         return AuthResponse(user=AuthResponse(**user), message="User found")
#     except Exception as e:
#         logger.error(f"Get user error: {e}")
#         raise HTTPException(status_code=400, detail="Failed to get user")


# @router.post("/admin/reset-password")
# async def reset_user_password(user_email: str):
#     """Send password reset email to user."""
#     try:
#         # Firebase will handle sending the reset email
#         # This is just a trigger - actual reset is done via Firebase Auth UI
#         firebase_user = AuthUtils.get_user_by_email(user_email)
        
#         # Generate password reset link (optional - for custom implementation)
#         reset_link = firebase_auth.generate_password_reset_link(user_email)
        
#         logger.info(f"Password reset initiated for user: {user_email}")
#         return {"message": "Password reset email sent", "reset_link": reset_link}
#     except Exception as e:
#         logger.error(f"Reset password error: {e}")
#         raise HTTPException(status_code=400, detail="Failed to send reset email")


# =========================
# Frontend signup/login flow (unchanged)
# =========================
@router.post("/signup", response_model=AuthResponse)
async def signup(request: FirebaseLoginRequest , background: BackgroundTasks):
    """Register or login user sent from frontend Firebase signup."""
    try:
        decoded = firebase_auth.verify_id_token(request.firebase_token)
        user = await _get_or_create_user(
            decoded["uid"],
            decoded.get("email"),
            decoded.get("name"),
            decoded.get("email_verified", False),
            background=background
        )
        return AuthResponse(user=UserResponse(**user), message="User created successfully")
    except Exception as e:
        logger.error(f"Signup error: {e}")
        raise HTTPException(status_code=400, detail="Failed to sign up")


@router.post("/login", response_model=AuthResponse)
async def login(request: FirebaseLoginRequest , background : BackgroundTasks):
    """Login user using Firebase ID token (no password check)."""
    try:
        decoded = firebase_auth.verify_id_token(request.firebase_token)
        user = await _get_or_create_user(
            decoded["uid"],
            decoded.get("email"),
            decoded.get("name"),
            decoded.get("email_verified", False),
            background=background
        )
        return AuthResponse(user=UserResponse(**user), message="Login successful")
    except Exception as e:
        logger.error(f"Login error: {e}")
        raise HTTPException(status_code=400, detail="Login failed")



@router.get("/me", response_model=UserResponse)
async def get_current_user_info(current_user: dict = Depends(get_current_user)):
    """Return current user profile."""
    return UserResponse(**current_user)



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
    logger.info(f"Weclome email has been sent Successfully to this Email {email}")
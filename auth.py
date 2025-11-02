import firebase_admin
from firebase_admin import auth, credentials
from fastapi import HTTPException, status, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from typing import Optional, Dict, Any
from config import settings
from logger import get_logger
import httpx
logger = get_logger(__name__)
from database import Database
# JWT token bearer
security = HTTPBearer()

# Initialize Firebase Admin
if not firebase_admin._apps:
    cred = credentials.Certificate(settings.FIREBASE_SERVICE_ACCOUNT_PATH)
    firebase_admin.initialize_app(cred)

class AuthUtils:
    @staticmethod
    def verify_firebase_token(id_token: str) -> Optional[Dict[str, Any]]:
        """
        Verify Firebase ID token and return decoded payload.
        Returns None if verification fails.
        """
        try:
            decoded = auth.verify_id_token(id_token)
            return decoded
        except Exception as e:
            logger.warning(f"Firebase token verification failed: {e}")
            return None

    @staticmethod
    def create_user(email: str, password: str, display_name: str):
        """
        Create a new Firebase user (backend only).
        Firebase Admin SDK methods are synchronous, not async.
        """
        try:
            user = auth.create_user(
                email=email,
                password=password,
                display_name=display_name
            )
            return user  # Return the full user record object
        except Exception as e:
            logger.error(f"Failed to create Firebase user: {e}")
            raise HTTPException(status_code=400, detail="Failed to create user")

    @staticmethod
    def change_password(uid: str, new_password: str) -> None:
        """
        Change user password (admin-side).
        Firebase Admin SDK methods are synchronous.
        """
        try:
            auth.update_user(uid, password=new_password)
        except Exception as e:
            logger.error(f"Failed to change password for {uid}: {e}")
            raise HTTPException(status_code=400, detail="Failed to change password")

    @staticmethod
    def delete_user(uid: str) -> None:
        """
        Delete user from Firebase.
        Firebase Admin SDK methods are synchronous.
        """
        try:
            auth.delete_user(uid)
        except Exception as e:
            logger.error(f"Failed to delete user {uid}: {e}")
            raise HTTPException(status_code=400, detail="Failed to delete user")

    @staticmethod
    def get_user_by_email(email: str):
        """
        Get Firebase user by email.
        """
        try:
            user = auth.get_user_by_email(email)
            return user
        except Exception as e:
            logger.error(f"Failed to get user by email {email}: {e}")
            raise HTTPException(status_code=404, detail="User not found")

    @staticmethod
    def update_user(uid: str, **kwargs):
        """
        Update Firebase user.
        """
        try:
            user = auth.update_user(uid, **kwargs)
            return user
        except Exception as e:
            logger.error(f"Failed to update user {uid}: {e}")
            raise HTTPException(status_code=400, detail="Failed to update user")

async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)) -> Dict[str, Any]:
    """
    Dependency to get current authenticated user from Firebase token.
    Returns Firebase UID and name so you can use it in your DB.
    """
    id_token = credentials.credentials
    decoded = AuthUtils.verify_firebase_token(id_token)
    if decoded is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    client = await Database.fetch_one(
            "SELECT * FROM users WHERE firebase_uid = ?",
            (decoded["uid"],)
        )
    
    return {
        "user_id" : client["id"],
        "firebase_id": decoded["uid"],
        "name": decoded.get("name", decoded.get("email", "")),
        "email": decoded.get("email", None),
        "currency" : client["currency"],
        "currency_symobl" : client["currency_symobl"],
        "plan_type" : client["plan_type"],
        "trial_end_date" : client["trial_end_date"],

    }

async def get_optional_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)) -> Optional[Dict[str, Any]]:
    """Return user info if token is valid, else None."""
    try:
        return await get_current_user(credentials)
    except HTTPException:
        return None


async def make_firebase_api_request(url: str, payload: dict):
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(url, json=payload)
            if resp.status_code != 200:
                err = resp.json().get("error", {}).get("message", "UNKNOWN_ERROR")
                raise HTTPException(status_code=resp.status_code, detail=err)
            return resp.json()
    except httpx.RequestError as e:
        raise HTTPException(
            status_code=500, detail=f"Firebase request failed: {str(e)}"
        )
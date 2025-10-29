import os
from typing import Optional
from dotenv import load_dotenv
import json


class Settings:
    # Database
    DATABASE_URL: str = "invoice_chase.db"
    firebase_base_url = "https://identitytoolkit.googleapis.com/v1/accounts:"
    firebase_signin_url = f"{firebase_base_url}signInWithPassword"
    FIREBASE_WEB_API_KEY: Optional[str] = "AIzaSyAGk5_SL1qA2wN38VSaSYsUUHdYw6CD8Ic"
    FIREBASE_SERVICE_ACCOUNT_PATH = "keys/firebase.json"
    resend_api_key : str = ""
    twilio_account_sid : str = ""
    twilio_auth_token : str = ""
    twilio_number : str = ""

    EMAIL_SUPPORT_INBOX = "Pursue Payments Support <support@pursuepayments.com>"
    EMAIL_FROM_VERIFY = "Pursue Payments <verify@pursuepayments.com>"
    EMAIL_FROM_SYSTEM = "Pursue Payments <system@pursuepayments.com>"

    EMAIL_FROM_INVOICE = "Pursue Payments <invoices@pursuepayments.com>"
    EMAIL_FROM_REMINDER = "Pursue Payments <reminders@pursuepayments.com>"
    EMAIL_FROM_RECEIPT = "Pursue Payments <receipts@pursuepayments.com>"
    DEBUG: bool = "true"
    @classmethod
    def get_conf(cls):
        
        with open("keys/keys.json" , "r" , encoding="utf-8") as api_keys:
            data = json.load(api_keys)
            cls.resend_api_key = data.get("resend_key")
            cls.twilio_account_sid = data.get("twilio_account_sid")
            cls.twilio_auth_token = data.get("twilio_auth_token")
            cls.twilio_number = data.get("twilio_number")
            return cls


settings = Settings.get_conf()

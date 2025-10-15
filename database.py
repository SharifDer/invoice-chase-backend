import aiosqlite
import os
from typing import List, Dict, Any, Optional
from contextlib import asynccontextmanager
from config import settings
from logger import get_logger

logger = get_logger(__name__)


class Database:
    _db_path: str = settings.DATABASE_URL
    
    @classmethod
    async def initialize(cls):
        """Initialize database and create tables if they don't exist"""
        logger.info(f"Initializing database at: {cls._db_path}")
        await cls._create_tables()
    
    @classmethod
    async def close(cls):
        """Close database connections - placeholder for cleanup if needed"""
        logger.info("Database cleanup completed")
    
    @classmethod
    @asynccontextmanager
    async def connection(cls):
        """Context manager for database connections"""
        async with aiosqlite.connect(cls._db_path) as conn:
            conn.row_factory = aiosqlite.Row  # Enable dict-like access
            yield conn
    
    @classmethod
    async def execute(cls, query: str, params: tuple = None) -> None:
        """Execute a query without returning results"""
        async with cls.connection() as conn:
            await conn.execute(query, params or ())
            await conn.commit()
            logger.debug(f"Executed: {query[:100]}...")
    
    @classmethod
    async def fetch_one(cls, query: str, params: tuple = None) -> Optional[Dict[str, Any]]:
        """Fetch a single row"""
        async with cls.connection() as conn:
            cursor = await conn.execute(query, params or ())
            row = await cursor.fetchone()
            logger.debug(f"Fetched one: {query[:100]}...")
            return dict(row) if row else None
    
    @classmethod
    async def fetch_all(cls, query: str, params: tuple = None) -> List[Dict[str, Any]]:
        """Fetch multiple rows"""
        async with cls.connection() as conn:
            cursor = await conn.execute(query, params or ())
            rows = await cursor.fetchall()
            logger.debug(f"Fetched {len(rows)} rows: {query[:100]}...")
            return [dict(row) for row in rows]
    
    @classmethod
    async def execute_many(cls, query: str, params_list: List[tuple]) -> None:
        """Execute query multiple times with different parameters"""
        async with cls.connection() as conn:
            await conn.executemany(query, params_list)
            await conn.commit()
            logger.debug(f"Executed many ({len(params_list)} times): {query[:100]}...")
    
    @classmethod
    async def health_check(cls) -> bool:
        """Check if database is accessible"""
        try:
            async with cls.connection() as conn:
                await conn.execute("SELECT 1")
            return True
        except Exception as e:
            logger.error(f"Database health check failed: {e}")
            return False
    
    @classmethod
    async def _create_tables(cls):
        """Create all database tables"""
        tables = [
            
            """
            CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT UNIQUE NOT NULL,
            firebase_uid TEXT UNIQUE,
            name TEXT NOT NULL,
            email_verified BOOLEAN DEFAULT FALSE,
            stripe_account_id TEXT UNIQUE,
            currency TEXT NOT NULL DEFAULT 'USD',
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
        );
            """,
            """
            CREATE TABLE IF NOT EXISTS business_info (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL UNIQUE,
                business_name TEXT NOT NULL,
                business_email TEXT,
                phone TEXT,
                address TEXT,
                website TEXT,
                logo_url TEXT,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
            );
                """
            

            """
            CREATE TABLE IF NOT EXISTS clients (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            email TEXT,
            phone TEXT,
            company TEXT,
            stripe_customer_id TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
        );
            """,
            
     
            """
    
            CREATE TABLE IF NOT EXISTS transactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            client_id INTEGER NOT NULL,
            transaction_number TEXT NOT NULL,
            amount DECIMAL(10,2) NOT NULL,
            type TEXT NOT NULL CHECK (type IN ('payment', 'invoice')),
            created_date DATE DEFAULT CURRENT_DATE,
            description TEXT,
            stripe_payment_intent_id TEXT,
            stripe_payment_link_id TEXT,
            payment_method TEXT DEFAULT 'manual',
            status TEXT DEFAULT 'completed' CHECK (status IN ('pending', 'completed', 'failed', 'refunded')),
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE,
            FOREIGN KEY (client_id) REFERENCES clients (id) ON DELETE CASCADE
        );

            """,
            
     
            """

        CREATE TABLE IF NOT EXISTS user_settings (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL UNIQUE,
        send_automated_reminders BOOLEAN DEFAULT true,
        reminder_frequency_days INTEGER DEFAULT 7,
        reminder_type TEXT DEFAULT 'email' CHECK (reminder_type IN ('email', 'sms', 'both')),
        reminder_minimum_balance DECIMAL(10,2) DEFAULT 0.00,
        send_transaction_notifications BOOLEAN DEFAULT true,
        transaction_notification_type TEXT DEFAULT 'email' CHECK (transaction_notification_type IN ('email', 'sms', 'both')),
        reminder_template TEXT,
        notification_template TEXT,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
    );
            """,
            """


        CREATE TABLE IF NOT EXISTS client_settings (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        client_id INTEGER NOT NULL,
        send_automated_reminders BOOLEAN,
        reminder_frequency_days INTEGER,
        reminder_type TEXT CHECK (reminder_type IN ('email', 'sms', 'both')),
        reminder_minimum_balance DECIMAL(10,2),
        send_transaction_notifications BOOLEAN,
        transaction_notification_type TEXT CHECK (transaction_notification_type IN ('email', 'sms', 'both')),
        reminder_template TEXT,
        notification_template TEXT,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(user_id, client_id),
        FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE,
        FOREIGN KEY (client_id) REFERENCES clients (id) ON DELETE CASCADE
    );
            """,
    """

        CREATE TABLE IF NOT EXISTS client_report_tokens (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        token TEXT UNIQUE NOT NULL,
        user_id INTEGER NOT NULL,
        client_id INTEGER NOT NULL,
        expires_at DATETIME NOT NULL,
        is_active BOOLEAN DEFAULT true,
        last_accessed_at DATETIME,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE,
        FOREIGN KEY (client_id) REFERENCES clients (id) ON DELETE CASCADE
    );
    """
        ]
        
        async with cls.connection() as conn:
            # Create tables
            for table_sql in tables:
                await conn.executescript(table_sql)
                logger.debug("Created table")
            
            await conn.commit()
            logger.info("All database tables created successfully")

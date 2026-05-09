"""
phantombox/auth/db.py
─────────────────────────────────────────────────────────────
MySQL database connection using mysql-connector-python.
Replaces SQLite. Connects to the existing phantombox_db
with the users, file_registry, and audit_ledger tables.
─────────────────────────────────────────────────────────────
"""

import os
import logging
import mysql.connector
from mysql.connector import pooling
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger("phantombox.db")

# ── Connection Config ────────────────────────────────────────
DB_CONFIG = {
    "host":     os.getenv("DB_HOST",     "localhost"),
    "port":     int(os.getenv("DB_PORT", "3306")),
    "user":     os.getenv("DB_USER",     "root"),
    "password": os.getenv("DB_PASSWORD", "Sachhu55@#"),
    "database": os.getenv("DB_NAME",     "phantombox_db"),
    "charset":  "utf8mb4",
    "collation":"utf8mb4_unicode_ci",
    "autocommit": False,
    "connection_timeout": 10,
}

# Connection pool (5–20 connections)
_pool = None

def _get_pool():
    global _pool
    if _pool is None:
        _pool = pooling.MySQLConnectionPool(
            pool_name="phantombox_pool",
            pool_size=10,
            pool_reset_session=True,
            **DB_CONFIG
        )
        logger.info("✅ MySQL connection pool created")
    return _pool


def get_connection():
    """Get a connection from the pool."""
    return _get_pool().get_connection()


# phantombox/auth/db.py

import os
import logging
import mysql.connector
from mysql.connector import pooling
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger("phantombox.db")

DB_CONFIG = {
    "host": os.getenv("DB_HOST", "localhost"),
    "port": int(os.getenv("DB_PORT", "3306")),
    "user": os.getenv("DB_USER", "root"),
    "password": os.getenv("DB_PASSWORD", "Sachhu55@#"),
    "database": os.getenv("DB_NAME", "phantombox_db"),
    "charset": "utf8mb4",
    "collation": "utf8mb4_unicode_ci",
}

_pool = None

def _get_pool():
    global _pool
    if _pool is None:
        try:
            # Increased pool_size to 32 to prevent "Queue is full"
            _pool = pooling.MySQLConnectionPool(
                pool_name="phantombox_pool",
                pool_size=32, 
                pool_reset_session=True,
                **DB_CONFIG
            )
            logger.info("✅ MySQL connection pool created (Size: 32)")
        except Exception as e:
            logger.error(f"❌ Failed to create status pool: {e}")
            raise
    return _pool

def get_db():
    """
    Get a connection and cursor. 
    IMPORTANT: You must call conn.close() in the calling function 
    to return the connection to the pool!
    """
    try:
        pool = _get_pool()
        conn = pool.get_connection()
        # buffered=True prevents the "Unread result found" error
        cursor = conn.cursor(dictionary=True, buffered=True)
        return conn, cursor
    except Exception as e:
        logger.error(f"❌ Pool connection error: {e}")
        raise

def init_db():
    """Check connection and clear any stale results."""
    conn = None
    cursor = None
    try:
        conn, cursor = get_db()
        cursor.execute("SELECT 1")
        cursor.fetchall()
        logger.info("✅ MySQL Database connected and verified")
    except Exception as e:
        logger.error(f"❌ DB connection error: {e}")
    finally:
        # ALWAYS CLOSE to release back to pool
        if cursor: cursor.close()
        if conn: conn.close()


def write_audit(action_type: str, user_id: str = None,
                file_id: str = None, details: str = None,
                ip: str = None):
    """Write an audit log entry (fire-and-forget)."""
    try:
        conn, cursor = get_db()
        cursor.execute(
            """INSERT INTO audit_ledger
               (action_type, user_id, file_id, details, ip_address)
               VALUES (%s, %s, %s, %s, %s)""",
            (action_type, user_id, file_id, details, ip)
        )
        conn.commit()
        cursor.close()
        conn.close()
    except Exception as e:
        logger.warning(f"Audit write failed: {e}")
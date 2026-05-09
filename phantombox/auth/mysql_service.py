"""
phantombox/auth/mysql_service.py
─────────────────────────────────────────────────────────────
MySQL-backed authentication service.
Replaces the SQLite service.py and the client-side localStorage logic.

All passwords stored as bcrypt hashes — never plaintext.
JWT issued on login; role embedded in token for RBAC.
─────────────────────────────────────────────────────────────
"""

import uuid
import json
import logging
from datetime import datetime, timezone, timedelta
from typing import Tuple, Optional

import bcrypt
import jwt

from .db import get_db, write_audit

logger = logging.getLogger("phantombox.auth")

# ── JWT Config ───────────────────────────────────────────────
import os
JWT_SECRET    = os.getenv("JWT_SECRET", "phantombox_jwt_secret_change_in_prod")
JWT_ALGORITHM = "HS256"
ACCESS_TTL    = 86400       # 24 hours (comfortable for demo)
MAX_FAILS     = 5
LOCK_SECONDS  = 900         # 15 min

def _now() -> float:
    return datetime.now(timezone.utc).timestamp()

def _new_id() -> str:
    return str(uuid.uuid4())


# ── Password Helpers ─────────────────────────────────────────

def hash_password(plain: str) -> str:
    return bcrypt.hashpw(plain.encode(), bcrypt.gensalt(rounds=12)).decode()

def verify_password(plain: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(plain.encode(), hashed.encode())
    except Exception:
        return False


# ── JWT ──────────────────────────────────────────────────────

def create_token(user: dict) -> str:
    payload = {
        "sub":   user["id"],
        "email": user["email"],
        "role":  user["role"],
        "name":  f"{user.get('first_name','')} {user.get('last_name','')}".strip(),
        "iat":   datetime.now(timezone.utc),
        "exp":   datetime.now(timezone.utc) + timedelta(seconds=ACCESS_TTL),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)

def decode_token(token: str) -> Optional[dict]:
    try:
        return jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
    except jwt.ExpiredSignatureError:
        return None
    except jwt.InvalidTokenError:
        return None


# ── Register ─────────────────────────────────────────────────

def register_user(email: str, password: str, first_name: str,
                  last_name: str, role: str = "User",
                  ip: str = None) -> Tuple[bool, dict]:
    if len(password) < 8:
        return False, {"error": "Password must be at least 8 characters.", "field": "password"}

    email = email.strip().lower()
    conn, cur = get_db()
    try:
        # Check duplicate
        cur.execute("SELECT id FROM users WHERE email = %s", (email,))
        if cur.fetchone():
            return False, {"error": "An account with this email already exists.", "field": "email"}

        uid    = _new_id()
        pw_hash = hash_password(password)

        cur.execute(
            """INSERT INTO users
               (id, email, password_hash, first_name, last_name, role, is_active)
               VALUES (%s, %s, %s, %s, %s, %s, 1)""",
            (uid, email, pw_hash, first_name.strip(), last_name.strip(), role)
        )
        conn.commit()

        write_audit("REGISTER", user_id=uid,
                    details=f"New {role} registered: {email}", ip=ip)

        user = {
            "id": uid, "email": email,
            "first_name": first_name.strip(),
            "last_name":  last_name.strip(),
            "role": role,
        }
        logger.info(f"Registered: {email} [{role}]")
        return True, {"user": user, "message": "Account created successfully!"}

    except Exception as e:
        conn.rollback()
        logger.error(f"Register error: {e}")
        return False, {"error": "Registration failed. Please try again."}
    finally:
        cur.close(); conn.close()


# ── Login ────────────────────────────────────────────────────

def login_user(email: str, password: str, ip: str = None) -> Tuple[bool, dict]:
    email = email.strip().lower()
    conn, cur = get_db()
    try:
        cur.execute(
            """SELECT id, email, password_hash, first_name, last_name,
                      role, is_active, failed_login_attempts, locked_until
               FROM users WHERE email = %s""",
            (email,)
        )
        user = cur.fetchone()

        if not user:
            write_audit("LOGIN_FAILED", details=f"Unknown email: {email}", ip=ip)
            return False, {"error": "Invalid email or password.", "code": "INVALID"}

        if not user["is_active"]:
            return False, {"error": "Account is deactivated.", "code": "INACTIVE"}

        # Lockout check
        if user["locked_until"] and _now() < user["locked_until"]:
            wait = int(user["locked_until"] - _now())
            return False, {
                "error": f"Account locked. Try again in {wait // 60}m {wait % 60}s.",
                "code": "LOCKED", "retry_after": wait
            }

        if not verify_password(password, user["password_hash"]):
            fails = user["failed_login_attempts"] + 1
            lock_until = None
            if fails >= MAX_FAILS:
                lock_until = int(_now() + LOCK_SECONDS)
                cur.execute(
                    "UPDATE users SET failed_login_attempts=%s, locked_until=%s WHERE id=%s",
                    (fails, lock_until, user["id"])
                )
                conn.commit()
                write_audit("ACCOUNT_LOCKED", user_id=user["id"], ip=ip)
                return False, {"error": "Too many failed attempts. Account locked 15 min.", "code": "LOCKED"}
            else:
                cur.execute(
                    "UPDATE users SET failed_login_attempts=%s WHERE id=%s",
                    (fails, user["id"])
                )
                conn.commit()
                left = MAX_FAILS - fails
                return False, {
                    "error": f"Invalid email or password. {left} attempt(s) left.",
                    "code": "INVALID"
                }

        # Success — reset fail counter, record login
        cur.execute(
            """UPDATE users
               SET failed_login_attempts=0, locked_until=NULL,
                   last_login_at=NOW()
               WHERE id=%s""",
            (user["id"],)
        )
        conn.commit()

        user_dict = {
            "id":         user["id"],
            "email":      user["email"],
            "first_name": user["first_name"],
            "last_name":  user["last_name"],
            "role":       user["role"],
        }
        token = create_token(user_dict)

        write_audit("LOGIN_SUCCESS", user_id=user["id"],
                    details=f"Login from {ip}", ip=ip)
        logger.info(f"Login: {email} [{user['role']}]")

        return True, {
            "access_token": token,
            "token_type":   "Bearer",
            "expires_in":   ACCESS_TTL,
            "user":         user_dict,
        }

    except Exception as e:
        conn.rollback()
        logger.error(f"Login error: {e}")
        return False, {"error": "Login failed.", "code": "SERVER_ERROR"}
    finally:
        cur.close(); conn.close()


# ── Get user by ID ───────────────────────────────────────────

def get_user_by_id(user_id: str) -> Optional[dict]:
    conn, cur = get_db()
    try:
        cur.execute(
            """SELECT id, email, first_name, last_name, role,
                      is_active, created_at, last_login_at
               FROM users WHERE id = %s""",
            (user_id,)
        )
        row = cur.fetchone()
        if not row:
            return None
        # Convert timestamps to strings
        for k in ("created_at", "last_login_at"):
            if row.get(k) and hasattr(row[k], "isoformat"):
                row[k] = row[k].isoformat()
        return row
    finally:
        cur.close(); conn.close()


# ── File Ownership ───────────────────────────────────────────

def register_file_owner(file_id: str, owner_id: str, original_filename: str,
                        file_hash: str, fragment_count: int = 3,
                        file_size: int = 0) -> bool:
    """Called after successful upload to record ownership."""
    conn, cur = get_db()
    try:
        cur.execute(
            """INSERT INTO file_registry
               (file_id, owner_id, original_filename, file_hash, fragment_count, file_size)
               VALUES (%s, %s, %s, %s, %s, %s)
               ON DUPLICATE KEY UPDATE
               owner_id=%s, original_filename=%s, file_hash=%s""",
            (file_id, owner_id, original_filename, file_hash,
             fragment_count, file_size,
             owner_id, original_filename, file_hash)
        )
        conn.commit()
        write_audit("UPLOAD", user_id=owner_id, file_id=file_id,
                    details=f"Uploaded {original_filename} ({file_size} bytes)")
        return True
    except Exception as e:
        conn.rollback()
        logger.error(f"register_file_owner error: {e}")
        return False
    finally:
        cur.close(); conn.close()


def get_file_owner(file_id: str) -> Optional[dict]:
    """Return the file_registry row for a given file_id."""
    conn, cur = get_db()
    try:
        cur.execute(
            "SELECT * FROM file_registry WHERE file_id = %s", (file_id,)
        )
        row = cur.fetchone()
        if row and row.get("upload_time") and hasattr(row["upload_time"], "isoformat"):
            row["upload_time"] = row["upload_time"].isoformat()
        return row
    finally:
        cur.close(); conn.close()


def can_access_file(file_id: str, user_id: str, role: str) -> Tuple[bool, str]:
    """
    Return (True, "") if user may download file_id.
    Admin can download anything. User only their own files.
    """
    if role == "Admin":
        return True, ""

    row = get_file_owner(file_id)
    if not row:
        return False, "File not found."
    if row["owner_id"] != user_id:
        return False, "Access denied. You are not the owner of this file."
    return True, ""


# ── User's own files ─────────────────────────────────────────

def get_user_files(user_id: str, role: str) -> list:
    """Admin sees all files; User sees only their own."""
    conn, cur = get_db()
    try:
        if role == "Admin":
            cur.execute(
                """SELECT fr.*, u.email as owner_email
                   FROM file_registry fr
                   JOIN users u ON fr.owner_id = u.id
                   ORDER BY fr.upload_time DESC"""
            )
        else:
            cur.execute(
                """SELECT fr.*, u.email as owner_email
                   FROM file_registry fr
                   JOIN users u ON fr.owner_id = u.id
                   WHERE fr.owner_id = %s
                   ORDER BY fr.upload_time DESC""",
                (user_id,)
            )
        rows = cur.fetchall()
        for r in rows:
            if r.get("upload_time") and hasattr(r["upload_time"], "isoformat"):
                r["upload_time"] = r["upload_time"].isoformat()
        return rows
    finally:
        cur.close(); conn.close()


# ── Admin: all users ─────────────────────────────────────────

def get_all_users() -> list:
    conn, cur = get_db()
    try:
        cur.execute(
            """SELECT id, email, first_name, last_name, role,
                      is_active, created_at, last_login_at
               FROM users ORDER BY created_at DESC"""
        )
        rows = cur.fetchall()
        for r in rows:
            for k in ("created_at", "last_login_at"):
                if r.get(k) and hasattr(r[k], "isoformat"):
                    r[k] = r[k].isoformat()
        return rows
    finally:
        cur.close(); conn.close()


# ── Audit log ────────────────────────────────────────────────

def get_audit_log(user_id: str = None, role: str = "User",
                  limit: int = 100) -> list:
    """Admin sees all events; User sees only their own."""
    conn, cur = get_db()
    try:
        if role == "Admin":
            cur.execute(
                """SELECT al.*, u.email as user_email
                   FROM audit_ledger al
                   LEFT JOIN users u ON al.user_id = u.id
                   ORDER BY al.timestamp DESC LIMIT %s""",
                (limit,)
            )
        else:
            cur.execute(
                """SELECT al.*, u.email as user_email
                   FROM audit_ledger al
                   LEFT JOIN users u ON al.user_id = u.id
                   WHERE al.user_id = %s
                   ORDER BY al.timestamp DESC LIMIT %s""",
                (user_id, limit)
            )
        rows = cur.fetchall()
        for r in rows:
            if r.get("timestamp") and hasattr(r["timestamp"], "isoformat"):
                r["timestamp"] = r["timestamp"].isoformat()
        return rows
    finally:
        cur.close(); conn.close()
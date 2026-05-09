"""
phantombox/auth/security.py
─────────────────────────────────────────────────────────────
Security utilities:
  - bcrypt password hashing & verification
  - JWT access token creation & validation
  - Refresh token generation & hashing
  - Account lockout logic
─────────────────────────────────────────────────────────────
"""

import os
import secrets
import hashlib
import json
from datetime import datetime, timezone, timedelta
from typing import Optional, Tuple

import bcrypt
import jwt

# ── Configuration ────────────────────────────────────────────
JWT_SECRET_KEY      = os.getenv("JWT_SECRET_KEY",      "CHANGE_THIS_IN_PRODUCTION_jwt_secret_phantombox_2024")
JWT_ALGORITHM       = os.getenv("JWT_ALGORITHM",       "HS256")
ACCESS_TOKEN_TTL    = int(os.getenv("ACCESS_TOKEN_TTL",  "900"))    # 15 min in seconds
REFRESH_TOKEN_TTL   = int(os.getenv("REFRESH_TOKEN_TTL", "604800")) # 7 days in seconds
RESET_TOKEN_TTL     = int(os.getenv("RESET_TOKEN_TTL",   "900"))    # 15 min in seconds

MAX_LOGIN_ATTEMPTS  = int(os.getenv("MAX_LOGIN_ATTEMPTS", "5"))
LOCKOUT_DURATION    = int(os.getenv("LOCKOUT_DURATION",   "900"))   # 15 min in seconds

BCRYPT_ROUNDS       = int(os.getenv("BCRYPT_ROUNDS", "12"))         # Cost factor


# ── Password Security ────────────────────────────────────────

def hash_password(plain_password: str) -> str:
    """
    Hash a plaintext password with bcrypt.
    Returns the hash string (includes salt — bcrypt auto-generates it).
    Cost factor = 12 (standard for 2024, ~300ms on modern CPU).
    """
    if not plain_password or len(plain_password) < 8:
        raise ValueError("Password must be at least 8 characters")

    # bcrypt requires bytes
    pw_bytes  = plain_password.encode("utf-8")
    salt      = bcrypt.gensalt(rounds=BCRYPT_ROUNDS)
    hashed    = bcrypt.hashpw(pw_bytes, salt)
    return hashed.decode("utf-8")


def verify_password(plain_password: str, hashed: str) -> bool:
    """
    Verify a plaintext password against a bcrypt hash.
    Uses constant-time comparison to prevent timing attacks.
    Returns True if match, False otherwise.
    """
    try:
        return bcrypt.checkpw(
            plain_password.encode("utf-8"),
            hashed.encode("utf-8")
        )
    except Exception:
        return False


def check_password_strength(password: str) -> Tuple[bool, str]:
    """
    Validate password strength.
    Returns (is_valid, message).
    """
    if len(password) < 8:
        return False, "Password must be at least 8 characters"
    if len(password) > 128:
        return False, "Password must not exceed 128 characters"

    has_upper  = any(c.isupper() for c in password)
    has_lower  = any(c.islower() for c in password)
    has_digit  = any(c.isdigit() for c in password)
    has_symbol = any(c in "!@#$%^&*()_+-=[]{}|;':\",./<>?" for c in password)

    score = sum([has_upper, has_lower, has_digit, has_symbol])
    if score < 2:
        return False, "Password must contain at least 2 of: uppercase, lowercase, digit, symbol"

    return True, "Password meets requirements"


# ── JWT Access Tokens ────────────────────────────────────────

def create_access_token(user_id: str, email: str, role: str = "user",
                        session_id: str = None) -> str:
    """
    Create a signed JWT access token.

    Payload claims:
      sub  — subject (user UUID)
      email — user email
      role  — user role
      sid  — session ID (optional, for session binding)
      iat  — issued at (epoch)
      exp  — expiry (epoch)
      type — "access"
    """
    now     = datetime.now(timezone.utc)
    payload = {
        "sub":   user_id,
        "email": email,
        "role":  role,
        "sid":   session_id,
        "iat":   now,
        "exp":   now + timedelta(seconds=ACCESS_TOKEN_TTL),
        "type":  "access",
    }
    return jwt.encode(payload, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)


def decode_access_token(token: str) -> Optional[dict]:
    """
    Decode and validate a JWT access token.
    Returns payload dict on success, None on any failure.
    """
    try:
        payload = jwt.decode(token, JWT_SECRET_KEY, algorithms=[JWT_ALGORITHM])
        if payload.get("type") != "access":
            return None
        return payload
    except jwt.ExpiredSignatureError:
        return None
    except jwt.InvalidTokenError:
        return None


# ── Refresh Tokens ───────────────────────────────────────────

def generate_refresh_token() -> Tuple[str, str]:
    """
    Generate a cryptographically secure refresh token.
    Returns (raw_token, hashed_token).
    raw_token  → sent to client (stored in HttpOnly cookie)
    hashed_token → stored in DB (SHA-256)
    """
    raw_token    = secrets.token_urlsafe(64)   # 512-bit entropy
    hashed_token = hash_token(raw_token)
    return raw_token, hashed_token


def hash_token(raw_token: str) -> str:
    """SHA-256 hash of a token for safe DB storage."""
    return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()


def generate_reset_token() -> Tuple[str, str]:
    """
    Generate a password reset token.
    Returns (raw_token, hashed_token).
    raw_token → sent via email
    hashed_token → stored in DB
    """
    raw_token    = secrets.token_urlsafe(32)   # 256-bit entropy
    hashed_token = hash_token(raw_token)
    return raw_token, hashed_token


# ── Account Lockout ──────────────────────────────────────────

def _now_ts() -> float:
    return datetime.now(timezone.utc).timestamp()


def should_lock_account(failed_attempts: int) -> bool:
    """Return True if account should be locked after this many failures."""
    return failed_attempts >= MAX_LOGIN_ATTEMPTS


def get_lockout_until() -> float:
    """Return epoch timestamp when lockout expires."""
    return _now_ts() + LOCKOUT_DURATION


def seconds_until_unlocked(locked_until: float) -> int:
    """Return seconds remaining until account is unlocked."""
    remaining = locked_until - _now_ts()
    return max(0, int(remaining))


# ── Token TTL helpers ────────────────────────────────────────

def refresh_token_expiry() -> float:
    """Return epoch timestamp for refresh token expiry."""
    return _now_ts() + REFRESH_TOKEN_TTL


def reset_token_expiry() -> float:
    """Return epoch timestamp for reset token expiry (15 min)."""
    return _now_ts() + RESET_TOKEN_TTL


def access_token_expiry() -> float:
    """Return epoch timestamp for access token expiry."""
    return _now_ts() + ACCESS_TOKEN_TTL


# ── Input Sanitization ───────────────────────────────────────

def sanitize_email(email: str) -> str:
    """Normalize and basic-validate an email address."""
    if not email:
        raise ValueError("Email is required")
    email = email.strip().lower()
    if len(email) > 255:
        raise ValueError("Email too long")
    if "@" not in email or "." not in email.split("@")[-1]:
        raise ValueError("Invalid email format")
    return email


def sanitize_name(name: str, field: str = "Name") -> str:
    """Sanitize a name field."""
    if not name:
        raise ValueError(f"{field} is required")
    name = name.strip()
    if len(name) < 2:
        raise ValueError(f"{field} must be at least 2 characters")
    if len(name) > 100:
        raise ValueError(f"{field} must not exceed 100 characters")
    # Only allow alphabetic + spaces + hyphens
    allowed = set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ -'")
    if not all(c in allowed for c in name):
        raise ValueError(f"{field} contains invalid characters")
    return name
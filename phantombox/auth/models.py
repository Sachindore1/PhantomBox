"""
phantombox/auth/models.py
─────────────────────────────────────────────────────────────
Database models for PhantomBox authentication system.
Uses SQLite via SQLAlchemy (zero-config for college demo,
swappable to PostgreSQL/MySQL by changing DATABASE_URL).
─────────────────────────────────────────────────────────────
"""

import uuid
import time
from datetime import datetime, timezone
from sqlalchemy import (
    create_engine, Column, String, Boolean,
    Float, Integer, Text, ForeignKey, Index
)
from sqlalchemy.orm import declarative_base, sessionmaker, relationship
import os

# ── Engine & Session ─────────────────────────────────────────
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///phantombox_auth.db")

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False} if "sqlite" in DATABASE_URL else {},
    echo=False
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


# ── Helper ───────────────────────────────────────────────────
def _now_ts() -> float:
    """Current UTC timestamp as float."""
    return datetime.now(timezone.utc).timestamp()

def _new_uuid() -> str:
    return str(uuid.uuid4())


# ── Models ───────────────────────────────────────────────────

class User(Base):
    """
    Core user account.
    Passwords are NEVER stored — only bcrypt hash.
    """
    __tablename__ = "users"

    id            = Column(String(36),  primary_key=True, default=_new_uuid)
    email         = Column(String(255), unique=True, nullable=False, index=True)
    first_name    = Column(String(100), nullable=False)
    last_name     = Column(String(100), nullable=False)
    password_hash = Column(String(255), nullable=False)   # bcrypt hash only
    is_active     = Column(Boolean,     default=True)
    is_verified   = Column(Boolean,     default=False)    # email verification
    role          = Column(String(20),  default="user")   # user | admin

    # Timestamps
    created_at    = Column(Float, default=_now_ts)
    updated_at    = Column(Float, default=_now_ts, onupdate=_now_ts)
    last_login_at = Column(Float, nullable=True)

    # Security fields
    failed_login_attempts = Column(Integer, default=0)
    locked_until          = Column(Float,   nullable=True)   # epoch timestamp
    password_changed_at   = Column(Float,   default=_now_ts)

    # Relationships
    sessions       = relationship("UserSession",      back_populates="user", cascade="all, delete-orphan")
    refresh_tokens = relationship("RefreshToken",     back_populates="user", cascade="all, delete-orphan")
    audit_logs     = relationship("AuthAuditLog",     back_populates="user", cascade="all, delete-orphan")
    reset_tokens   = relationship("PasswordResetToken", back_populates="user", cascade="all, delete-orphan")

    def to_dict(self) -> dict:
        """Safe public representation (no secrets)."""
        return {
            "id":         self.id,
            "email":      self.email,
            "first_name": self.first_name,
            "last_name":  self.last_name,
            "full_name":  f"{self.first_name} {self.last_name}",
            "role":       self.role,
            "is_active":  self.is_active,
            "is_verified":self.is_verified,
            "created_at": self.created_at,
            "last_login_at": self.last_login_at,
        }

    def is_locked(self) -> bool:
        if self.locked_until is None:
            return False
        return _now_ts() < self.locked_until

    def __repr__(self):
        return f"<User {self.email}>"


class UserSession(Base):
    """
    Tracks active login sessions per device.
    Allows multi-device login and selective logout.
    """
    __tablename__ = "user_sessions"

    id         = Column(String(36), primary_key=True, default=_new_uuid)
    user_id    = Column(String(36), ForeignKey("users.id"), nullable=False, index=True)
    device_id  = Column(String(255), nullable=True)    # browser fingerprint
    ip_address = Column(String(45),  nullable=True)    # IPv4/IPv6
    user_agent = Column(Text,        nullable=True)
    is_active  = Column(Boolean, default=True)

    created_at  = Column(Float, default=_now_ts)
    last_seen   = Column(Float, default=_now_ts)
    expires_at  = Column(Float, nullable=False)

    user = relationship("User", back_populates="sessions")

    def is_expired(self) -> bool:
        return _now_ts() > self.expires_at

    def to_dict(self) -> dict:
        return {
            "id":         self.id,
            "device_id":  self.device_id,
            "ip_address": self.ip_address,
            "user_agent": self.user_agent,
            "created_at": self.created_at,
            "last_seen":  self.last_seen,
            "expires_at": self.expires_at,
            "is_active":  self.is_active,
        }


class RefreshToken(Base):
    """
    Long-lived refresh tokens (stored hashed).
    Used to issue new access tokens without re-login.
    """
    __tablename__ = "refresh_tokens"

    id         = Column(String(36),  primary_key=True, default=_new_uuid)
    user_id    = Column(String(36),  ForeignKey("users.id"), nullable=False, index=True)
    token_hash = Column(String(255), nullable=False, unique=True)  # SHA-256 of raw token
    session_id = Column(String(36),  ForeignKey("user_sessions.id"), nullable=True)
    is_revoked = Column(Boolean, default=False)
    created_at = Column(Float, default=_now_ts)
    expires_at = Column(Float, nullable=False)

    user = relationship("User", back_populates="refresh_tokens")

    def is_expired(self) -> bool:
        return _now_ts() > self.expires_at

    def is_valid(self) -> bool:
        return not self.is_revoked and not self.is_expired()


class PasswordResetToken(Base):
    """
    Single-use password reset tokens.
    Token is hashed before storage — raw token only sent via email.
    """
    __tablename__ = "password_reset_tokens"

    id         = Column(String(36),  primary_key=True, default=_new_uuid)
    user_id    = Column(String(36),  ForeignKey("users.id"), nullable=False, index=True)
    token_hash = Column(String(255), nullable=False, unique=True)
    is_used    = Column(Boolean, default=False)
    created_at = Column(Float, default=_now_ts)
    expires_at = Column(Float, nullable=False)    # short TTL: 15 minutes
    ip_address = Column(String(45), nullable=True)

    user = relationship("User", back_populates="reset_tokens")

    def is_expired(self) -> bool:
        return _now_ts() > self.expires_at

    def is_valid(self) -> bool:
        return not self.is_used and not self.is_expired()


class AuthAuditLog(Base):
    """
    Immutable audit log for every auth event.
    Important for security compliance / viva demonstration.
    """
    __tablename__ = "auth_audit_logs"

    id         = Column(String(36), primary_key=True, default=_new_uuid)
    user_id    = Column(String(36), ForeignKey("users.id"), nullable=True, index=True)
    event_type = Column(String(50), nullable=False, index=True)
    # Event types: LOGIN_SUCCESS, LOGIN_FAILED, LOGOUT, REGISTER,
    #              PASSWORD_RESET_REQUEST, PASSWORD_RESET_SUCCESS,
    #              TOKEN_REFRESH, ACCOUNT_LOCKED, TOKEN_REVOKED

    ip_address = Column(String(45),  nullable=True)
    user_agent = Column(Text,        nullable=True)
    extra_data = Column(Text,        nullable=True)   # JSON string
    timestamp  = Column(Float,       default=_now_ts, index=True)
    success    = Column(Boolean,     default=True)

    user = relationship("User", back_populates="audit_logs")

    def to_dict(self) -> dict:
        import json
        return {
            "id":         self.id,
            "user_id":    self.user_id,
            "event_type": self.event_type,
            "ip_address": self.ip_address,
            "timestamp":  self.timestamp,
            "success":    self.success,
            "extra_data": json.loads(self.extra_data) if self.extra_data else {},
        }


# Indexes for performance
Index("ix_audit_user_event", AuthAuditLog.user_id, AuthAuditLog.event_type)
Index("ix_sessions_user_active", UserSession.user_id, UserSession.is_active)


def init_db():
    """Create all tables. Call once on startup."""
    Base.metadata.create_all(bind=engine)
    print("✅ PhantomBox Auth DB initialized")


def get_db():
    """
    Dependency-style DB session getter.
    Use in a try/finally to ensure session is always closed.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
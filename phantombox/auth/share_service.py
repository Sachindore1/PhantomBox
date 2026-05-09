"""
phantombox/auth/share_service.py
─────────────────────────────────────────────────────────────
Ephemeral "Self-Destruct" Share Links service.

An owner can generate a time-limited, download-limited link
for any file they own. When the link expires or hits its
download limit it is automatically invalidated — the Phantom
theme: data that exists only when needed, then vanishes.

MySQL table: shared_links
─────────────────────────────────────────────────────────────
"""

import uuid
import secrets
import logging
from datetime import datetime, timezone, timedelta
from typing import Tuple, Optional

from .db import get_db, write_audit
from .mysql_service import can_access_file, get_file_owner

logger = logging.getLogger("phantombox.share")


def _now_ts() -> float:
    return datetime.now(timezone.utc).timestamp()


# ── Create a share link ──────────────────────────────────────

def create_share_link(
    file_id:       str,
    owner_id:      str,
    owner_role:    str,
    label:         str  = None,
    expires_in_hours: int = 24,
    max_downloads: int  = 1,
    ip:            str  = None,
) -> Tuple[bool, dict]:
    """
    Generate a one-time (or N-time) self-destruct share link.

    Returns:
        (True,  {"share_id": ..., "token": ..., "url": ..., "expires_at": ...})
        (False, {"error": "..."})
    """
    # Ownership check (Admin can share any file)
    allowed, reason = can_access_file(file_id, owner_id, owner_role)
    if not allowed:
        return False, {"error": reason}

    # Validate params
    if expires_in_hours < 1 or expires_in_hours > 168:   # 1h – 7 days
        return False, {"error": "Expiry must be between 1 and 168 hours (7 days)."}
    if max_downloads < 1 or max_downloads > 100:
        return False, {"error": "Max downloads must be between 1 and 100."}

    share_id   = str(uuid.uuid4())
    token      = secrets.token_urlsafe(32)          # 256-bit URL-safe token
    expires_at = int(_now_ts() + expires_in_hours * 3600)

    conn, cur = get_db()
    try:
        cur.execute(
            """INSERT INTO shared_links
               (id, file_id, owner_id, token, label,
                max_downloads, download_count, expires_at, is_revoked)
               VALUES (%s, %s, %s, %s, %s, %s, 0, %s, 0)""",
            (share_id, file_id, owner_id, token,
             label or f"Share {share_id[:8]}",
             max_downloads, expires_at)
        )
        conn.commit()

        write_audit("SHARE_CREATED", user_id=owner_id, file_id=file_id,
                    details=f"Share link created: expires in {expires_in_hours}h, max={max_downloads}",
                    ip=ip)

        logger.info(f"Share link created: {share_id} for file {file_id}")
        return True, {
            "share_id":     share_id,
            "token":        token,
            "expires_at":   expires_at,
            "expires_in_hours": expires_in_hours,
            "max_downloads": max_downloads,
            "label":        label,
        }

    except Exception as e:
        conn.rollback()
        logger.error(f"create_share_link error: {e}")
        return False, {"error": "Failed to create share link."}
    finally:
        cur.close()
        conn.close()


# ── Validate & consume a share link ─────────────────────────

def consume_share_link(token: str, ip: str = None) -> Tuple[bool, dict]:
    """
    Validate a share token and return the file_id if valid.
    Increments download_count; auto-revokes when limit reached.

    Returns:
        (True,  {"file_id": ..., "original_filename": ..., "downloads_remaining": ...})
        (False, {"error": "..."})
    """
    conn, cur = get_db()
    try:
        cur.execute(
            """SELECT sl.*, fr.original_filename, fr.file_size,
                      u.email as owner_email
               FROM   shared_links sl
               JOIN   file_registry fr ON sl.file_id = fr.file_id
               JOIN   users u          ON sl.owner_id = u.id
               WHERE  sl.token = %s""",
            (token,)
        )
        link = cur.fetchone()

        if not link:
            return False, {"error": "Share link not found or already expired."}

        if link["is_revoked"]:
            return False, {"error": "This share link has been revoked."}

        if _now_ts() > link["expires_at"]:
            # Auto-revoke expired link
            cur.execute(
                "UPDATE shared_links SET is_revoked=1 WHERE id=%s", (link["id"],)
            )
            conn.commit()
            return False, {"error": "This share link has expired. The phantom has vanished."}

        if link["download_count"] >= link["max_downloads"]:
            # Already consumed
            cur.execute(
                "UPDATE shared_links SET is_revoked=1 WHERE id=%s", (link["id"],)
            )
            conn.commit()
            return False, {"error": "Download limit reached. This link is now destroyed."}

        # Valid — increment counter
        new_count = link["download_count"] + 1
        remaining = link["max_downloads"] - new_count

        if remaining == 0:
            cur.execute(
                """UPDATE shared_links
                   SET download_count=%s, is_revoked=1, last_accessed=NOW()
                   WHERE id=%s""",
                (new_count, link["id"])
            )
        else:
            cur.execute(
                """UPDATE shared_links
                   SET download_count=%s, last_accessed=NOW()
                   WHERE id=%s""",
                (new_count, link["id"])
            )

        conn.commit()

        write_audit("SHARE_DOWNLOAD", user_id=link["owner_id"],
                    file_id=link["file_id"],
                    details=f"Share link used ({new_count}/{link['max_downloads']}), from {ip}",
                    ip=ip)

        # Convert timestamps
        for k in ("created_at", "last_accessed"):
            if link.get(k) and hasattr(link[k], "isoformat"):
                link[k] = link[k].isoformat()

        return True, {
            "file_id":           link["file_id"],
            "original_filename": link["original_filename"],
            "file_size":         link["file_size"],
            "owner_email":       link["owner_email"],
            "downloads_remaining": remaining,
            "download_count":    new_count,
            "max_downloads":     link["max_downloads"],
            "label":             link["label"],
        }

    except Exception as e:
        conn.rollback()
        logger.error(f"consume_share_link error: {e}")
        return False, {"error": "Failed to process share link."}
    finally:
        cur.close()
        conn.close()


# ── List share links for a file / user ──────────────────────

def get_user_share_links(owner_id: str, role: str) -> list:
    """Admin sees all; User sees only their own."""
    conn, cur = get_db()
    try:
        if role == "Admin":
            cur.execute(
                """SELECT sl.*, fr.original_filename, u.email as owner_email
                   FROM   shared_links sl
                   JOIN   file_registry fr ON sl.file_id = fr.file_id
                   JOIN   users u          ON sl.owner_id = u.id
                   ORDER BY sl.created_at DESC
                   LIMIT 200"""
            )
        else:
            cur.execute(
                """SELECT sl.*, fr.original_filename, u.email as owner_email
                   FROM   shared_links sl
                   JOIN   file_registry fr ON sl.file_id = fr.file_id
                   JOIN   users u          ON sl.owner_id = u.id
                   WHERE  sl.owner_id = %s
                   ORDER BY sl.created_at DESC""",
                (owner_id,)
            )
        rows = cur.fetchall()
        now  = _now_ts()
        for r in rows:
            for k in ("created_at", "last_accessed"):
                if r.get(k) and hasattr(r[k], "isoformat"):
                    r[k] = r[k].isoformat()
            # Computed fields
            r["is_expired"]  = now > r.get("expires_at", 0)
            r["is_active"]   = not r["is_revoked"] and not r["is_expired"]
            r["time_left"]   = max(0, int(r.get("expires_at", 0) - now))
        return rows
    finally:
        cur.close()
        conn.close()


def revoke_share_link(share_id: str, owner_id: str, role: str) -> Tuple[bool, dict]:
    """Manually revoke a share link."""
    conn, cur = get_db()
    try:
        if role == "Admin":
            cur.execute(
                "UPDATE shared_links SET is_revoked=1 WHERE id=%s", (share_id,)
            )
        else:
            cur.execute(
                "UPDATE shared_links SET is_revoked=1 WHERE id=%s AND owner_id=%s",
                (share_id, owner_id)
            )

        if cur.rowcount == 0:
            return False, {"error": "Share link not found or not yours."}

        conn.commit()
        write_audit("SHARE_REVOKED", user_id=owner_id,
                    details=f"Share link revoked: {share_id}")
        return True, {"message": "Share link revoked. The phantom has been destroyed."}

    except Exception as e:
        conn.rollback()
        return False, {"error": str(e)}
    finally:
        cur.close()
        conn.close()
"""
phantombox/auth/admin_routes.py
─────────────────────────────────────────────────────────────
Admin dashboard API + user-scoped history + share link endpoints.

GET  /api/admin/stats           — Admin: dashboard statistics
GET  /api/admin/audit           — Admin: full audit log
GET  /api/admin/files           — Admin: all files
GET  /api/admin/users           — Admin: all users
GET  /api/admin/security        — Admin: security monitor
GET  /api/admin/blockchain      — Admin: blockchain explorer

GET  /api/history/uploads       — User: own upload history
GET  /api/history/downloads     — User: own download history

POST /api/share/create          — Create ephemeral share link
GET  /api/share/list            — List user's share links
DELETE /api/share/<id>          — Revoke share link
GET  /api/share/use/<token>     — Public: use a share link
─────────────────────────────────────────────────────────────
"""

import os
import time
import logging
import requests as http_req

from flask import Blueprint, request, jsonify, g

from .middleware     import jwt_required, admin_required
from .mysql_service  import (
    get_audit_log, get_all_users, get_user_files,
    get_file_owner,
)
from .db             import get_db, write_audit
from .share_service  import (
    create_share_link, consume_share_link,
    get_user_share_links, revoke_share_link,
)

logger = logging.getLogger("phantombox.admin")

admin_bp  = Blueprint("admin",   __name__, url_prefix="/api/admin")
history_bp= Blueprint("history", __name__, url_prefix="/api/history")
share_bp  = Blueprint("share",   __name__, url_prefix="/api/share")


def _ip():
    return (request.headers.get("X-Forwarded-For","").split(",")[0].strip()
            or request.remote_addr or "unknown")

def _body():
    return request.get_json(silent=True) or {}

def _ok(data, status=200):
    return jsonify({"success": True, **data}), status

def _err(msg, status=400, code=None):
    body = {"success": False, "error": msg}
    if code: body["code"] = code
    return jsonify(body), status


# ══════════════════════════════════════════════════════════════
# ADMIN ROUTES
# ══════════════════════════════════════════════════════════════

@admin_bp.route("/stats", methods=["GET"])
@admin_required
def admin_stats():
    """Dashboard statistics for admin."""
    conn, cur = get_db()
    try:
        # Total users
        cur.execute("SELECT COUNT(*) AS cnt FROM users")
        total_users = cur.fetchone()["cnt"]

        # Users by role
        cur.execute("SELECT role, COUNT(*) AS cnt FROM users GROUP BY role")
        roles = {r["role"]: r["cnt"] for r in cur.fetchall()}

        # Total files
        cur.execute("SELECT COUNT(*) AS cnt FROM file_registry")
        total_files = cur.fetchone()["cnt"]

        # Total size
        cur.execute("SELECT COALESCE(SUM(file_size),0) AS total FROM file_registry")
        total_size = cur.fetchone()["total"]

        # Recent uploads (last 24h)
        cur.execute(
            "SELECT COUNT(*) AS cnt FROM file_registry WHERE upload_time > NOW() - INTERVAL 1 DAY"
        )
        uploads_24h = cur.fetchone()["cnt"]

        # Total audit events
        cur.execute("SELECT COUNT(*) AS cnt FROM audit_ledger")
        total_events = cur.fetchone()["cnt"]

        # Active share links
        cur.execute(
            "SELECT COUNT(*) AS cnt FROM shared_links WHERE is_revoked=0 AND expires_at > %s",
            (int(time.time()),)
        )
        active_shares = cur.fetchone()["cnt"]

        # Recent activity (last 7 days by day)
        cur.execute(
            """SELECT DATE(timestamp) AS day, COUNT(*) AS cnt
               FROM   audit_ledger
               WHERE  timestamp > NOW() - INTERVAL 7 DAY
               GROUP  BY DATE(timestamp)
               ORDER  BY day""")
        activity_chart = [{"day": str(r["day"]), "count": r["cnt"]}
                          for r in cur.fetchall()]

        # Top uploaders
        cur.execute(
            """SELECT u.email, COUNT(*) AS uploads, COALESCE(SUM(fr.file_size),0) AS total_size
               FROM   file_registry fr
               JOIN   users u ON fr.owner_id = u.id
               GROUP  BY u.id, u.email
               ORDER  BY uploads DESC LIMIT 5"""
        )
        top_uploaders = cur.fetchall()

        # Node health (quick check)
        nodes_online = 0
        for url in ["http://127.0.0.1:5001","http://127.0.0.1:5002",
                    "http://127.0.0.1:9001","http://127.0.0.1:9002"]:
            try:
                if http_req.get(f"{url}/status", timeout=1).ok:
                    nodes_online += 1
            except Exception:
                pass

        return _ok({
            "users":          {"total": total_users, "by_role": roles},
            "files":          {"total": total_files, "total_size": int(total_size),
                               "uploads_24h": uploads_24h},
            "audit":          {"total_events": total_events},
            "shares":         {"active": active_shares},
            "nodes_online":   nodes_online,
            "nodes_total":    4,
            "activity_chart": activity_chart,
            "top_uploaders":  top_uploaders,
            "timestamp":      time.time(),
        })

    finally:
        cur.close(); conn.close()


@admin_bp.route("/audit", methods=["GET"])
@admin_required
def admin_audit():
    """Full audit log with optional filters."""
    limit       = min(int(request.args.get("limit", 100)), 500)
    action_type = request.args.get("action_type")
    user_email  = request.args.get("user_email")

    conn, cur = get_db()
    try:
        query = """
            SELECT al.*, u.email AS user_email, u.role AS user_role
            FROM   audit_ledger al
            LEFT   JOIN users u ON al.user_id = u.id
            WHERE  1=1
        """
        params = []

        if action_type:
            query += " AND al.action_type = %s"
            params.append(action_type)

        if user_email:
            query += " AND u.email LIKE %s"
            params.append(f"%{user_email}%")

        query += " ORDER BY al.timestamp DESC LIMIT %s"
        params.append(limit)

        cur.execute(query, params)
        rows = cur.fetchall()
        for r in rows:
            if r.get("timestamp") and hasattr(r["timestamp"], "isoformat"):
                r["timestamp"] = r["timestamp"].isoformat()

        # Count by action type
        cur.execute("SELECT action_type, COUNT(*) AS cnt FROM audit_ledger GROUP BY action_type ORDER BY cnt DESC")
        summary = {r["action_type"]: r["cnt"] for r in cur.fetchall()}

        return _ok({"logs": rows, "count": len(rows), "summary": summary})
    finally:
        cur.close(); conn.close()


@admin_bp.route("/files", methods=["GET"])
@admin_required
def admin_files():
    """All files with owner info."""
    search = request.args.get("search", "")
    limit  = min(int(request.args.get("limit", 100)), 500)

    conn, cur = get_db()
    try:
        if search:
            cur.execute(
                """SELECT fr.*, u.email AS owner_email, u.role AS owner_role
                   FROM   file_registry fr
                   JOIN   users u ON fr.owner_id = u.id
                   WHERE  fr.original_filename LIKE %s OR u.email LIKE %s
                   ORDER  BY fr.upload_time DESC LIMIT %s""",
                (f"%{search}%", f"%{search}%", limit)
            )
        else:
            cur.execute(
                """SELECT fr.*, u.email AS owner_email, u.role AS owner_role
                   FROM   file_registry fr
                   JOIN   users u ON fr.owner_id = u.id
                   ORDER  BY fr.upload_time DESC LIMIT %s""",
                (limit,)
            )
        rows = cur.fetchall()
        for r in rows:
            if r.get("upload_time") and hasattr(r["upload_time"], "isoformat"):
                r["upload_time"] = r["upload_time"].isoformat()
        return _ok({"files": rows, "count": len(rows)})
    finally:
        cur.close(); conn.close()


@admin_bp.route("/users", methods=["GET"])
@admin_required
def admin_users():
    """All users with file counts and last activity."""
    conn, cur = get_db()
    try:
        cur.execute(
            """SELECT u.*,
                      COUNT(DISTINCT fr.file_id) AS file_count,
                      COALESCE(SUM(fr.file_size),0) AS total_size,
                      MAX(al.timestamp) AS last_activity
               FROM   users u
               LEFT   JOIN file_registry fr ON fr.owner_id = u.id
               LEFT   JOIN audit_ledger  al ON al.user_id  = u.id
               GROUP  BY u.id
               ORDER  BY u.created_at DESC"""
        )
        rows = cur.fetchall()
        for r in rows:
            r.pop("password_hash", None)   # Never send hash
            for k in ("created_at", "last_login_at", "last_activity"):
                if r.get(k) and hasattr(r[k], "isoformat"):
                    r[k] = r[k].isoformat()
        return _ok({"users": rows, "count": len(rows)})
    finally:
        cur.close(); conn.close()


@admin_bp.route("/security", methods=["GET"])
@admin_required
def admin_security():
    """Security monitor — failed logins, locked accounts, suspicious activity."""
    conn, cur = get_db()
    try:
        # Locked accounts
        cur.execute(
            """SELECT id, email, failed_login_attempts, locked_until
               FROM   users
               WHERE  locked_until IS NOT NULL AND locked_until > %s""",
            (int(time.time()),)
        )
        locked_accounts = cur.fetchall()

        # Recent failed logins (last 24h)
        cur.execute(
            """SELECT al.*, u.email AS user_email
               FROM   audit_ledger al
               LEFT   JOIN users u ON al.user_id = u.id
               WHERE  al.action_type = 'LOGIN_FAILED'
               AND    al.timestamp > NOW() - INTERVAL 24 HOUR
               ORDER  BY al.timestamp DESC LIMIT 50"""
        )
        failed_logins = cur.fetchall()
        for r in failed_logins:
            if r.get("timestamp") and hasattr(r["timestamp"], "isoformat"):
                r["timestamp"] = r["timestamp"].isoformat()

        # Denied downloads
        cur.execute(
            """SELECT al.*, u.email AS user_email
               FROM   audit_ledger al
               LEFT   JOIN users u ON al.user_id = u.id
               WHERE  al.action_type = 'DOWNLOAD_DENIED'
               AND    al.timestamp > NOW() - INTERVAL 24 HOUR
               ORDER  BY al.timestamp DESC LIMIT 20"""
        )
        denied_downloads = cur.fetchall()
        for r in denied_downloads:
            if r.get("timestamp") and hasattr(r["timestamp"], "isoformat"):
                r["timestamp"] = r["timestamp"].isoformat()

        # Node health
        nodes = {}
        for name, url in [("genesis","http://127.0.0.1:5001"),
                           ("peer","http://127.0.0.1:5002"),
                           ("noise_a","http://127.0.0.1:9001"),
                           ("noise_b","http://127.0.0.1:9002")]:
            try:
                r = http_req.get(f"{url}/status", timeout=1)
                nodes[name] = {"online": r.ok, "url": url}
            except Exception:
                nodes[name] = {"online": False, "url": url}

        # Memory stats
        try:
            mem_r = http_req.get("http://127.0.0.1:8000/api/memory_stats", timeout=2)
            mem_stats = mem_r.json() if mem_r.ok else {}
        except Exception:
            mem_stats = {}

        return _ok({
            "locked_accounts":  locked_accounts,
            "failed_logins":    failed_logins,
            "denied_downloads": denied_downloads,
            "nodes":            nodes,
            "memory":           mem_stats,
            "timestamp":        time.time(),
        })
    finally:
        cur.close(); conn.close()


@admin_bp.route("/blockchain", methods=["GET"])
@admin_required
def admin_blockchain():
    """Blockchain explorer data."""
    try:
        r = http_req.get("http://127.0.0.1:5001/chain", timeout=5)
        if not r.ok:
            return _err("Blockchain node not available", status=503)

        chain = r.json().get("chain", [])

        registrations = [
            {
                "index":       b["index"],
                "file_id":     b["data"].get("file_id"),
                "file_hash":   b["data"].get("file_hash","")[:16] + "...",
                "owner_id":    b["data"].get("owner_id",""),
                "timestamp":   b["timestamp"],
                "fragments":   len(b["data"].get("fragment_map",{}).get("fragments",{})),
                "hash":        b["hash"][:16] + "...",
            }
            for b in chain
            if b.get("data",{}).get("type") == "file_registration"
        ]

        return _ok({
            "chain_length":      len(chain),
            "registrations":     registrations,
            "genesis_hash":      chain[0]["hash"][:32] if chain else "",
            "latest_hash":       chain[-1]["hash"][:32] if chain else "",
            "timestamp":         time.time(),
        })
    except Exception as e:
        return _err(str(e), status=500)


# ══════════════════════════════════════════════════════════════
# HISTORY ROUTES  (user-scoped — only shows OWN files)
# ══════════════════════════════════════════════════════════════

@history_bp.route("/uploads", methods=["GET"])
@jwt_required
def upload_history():
    """
    Returns the authenticated user's own uploaded files.
    Admin sees ALL files; User sees only their own.
    Pulls from MySQL file_registry — server-authoritative.
    """
    u     = g.current_user
    limit = min(int(request.args.get("limit", 50)), 200)

    conn, cur = get_db()
    try:
        if u["role"] == "Admin":
            cur.execute(
                """SELECT fr.*, u2.email AS owner_email
                   FROM   file_registry fr
                   JOIN   users u2 ON fr.owner_id = u2.id
                   ORDER  BY fr.upload_time DESC LIMIT %s""",
                (limit,)
            )
        else:
            cur.execute(
                """SELECT fr.*, u2.email AS owner_email
                   FROM   file_registry fr
                   JOIN   users u2 ON fr.owner_id = u2.id
                   WHERE  fr.owner_id = %s
                   ORDER  BY fr.upload_time DESC LIMIT %s""",
                (u["id"], limit)
            )
        rows = cur.fetchall()
        for r in rows:
            if r.get("upload_time") and hasattr(r["upload_time"], "isoformat"):
                r["upload_time"] = r["upload_time"].isoformat()
        return _ok({"files": rows, "count": len(rows), "role": u["role"]})
    finally:
        cur.close(); conn.close()


@history_bp.route("/downloads", methods=["GET"])
@jwt_required
def download_history():
    """
    Returns download audit events for this user.
    Admin sees ALL; User sees their own.
    """
    u     = g.current_user
    limit = min(int(request.args.get("limit", 50)), 200)

    conn, cur = get_db()
    try:
        if u["role"] == "Admin":
            cur.execute(
                """SELECT al.*, u2.email AS user_email, fr.original_filename
                   FROM   audit_ledger al
                   LEFT   JOIN users u2 ON al.user_id = u2.id
                   LEFT   JOIN file_registry fr ON al.file_id = fr.file_id
                   WHERE  al.action_type IN ('DOWNLOAD','SHARE_DOWNLOAD')
                   ORDER  BY al.timestamp DESC LIMIT %s""",
                (limit,)
            )
        else:
            cur.execute(
                """SELECT al.*, u2.email AS user_email, fr.original_filename
                   FROM   audit_ledger al
                   LEFT   JOIN users u2 ON al.user_id = u2.id
                   LEFT   JOIN file_registry fr ON al.file_id = fr.file_id
                   WHERE  al.action_type IN ('DOWNLOAD','SHARE_DOWNLOAD')
                   AND    al.user_id = %s
                   ORDER  BY al.timestamp DESC LIMIT %s""",
                (u["id"], limit)
            )
        rows = cur.fetchall()
        for r in rows:
            if r.get("timestamp") and hasattr(r["timestamp"], "isoformat"):
                r["timestamp"] = r["timestamp"].isoformat()
        return _ok({"downloads": rows, "count": len(rows)})
    finally:
        cur.close(); conn.close()


# ══════════════════════════════════════════════════════════════
# SHARE LINK ROUTES
# ══════════════════════════════════════════════════════════════

@share_bp.route("/create", methods=["POST"])
@jwt_required
def create_link():
    """Create an ephemeral share link."""
    b   = _body()
    u   = g.current_user

    file_id       = b.get("file_id")
    expires_hours = int(b.get("expires_in_hours", 24))
    max_downloads = int(b.get("max_downloads", 1))
    label         = b.get("label")

    if not file_id:
        return _err("file_id is required.", status=422)

    ok, result = create_share_link(
        file_id           = file_id,
        owner_id          = u["id"],
        owner_role        = u["role"],
        label             = label,
        expires_in_hours  = expires_hours,
        max_downloads     = max_downloads,
        ip                = _ip(),
    )

    if not ok:
        return _err(result["error"], status=403)

    # Build the full share URL (frontend will use this)
    base_url = os.getenv("PHANTOMBOX_URL", "http://127.0.0.1:8000")
    share_url = f"{base_url}/share/{result['token']}"

    return _ok({
        **result,
        "share_url": share_url,
        "message":   "Phantom share link created. It will self-destruct.",
    }, status=201)


@share_bp.route("/list", methods=["GET"])
@jwt_required
def list_links():
    """List user's share links."""
    u     = g.current_user
    links = get_user_share_links(u["id"], u["role"])
    return _ok({"links": links, "count": len(links)})


@share_bp.route("/<share_id>", methods=["DELETE"])
@jwt_required
def revoke_link(share_id):
    """Manually revoke a share link."""
    u = g.current_user
    ok, result = revoke_share_link(share_id, u["id"], u["role"])
    if not ok:
        return _err(result["error"], status=404)
    return _ok(result)


# ── REPLACE the use_share_link function in phantombox/auth/admin_routes.py ──
# Find the existing @share_bp.route("/use/<token>") function and replace with this:

@share_bp.route("/use/<token>", methods=["GET"])
def use_share_link(token):
    """
    Public endpoint — no auth required.
    Validates the share token and returns download tokens
    so the frontend can serve the file.
    """
    ok, info = consume_share_link(token, ip=_ip())
    if not ok:
        return _err(info["error"], status=410)   # 410 Gone

    file_id = info["file_id"]

    try:
        from ..config import AppConfig

        # ── 1. Get fragment map from blockchain ──────────────
        res = http_req.get(f"{AppConfig.GENESIS_NODE}/fragments/{file_id}", timeout=10)
        if not res.ok:
            return _err("File not found on blockchain", status=404)

        fragment_map = res.json().get("fragment_map", {})
        if not fragment_map:
            return _err("No fragment map found for this file", status=404)

        # ── 2. Inject original filename ──────────────────────
        fragment_map["original_filename"] = info.get("original_filename")

        # Also try to get filename from blockchain if not in fragment_map
        if not fragment_map.get("original_filename"):
            try:
                chain_res = http_req.get(f"{AppConfig.GENESIS_NODE}/chain", timeout=5)
                if chain_res.ok:
                    for block in reversed(chain_res.json().get("chain", [])):
                        bd = block.get("data", {})
                        if bd.get("file_id") == file_id:
                            fragment_map["original_filename"] = bd.get("original_filename")
                            break
            except Exception:
                pass

        # ── 3. Reconstruct in RAM ────────────────────────────
        from ..services.reconstruction import reconstructor
        result = reconstructor.reconstruct_file(file_id, fragment_map)

        if not result:
            return _err("File reconstruction failed", status=500)

        filename = (
            info.get("original_filename")
            or result.get("original_filename")
            or result.get("filename")
            or "shared_file"
        )

        # ── 4. Return ALL tokens + metadata ─────────────────
        return _ok({
            # Tokens
            "preview_token":      result["preview_token"],
            "download_token":     result["download_token"],
            # File info
            "file_id":            file_id,
            "filename":           filename,
            "original_filename":  filename,
            "file_type":          result.get("file_type", "bin"),
            "file_size":          result.get("file_size", 0),
            # URLs
            "preview_url":        f"/api/preview/{result['preview_token']}",
            "download_url":       f"/api/download/{result['download_token']}",
            # Share metadata
            "downloads_remaining": info["downloads_remaining"],
            "owner":              info.get("owner_email", ""),
            "label":              info.get("label", ""),
            # TTL values — CRITICAL: frontend needs these
            "preview_ttl":        result.get("preview_ttl", 60),
            "download_ttl":       result.get("download_ttl", 300),
        })

    except Exception as e:
        logger.error(f"share use error: {e}")
        import traceback; traceback.print_exc()
        return _err(f"Failed to serve share: {str(e)}", status=500)
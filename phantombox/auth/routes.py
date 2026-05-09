"""
phantombox/auth/routes.py
─────────────────────────────────────────────────────────────
Auth REST API endpoints backed by MySQL.

POST  /api/auth/register
POST  /api/auth/login
GET   /api/auth/me
GET   /api/auth/files          — current user's uploaded files
GET   /api/auth/all-files      — Admin: all files
GET   /api/auth/all-users      — Admin: all users
GET   /api/auth/audit          — audit log (scoped by role)
GET   /api/auth/health
─────────────────────────────────────────────────────────────
"""

import os
from flask import Blueprint, request, jsonify, g
from .mysql_service import (
    register_user, login_user, get_user_by_id,
    get_user_files, get_all_users, get_audit_log,
)
from .middleware import jwt_required, admin_required, get_current_user

auth_bp = Blueprint("auth", __name__, url_prefix="/api/auth")


def _ip():
    return (request.headers.get("X-Forwarded-For","").split(",")[0].strip()
            or request.remote_addr or "unknown")

def _body():
    return request.get_json(silent=True) or {}

def _ok(data, status=200):
    return jsonify({"success": True, **data}), status

def _err(msg, code=None, status=400):
    body = {"success": False, "error": msg}
    if code: body["code"] = code
    return jsonify(body), status


# ── Health ───────────────────────────────────────────────────

@auth_bp.route("/health", methods=["GET"])
def health():
    return _ok({"service": "PhantomBox Auth (MySQL)", "status": "healthy"})


# ── Register ─────────────────────────────────────────────────

@auth_bp.route("/register", methods=["POST"])
def register():
    b = _body()
    missing = [f for f in ["email","password","first_name","last_name"] if not b.get(f)]
    if missing:
        return _err(f"Missing: {', '.join(missing)}", status=422)

    # Admin registration requires the ADMIN_SECRET_KEY from .env
    requested_role = b.get("role", "User")
    if requested_role == "Admin":
        admin_secret = os.getenv("ADMIN_SECRET_KEY", "")
        provided_key = b.get("admin_key", "")
        if not admin_secret or provided_key != admin_secret:
            return _err("Invalid admin secret key. Contact your system administrator.",
                        code="INVALID_ADMIN_KEY", status=403)

    ok, result = register_user(
        email      = b["email"],
        password   = b["password"],
        first_name = b["first_name"],
        last_name  = b["last_name"],
        role       = requested_role,
        ip         = _ip(),
    )
    if not ok:
        status = 409 if result.get("field") == "email" else 422
        return _err(result["error"], status=status)
    return _ok(result, status=201)


# ── Login ────────────────────────────────────────────────────

@auth_bp.route("/login", methods=["POST"])
def login():
    b = _body()
    if not b.get("email") or not b.get("password"):
        return _err("Email and password are required.", status=422)

    ok, result = login_user(b["email"], b["password"], ip=_ip())
    if not ok:
        code   = result.get("code","INVALID")
        status = 423 if code == "LOCKED" else 401
        return _err(result["error"], code=code, status=status)
    return _ok(result)


# ── Me ───────────────────────────────────────────────────────

@auth_bp.route("/me", methods=["GET"])
@jwt_required
def me():
    user = get_user_by_id(g.current_user["id"])
    if not user:
        return _err("User not found.", status=404)
    return _ok({"user": user})


# ── My Files ─────────────────────────────────────────────────

@auth_bp.route("/files", methods=["GET"])
@jwt_required
def my_files():
    """Returns files owned by current user (Admin sees all)."""
    u     = g.current_user
    files = get_user_files(u["id"], u["role"])
    return _ok({"files": files, "count": len(files), "role": u["role"]})


# ── Admin: All Files ─────────────────────────────────────────

@auth_bp.route("/all-files", methods=["GET"])
@admin_required
def all_files():
    files = get_user_files(None, "Admin")
    return _ok({"files": files, "count": len(files)})


# ── Admin: All Users ─────────────────────────────────────────

@auth_bp.route("/all-users", methods=["GET"])
@admin_required
def all_users():
    users = get_all_users()
    return _ok({"users": users, "count": len(users)})


# ── Audit Log ────────────────────────────────────────────────

@auth_bp.route("/audit", methods=["GET"])
@jwt_required
def audit():
    u     = g.current_user
    limit = min(int(request.args.get("limit", 100)), 500)
    logs  = get_audit_log(user_id=u["id"], role=u["role"], limit=limit)
    return _ok({"logs": logs, "count": len(logs)})


# ── CORS preflight ───────────────────────────────────────────

@auth_bp.route("/<path:path>", methods=["OPTIONS"])
def options(path):
    from flask import make_response
    r = make_response()
    r.headers["Access-Control-Allow-Origin"]  = "*"
    r.headers["Access-Control-Allow-Methods"] = "GET,POST,DELETE,OPTIONS"
    r.headers["Access-Control-Allow-Headers"] = "Content-Type,Authorization"
    return r, 204
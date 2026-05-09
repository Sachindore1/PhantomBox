"""
phantombox/auth/middleware.py
─────────────────────────────────────────────────────────────
JWT-based request authentication decorators.
Reads token from Authorization: Bearer <token> header.
Injects current_user into Flask g object.
─────────────────────────────────────────────────────────────
"""

import functools
from flask import request, jsonify, g
from .mysql_service import decode_token, get_user_by_id


def _extract_token() -> str | None:
    auth = request.headers.get("Authorization", "")
    if auth.startswith("Bearer "):
        return auth[7:].strip()
    # Also accept from query param (for iframe previews)
    return request.args.get("token")


def jwt_required(f):
    """Decorator: requires valid JWT. Sets g.current_user."""
    @functools.wraps(f)
    def decorated(*args, **kwargs):
        token = _extract_token()
        if not token:
            return jsonify({"success": False, "error": "Authentication required.", "code": "NO_TOKEN"}), 401

        payload = decode_token(token)
        if not payload:
            return jsonify({"success": False, "error": "Token expired or invalid.", "code": "INVALID_TOKEN"}), 401

        # Attach minimal user info — avoid extra DB call on every request
        g.current_user = {
            "id":    payload["sub"],
            "email": payload.get("email"),
            "role":  payload.get("role", "User"),
            "name":  payload.get("name", ""),
        }
        return f(*args, **kwargs)
    return decorated


def admin_required(f):
    """Decorator: requires Admin role."""
    @functools.wraps(f)
    @jwt_required
    def decorated(*args, **kwargs):
        if g.current_user.get("role") != "Admin":
            return jsonify({"success": False, "error": "Admin access required.", "code": "FORBIDDEN"}), 403
        return f(*args, **kwargs)
    return decorated


def get_current_user() -> dict | None:
    return getattr(g, "current_user", None)
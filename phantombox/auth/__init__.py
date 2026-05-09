"""phantombox/auth/__init__.py"""
from .routes        import auth_bp
from .db            import init_db, write_audit
from .db_extensions import extend_db
from .middleware    import jwt_required, admin_required, get_current_user
from .mysql_service import (
    register_user, login_user, decode_token,
    register_file_owner, get_file_owner, can_access_file,
)
from .share_service import (
    create_share_link, consume_share_link,
    get_user_share_links, revoke_share_link,
)

__all__ = [
    "auth_bp", "init_db", "extend_db", "write_audit",
    "jwt_required", "admin_required", "get_current_user",
    "register_user", "login_user", "decode_token",
    "register_file_owner", "get_file_owner", "can_access_file",
    "create_share_link", "consume_share_link",
    "get_user_share_links", "revoke_share_link",
]
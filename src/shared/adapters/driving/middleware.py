import hmac
from functools import wraps
from flask import current_app, request
from shared.helpers.security import verify_jwt
from shared.generics.errors import DrivingAdapterError

_UNSAFE_METHODS = {"POST", "PUT", "PATCH", "DELETE"}


def init_middleware(app, jwt_secret: str) -> None:
    """Store JWT secret on the Flask app config. Call once during startup."""
    app.config["JWT_SECRET"] = jwt_secret


def jwt_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        token = request.cookies.get("token")
        token_source = "cookie" if token else None
        if not token:
            auth = request.headers.get("Authorization", "")
            if auth.startswith("Bearer "):
                token = auth.split(" ", 1)[1]
                token_source = "bearer"
        if not token:
            raise DrivingAdapterError("Authentication required", "AUTH_REQUIRED")
        payload = verify_jwt(token, current_app.config["JWT_SECRET"])
        if payload is None:
            raise DrivingAdapterError("Invalid or expired token", "AUTH_INVALID")
        request.admin_payload = payload
        request.admin_token_source = token_source
        if token_source == "cookie":
            _validate_csrf(payload)
        return f(*args, **kwargs)
    return decorated


def _request_csrf_token() -> str:
    header_token = request.headers.get("X-CSRF-Token", "")
    if header_token:
        return header_token
    if request.form:
        return request.form.get("_csrf_token", "")
    payload = request.get_json(silent=True) or {}
    return str(payload.get("_csrf_token", "")) if isinstance(payload, dict) else ""


def _validate_csrf(payload: dict) -> None:
    if request.method not in _UNSAFE_METHODS:
        return

    expected = str(payload.get("csrf") or "")
    cookie_token = request.cookies.get("csrf_token", "")
    supplied = _request_csrf_token()
    if not expected or not cookie_token or not supplied:
        raise DrivingAdapterError("Invalid CSRF token", "CSRF_INVALID")
    if not (
        hmac.compare_digest(expected, cookie_token)
        and hmac.compare_digest(expected, supplied)
    ):
        raise DrivingAdapterError("Invalid CSRF token", "CSRF_INVALID")


def current_admin_payload() -> dict:
    return getattr(request, "admin_payload", {}) or {}


def is_superadmin() -> bool:
    return current_admin_payload().get("role") == "superadmin"


def has_permission(permission: str) -> bool:
    payload = current_admin_payload()
    if payload.get("role") == "superadmin":
        return True
    runtime_keys = set()
    try:
        provider = current_app.config.get("PERMISSION_PROVIDER")
        runtime_keys = set(current_app.config.get("RUNTIME_PERMISSION_KEYS") or ())
    except RuntimeError:
        provider = None
    if callable(provider):
        return bool(provider(payload, permission))
    if permission in runtime_keys:
        return False
    permissions = payload.get("permissions") or {}
    return bool(permissions.get(permission))


def permission_required(permission: str):
    def decorator(f):
        @wraps(f)
        @jwt_required
        def decorated(*args, **kwargs):
            if not has_permission(permission):
                raise DrivingAdapterError("Forbidden", "FORBIDDEN")
            return f(*args, **kwargs)
        return decorated
    return decorator


def any_permission_required(*permissions: str):
    def decorator(f):
        @wraps(f)
        @jwt_required
        def decorated(*args, **kwargs):
            if not any(has_permission(permission) for permission in permissions):
                raise DrivingAdapterError("Forbidden", "FORBIDDEN")
            return f(*args, **kwargs)
        return decorated
    return decorator


def superadmin_required(f):
    @wraps(f)
    @jwt_required
    def decorated(*args, **kwargs):
        if not is_superadmin():
            raise DrivingAdapterError("Forbidden", "FORBIDDEN")
        return f(*args, **kwargs)
    return decorated

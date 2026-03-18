from functools import wraps
from flask import current_app, request
from shared.helpers.security import verify_jwt
from shared.generics.errors import DrivingAdapterError


def init_middleware(app, jwt_secret: str) -> None:
    """Store JWT secret on the Flask app config. Call once during startup."""
    app.config["JWT_SECRET"] = jwt_secret


def jwt_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        token = request.cookies.get("token")
        if not token:
            auth = request.headers.get("Authorization", "")
            if auth.startswith("Bearer "):
                token = auth.split(" ", 1)[1]
        if not token:
            raise DrivingAdapterError("Authentication required", "AUTH_REQUIRED")
        payload = verify_jwt(token, current_app.config["JWT_SECRET"])
        if payload is None:
            raise DrivingAdapterError("Invalid or expired token", "AUTH_INVALID")
        request.admin_payload = payload
        return f(*args, **kwargs)
    return decorated

import datetime

import jwt
from werkzeug.security import check_password_hash, generate_password_hash


def hash_password(password: str) -> str:
    return generate_password_hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    return check_password_hash(password_hash, password)


def create_jwt(payload: dict, secret: str, expires_hours: int = 24) -> str:
    data = payload.copy()
    data["exp"] = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(
        hours=expires_hours
    )
    return jwt.encode(data, secret, algorithm="HS256")


def verify_jwt(token: str, secret: str) -> dict | None:
    try:
        return jwt.decode(
            token, secret, algorithms=["HS256"], options={"verify_sub": False}
        )
    except (jwt.ExpiredSignatureError, jwt.InvalidTokenError, Exception):
        return None

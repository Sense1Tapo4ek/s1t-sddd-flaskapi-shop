from apiflask import APIBlueprint
from dishka.integrations.flask import inject, FromDishka
from flask import request

from access.domain import InvalidPasswordError
from access.ports.driving import (
    AccessFacade,
    ChangePasswordIn,
    LoginIn,
    LoginOut,
)
from shared.adapters.driving.middleware import jwt_required
from shared.generics.errors import DrivingAdapterError

access_bp = APIBlueprint("access", __name__, url_prefix="/auth")


@access_bp.post("/login")
@access_bp.input(LoginIn)
@access_bp.output(LoginOut)
@access_bp.doc(summary="Вход для персонала")
@inject
def login(json_data: LoginIn, facade: FromDishka[AccessFacade]):
    try:
        return facade.login(json_data)
    except InvalidPasswordError:
        raise DrivingAdapterError("Неверный логин или пароль", "INVALID_CREDENTIALS")


@access_bp.post("/password")
@jwt_required
@access_bp.input(ChangePasswordIn)
@access_bp.doc(
    summary="Смена пароля администратора (ADMIN ONLY)",
    description="Изменяет пароль текущего авторизованного администратора.",
    security="JWTAuth",
)
@inject
def change_password(json_data: ChangePasswordIn, facade: FromDishka[AccessFacade]):
    admin_id = request.admin_payload.get("sub", 1)
    facade.change_password(admin_id, json_data.model_dump())
    return {"success": True}

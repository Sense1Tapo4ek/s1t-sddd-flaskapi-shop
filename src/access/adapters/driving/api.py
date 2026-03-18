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

access_bp = APIBlueprint("access", __name__, url_prefix="/auth")


@access_bp.post("/login")
@access_bp.input(LoginIn)
@access_bp.output(LoginOut)
@access_bp.doc(summary="Staff Login")
@inject
def login(json_data: LoginIn, facade: FromDishka[AccessFacade]):
    try:
        return facade.login(json_data)
    except InvalidPasswordError:
        return {"error": "Invalid login or password"}, 401


@access_bp.post("/password")
@jwt_required
@access_bp.input(ChangePasswordIn)
@access_bp.doc(
    summary="Change admin password (ADMIN ONLY)",
    description="Changes the password for the currently authenticated admin user.",
    security="JWTAuth",
)
@inject
def change_password(json_data: ChangePasswordIn, facade: FromDishka[AccessFacade]):
    admin_id = request.admin_payload.get("sub", 1)
    facade.change_password(admin_id, json_data.model_dump())
    return {"success": True}

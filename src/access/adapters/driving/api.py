import logging

from apiflask import APIBlueprint
from dishka.integrations.flask import inject, FromDishka
from flask import request

from access.domain import (
    AdminInactiveError,
    CustomerInactiveError,
    InvalidPasswordError,
)

logger = logging.getLogger(__name__)
from access.ports.driving import (
    AccessFacade,
    AdminFacade,
    CustomerFacade,
    ChangePasswordIn,
    CustomerRecoverIn,
    CustomerRegisterIn,
    CustomerVerifyIn,
    LoginIn,
    LoginOut,
)
from shared.adapters.driving.middleware import admin_required
from shared.generics.errors import DrivingAdapterError

access_bp = APIBlueprint("access", __name__, url_prefix="/auth")


@access_bp.post("/login")
@access_bp.input(LoginIn)
@access_bp.output(LoginOut)
@access_bp.doc(summary="Вход для персонала и клиентов")
@inject
def login(json_data: LoginIn, facade: FromDishka[AccessFacade]):
    try:
        return facade.login(json_data)
    except InvalidPasswordError:
        raise DrivingAdapterError("Неверный логин или пароль", "INVALID_CREDENTIALS")
    except (AdminInactiveError, CustomerInactiveError):
        raise DrivingAdapterError("Аккаунт отключён", "ACCOUNT_INACTIVE")


@access_bp.post("/customer/register")
@access_bp.input(CustomerRegisterIn)
@access_bp.output(LoginOut, status_code=201)
@access_bp.doc(summary="Регистрация клиента")
@inject
def register_customer(json_data: CustomerRegisterIn, facade: FromDishka[CustomerFacade]):
    return facade.register(json_data)


@access_bp.post("/customer/recover")
@access_bp.input(CustomerRecoverIn)
@access_bp.doc(summary="Запрос кода восстановления")
@inject
def recover_customer(json_data: CustomerRecoverIn, facade: FromDishka[CustomerFacade]):
    # Always 202 — even on unknown email — to avoid leaking the registration base.
    # Failures are logged at boundary; the client response stays uniform.
    try:
        facade.send_recovery_code(json_data)
    except Exception:
        logger.exception("customer recovery send failed")
    return "", 202


@access_bp.post("/customer/verify")
@access_bp.input(CustomerVerifyIn)
@access_bp.output(LoginOut)
@access_bp.doc(summary="Подтверждение кода и смена пароля")
@inject
def verify_customer(json_data: CustomerVerifyIn, facade: FromDishka[CustomerFacade]):
    return facade.verify_and_reset(json_data)


@access_bp.post("/password")
@admin_required
@access_bp.input(ChangePasswordIn)
@access_bp.doc(
    summary="Смена пароля администратора (ADMIN ONLY)",
    description="Изменяет пароль текущего авторизованного администратора.",
    security="JWTAuth",
)
@inject
def change_password(json_data: ChangePasswordIn, facade: FromDishka[AdminFacade]):
    admin_id = request.admin_payload.get("sub", 1)
    facade.change_password(admin_id, json_data)
    return {"success": True}

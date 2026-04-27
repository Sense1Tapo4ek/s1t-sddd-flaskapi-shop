import secrets

from flask import request, make_response, render_template
from markupsafe import escape
from apiflask import APIBlueprint
from dishka.integrations.flask import inject, FromDishka

from access.config import AccessConfig
from access.ports.driving.facade import AccessFacade
from access.ports.driving.schemas import LoginIn
from system.ports.driving.facade import SystemFacade
from shared.adapters.driving.middleware import jwt_required
from shared.generics.errors import LayerError


access_admin_bp = APIBlueprint("access_admin", __name__, url_prefix="/admin", enable_openapi=False)


def _remember_enabled(value: str | None) -> bool:
    return str(value or "").lower() in ("1", "true", "yes", "on")


def _set_auth_cookie(response, token: str, *, remember_me: bool, csrf_token: str):
    max_age = 60 * 60 * 24 * (30 if remember_me else 1)
    response.set_cookie(
        "token", token,
        httponly=True,
        samesite="Strict",
        path="/",
        max_age=max_age,
        secure=request.is_secure,
    )
    response.set_cookie(
        "csrf_token", csrf_token,
        httponly=False,
        samesite="Strict",
        path="/",
        max_age=max_age,
        secure=request.is_secure,
    )
    return response


@access_admin_bp.route("/login", methods=["GET"])
@inject
def login_page(config: FromDishka[AccessConfig]):
    return render_template(
        "access/pages/login.html",
        recovery_code_ttl_minutes=config.recovery_code_ttl_minutes,
    )


@access_admin_bp.route("/login", methods=["POST"])
@inject
def login(facade: FromDishka[AccessFacade]):
    data = request.form
    remember_me = _remember_enabled(data.get("remember_me"))
    csrf_token = secrets.token_urlsafe(32)
    schema = LoginIn(
        login=data.get("login", ""),
        password=data.get("password", ""),
        remember_me=remember_me,
    )
    result = facade.login(schema, csrf_token=csrf_token)
    response = make_response("")
    _set_auth_cookie(
        response,
        result.token,
        remember_me=remember_me,
        csrf_token=csrf_token,
    )
    response.headers["HX-Redirect"] = "/admin/"
    return response


@access_admin_bp.route("/logout", methods=["DELETE"])
@jwt_required
def logout():
    response = make_response("")
    response.set_cookie("token", "", max_age=0, path="/")
    response.set_cookie("csrf_token", "", max_age=0, path="/")
    response.headers["HX-Redirect"] = "/admin/login"
    return response


@access_admin_bp.route("/telegram/request-code", methods=["POST"])
@inject
def request_telegram_code(
    access_facade: FromDishka[AccessFacade],
    system_facade: FromDishka[SystemFacade],
    config: FromDishka[AccessConfig],
):
    login = request.form.get("login", "").strip()
    remember_me = _remember_enabled(request.form.get("remember_me"))
    try:
        resolved_login, chat_id, code = access_facade.request_telegram_login_code(login)
        sent = system_facade.send_login_code(
            chat_id=chat_id,
            login=resolved_login,
            code=code,
            ttl_minutes=config.recovery_code_ttl_minutes,
        )
        if not sent:
            raise LayerError(
                "Telegram-бот не настроен или сообщение не отправлено",
                "TELEGRAM_SEND_FAILED",
            )
    except LayerError as e:
        msg = escape(e.message or "Telegram-вход недоступен")
        return (
            f'<p class="recovery-desc" style="color:var(--color-danger);">{msg}</p>'
            f'<div style="text-align:center;">'
            f'<a href="/admin/login" class="btn btn--ghost btn--sm">Назад</a></div>'
        )
    return render_template(
        "access/partials/recovery_code_form.html",
        login=resolved_login,
        remember_me=remember_me,
        recovery_code_ttl_minutes=config.recovery_code_ttl_minutes,
    )


@access_admin_bp.route("/verify-code", methods=["POST"])
@inject
def verify_recovery_code(facade: FromDishka[AccessFacade]):
    login = request.form.get("login", "").strip()
    code = request.form.get("code", "").strip()
    remember_me = _remember_enabled(request.form.get("remember_me"))
    csrf_token = secrets.token_urlsafe(32)
    try:
        token = facade.verify_telegram_login_code(
            login=login,
            code=code,
            remember_me=remember_me,
            csrf_token=csrf_token,
        ).token
    except LayerError as e:
        msg = escape(e.message or "Неверный код")
        return f'<span style="color:var(--color-danger);">{msg}</span>'
    response = make_response("")
    _set_auth_cookie(
        response,
        token,
        remember_me=remember_me,
        csrf_token=csrf_token,
    )
    response.headers["HX-Redirect"] = "/admin/"
    return response

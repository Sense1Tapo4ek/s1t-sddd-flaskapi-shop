from flask import request, make_response, render_template
from apiflask import APIBlueprint
from dishka.integrations.flask import inject, FromDishka

from access.ports.driving.facade import AccessFacade
from access.ports.driving.schemas import LoginIn
from system.ports.driving.facade import SystemFacade
from shared.generics.errors import LayerError


access_admin_bp = APIBlueprint("access_admin", __name__, url_prefix="/admin", enable_openapi=False)


@access_admin_bp.route("/login", methods=["GET"])
def login_page():
    return render_template("access/pages/login.html")


@access_admin_bp.route("/login", methods=["POST"])
@inject
def login(facade: FromDishka[AccessFacade]):
    data = request.form
    schema = LoginIn(login=data.get("login", ""), password=data.get("password", ""))
    result = facade.login(schema)
    response = make_response("")
    response.set_cookie(
        "token", result.token,
        httponly=True, samesite="Strict", path="/",
    )
    response.headers["HX-Redirect"] = "/admin/products/"
    return response


@access_admin_bp.route("/logout", methods=["DELETE"])
def logout():
    response = make_response("")
    response.set_cookie("token", "", max_age=0, path="/")
    response.headers["HX-Redirect"] = "/admin/login"
    return response


@access_admin_bp.route("/recover", methods=["POST"])
@inject
def request_recovery(system_facade: FromDishka[SystemFacade]):
    try:
        system_facade.recover_password()
    except LayerError as e:
        msg = e.message or "Ошибка восстановления пароля"
        return f'<p class="recovery-desc" style="color:var(--color-danger);">{msg}</p>' \
               f'<div style="text-align:center;">' \
               f'<a href="/admin/login" class="btn btn--ghost btn--sm">Назад</a></div>'
    return render_template("access/partials/recovery_code_form.html")


@access_admin_bp.route("/verify-code", methods=["POST"])
@inject
def verify_recovery_code(facade: FromDishka[AccessFacade]):
    code = request.form.get("code", "").strip()
    try:
        token = facade.verify_recovery_code(code)
    except LayerError as e:
        msg = e.message or "Неверный код"
        return f'<span style="color:var(--color-danger);">{msg}</span>'
    response = make_response("")
    response.set_cookie(
        "token", token,
        httponly=True, samesite="Strict", path="/",
    )
    response.headers["HX-Redirect"] = "/admin/products/"
    return response

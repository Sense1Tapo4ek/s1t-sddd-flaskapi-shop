import json
from flask import request, render_template, make_response
from apiflask import APIBlueprint
from dishka.integrations.flask import inject, FromDishka

from system.ports.driving.facade import SystemFacade
from system.ports.driving.schemas import FetchChatIdIn, SettingsUpdateIn
from access.ports.driving.facade import AccessFacade
from access.ports.driving.schemas import ChangePasswordIn
from shared.adapters.driving.middleware import jwt_required

system_admin_bp = APIBlueprint("system_admin", __name__, url_prefix="/admin/settings", enable_openapi=False)


TAB_TITLES = {"store": "Магазин", "telegram": "Оповещения", "security": "Безопасность"}


@system_admin_bp.route("/")
@system_admin_bp.route("/<tab>")
@jwt_required
@inject
def settings_page(facade: FromDishka[SystemFacade], tab: str = "store"):
    if tab not in TAB_TITLES:
        tab = "store"
    settings = facade.get_settings()
    return render_template(
        "system/pages/settings.html",
        settings=settings,
        tab=tab,
        tab_title=TAB_TITLES[tab],
    )


@system_admin_bp.route("/store", methods=["PUT"])
@jwt_required
@inject
def update_store(facade: FromDishka[SystemFacade]):
    f = request.form
    schema = SettingsUpdateIn(
        contacts={
            "phone": f.get("phone", ""),
            "email": f.get("email", ""),
            "address": f.get("address", ""),
            "working_hours": f.get("working_hours", ""),
        },
        coords={
            "lat": f.get("coords_lat", 0),
            "lon": f.get("coords_lon", 0),
        },
        socials={"instagram": f.get("instagram", "")},
    )
    settings = facade.update_settings(schema)
    response = make_response(
        render_template("system/partials/store_form.html", settings=settings)
    )
    response.headers["HX-Trigger"] = json.dumps({
        "showToast": {"message": "Settings saved", "type": "success"}
    })
    return response


@system_admin_bp.route("/telegram", methods=["PUT"])
@jwt_required
@inject
def update_telegram(facade: FromDishka[SystemFacade]):
    f = request.form
    schema = SettingsUpdateIn(
        telegram={
            "bot_token": f.get("bot_token", ""),
            "chat_id": f.get("chat_id", ""),
        }
    )
    settings = facade.update_settings(schema)
    response = make_response(
        render_template("system/partials/telegram_form.html", settings=settings)
    )
    response.headers["HX-Trigger"] = json.dumps({
        "showToast": {"message": "Telegram settings saved", "type": "success"}
    })
    return response


@system_admin_bp.route("/telegram/fetch-chat-id", methods=["POST"])
@jwt_required
@inject
def fetch_chat_id(facade: FromDishka[SystemFacade]):
    bot_token = request.form.get("bot_token", "").strip()
    if not bot_token:
        return '<input class="form-input" type="text" id="chat_id" name="chat_id" placeholder="Not connected" value="">'
    try:
        schema = FetchChatIdIn(bot_token=bot_token)
        chat_id = facade.fetch_telegram_chat_id(schema)
    except Exception as e:
        msg = getattr(e, "user_message", None) or getattr(e, "message", None) or "Ошибка получения Chat ID"
        response = make_response(
            f'<input class="form-input" type="text" id="chat_id" name="chat_id" placeholder="Not connected" value="">'
        )
        response.headers["HX-Trigger"] = json.dumps({
            "showToast": {"message": msg, "type": "error"}
        })
        return response
    response = make_response(
        f'<input class="form-input" type="text" id="chat_id" name="chat_id" value="{chat_id}">'
    )
    response.headers["HX-Trigger"] = json.dumps({
        "showToast": {"message": "Chat ID получен", "type": "success"}
    })
    return response


@system_admin_bp.route("/telegram/test", methods=["POST"])
@jwt_required
@inject
def test_telegram(facade: FromDishka[SystemFacade]):
    success = facade.test_telegram()
    return render_template("system/partials/telegram_status.html", success=success)


@system_admin_bp.route("/password", methods=["PUT"])
@jwt_required
@inject
def change_password(access_facade: FromDishka[AccessFacade]):
    admin_id = request.admin_payload.get("sub", 1)
    schema = ChangePasswordIn(
        old_password=request.form.get("old_password", ""),
        new_password=request.form.get("new_password", ""),
    )
    access_facade.change_password(admin_id, schema.model_dump())
    response = make_response("")
    response.headers["HX-Trigger"] = json.dumps({
        "showToast": {"message": "Password changed", "type": "success"}
    })
    return response

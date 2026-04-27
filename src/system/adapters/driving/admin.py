import json
import sqlite3
import tempfile
from datetime import datetime
from pathlib import Path

from flask import after_this_request, request, render_template, make_response, redirect, send_file
from markupsafe import escape
from apiflask import APIBlueprint
from dishka.integrations.flask import inject, FromDishka
from sqlalchemy.engine import make_url

from system.ports.driving.facade import SystemFacade
from system.ports.driving.schemas import FetchChatIdIn, SettingsUpdateIn
from access.config import AccessConfig
from access.ports.driving.facade import AccessFacade
from access.ports.driving.schemas import ChangePasswordIn
from shared.adapters.driving.middleware import (
    has_permission,
    jwt_required,
    permission_required,
    superadmin_required,
)
from shared.config import InfraConfig
from shared.generics.errors import DrivingAdapterError
from shared.generics.errors import DrivingPortError

system_admin_bp = APIBlueprint("system_admin", __name__, url_prefix="/admin/settings", enable_openapi=False)
account_admin_bp = APIBlueprint("account_admin", __name__, url_prefix="/admin/account", enable_openapi=False)


TAB_TITLES = {"store": "Магазин", "telegram": "Оповещения"}


def _form_bool(name: str) -> bool:
    return str(request.form.get(name, "")).lower() in {"1", "true", "yes", "on"}


def _form_float(name: str, default: float = 0.0) -> float:
    raw = request.form.get(name, "")
    if raw in (None, ""):
        return default
    try:
        return float(raw)
    except (TypeError, ValueError) as exc:
        raise DrivingPortError(f"Некорректное числовое значение: {name}") from exc


def _sqlite_database_path(database_url: str) -> Path:
    url = make_url(database_url)
    if url.get_backend_name() != "sqlite":
        raise DrivingPortError("Дамп через UI пока поддержан только для SQLite")
    if not url.database or url.database == ":memory:":
        raise DrivingPortError("Дамп in-memory SQLite базы недоступен")
    path = Path(url.database)
    if not path.is_absolute():
        path = Path.cwd() / path
    if not path.exists():
        raise DrivingPortError("Файл базы данных не найден")
    return path


@system_admin_bp.route("/database-dump", methods=["GET"])
@superadmin_required
@inject
def download_database_dump(
    infra_config: FromDishka[InfraConfig],
    access_facade: FromDishka[AccessFacade],
):
    current_user = access_facade.get_user(request.admin_payload.get("sub", 1))
    if current_user.role != "superadmin" or current_user.password_changed_at is None:
        raise DrivingAdapterError("Password change required before database dump", "FORBIDDEN")

    database_path = _sqlite_database_path(infra_config.database_url)
    tmp_path = _backup_sqlite_database(database_path)

    @after_this_request
    def cleanup(response):
        try:
            tmp_path.unlink(missing_ok=True)
        finally:
            return response

    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    response = send_file(
        tmp_path,
        as_attachment=True,
        download_name=f"shop-{timestamp}.sqlite",
        mimetype="application/vnd.sqlite3",
    )
    response.headers["Cache-Control"] = "no-store"
    return response


def _backup_sqlite_database(database_path: Path) -> Path:
    tmp = tempfile.NamedTemporaryFile(prefix="shop-", suffix=".sqlite", delete=False)
    tmp.close()
    tmp_path = Path(tmp.name)

    source = None
    target = None
    error: sqlite3.Error | None = None
    try:
        source = sqlite3.connect(database_path)
        target = sqlite3.connect(tmp_path)
        source.backup(target)
    except sqlite3.Error as exc:
        error = exc
    finally:
        for connection in (target, source):
            if connection is None:
                continue
            try:
                connection.close()
            except sqlite3.Error as exc:
                if error is None:
                    error = exc

    if error is not None:
        tmp_path.unlink(missing_ok=True)
        raise DrivingPortError("Не удалось подготовить SQLite дамп") from error
    return tmp_path


@system_admin_bp.route("/")
@system_admin_bp.route("/<tab>")
@jwt_required
@inject
def settings_page(
    facade: FromDishka[SystemFacade],
    access_facade: FromDishka[AccessFacade],
    tab: str = "store",
):
    if tab == "security":
        return redirect("/admin/account")
    if tab not in TAB_TITLES:
        tab = "store"
    if tab != "security" and not has_permission("manage_settings"):
        raise DrivingAdapterError("Forbidden", "FORBIDDEN")
    settings = facade.get_settings()
    current_user = access_facade.get_user(request.admin_payload.get("sub", 1))
    return render_template(
        "system/pages/settings.html",
        settings=settings,
        current_user=current_user,
        tab=tab,
        tab_title=TAB_TITLES[tab],
    )


@account_admin_bp.route("")
@jwt_required
@inject
def account_page(access_facade: FromDishka[AccessFacade]):
    current_user = access_facade.get_user(request.admin_payload.get("sub", 1))
    return render_template(
        "system/pages/account.html",
        current_user=current_user,
    )


@system_admin_bp.route("/store", methods=["PUT"])
@permission_required("manage_settings")
@inject
def update_store(facade: FromDishka[SystemFacade]):
    f = request.form
    schema = SettingsUpdateIn(
        branding={
            "app_name": f.get("app_name", ""),
            "admin_panel_title": f.get("admin_panel_title", ""),
        },
        contacts={
            "phone": f.get("phone", ""),
            "email": f.get("email", ""),
            "address": f.get("address", ""),
            "working_hours": f.get("working_hours", ""),
        },
        coords={
            "lat": _form_float("coords_lat"),
            "lon": _form_float("coords_lon"),
        },
        socials={"instagram": f.get("instagram", "")},
        catalog_access={
            "owner_can_edit_taxonomy": _form_bool("owner_can_edit_taxonomy"),
            "owner_can_view_products": _form_bool("owner_can_view_products"),
            "owner_can_edit_products": _form_bool("owner_can_edit_products"),
            "owner_can_create_demo_data": _form_bool("owner_can_create_demo_data"),
        },
    )
    settings = facade.update_settings(schema)
    response = make_response(
        render_template("system/partials/store_form.html", settings=settings)
    )
    response.headers["HX-Trigger"] = json.dumps({
        "showToast": {"message": "Settings saved", "type": "success"}
    })
    response.headers["HX-Refresh"] = "true"
    return response


@system_admin_bp.route("/telegram", methods=["PUT"])
@permission_required("manage_settings")
@inject
def update_telegram(facade: FromDishka[SystemFacade]):
    f = request.form
    schema = SettingsUpdateIn(
        telegram={
            "bot_token": f.get("bot_token", ""),
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
@permission_required("manage_settings")
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
        f'<input class="form-input" type="text" id="chat_id" name="chat_id" value="{escape(chat_id)}">'
    )
    response.headers["HX-Trigger"] = json.dumps({
        "showToast": {"message": "Chat ID получен", "type": "success"}
    })
    return response


@system_admin_bp.route("/telegram/test", methods=["POST"])
@permission_required("manage_settings")
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
        confirmation_code=request.form.get("confirmation_code", ""),
    )
    access_facade.change_password(admin_id, schema.model_dump())
    response = make_response("")
    response.headers["HX-Trigger"] = json.dumps({
        "showToast": {"message": "Password changed", "type": "success"},
        "passwordChanged": True,
    })
    return response


@system_admin_bp.route("/security/password-code", methods=["POST"])
@jwt_required
@inject
def request_password_confirmation_code(
    access_facade: FromDishka[AccessFacade],
    system_facade: FromDishka[SystemFacade],
    access_config: FromDishka[AccessConfig],
):
    admin_id = request.admin_payload.get("sub", 1)
    login, chat_id, code = access_facade.request_user_confirmation_code(admin_id)
    sent = system_facade.send_login_code(
        chat_id=chat_id,
        login=login,
        code=code,
        title="Password Change Code",
        ttl_minutes=access_config.recovery_code_ttl_minutes,
    )
    if not sent:
        raise DrivingPortError("Telegram-бот не настроен или сообщение не отправлено")
    response = make_response("")
    response.headers["HX-Trigger"] = json.dumps({
        "showToast": {"message": "Код отправлен в Telegram", "type": "success"}
    })
    return response


@system_admin_bp.route("/security/fetch-chat-id", methods=["POST"])
@jwt_required
@inject
def fetch_current_user_chat_id(facade: FromDishka[SystemFacade]):
    settings = facade.get_settings()
    bot_token = settings.telegram.bot_token.strip()
    if not bot_token:
        response = make_response(
            '<input class="form-input" type="text" id="user_telegram_chat_id" '
            'name="telegram_chat_id" placeholder="Сначала настройте токен бота" value="">'
        )
        response.headers["HX-Trigger"] = json.dumps({
            "showToast": {"message": "Сначала настройте Telegram bot token", "type": "error"}
        })
        return response
    try:
        chat_id = facade.fetch_telegram_chat_id(FetchChatIdIn(bot_token=bot_token))
    except Exception as e:
        msg = getattr(e, "user_message", None) or getattr(e, "message", None) or "Ошибка получения Chat ID"
        response = make_response(
            '<input class="form-input" type="text" id="user_telegram_chat_id" '
            'name="telegram_chat_id" placeholder="Не подключён" value="">'
        )
        response.headers["HX-Trigger"] = json.dumps({
            "showToast": {"message": msg, "type": "error"}
        })
        return response
    response = make_response(
        f'<input class="form-input" type="text" id="user_telegram_chat_id" '
        f'name="telegram_chat_id" value="{escape(chat_id)}">'
    )
    response.headers["HX-Trigger"] = json.dumps({
        "showToast": {"message": "Chat ID получен", "type": "success"}
    })
    return response


@system_admin_bp.route("/security/telegram-chat", methods=["PUT"])
@jwt_required
@inject
def update_current_user_chat_id(
    access_facade: FromDishka[AccessFacade],
):
    admin_id = request.admin_payload.get("sub", 1)
    chat_id = request.form.get("telegram_chat_id", "").strip()
    access_facade.update_telegram_chat_id(admin_id, chat_id or None)
    response = make_response("")
    response.headers["HX-Trigger"] = json.dumps({
        "showToast": {"message": "Telegram привязка сохранена", "type": "success"}
    })
    return response

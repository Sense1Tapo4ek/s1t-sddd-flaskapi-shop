import json
from datetime import datetime
from pathlib import Path

from flask import request, render_template, make_response, redirect, send_file
from markupsafe import escape
from apiflask import APIBlueprint
from dishka.integrations.flask import inject, FromDishka

from system.ports.driving.facade import SystemFacade
from system.ports.driving.schemas import (
    FetchChatIdIn,
    SettingsUpdateIn,
    StorageSettingsUpdateIn,
)
from access.config import AccessConfig
from access.ports.driving import AdminFacade, ChangePasswordIn
from shared.adapters.driving.middleware import (
    has_permission,
    jwt_required,
    permission_required,
    superadmin_required,
)
from shared.generics.errors import DrivingAdapterError
from shared.generics.errors import DrivingPortError

system_admin_bp = APIBlueprint("system_admin", __name__, url_prefix="/admin/settings", enable_openapi=False)
account_admin_bp = APIBlueprint("account_admin", __name__, url_prefix="/admin/account", enable_openapi=False)
backups_admin_bp = APIBlueprint("backups_admin", __name__, url_prefix="/admin/backups", enable_openapi=False)


TAB_TITLES = {
    "store": "Магазин",
    "telegram": "Оповещения",
    "storage": "Хранилище",
}


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


_DAYS = ("mon", "tue", "wed", "thu", "fri", "sat", "sun")


def _parse_working_hours_schedule() -> dict[str, dict | None]:
    """Read seven day rows from the form.

    Convention per day:
        {day}_off          → checkbox; on means closed
        {day}_opens        → HH:MM
        {day}_closes       → HH:MM
        {day}_break_start  → HH:MM (optional)
        {day}_break_end    → HH:MM (optional)
    """
    f = request.form
    schedule: dict[str, dict | None] = {}
    for day in _DAYS:
        if _form_bool(f"{day}_off"):
            schedule[day] = None
            continue
        opens = (f.get(f"{day}_opens", "") or "").strip()
        closes = (f.get(f"{day}_closes", "") or "").strip()
        if not opens or not closes:
            schedule[day] = None
            continue
        bs = (f.get(f"{day}_break_start", "") or "").strip() or None
        be = (f.get(f"{day}_break_end", "") or "").strip() or None
        schedule[day] = {
            "opens_at": opens,
            "closes_at": closes,
            "break_start": bs,
            "break_end": be,
        }
    return schedule


# Project root: src/system/adapters/driving/admin.py → parents[4]. The
# dumps directory must be an absolute path because ``send_file`` resolves
# relative paths against ``app.root_path`` (the blueprint module dir),
# not the CWD.
_PROJECT_ROOT = Path(__file__).resolve().parents[4]
_DUMPS_DIR = _PROJECT_ROOT / "data" / "dumps"


def _latest_dump_file() -> Path | None:
    if not _DUMPS_DIR.is_dir():
        return None
    candidates = sorted(
        (p for p in _DUMPS_DIR.iterdir() if p.is_file()),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    return candidates[0] if candidates else None


@system_admin_bp.route("/database-dump", methods=["GET"])
@superadmin_required
@inject
def download_database_dump(access_facade: FromDishka[AdminFacade]):
    """Serve the most recent MySQL dump produced by scripts/db_dump.py.

    Dumps are created out-of-process (cron in CPanel, manual on a workstation)
    and stored under data/dumps/. The endpoint never shells out to mysqldump
    itself — that's unreliable on shared Passenger venvs.
    """
    current_user = access_facade.get_user(request.admin_payload.get("sub", 1))
    if current_user.role != "superadmin" or current_user.password_changed_at is None:
        raise DrivingAdapterError(
            "Смените пароль перед скачиванием дампа базы данных", "FORBIDDEN"
        )

    dump_path = _latest_dump_file()
    if dump_path is None:
        raise DrivingPortError(
            "Нет доступных дампов. Запустите `python scripts/db_dump.py` "
            "или настройте cron на хостинге."
        )

    timestamp = datetime.fromtimestamp(dump_path.stat().st_mtime).strftime(
        "%Y%m%d-%H%M%S"
    )
    response = send_file(
        dump_path,
        as_attachment=True,
        download_name=f"shop-{timestamp}{''.join(dump_path.suffixes)}",
        mimetype="application/gzip"
        if dump_path.suffix == ".gz"
        else "application/sql",
    )
    response.headers["Cache-Control"] = "no-store"
    return response


@system_admin_bp.route("/")
@system_admin_bp.route("/<tab>")
@jwt_required
@inject
def settings_page(
    facade: FromDishka[SystemFacade],
    access_facade: FromDishka[AdminFacade],
    tab: str = "store",
):
    if tab == "security":
        return redirect("/admin/account")
    if tab not in TAB_TITLES:
        tab = "store"
    if not has_permission("manage_settings"):
        raise DrivingAdapterError("Доступ запрещён", "FORBIDDEN")
    current_user = access_facade.get_user(request.admin_payload.get("sub", 1))
    if tab == "storage" and current_user.role != "superadmin":
        raise DrivingAdapterError("Настройки хранилища доступны только суперадмину", "FORBIDDEN")
    settings = facade.get_settings()
    storage_settings = (
        facade.get_storage_settings() if tab == "storage" else None
    )
    return render_template(
        "system/pages/settings.html",
        settings=settings,
        storage_settings=storage_settings,
        current_user=current_user,
        tab=tab,
        tab_title=TAB_TITLES[tab],
    )


@account_admin_bp.route("")
@jwt_required
@inject
def account_page(access_facade: FromDishka[AdminFacade]):
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
        contacts={
            "phone": f.get("phone", ""),
            "email": f.get("email", ""),
            "address": f.get("address", ""),
            "working_hours_schedule": _parse_working_hours_schedule(),
        },
        coords={
            "lat": _form_float("coords_lat"),
            "lon": _form_float("coords_lon"),
        },
        socials={
            "instagram": f.get("instagram", ""),
            "telegram": f.get("telegram_public_url", ""),
            "whatsapp": f.get("whatsapp_url", ""),
            "viber": f.get("viber_url", ""),
        },
        # catalog_access НЕ принимается через UI: владелец-права задаются в
        # .env (ACCESS_OWNER_CAN_*) и применяются на старте процесса.
    )
    settings = facade.update_settings(schema)
    response = make_response(
        render_template("system/partials/store_form.html", settings=settings)
    )
    response.headers["HX-Trigger"] = json.dumps({
        "showToast": {"message": "Настройки сохранены", "type": "success"}
    })
    response.headers["HX-Refresh"] = "true"
    return response


@system_admin_bp.route("/storage", methods=["PUT"])
@superadmin_required
@inject
def update_storage(facade: FromDishka[SystemFacade]):
    f = request.form
    backend = f.get("backend") or None

    secret_raw = f.get("secret_access_key", "")
    # Empty input = "не менять текущий секрет". Use the explicit "clear" flag
    # to wipe it. Sending a non-empty value replaces the stored secret.
    if _form_bool("clear_secret"):
        secret_value: str | None = ""
    elif secret_raw:
        secret_value = secret_raw
    else:
        secret_value = None

    schema = StorageSettingsUpdateIn(
        backend=backend,
        endpoint_url=f.get("endpoint_url", "") or None,
        region=f.get("region", "") or None,
        bucket=f.get("bucket", "") or None,
        access_key_id=f.get("access_key_id", "") or None,
        secret_access_key=secret_value,
        public_base_url=f.get("public_base_url", "") or None,
        force_path_style=_form_bool("force_path_style"),
        test_connection=_form_bool("test_connection"),
    )
    storage_settings = facade.update_storage_settings(schema)
    response = make_response(
        render_template(
            "system/partials/storage_form.html",
            storage_settings=storage_settings,
        )
    )
    response.headers["HX-Trigger"] = json.dumps({
        "showToast": {"message": "Настройки хранилища сохранены", "type": "success"}
    })
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
        "showToast": {"message": "Настройки Telegram сохранены", "type": "success"}
    })
    return response


@system_admin_bp.route("/telegram/fetch-chat-id", methods=["POST"])
@permission_required("manage_settings")
@inject
def fetch_chat_id(facade: FromDishka[SystemFacade]):
    bot_token = request.form.get("bot_token", "").strip()
    if not bot_token:
        return '<input class="form-input" type="text" id="chat_id" name="chat_id" placeholder="Не подключён" value="">'
    try:
        schema = FetchChatIdIn(bot_token=bot_token)
        chat_id = facade.fetch_telegram_chat_id(schema)
    except Exception as e:
        msg = getattr(e, "user_message", None) or getattr(e, "message", None) or "Ошибка получения Chat ID"
        response = make_response(
            f'<input class="form-input" type="text" id="chat_id" name="chat_id" placeholder="Не подключён" value="">'
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
def change_password(access_facade: FromDishka[AdminFacade]):
    admin_id = request.admin_payload.get("sub", 1)
    schema = ChangePasswordIn(
        old_password=request.form.get("old_password", ""),
        new_password=request.form.get("new_password", ""),
        confirmation_code=request.form.get("confirmation_code", ""),
    )
    access_facade.change_password(admin_id, schema)
    response = make_response("")
    response.headers["HX-Trigger"] = json.dumps({
        "showToast": {"message": "Пароль изменён", "type": "success"},
        "passwordChanged": True,
    })
    return response


@system_admin_bp.route("/security/password-code", methods=["POST"])
@jwt_required
@inject
def request_password_confirmation_code(
    access_facade: FromDishka[AdminFacade],
    system_facade: FromDishka[SystemFacade],
    access_config: FromDishka[AccessConfig],
):
    admin_id = request.admin_payload.get("sub", 1)
    login, chat_id, code = access_facade.request_user_confirmation_code(admin_id)
    sent = system_facade.send_login_code(
        chat_id=chat_id,
        login=login,
        code=code,
        title="Код для смены пароля",
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
            "showToast": {"message": "Сначала настройте токен бота Telegram", "type": "error"}
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
    access_facade: FromDishka[AdminFacade],
):
    admin_id = request.admin_payload.get("sub", 1)
    chat_id = request.form.get("telegram_chat_id", "").strip()
    access_facade.update_telegram_chat_id(admin_id, chat_id or None)
    response = make_response("")
    response.headers["HX-Trigger"] = json.dumps({
        "showToast": {"message": "Привязка Telegram сохранена", "type": "success"}
    })
    return response


# ---------------------------------------------------------------------------
# Backups admin (superadmin-only)
# ---------------------------------------------------------------------------

@backups_admin_bp.route("/")
@superadmin_required
@inject
def backups_page(facade: FromDishka[SystemFacade]):
    """List all snapshots — main backups admin page."""
    snapshots = facade.list_snapshots()
    return render_template("system/pages/backups.html", snapshots=snapshots)


@backups_admin_bp.route("/snapshot", methods=["POST"])
@superadmin_required
@inject
def create_snapshot(facade: FromDishka[SystemFacade]):
    """Create a new snapshot and return a refreshed table partial + toast."""
    facade.create_snapshot()
    snapshots = facade.list_snapshots()
    response = make_response(
        render_template("system/partials/backups_table.html", snapshots=snapshots)
    )
    response.headers["HX-Trigger"] = json.dumps({
        "showToast": {"message": "Снапшот создан", "type": "success"}
    })
    return response


@backups_admin_bp.route("/<string:name>/restore", methods=["POST"])
@superadmin_required
@inject
def restore_snapshot(facade: FromDishka[SystemFacade], name: str):
    """
    Restore the database from snapshot *name*.

    Side effect: maintenance mode is entered (and exited) inside the use case.
    Returns a full-page redirect so the admin is sent back to a clean state.
    """
    facade.restore_snapshot(name=name)
    response = make_response("")
    response.headers["HX-Trigger"] = json.dumps({
        "showToast": {"message": "База данных восстановлена", "type": "success"}
    })
    response.headers["HX-Redirect"] = "/admin/backups/"
    return response


@backups_admin_bp.route("/<string:name>", methods=["DELETE"])
@superadmin_required
@inject
def delete_snapshot(facade: FromDishka[SystemFacade], name: str):
    """Delete snapshot *name* and return a refreshed table partial + toast."""
    facade.delete_snapshot(name=name)
    snapshots = facade.list_snapshots()
    response = make_response(
        render_template("system/partials/backups_table.html", snapshots=snapshots)
    )
    response.headers["HX-Trigger"] = json.dumps({
        "showToast": {"message": "Снапшот удалён", "type": "success"}
    })
    return response

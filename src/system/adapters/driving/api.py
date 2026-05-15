from apiflask import APIBlueprint
from dishka.integrations.flask import inject, FromDishka

from shared.adapters.driving.middleware import permission_required
from shared.generics.errors import ApplicationError
from shared.adapters.driving.error_handlers import json_error_response
from shared.ports.driving.schemas import SuccessResponse
from system.ports.driving import (
    SystemFacade,
    SettingsUpdateIn,
    FetchChatIdIn,
    SettingsOut,
    InfoOut,
)
from system.ports.driving.schemas import TelegramChatIdOut

system_bp = APIBlueprint("system", __name__, url_prefix="/system", tag="System")


# --- ADMIN (Protected) ---


@system_bp.get("/settings")
@permission_required("manage_settings")
@system_bp.output(SettingsOut)
@system_bp.doc(
    summary="Получить все настройки (ADMIN ONLY)",
    description="Возвращает все системные настройки, включая конфиденциальные данные.",
    security="JWTAuth",
)
@inject
def get_settings(facade: FromDishka[SystemFacade]):
    return facade.get_settings()


@system_bp.put("/settings")
@permission_required("manage_settings")
@system_bp.input(SettingsUpdateIn)
@system_bp.output(SettingsOut)
@system_bp.doc(
    summary="Обновить настройки (ADMIN ONLY)",
    description="Частично или полностью обновляет системные настройки.",
    security="JWTAuth",
)
@inject
def update_settings(json_data: SettingsUpdateIn, facade: FromDishka[SystemFacade]):
    return facade.update_settings(json_data)


@system_bp.post("/settings/test-telegram")
@permission_required("manage_settings")
@system_bp.output(SuccessResponse)
@system_bp.doc(
    summary="Отправить тестовое сообщение в Telegram (ADMIN ONLY)",
    description="Отправляет тестовое уведомление для проверки токена и chat ID Telegram.",
    security="JWTAuth",
)
@inject
def test_telegram(facade: FromDishka[SystemFacade]):
    success = facade.test_telegram()
    return {"success": success}


@system_bp.post("/settings/telegram/fetch-chat-id")
@permission_required("manage_settings")
@system_bp.input(FetchChatIdIn)
@system_bp.output(TelegramChatIdOut)
@system_bp.doc(
    summary="Получить Chat ID Telegram (ADMIN ONLY)",
    description="Опрашивает API Telegram для получения chat_id. Требуется отправить боту /start.",
    security="JWTAuth",
)
@inject
def fetch_chat_id(json_data: FetchChatIdIn, facade: FromDishka[SystemFacade]):
    chat_id = facade.fetch_telegram_chat_id(json_data)
    return {"success": True, "chat_id": chat_id}


# --- PUBLIC ---


@system_bp.get("/info")
@system_bp.output(InfoOut)
@system_bp.doc(
    summary="Публичная информация (Public)",
    description="Возвращает безопасную контактную информацию для отображения в шапке и подвале сайта.",
)
@inject
def get_public_info(facade: FromDishka[SystemFacade]):
    return facade.get_public_info()


@system_bp.post("/settings/recover-password/<token>")
@system_bp.output(SuccessResponse)
@system_bp.doc(
    summary="Восстановить пароль через Telegram (Public)",
    description="Генерирует код восстановления и отправляет его в Telegram чат целевого администратора. Требуется совпадение секретного токена восстановления.",
)
@inject
def recover_password(token: str, facade: FromDishka[SystemFacade]):
    if token != facade.get_config().recovery_token:
        raise ApplicationError("Неверный путь восстановления", "NOT_FOUND")

    success = facade.recover_password()
    if not success:
        return json_error_response(
            code="RECOVERY_FAILED",
            message="Не удалось отправить сообщение",
            status=500,
        )
    return {"success": True}

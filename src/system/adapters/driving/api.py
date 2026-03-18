from apiflask import APIBlueprint
from dishka.integrations.flask import inject, FromDishka

from shared.adapters.driving.middleware import jwt_required
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
@jwt_required
@system_bp.output(SettingsOut)
@system_bp.doc(
    summary="Get all settings (ADMIN ONLY)",
    description="Returns all system settings including sensitive data.",
    security="JWTAuth",
)
@inject
def get_settings(facade: FromDishka[SystemFacade]):
    return facade.get_settings()


@system_bp.put("/settings")
@jwt_required
@system_bp.input(SettingsUpdateIn)
@system_bp.output(SettingsOut)
@system_bp.doc(
    summary="Update settings (ADMIN ONLY)",
    description="Partially or fully updates system settings.",
    security="JWTAuth",
)
@inject
def update_settings(json_data: SettingsUpdateIn, facade: FromDishka[SystemFacade]):
    return facade.update_settings(json_data)


@system_bp.post("/settings/test-telegram")
@jwt_required
@system_bp.output(SuccessResponse)
@system_bp.doc(
    summary="Send test Telegram message (ADMIN ONLY)",
    description="Sends a test notification to verify the Telegram token and chat ID.",
    security="JWTAuth",
)
@inject
def test_telegram(facade: FromDishka[SystemFacade]):
    success = facade.test_telegram()
    return {"success": success}


@system_bp.post("/settings/telegram/fetch-chat-id")
@jwt_required
@system_bp.input(FetchChatIdIn)
@system_bp.output(TelegramChatIdOut)
@system_bp.doc(
    summary="Fetch Telegram chat ID (ADMIN ONLY)",
    description="Polls Telegram API to get the chat_id. Requires /start sent to the bot.",
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
    summary="Get public info (Public)",
    description="Returns safe contact information for display in the site footer and header.",
)
@inject
def get_public_info(facade: FromDishka[SystemFacade]):
    return facade.get_public_info()


@system_bp.post("/settings/recover-password/<token>")
@system_bp.output(SuccessResponse)
@system_bp.doc(
    summary="Recover password via Telegram (Public)",
    description="Generates new credentials and sends them to the configured Telegram chat. Requires matching the secret recovery token.",
)
@inject
def recover_password(token: str, facade: FromDishka[SystemFacade]):
    if token != facade.get_config().recovery_token:
        return {"error": "NOT_FOUND", "message": "Invalid recovery path"}, 404

    success = facade.recover_password()
    if not success:
        return {"error": "RECOVERY_FAILED", "message": "Failed to send message"}, 500
    return {"success": True}

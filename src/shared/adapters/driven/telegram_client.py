import logging
import httpx

logger = logging.getLogger(__name__)

TELEGRAM_API = "https://api.telegram.org/bot{token}"


class TelegramClient:
    """
    Low-level sync HTTP wrapper for Telegram Bot API.
    Stateless — receives token/chat_id per call.
    No knowledge of shop settings.
    Not a dataclass — no dependencies to inject, pure utility.
    """

    def send_message(self, token: str, chat_id: str, text: str) -> bool:
        url = f"{TELEGRAM_API.format(token=token)}/sendMessage"
        try:
            resp = httpx.post(url, json={
                "chat_id": chat_id,
                "text": text,
                "parse_mode": "HTML",
            }, timeout=10)
            resp.raise_for_status()
            return True
        except httpx.HTTPError as e:
            logger.warning("Telegram API error while sending message: %s", type(e).__name__)
            return False

    def get_updates(self, token: str, limit: int = 20) -> list[dict]:
        url = f"{TELEGRAM_API.format(token=token)}/getUpdates"
        try:
            resp = httpx.get(url, params={"limit": limit}, timeout=10)
            resp.raise_for_status()
            data = resp.json()
            return data.get("result", [])
        except httpx.HTTPError as e:
            logger.warning("Telegram API error while fetching updates: %s", type(e).__name__)
            return []

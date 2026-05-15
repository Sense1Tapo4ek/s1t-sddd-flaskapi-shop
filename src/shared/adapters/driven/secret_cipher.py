from dataclasses import dataclass

from cryptography.fernet import Fernet, InvalidToken

from shared.generics.errors import DrivenAdapterError


class SecretCipherKeyMissingError(DrivenAdapterError):
    def __init__(self) -> None:
        super().__init__(
            message=(
                "STORAGE_SECRETS_KEY не настроен. "
                "Сгенерируйте ключ командой `python -c 'from cryptography.fernet import Fernet; "
                "print(Fernet.generate_key().decode())'` и задайте его в переменных окружения."
            ),
            code="STORAGE_SECRETS_KEY_MISSING",
        )


class SecretCipherDecryptError(DrivenAdapterError):
    def __init__(self) -> None:
        super().__init__(
            message=(
                "Не удалось расшифровать сохранённый секрет. "
                "Возможно, изменился STORAGE_SECRETS_KEY или значение повреждено. "
                "Введите секрет заново через панель администратора."
            ),
            code="STORAGE_SECRET_DECRYPT_FAILED",
        )


@dataclass(frozen=True, slots=True, kw_only=True)
class SecretCipher:
    """Symmetric Fernet wrapper for at-rest encryption of small secrets."""

    _key: str

    def _fernet(self) -> Fernet:
        if not self._key:
            raise SecretCipherKeyMissingError()
        try:
            return Fernet(self._key.encode("utf-8"))
        except (ValueError, TypeError) as exc:
            raise SecretCipherKeyMissingError() from exc

    def encrypt(self, plaintext: str) -> str:
        if not plaintext:
            return ""
        token = self._fernet().encrypt(plaintext.encode("utf-8"))
        return token.decode("utf-8")

    def decrypt(self, token: str) -> str:
        if not token:
            return ""
        try:
            return self._fernet().decrypt(token.encode("utf-8")).decode("utf-8")
        except InvalidToken as exc:
            raise SecretCipherDecryptError() from exc

import os

from shared.generics.errors import ApplicationError


ALLOWED_EXTENSIONS: frozenset[str] = frozenset(
    {".jpg", ".jpeg", ".png", ".webp", ".gif"}
)
MAX_FILE_SIZE: int = 10 * 1024 * 1024  # 10 MB


def normalized_extension(filename: str) -> str:
    """Return lowercase file extension with leading dot, defaults to '.jpg'."""
    return os.path.splitext(filename)[1].lower() or ".jpg"


def validate_media_upload(filename: str, data: bytes) -> str:
    """
    Enforce extension whitelist and size cap shared by all storage backends.

    Returns the normalized extension on success, raises ApplicationError otherwise.
    """
    ext = normalized_extension(filename)
    if ext not in ALLOWED_EXTENSIONS:
        allowed = ", ".join(sorted(ALLOWED_EXTENSIONS))
        raise ApplicationError(
            f"Недопустимый формат файла: {ext}. Разрешены: {allowed}",
            code="MEDIA_EXT_INVALID",
        )
    if len(data) > MAX_FILE_SIZE:
        raise ApplicationError(
            f"Файл слишком большой ({len(data) // 1024 // 1024} МБ). "
            f"Максимум: {MAX_FILE_SIZE // 1024 // 1024} МБ",
            code="MEDIA_TOO_LARGE",
        )
    return ext

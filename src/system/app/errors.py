from shared.generics.errors import ApplicationError


class S3ConnectionError(ApplicationError):
    """Infrastructure-side failure when reaching the configured S3 bucket."""

    def __init__(self, detail: str) -> None:
        super().__init__(
            message=f"Не удалось подключиться к S3: {detail}",
            code="S3_CONNECTION_FAILED",
        )

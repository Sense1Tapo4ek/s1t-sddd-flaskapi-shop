from shared.generics.errors import DomainError


class SnapshotNotFoundError(DomainError):
    def __init__(self, name: str) -> None:
        self.name = name
        super().__init__(
            message=f"Снапшот не найден: {name}",
            code="SNAPSHOT_NOT_FOUND",
        )


class SnapshotNameInvalidError(DomainError):
    def __init__(self, name: str, reason: str) -> None:
        self.name = name
        self.reason = reason
        super().__init__(
            message=f"Недопустимое имя снапшота '{name}': {reason}",
            code="SNAPSHOT_NAME_INVALID",
        )


class InsufficientDiskSpaceError(DomainError):
    def __init__(self, required_bytes: int, available_bytes: int) -> None:
        self.required_bytes = required_bytes
        self.available_bytes = available_bytes
        super().__init__(
            message=(
                f"Недостаточно места на диске: требуется {required_bytes} байт, "
                f"доступно {available_bytes} байт"
            ),
            code="INSUFFICIENT_DISK_SPACE",
        )


class SnapshotMissingAfterDumpError(DomainError):
    def __init__(self, name: str) -> None:
        self.name = name
        super().__init__(
            message=f"Снапшот не найден после создания дампа: {name}",
            code="SNAPSHOT_MISSING_AFTER_DUMP",
        )

from shared.generics.errors import DomainError


class InquiryCreationError(DomainError):
    def __init__(self, reason: str) -> None:
        super().__init__(
            message=f"Невозможно создать обращение: {reason}", code="INQUIRY_CREATION_FAILED"
        )


class InvalidInquiryTransitionError(DomainError):
    def __init__(self, message: str, code: str = "INVALID_TRANSITION") -> None:
        super().__init__(message=message, code=code)

    @classmethod
    def for_transition(cls, current: str, target: str) -> "InvalidInquiryTransitionError":
        return cls(f"Невозможно перевести обращение из статуса «{current}» в «{target}»")


class IllegalInquiryTransitionError(InvalidInquiryTransitionError):
    def __init__(self, current: str, target: str) -> None:
        super().__init__(
            message=f"Недопустимый переход обращения из «{current}» в «{target}»",
            code="illegal_transition",
        )


class InquiryAlreadyTerminalError(InvalidInquiryTransitionError):
    def __init__(self, current: str, target: str) -> None:
        super().__init__(
            message=f"Обращение в финальном статусе «{current}»; переход в «{target}» невозможен",
            code="inquiry_already_terminal",
        )

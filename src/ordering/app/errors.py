from shared.generics.errors import ApplicationError


class InquiryNotFoundError(ApplicationError):
    def __init__(self, inquiry_id: int) -> None:
        super().__init__(message=f"Обращение {inquiry_id} не найдено", code="INQUIRY_NOT_FOUND")

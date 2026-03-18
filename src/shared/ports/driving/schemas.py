from pydantic import BaseModel, ConfigDict


class SuccessResponse(BaseModel):
    model_config = ConfigDict(frozen=True)
    success: bool = True


class ErrorResponse(BaseModel):
    model_config = ConfigDict(frozen=True)
    error: str
    message: str | None = None

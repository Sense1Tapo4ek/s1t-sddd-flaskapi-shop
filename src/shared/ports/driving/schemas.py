from pydantic import BaseModel, ConfigDict, Field


class SuccessResponse(BaseModel):
    model_config = ConfigDict(frozen=True)
    success: bool = True


class CreatedIdResponse(BaseModel):
    model_config = ConfigDict(frozen=True)
    success: bool = True
    id: int = Field(..., description="Идентификатор созданной сущности.")

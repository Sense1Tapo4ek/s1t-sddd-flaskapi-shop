from pydantic import BaseModel, ConfigDict


class SuccessResponse(BaseModel):
    model_config = ConfigDict(frozen=True)
    success: bool = True

from pydantic import BaseModel
from typing import Any, Optional


class SuccessResponse(BaseModel):
    success: bool = True
    data: Any
    message: Optional[str] = None


class ErrorResponse(BaseModel):
    success: bool = False
    error: str
    detail: Optional[str] = None

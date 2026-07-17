"""少量跨 API 复用的响应结构。"""

from typing import Any

from pydantic import BaseModel, Field


class MessageResponse(BaseModel):
    message: str


class ErrorResponse(BaseModel):
    code: str
    message: str
    details: dict[str, Any] | None = Field(default=None)

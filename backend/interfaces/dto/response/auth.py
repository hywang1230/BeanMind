"""认证相关的响应 DTO

定义认证 API 的响应数据结构。
"""
from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime


class UserResponse(BaseModel):
    """
    用户信息响应
    """
    id: str = Field(..., description="用户 ID")
    username: str = Field(..., description="用户名")
    display_name: Optional[str] = Field(None, description="显示名称")
    created_at: Optional[str] = Field(None, description="创建时间")
    updated_at: Optional[str] = Field(None, description="更新时间")
    
    class Config:
        json_schema_extra = {
            "example": {
                "id": "uuid",
                "username": "admin",
                "display_name": "管理员",
                "created_at": "2025-01-01T00:00:00Z",
                "updated_at": "2025-01-01T00:00:00Z"
            }
        }


class LoginResponse(BaseModel):
    """
    登录响应
    
    包含访问令牌和用户信息。
    """
    access_token: str = Field(..., description="访问令牌")
    token_type: str = Field(default="Bearer", description="令牌类型")
    expires_in: int = Field(..., description="过期时间（秒）")
    user: dict = Field(..., description="用户信息")
    
    class Config:
        json_schema_extra = {
            "example": {
                "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
                "token_type": "Bearer",
                "expires_in": 86400,
                "user": {
                    "id": "uuid",
                    "username": "admin",
                    "display_name": "管理员"
                }
            }
        }


class RefreshTokenResponse(BaseModel):
    """
    刷新 Token 响应
    
    结构与登录响应相同。
    """
    access_token: str = Field(..., description="新的访问令牌")
    token_type: str = Field(default="Bearer", description="令牌类型")
    expires_in: int = Field(..., description="过期时间（秒）")
    user: dict = Field(..., description="用户信息")
    
    class Config:
        json_schema_extra = {
            "example": {
                "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
                "token_type": "Bearer",
                "expires_in": 86400,
                "user": {
                    "id": "uuid",
                    "username": "admin",
                    "display_name": "管理员"
                }
            }
        }


class MessageResponse(BaseModel):
    """
    通用消息响应
    """
    message: str = Field(..., description="消息内容")
    
    class Config:
        json_schema_extra = {
            "example": {
                "message": "操作成功"
            }
        }


class ErrorResponse(BaseModel):
    """
    错误响应
    """
    detail: str = Field(..., description="错误详情")
    
    class Config:
        json_schema_extra = {
            "example": {
                "detail": "用户名或密码错误"
            }
        }

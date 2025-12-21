"""认证相关的请求 DTO

定义认证 API 的请求数据结构。
使用 Pydantic 进行数据验证。
"""
from pydantic import BaseModel, Field
from typing import Optional


class LoginRequest(BaseModel):
    """
    登录请求
    
    Example:
        {
            "username": "admin",
            "password": "password123"
        }
    """
    username: str = Field(..., min_length=3, max_length=50, description="用户名")
    password: Optional[str] = Field(None, min_length=1, description="密码（在 none 模式下可选）")
    
    class Config:
        json_schema_extra = {
            "example": {
                "username": "admin",
                "password": "password123"
            }
        }


class RefreshTokenRequest(BaseModel):
    """
    刷新 Token 请求
    
    Note:
        也可以通过 Authorization Header 传递，此 DTO 用于请求体方式
    """
    token: Optional[str] = Field(None, description="要刷新的旧 Token（可选，优先使用 Header）")
    
    class Config:
        json_schema_extra = {
            "example": {
                "token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
            }
        }


class UpdateProfileRequest(BaseModel):
    """
    更新用户资料请求
    """
    display_name: Optional[str] = Field(None, max_length=100, description="显示名称")
    
    class Config:
        json_schema_extra = {
            "example": {
                "display_name": "新的显示名称"
            }
        }


class ChangePasswordRequest(BaseModel):
    """
    修改密码请求
    """
    old_password: str = Field(..., min_length=1, description="旧密码")
    new_password: str = Field(..., min_length=6, description="新密码（至少6个字符）")
    
    class Config:
        json_schema_extra = {
            "example": {
                "old_password": "old_password",
                "new_password": "new_password"
            }
        }

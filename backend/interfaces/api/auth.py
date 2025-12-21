"""认证 API 端点

提供用户认证相关的 HTTP 接口。
"""
from fastapi import APIRouter, Depends, HTTPException, status, Header
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from typing import Optional

from backend.config import get_db
from backend.application.services import AuthApplicationService
from backend.infrastructure.persistence.db.repositories import UserRepositoryImpl
from backend.interfaces.dto.request.auth import (
    LoginRequest,
    RefreshTokenRequest,
    UpdateProfileRequest,
    ChangePasswordRequest
)
from backend.interfaces.dto.response.auth import (
    LoginResponse,
    RefreshTokenResponse,
    UserResponse,
    MessageResponse,
    ErrorResponse
)


# 创建路由
router = APIRouter(prefix="/api/auth", tags=["认证"])

# HTTP Bearer 认证
security = HTTPBearer()


def get_auth_service(db=Depends(get_db)) -> AuthApplicationService:
    """
    获取认证应用服务
    
    依赖注入工厂函数。
    """
    user_repo = UserRepositoryImpl(db)
    return AuthApplicationService(user_repo)


def get_current_user_id(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    auth_service: AuthApplicationService = Depends(get_auth_service)
) -> str:
    """
    从 Token 获取当前用户 ID
    
    用于需要认证的端点。
    """
    token = credentials.credentials
    user_info = auth_service.get_current_user(token)
    
    if not user_info:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="无效的认证凭据",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    return user_info["id"]


@router.post(
    "/login",
    response_model=LoginResponse,
    summary="用户登录",
    description="使用用户名和密码登录，返回访问令牌",
    responses={
        200: {"description": "登录成功", "model": LoginResponse},
        401: {"description": "用户名或密码错误", "model": ErrorResponse},
    }
)
def login(
    request: LoginRequest,
    auth_service: AuthApplicationService = Depends(get_auth_service)
):
    """
    用户登录
    
    根据配置的鉴权模式进行认证：
    - none: 无需密码
    - single_user: 验证配置的用户名密码
    - multi_user: 验证数据库中的用户
    """
    result = auth_service.login(request.username, request.password)
    
    if not result:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="用户名或密码错误"
        )
    
    return result


@router.post(
    "/refresh",
    response_model=RefreshTokenResponse,
    summary="刷新访问令牌",
    description="使用旧令牌刷新并获取新的访问令牌",
    responses={
        200: {"description": "刷新成功", "model": RefreshTokenResponse},
        401: {"description": "令牌无效或已过期", "model": ErrorResponse},
    }
)
def refresh_token(
    request: Optional[RefreshTokenRequest] = None,
    authorization: Optional[str] = Header(None),
    auth_service: AuthApplicationService = Depends(get_auth_service)
):
    """
    刷新访问令牌
    
    可以通过以下两种方式提供令牌：
    1. Authorization Header: Bearer <token>
    2. 请求体: {"token": "<token>"}
    """
    # 优先使用 Header 中的 Token
    token = None
    if authorization and authorization.startswith("Bearer "):
        token = authorization[7:]
    elif request and request.token:
        token = request.token
    
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="未提供认证令牌"
        )
    
    result = auth_service.refresh_token(token)
    
    if not result:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="令牌无效或已过期"
        )
    
    return result


@router.get(
    "/me",
    response_model=UserResponse,
    summary="获取当前用户信息",
    description="根据访问令牌获取当前登录用户的信息",
    responses={
        200: {"description": "获取成功", "model": UserResponse},
        401: {"description": "未认证或令牌无效", "model": ErrorResponse},
    }
)
def get_current_user(
    user_id: str = Depends(get_current_user_id),
    auth_service: AuthApplicationService = Depends(get_auth_service)
):
    """
    获取当前用户信息
    
    需要在 Header 中提供有效的访问令牌：
    Authorization: Bearer <token>
    """
    user_info = auth_service.get_user_by_id(user_id)
    
    if not user_info:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="用户不存在"
        )
    
    return user_info


@router.put(
    "/profile",
    response_model=UserResponse,
    summary="更新用户资料",
    description="更新当前用户的资料信息",
    responses={
        200: {"description": "更新成功", "model": UserResponse},
        401: {"description": "未认证", "model": ErrorResponse},
    }
)
def update_profile(
    request: UpdateProfileRequest,
    user_id: str = Depends(get_current_user_id),
    auth_service: AuthApplicationService = Depends(get_auth_service)
):
    """
    更新用户资料
    
    当前仅支持更新显示名称。
    """
    result = auth_service.update_user_profile(
        user_id,
        display_name=request.display_name
    )
    
    if not result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="用户不存在"
        )
    
    return result


@router.post(
    "/change-password",
    response_model=MessageResponse,
    summary="修改密码",
    description="修改当前用户的密码",
    responses={
        200: {"description": "修改成功", "model": MessageResponse},
        400: {"description": "旧密码错误", "model": ErrorResponse},
        401: {"description": "未认证", "model": ErrorResponse},
    }
)
def change_password(
    request: ChangePasswordRequest,
    user_id: str = Depends(get_current_user_id),
    auth_service: AuthApplicationService = Depends(get_auth_service)
):
    """
    修改密码
    
    需要提供旧密码进行验证。
    """
    success = auth_service.change_password(
        user_id,
        request.old_password,
        request.new_password
    )
    
    if not success:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="旧密码错误或用户不存在"
        )
    
    return {"message": "密码修改成功"}


@router.get(
    "/config",
    summary="获取认证配置",
    description="获取当前的认证模式配置",
    responses={
        200: {"description": "获取成功"},
    }
)
def get_auth_config(
    auth_service: AuthApplicationService = Depends(get_auth_service)
):
    """
    获取认证配置
    
    返回当前的鉴权模式（none/single_user/multi_user）。
    """
    return {
        "auth_mode": auth_service.get_auth_mode()
    }

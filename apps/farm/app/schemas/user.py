"""
用户模块 DTO —— 注册 / 登录 / 用户信息 / 改密码
"""
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field, field_validator


# ============================================================
# 请求体
# ============================================================
class UserRegister(BaseModel):
    """用户注册请求"""
    username: str = Field(..., min_length=3, max_length=32, description="用户名")
    password: str = Field(..., min_length=6, max_length=64, description="密码")

    @field_validator("username")
    @classmethod
    def validate_username(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("用户名不能为空")
        # 仅允许字母、数字、下划线
        import re
        if not re.match(r"^[a-zA-Z0-9_]+$", v):
            raise ValueError("用户名只能包含字母、数字和下划线")
        return v


class UserLogin(BaseModel):
    """用户登录请求"""
    username: str = Field(..., description="用户名")
    password: str = Field(..., description="密码")


class PasswordChange(BaseModel):
    """修改密码请求"""
    old_password: str = Field(..., description="原密码")
    new_password: str = Field(..., min_length=6, max_length=64, description="新密码")


# ============================================================
# 响应体
# ============================================================
class UserLoginResponse(BaseModel):
    """登录成功响应 —— 返回 JWT"""
    access_token: str
    token_type: str = "bearer"
    expires_minutes: int


class UserInfoResponse(BaseModel):
    """个人信息响应"""
    id: int
    username: str
    gold: int
    level: int
    cell_count: int
    role: str
    is_banned: bool
    created_at: datetime

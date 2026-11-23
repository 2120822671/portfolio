"""
认证路由 —— 注册 / 登录 / 获取个人信息 / 改密码

路径前缀: /api/v1/auth
"""
from __future__ import annotations

from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.dependencies import get_current_user
from app.models.farm import FarmCell
from app.models.user import User
from app.schemas.common import MessageResponse
from app.schemas.user import (
    PasswordChange,
    UserInfoResponse,
    UserLogin,
    UserLoginResponse,
    UserRegister,
)
from app.services.daily_tasks import ensure_daily_tasks
from app.utils.security import create_access_token, hash_password, verify_password


router = APIRouter(prefix="/auth", tags=["认证"])


# ============================================================
# POST /auth/register  —— 用户注册
# ============================================================
@router.post(
    "/register",
    status_code=status.HTTP_201_CREATED,
    response_model=MessageResponse,
    summary="用户注册",
    description="注册新账号，自动获得初始金币 100 + 初始 3 块空地。相同用户名返回 400。",
)
async def register(
    body: UserRegister,
    db: AsyncSession = Depends(get_db),
) -> MessageResponse:
    # 1. 检查用户名是否已被占用
    result = await db.execute(
        select(User).where(User.username == body.username)
    )
    if result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"用户名 '{body.username}' 已被占用",
        )

    # 2. 创建用户
    user = User(
        username=body.username,
        password_hash=hash_password(body.password),
        gold=settings.INITIAL_GOLD,
        level=1,
        cell_count=settings.INITIAL_CELL_COUNT,
        role="player",
        is_banned=0,
    )
    db.add(user)
    await db.flush()  # 拿到 user.id

    # 3. 同时为用户创建 INITIAL_CELL_COUNT 个空地格子
    for i in range(settings.INITIAL_CELL_COUNT):
        db.add(FarmCell(
            user_id=user.id,
            cell_index=i,
            status="empty",
        ))

    await db.commit()

    return MessageResponse(
        message=f"注册成功 🎉 欢迎来到像素农场！已赠送 {settings.INITIAL_GOLD} 金币。",
        code=201,
    )


# ============================================================
# POST /auth/login  —— 用户登录
# ============================================================
@router.post(
    "/login",
    response_model=UserLoginResponse,
    summary="用户登录",
    description="验证账号密码，返回 JWT Access Token。被封禁账号返回 403。",
)
async def login(
    body: UserLogin,
    db: AsyncSession = Depends(get_db),
) -> UserLoginResponse:
    # 1. 查询用户
    result = await db.execute(
        select(User).where(User.username == body.username)
    )
    user: Optional[User] = result.scalar_one_or_none()

    if user is None or not verify_password(body.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="用户名或密码错误",
        )

    # 2. 封禁检查
    if user.is_banned:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="账号已被封禁，请联系管理员",
        )

    # 3. 签发 JWT
    token = create_access_token(
        subject=user.id,
        extra_data={"role": user.role},
    )

    # 4. 确保今日任务记录存在（签到任务自动记为完成）
    #    真正发金币在 POST /tasks/claim/login，由前端进入游戏时自动触发一次
    await ensure_daily_tasks(db, user.id, today=date.today())
    await db.commit()

    return UserLoginResponse(
        access_token=token,
        token_type="bearer",
        expires_minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES,
    )


# ============================================================
# GET /auth/me  —— 获取当前用户信息
# ============================================================
@router.get(
    "/me",
    response_model=UserInfoResponse,
    summary="获取个人信息",
    description="需要登录。返回当前用户的金币、等级、格子数等。",
)
async def get_me(
    user_id: int = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> UserInfoResponse:
    result = await db.execute(select(User).where(User.id == user_id))
    user: Optional[User] = result.scalar_one_or_none()

    if user is None:
        raise HTTPException(status_code=404, detail="用户不存在")

    if user.is_banned:
        raise HTTPException(status_code=403, detail="账号已被封禁")

    return UserInfoResponse(
        id=user.id,
        username=user.username,
        gold=user.gold,
        level=user.level,
        cell_count=user.cell_count,
        role=user.role,
        is_banned=bool(user.is_banned),
        created_at=user.created_at,
    )


# ============================================================
# PUT /auth/password  —— 修改密码
# ============================================================
@router.put(
    "/password",
    response_model=MessageResponse,
    summary="修改密码",
    description="需要登录。验证原密码后更新为新密码。",
)
async def change_password(
    body: PasswordChange,
    user_id: int = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> MessageResponse:
    result = await db.execute(select(User).where(User.id == user_id))
    user: Optional[User] = result.scalar_one_or_none()

    if user is None:
        raise HTTPException(status_code=404, detail="用户不存在")

    if not verify_password(body.old_password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="原密码错误",
        )

    user.password_hash = hash_password(body.new_password)
    await db.commit()

    return MessageResponse(message="密码修改成功 ✅")

"""
依赖注入模块 —— 封装 FastAPI 常用的 Depends() 工厂函数
"""
from __future__ import annotations

from typing import Optional

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.utils.security import decode_access_token


# ---------- 角色常量 ----------
class Role:
    PLAYER = "player"
    ADMIN = "admin"


async def get_current_user(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> int:
    """
    获取当前登录玩家的 user_id（依赖注入）。

    自动从请求头 Authorization: Bearer <token> 中提取并验证 JWT。
    未登录或 Token 无效时返回 401。

    使用示例:
        @app.get("/farm/")
        async def get_farm(user_id: int = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
            ...
    """
    auth_header: Optional[str] = request.headers.get("Authorization")

    if not auth_header or not auth_header.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="未登录或 Token 缺失",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token: str = auth_header.split(" ", 1)[1].strip()

    try:
        payload: dict = decode_access_token(token)
        user_id: Optional[int] = payload.get("sub")
        if user_id is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token 无效",
            )
        return int(user_id)
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token 验证失败",
        )


async def get_admin_user(
    request: Request,
    db: AsyncSession = Depends(get_db),
    user_id: int = Depends(get_current_user),
) -> int:
    """
    管理员权限校验依赖。在 get_current_user 基础上额外检查 role=admin。
    无权限时返回 403。
    """
    # 延迟 import 避免循环依赖
    from sqlalchemy import select
    from app.models.user import User

    result = await db.execute(select(User).where(User.id == user_id))
    user: Optional[User] = result.scalar_one_or_none()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="用户不存在",
        )

    if user.role != Role.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="需要管理员权限",
        )

    if user.is_banned:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="账号已被封禁",
        )

    return user_id


async def check_not_banned(
    db: AsyncSession = Depends(get_db),
    user_id: int = Depends(get_current_user),
) -> int:
    """
    通用检查：确保账号未被封禁。
    路由中可按需添加此依赖。
    """
    from sqlalchemy import select
    from app.models.user import User

    result = await db.execute(select(User).where(User.id == user_id))
    user: Optional[User] = result.scalar_one_or_none()

    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")
    if user.is_banned:
        raise HTTPException(status_code=403, detail="账号已被封禁，无法游戏")

    return user_id

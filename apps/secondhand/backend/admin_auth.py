"""增量新增：管理员权限依赖，独立于 auth.py / goods._require_user。

身份来自 main.py 签名令牌中间件写入的可信 X-User-Id，不接受客户端自报值。
角色存放于新增的 admin_role 表，不改动 User 模型。
"""
from fastapi import Depends, Header, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from async_database import get_async_db
from models import AdminRole

ADMIN_ROLES = ("admin", "super_admin")


async def require_admin(
    x_user_id: int | None = Header(None),
    db: AsyncSession = Depends(get_async_db),
) -> int:
    """管理员权限依赖：未登录返回 401，非管理员返回 403，合法时返回 uid。"""
    if not x_user_id:
        raise HTTPException(status_code=401, detail="请先登录")

    role = await db.scalar(
        select(AdminRole.role).where(
            AdminRole.user_id == x_user_id,
            AdminRole.role.in_(ADMIN_ROLES),
        )
    )
    if not role:
        raise HTTPException(status_code=403, detail="无权限访问：仅管理员可查看统计看板")
    return x_user_id

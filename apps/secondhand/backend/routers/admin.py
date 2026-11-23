"""管理后台：统计看板（增量新增，不改动任何原有业务接口）"""
from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from admin_auth import require_admin
from async_database import get_async_db
from models import Goods, Order, User
from resp import ok
from schemas import AdminDashboardData

router = APIRouter(prefix="/api/v1/admin", tags=["管理后台"])


@router.get(
    "/dashboard",
    summary="管理员统计看板",
    description="仅管理员/超级管理员可访问，返回四项统计指标（统一响应 {code,msg,data}）。",
)
async def dashboard(
    db: AsyncSession = Depends(get_async_db),
    _admin_uid: int = Depends(require_admin),
):
    """管理员统计看板：GET /api/v1/admin/dashboard

    权限：仅 admin / super_admin 角色可调用，普通用户由 require_admin 返回 403。
    指标口径：
      1. today_new_users —— 今日新增注册用户数（user.created_at >= CURDATE()）；
      2. today_new_goods —— 今日新增发布商品数（goods.created_at >= CURDATE()）；
      3. today_orders —— 今日产生订单总数（orders.created_at >= CURDATE()）；
      4. pending_goods —— 待审核商品总数（goods.status = 1，本工程语义为“在售”，按需求字面统计）。
    时间统一用 SQL 侧 CURDATE()，避免应用服务器与数据库时钟漂移。
    """
    today = func.current_date()

    today_new_users = await db.scalar(select(func.count(User.id)).where(User.created_at >= today))
    today_new_goods = await db.scalar(select(func.count(Goods.id)).where(Goods.created_at >= today))
    today_orders = await db.scalar(select(func.count(Order.id)).where(Order.created_at >= today))
    pending_goods = await db.scalar(select(func.count(Goods.id)).where(Goods.status == 1))

    data = AdminDashboardData(
        today_new_users=today_new_users or 0,
        today_new_goods=today_new_goods or 0,
        today_orders=today_orders or 0,
        pending_goods=pending_goods or 0,
    )
    return ok(data.model_dump(), "统计看板获取成功")

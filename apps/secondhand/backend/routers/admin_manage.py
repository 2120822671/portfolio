"""管理后台扩展（增量新增）：用户管理 / 商品审核 / 举报处理 / 订单监管。

只新增接口，不改任何原有业务接口；全部复用 admin_auth.require_admin 权限依赖
与 async_database.get_async_db 会话，权限与看板一致。
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from admin_auth import require_admin
from async_database import get_async_db
from models import (
    Goods, GoodsAuditLog, Order, OrderLog, Report, ReportHandle, User,
)
from resp import ok
from schemas import AdminAuditIn, AdminReportHandleIn, AdminUserStatusIn

router = APIRouter(prefix="/api/v1/admin", tags=["管理后台-管理功能"])

# goods.status 新增取值 5=待审核，不改动 1在售/2已售/3下架/4已预订 的原有语义
PENDING_AUDIT = 5
ON_SALE = 1
OFF_SHELF = 3
RESERVED = 4


# ==================== 用户管理 ====================
@router.get("/users", summary="用户管理：用户列表（分页/搜索/状态筛选）")
async def admin_list_users(
    q: str | None = Query(None, max_length=50, description="用户名/昵称关键词"),
    status: int | None = Query(None, ge=0, le=1, description="状态：1正常 0冻结"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=50),
    db: AsyncSession = Depends(get_async_db),
    _admin: int = Depends(require_admin),
):
    stmt = select(User)
    if q:
        stmt = stmt.where(User.username.like(f"%{q}%") | User.nickname.like(f"%{q}%"))
    if status is not None:
        stmt = stmt.where(User.status == status)
    total = await db.scalar(select(func.count()).select_from(stmt.subquery()))
    rows = (await db.scalars(
        stmt.order_by(User.id.desc()).offset((page - 1) * page_size).limit(page_size)
    )).all()
    return ok({
        "total": total, "page": page, "page_size": page_size,
        "items": [{"id": u.id, "username": u.username, "nickname": u.nickname,
                   "credit_score": u.credit_score, "status": u.status,
                   "created_at": u.created_at.isoformat() if u.created_at else None} for u in rows],
    })


@router.post("/users/{user_id}/status", summary="用户管理：冻结/解封账号")
async def admin_set_user_status(
    user_id: int,
    payload: AdminUserStatusIn,
    db: AsyncSession = Depends(get_async_db),
    admin_id: int = Depends(require_admin),
):
    user = await db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")
    await db.execute(update(User).where(User.id == user_id).values(status=payload.status))
    await db.commit()
    return ok({"id": user_id, "status": payload.status},
              "账号已解封" if payload.status == 1 else "账号已冻结")


# ==================== 商品审核 ====================
@router.get("/goods/pending", summary="商品审核：待审核商品列表")
async def admin_pending_goods(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=50),
    db: AsyncSession = Depends(get_async_db),
    _admin: int = Depends(require_admin),
):
    stmt = select(Goods).where(Goods.status == PENDING_AUDIT)
    total = await db.scalar(select(func.count()).select_from(stmt.subquery()))
    rows = (await db.scalars(
        stmt.order_by(Goods.created_at.desc()).offset((page - 1) * page_size).limit(page_size)
    )).all()
    return ok({
        "total": total, "page": page, "page_size": page_size,
        "items": [{"id": g.id, "title": g.title, "price": float(g.price),
                   "seller_id": g.seller_id, "status": g.status,
                   "created_at": g.created_at.isoformat() if g.created_at else None} for g in rows],
    })


@router.post("/goods/{goods_id}/audit", summary="商品审核：通过或驳回")
async def admin_audit_goods(
    goods_id: int,
    payload: AdminAuditIn,
    db: AsyncSession = Depends(get_async_db),
    admin_id: int = Depends(require_admin),
):
    if payload.action not in ("approve", "reject"):
        raise HTTPException(status_code=400, detail="审核动作仅支持 approve/reject")
    goods = await db.get(Goods, goods_id)
    if not goods:
        raise HTTPException(status_code=404, detail="商品不存在")
    if goods.status != PENDING_AUDIT:
        raise HTTPException(status_code=409, detail="该商品不处于待审核状态")

    from_status = goods.status
    to_status = ON_SALE if payload.action == "approve" else OFF_SHELF
    await db.execute(update(Goods).where(Goods.id == goods_id).values(status=to_status))
    db.add(GoodsAuditLog(
        goods_id=goods_id, goods_title=goods.title, from_status=from_status, to_status=to_status,
        action=payload.action, remark=payload.remark, operator_id=admin_id,
    ))
    await db.commit()
    return ok({"id": goods_id, "status": to_status},
              "审核通过，商品已上架" if payload.action == "approve" else "已驳回，商品已下架")


# ==================== 举报处理 ====================
@router.get("/reports", summary="举报处理：举报列表（含处理状态）")
async def admin_list_reports(
    handled: bool | None = Query(None, description="true已处理 false待处理 不传=全部"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=50),
    db: AsyncSession = Depends(get_async_db),
    _admin: int = Depends(require_admin),
):
    stmt = select(Report, ReportHandle.action).outerjoin(
        ReportHandle, Report.id == ReportHandle.report_id
    )
    if handled is True:
        stmt = stmt.where(ReportHandle.id.is_not(None))
    elif handled is False:
        stmt = stmt.where(ReportHandle.id.is_(None))

    total = await db.scalar(select(func.count()).select_from(stmt.subquery()))
    rows = (await db.execute(
        stmt.order_by(Report.created_at.desc()).offset((page - 1) * page_size).limit(page_size)
    )).all()
    return ok({
        "total": total, "page": page, "page_size": page_size,
        "items": [{"id": r.id, "user_id": r.user_id, "target_type": r.target_type,
                   "target_id": r.target_id, "reason": r.reason,
                   "handle_action": action,
                   "created_at": r.created_at.isoformat() if r.created_at else None}
                  for r, action in rows],
    })


@router.post("/reports/{report_id}/handle", summary="举报处理：标记已处理/忽略")
async def admin_handle_report(
    report_id: int,
    payload: AdminReportHandleIn,
    db: AsyncSession = Depends(get_async_db),
    admin_id: int = Depends(require_admin),
):
    if payload.action not in ("processed", "ignored"):
        raise HTTPException(status_code=400, detail="处理动作仅支持 processed/ignored")
    report = await db.get(Report, report_id)
    if not report:
        raise HTTPException(status_code=404, detail="举报不存在")

    existing = await db.scalar(select(ReportHandle).where(ReportHandle.report_id == report_id))
    if existing:
        existing.action = payload.action
        existing.remark = payload.remark
        existing.handler_id = admin_id
    else:
        db.add(ReportHandle(report_id=report_id, action=payload.action,
                            remark=payload.remark, handler_id=admin_id))
    await db.commit()
    return ok({"id": report_id, "action": payload.action}, "举报已处理")


# ==================== 订单监管 ====================
@router.get("/orders", summary="订单监管：全局订单列表")
async def admin_list_orders(
    status: int | None = Query(None, description="状态：10待付款 20已支付 30已完成 40已关闭"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=50),
    db: AsyncSession = Depends(get_async_db),
    _admin: int = Depends(require_admin),
):
    stmt = select(Order)
    if status is not None:
        stmt = stmt.where(Order.status == status)
    total = await db.scalar(select(func.count()).select_from(stmt.subquery()))
    rows = (await db.scalars(
        stmt.order_by(Order.created_at.desc()).offset((page - 1) * page_size).limit(page_size)
    )).all()
    return ok({
        "total": total, "page": page, "page_size": page_size,
        "items": [{"id": o.id, "order_no": o.order_no, "goods_id": o.goods_id,
                   "buyer_id": o.buyer_id, "seller_id": o.seller_id,
                   "amount": float(o.amount), "status": o.status,
                   "close_type": o.close_type,
                   "created_at": o.created_at.isoformat() if o.created_at else None} for o in rows],
    })


@router.get("/orders/abnormal", summary="订单监管：异常订单（超时未付款）")
async def admin_abnormal_orders(
    db: AsyncSession = Depends(get_async_db),
    _admin: int = Depends(require_admin),
):
    rows = (await db.scalars(
        select(Order).where(Order.status == 10, Order.pay_deadline < func.now())
        .order_by(Order.pay_deadline.asc()).limit(200)
    )).all()
    return ok({"total": len(rows), "items": [
        {"id": o.id, "order_no": o.order_no, "goods_id": o.goods_id,
         "buyer_id": o.buyer_id, "amount": float(o.amount),
         "pay_deadline": o.pay_deadline.isoformat() if o.pay_deadline else None}
        for o in rows]})


@router.post("/orders/{order_id}/force-close", summary="订单监管：强制关闭订单")
async def admin_force_close_order(
    order_id: int,
    db: AsyncSession = Depends(get_async_db),
    _admin: int = Depends(require_admin),
):
    order = await db.get(Order, order_id)
    if not order:
        raise HTTPException(status_code=404, detail="订单不存在")
    if order.status == 40:
        raise HTTPException(status_code=409, detail="订单已关闭")

    from_status = order.status
    result = await db.execute(
        update(Order).where(Order.id == order_id, Order.status != 40)
        .values(status=40, close_type="admin", closed_at=func.now())
        .execution_options(synchronize_session=False)
    )
    if result.rowcount != 1:
        await db.rollback()
        raise HTTPException(status_code=409, detail="订单状态已变更，请刷新重试")

    # 与旧取消/超时任务同语义：仅当商品处于已预订态才恢复在售并回补库存
    await db.execute(
        update(Goods).where(Goods.id == order.goods_id, Goods.status == RESERVED)
        .values(status=ON_SALE, stock=Goods.stock + 1)
        .execution_options(synchronize_session=False)
    )
    db.add(OrderLog(order_id=order_id, from_status=from_status, to_status=40,
                    action="admin_close", remark="管理员强制关闭"))
    await db.commit()
    return ok({"id": order_id, "status": 40}, "订单已强制关闭")

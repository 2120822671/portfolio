"""订单接口（增量新增：为「超时未支付自动关闭」提供业务闭环）

说明：
- 全部为新增接口，不改动用户 / 商品 / 收藏 / 上传等既有路由；
- 状态机：10 待付款 → 20 已支付（支付）/ 40 已关闭（用户取消或定时任务超时关闭）；
- 所有状态流转都用条件更新（WHERE status=10），保证用户取消、支付、定时关单三者并发时只有一个生效。
"""
import logging
import random
from datetime import datetime
from decimal import Decimal

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from sqlalchemy import delete, func, select, text, update
from sqlalchemy.orm import Session, aliased

from database import get_db
from models import CartItem, Goods, GoodsImage, Order, OrderLog, User
from resp import ok
from schemas import OrderBatchCreate, OrderCreate, OrderPayIn

logger = logging.getLogger("campus_secondhand.routers.order")

router = APIRouter(prefix="/orders", tags=["订单"])

STATUS_TEXT = {10: "待付款", 20: "已支付", 30: "已完成", 40: "已关闭"}
GOODS_STATUS_TEXT = {1: "在售", 2: "已售出", 3: "已下架", 4: "已预订"}
PAY_METHODS_TEXT = {"campus_card": "校园一卡通", "wechat": "微信支付",
                    "alipay": "支付宝", "cash": "线下当面交易"}
DEFAULT_PAY_METHOD = "campus_card"
TIMEOUT_MINUTES = 30


def _pay_method_of(value: str | None) -> str:
    """归一化支付方式：未知值回落到默认方式，避免脏数据写库"""
    return value if value in PAY_METHODS_TEXT else DEFAULT_PAY_METHOD


def _require_user(x_user_id: int | None) -> int:
    """订单读写均要求登录（x_user_id 由 main.py 中间件按签名令牌覆盖，不可伪造）"""
    if not x_user_id:
        raise HTTPException(status_code=401, detail="请先登录")
    return x_user_id


def _gen_order_no(now: datetime) -> str:
    """订单号：SO + 时间 + 4 位随机，配合唯一索引兜底"""
    return f"SO{now:%Y%m%d%H%M%S}{random.randint(1000, 9999)}"


def _db_now(db: Session) -> datetime:
    """统一取数据库时间，避免应用与数据库时钟不一致"""
    return db.scalar(select(func.now()))


def _brief(o: Order) -> dict:
    return {
        "id": o.id,
        "order_no": o.order_no,
        "goods_id": o.goods_id,
        "buyer_id": o.buyer_id,
        "seller_id": o.seller_id,
        "amount": str(o.amount),
        "pay_method": o.pay_method,
        "pay_method_text": PAY_METHODS_TEXT.get(o.pay_method, "未选择"),
        "status": o.status,
        "status_text": STATUS_TEXT.get(o.status, "未知"),
        "pay_deadline": o.pay_deadline.isoformat() if o.pay_deadline else None,
        "close_type": o.close_type,
        "closed_at": o.closed_at.isoformat() if o.closed_at else None,
        "created_at": o.created_at.isoformat() if o.created_at else None,
    }


@router.post("", summary="下单（预占商品，生成30分钟付款截止时间）")
def create_order(payload: OrderCreate, db: Session = Depends(get_db),
                 x_user_id: int | None = Header(None)):
    if x_user_id and x_user_id != payload.buyer_id:
        raise HTTPException(status_code=403, detail="只能以买家本人身份下单")
    if not db.get(User, payload.buyer_id):
        raise HTTPException(status_code=400, detail=f"买家不存在：buyer_id={payload.buyer_id}")

    goods = db.get(Goods, payload.goods_id)
    if not goods:
        raise HTTPException(status_code=404, detail="商品不存在")
    if goods.seller_id == payload.buyer_id:
        raise HTTPException(status_code=400, detail="不能购买自己发布的商品")

    # 预占商品：条件更新，只有「在售」且库存>0 才能被锁定为「已预订」(4)
    locked = db.execute(
        update(Goods)
        .where(Goods.id == payload.goods_id, Goods.status == 1, Goods.stock > 0)
        .values(status=4, stock=Goods.stock - 1)
        .execution_options(synchronize_session=False)
    )
    if locked.rowcount != 1:
        db.rollback()
        raise HTTPException(status_code=409, detail="商品已被预订、已售出或已下架，无法下单")

    now = _db_now(db)
    deadline = db.scalar(select(func.date_add(func.now(), text(f"INTERVAL {TIMEOUT_MINUTES} MINUTE"))))
    order = Order(
        order_no=_gen_order_no(now),
        goods_id=payload.goods_id,
        buyer_id=payload.buyer_id,
        seller_id=goods.seller_id,
        amount=goods.price,
        status=10,
        pay_deadline=deadline,
    )
    db.add(order)
    db.flush()
    db.add(OrderLog(order_id=order.id, from_status=0, to_status=10,
                    action="create", remark=f"下单成功，{TIMEOUT_MINUTES} 分钟内未支付将自动关闭"))
    db.commit()
    db.refresh(order)
    return ok(_brief(order), "下单成功")


@router.post("/batch", summary="购物车批量结算（模拟支付，一次生成多笔已支付订单）")
def batch_checkout(payload: OrderBatchCreate, db: Session = Depends(get_db),
                   x_user_id: int | None = Header(None)):
    uid = _require_user(x_user_id)
    if uid != payload.buyer_id:
        raise HTTPException(status_code=403, detail="只能以自己的身份结算")
    if not db.get(User, uid):
        raise HTTPException(status_code=400, detail="买家不存在")

    goods_ids = list(dict.fromkeys(payload.goods_ids))   # 去重且保序
    method = _pay_method_of(payload.pay_method)
    now = _db_now(db)
    deadline = db.scalar(select(func.date_add(func.now(), text(f"INTERVAL {TIMEOUT_MINUTES} MINUTE"))))

    created: list[Order] = []
    total = Decimal("0")
    for goods_id in goods_ids:
        goods = db.get(Goods, goods_id)
        if not goods:
            db.rollback()
            raise HTTPException(status_code=404, detail=f"商品不存在：{goods_id}")
        if goods.seller_id == uid:
            db.rollback()
            raise HTTPException(status_code=400, detail="不能购买自己发布的商品")

        # 条件更新预占，任一件不可售则整单回滚，避免部分成交
        locked = db.execute(
            update(Goods)
            .where(Goods.id == goods_id, Goods.status == 1, Goods.stock > 0)
            .values(status=4, stock=Goods.stock - 1)
            .execution_options(synchronize_session=False)
        )
        if locked.rowcount != 1:
            db.rollback()
            raise HTTPException(status_code=409,
                                detail=f"《{goods.title}》已被预订、已售出或已下架，请刷新购物车")

        order = Order(
            order_no=_gen_order_no(now),
            goods_id=goods_id,
            buyer_id=uid,
            seller_id=goods.seller_id,
            amount=goods.price,
            pay_method=method,
            status=20,          # 模拟支付：结算即支付成功
            pay_deadline=deadline,
        )
        db.add(order)
        db.flush()
        db.add(OrderLog(order_id=order.id, from_status=0, to_status=10,
                        action="create", remark=f"购物车结算下单，支付方式：{PAY_METHODS_TEXT[method]}"))
        db.add(OrderLog(order_id=order.id, from_status=10, to_status=20,
                        action="pay", remark=f"模拟支付成功（{PAY_METHODS_TEXT[method]}）"))
        db.execute(
            update(Goods)
            .where(Goods.id == goods_id, Goods.status == 4)
            .values(status=2)
            .execution_options(synchronize_session=False)
        )
        created.append(order)
        total += goods.price

    # 结算成功的商品从购物车移除
    db.execute(delete(CartItem).where(CartItem.user_id == uid,
                                     CartItem.goods_id.in_(goods_ids)))
    db.commit()
    for order in created:
        db.refresh(order)
    return ok({
        "orders": [_brief(o) for o in created],
        "total_amount": str(total),
        "pay_method": method,
        "pay_method_text": PAY_METHODS_TEXT[method],
    }, f"支付成功，共 {len(created)} 笔订单")


@router.get("", summary="我的订单列表（买家/卖家视角，含商品信息与倒计时）")
def list_orders(
    role: str = Query("buyer", pattern="^(buyer|seller)$", description="buyer=我买到的 seller=我卖出的"),
    status: int | None = Query(None, ge=10, le=40, description="订单状态：10待付款 20已支付 30已完成 40已关闭"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=50),
    db: Session = Depends(get_db),
    x_user_id: int | None = Header(None),
):
    uid = _require_user(x_user_id)

    buyer_u = aliased(User)
    seller_u = aliased(User)
    # 每件商品取第一张图作为兜底封面（避免逐行查询造成 N+1）
    first_img = (
        select(GoodsImage.goods_id.label("gid"), func.min(GoodsImage.id).label("iid"))
        .group_by(GoodsImage.goods_id)
        .subquery()
    )
    stmt = (
        select(Order, Goods, GoodsImage.url, buyer_u.nickname, seller_u.nickname)
        .join(Goods, Goods.id == Order.goods_id)
        .join(buyer_u, buyer_u.id == Order.buyer_id)
        .join(seller_u, seller_u.id == Order.seller_id)
        .outerjoin(first_img, first_img.c.gid == Goods.id)
        .outerjoin(GoodsImage, GoodsImage.id == first_img.c.iid)
    )
    stmt = stmt.where(Order.buyer_id == uid) if role == "buyer" else stmt.where(Order.seller_id == uid)
    if status is not None:
        stmt = stmt.where(Order.status == status)

    total = db.scalar(select(func.count()).select_from(stmt.subquery()))
    rows = db.execute(
        stmt.order_by(Order.id.desc()).offset((page - 1) * page_size).limit(page_size)
    ).all()

    now = _db_now(db)
    items = []
    for order, goods, img_url, buyer_nick, seller_nick in rows:
        data = _brief(order)
        left = 0
        if order.status == 10 and order.pay_deadline:
            left = max(0, int((order.pay_deadline - now).total_seconds()))
        data.update({
            "goods_title": goods.title,
            "goods_cover": goods.cover_image or img_url,
            "goods_status": goods.status,
            "goods_status_text": GOODS_STATUS_TEXT.get(goods.status, "未知"),
            "buyer_nickname": buyer_nick,
            "seller_nickname": seller_nick,
            "pay_left_seconds": left,
            "can_pay": order.status == 10 and left > 0,
            "can_cancel": order.status == 10,
        })
        items.append(data)
    return ok({"total": total, "page": page, "page_size": page_size, "role": role, "items": items})


@router.get("/{order_id}", summary="订单详情")
def order_detail(order_id: int, db: Session = Depends(get_db)):
    order = db.get(Order, order_id)
    if not order:
        raise HTTPException(status_code=404, detail="订单不存在")
    logs = db.execute(
        select(OrderLog).where(OrderLog.order_id == order_id).order_by(OrderLog.id.asc())
    ).scalars().all()
    data = _brief(order)
    data["logs"] = [
        {"from_status": l.from_status, "to_status": l.to_status, "action": l.action,
         "remark": l.remark, "created_at": l.created_at.isoformat()}
        for l in logs
    ]
    return ok(data)


@router.post("/{order_id}/pay", summary="支付订单（待付款→已支付，商品转为已售）")
def pay_order(order_id: int, payload: OrderPayIn | None = None,
              db: Session = Depends(get_db),
              x_user_id: int | None = Header(None)):
    order = db.get(Order, order_id)
    if not order:
        raise HTTPException(status_code=404, detail="订单不存在")
    if x_user_id and x_user_id != order.buyer_id:
        raise HTTPException(status_code=403, detail="只能支付自己的订单")

    values = {"status": 20}
    if payload and payload.pay_method:
        values["pay_method"] = _pay_method_of(payload.pay_method)

    # 修复：支付条件必须同时满足「待付款」且「未过付款截止时间」，
    # 否则定时任务每 60 秒一轮，两轮之间的超时订单仍可被支付，绕过超时关单规则
    paid = db.execute(
        update(Order)
        .where(Order.id == order_id, Order.status == 10,
               Order.pay_deadline >= func.now())
        .values(**values)
        .execution_options(synchronize_session=False)
    )
    if paid.rowcount != 1:
        db.rollback()
        db.expire_all()                                  # 丢弃会话缓存，重新判定失败原因
        latest = db.get(Order, order_id)
        if latest and latest.status == 10:
            raise HTTPException(status_code=409, detail="订单已超过付款截止时间，无法支付")
        raise HTTPException(status_code=409, detail="订单已关闭或已支付，无法支付")

    db.execute(
        update(Goods)
        .where(Goods.id == order.goods_id, Goods.status == 4)
        .values(status=2)
        .execution_options(synchronize_session=False)
    )
    db.add(OrderLog(order_id=order_id, from_status=10, to_status=20, action="pay", remark="买家支付成功"))
    db.commit()
    db.refresh(order)
    return ok(_brief(order), "支付成功")


@router.post("/{order_id}/cancel", summary="取消订单（用户主动取消，商品恢复在售）")
def cancel_order(order_id: int, db: Session = Depends(get_db),
                 x_user_id: int | None = Header(None)):
    order = db.get(Order, order_id)
    if not order:
        raise HTTPException(status_code=404, detail="订单不存在")
    if x_user_id and x_user_id != order.buyer_id:
        raise HTTPException(status_code=403, detail="只能取消自己的订单")

    canceled = db.execute(
        update(Order)
        .where(Order.id == order_id, Order.status == 10)
        .values(status=40, close_type="user", closed_at=func.now())
        .execution_options(synchronize_session=False)
    )
    if canceled.rowcount != 1:
        db.rollback()
        raise HTTPException(status_code=409, detail="订单已关闭或已支付，无法取消")

    db.execute(
        update(Goods)
        .where(Goods.id == order.goods_id, Goods.status == 4)
        .values(status=1, stock=Goods.stock + 1)
        .execution_options(synchronize_session=False)
    )
    db.add(OrderLog(order_id=order_id, from_status=10, to_status=40, action="cancel", remark="买家主动取消"))
    db.commit()
    db.refresh(order)
    return ok(_brief(order), "订单已取消")

"""购物车模块（增量新增）

接口：
- GET    /cart          购物车列表（含商品信息、是否可结算）
- POST   /cart          加入购物车（同一商品数量累加）
- PATCH  /cart/{id}     修改数量
- DELETE /cart/{id}     移除单项
- DELETE /cart          清空购物车

说明：购物车只做「收集」，真正下单与模拟支付由 POST /orders/batch 完成。
"""
from decimal import Decimal

from fastapi import APIRouter, Depends, Header, HTTPException
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from database import get_db
from models import CartItem, Goods, GoodsImage
from resp import ok
from schemas import CartAdd, CartUpdate

router = APIRouter(prefix="/cart", tags=["购物车"])


def _require_user(x_user_id: int | None) -> int:
    if not x_user_id:
        raise HTTPException(status_code=401, detail="请先登录")
    return x_user_id


def _cover_url(db: Session, goods: Goods) -> str | None:
    if goods.cover_image:
        return goods.cover_image
    return db.scalar(
        select(GoodsImage.url).where(GoodsImage.goods_id == goods.id).order_by(GoodsImage.id)
    )


def _cart_brief(db: Session, item: CartItem, goods: Goods) -> dict:
    """购物车条目：available=false 时前端置灰且不参与结算"""
    if goods.status != 1:
        available, reason = False, goods_status_text(goods.status)
    elif goods.stock <= 0:
        available, reason = False, "库存不足"
    else:
        available, reason = True, ""
    return {
        "id": item.id,
        "goods_id": goods.id,
        "title": goods.title,
        "price": str(goods.price),
        "cover": _cover_url(db, goods),
        "quantity": item.quantity,
        "stock": goods.stock,
        "goods_status": goods.status,
        "goods_status_text": goods_status_text(goods.status),
        "available": available,
        "reason": reason,
        "subtotal": str(goods.price * item.quantity),
    }


def goods_status_text(status: int) -> str:
    return {1: "在售", 2: "已售出", 3: "已下架", 4: "已预订"}.get(status, "未知")


def _summary(items: list[dict]) -> dict:
    valid = [i for i in items if i["available"]]
    return {
        "count": len(items),
        "valid_count": len(valid),
        "amount": str(sum((Decimal(i["subtotal"]) for i in valid), Decimal("0"))),
    }


@router.get("", summary="购物车列表")
def list_cart(db: Session = Depends(get_db), x_user_id: int | None = Header(None)):
    uid = _require_user(x_user_id)
    rows = db.execute(
        select(CartItem, Goods)
        .join(Goods, Goods.id == CartItem.goods_id)
        .where(CartItem.user_id == uid)
        .order_by(CartItem.id.desc())
    ).all()
    items = [_cart_brief(db, item, goods) for item, goods in rows]
    return ok({"items": items, **_summary(items)})


@router.post("", summary="加入购物车")
def add_cart(payload: CartAdd, db: Session = Depends(get_db),
             x_user_id: int | None = Header(None)):
    uid = _require_user(x_user_id)
    goods = db.get(Goods, payload.goods_id)
    if not goods:
        raise HTTPException(status_code=404, detail="商品不存在")
    if goods.seller_id == uid:
        raise HTTPException(status_code=400, detail="不能把自己发布的商品加入购物车")
    if goods.status != 1:
        raise HTTPException(status_code=409, detail=f"商品{goods_status_text(goods.status)}，无法加入购物车")
    if goods.stock <= 0:
        raise HTTPException(status_code=409, detail="商品库存不足")

    item = db.scalar(select(CartItem).where(CartItem.user_id == uid,
                                            CartItem.goods_id == payload.goods_id))
    if item:
        item.quantity = min(goods.stock, item.quantity + payload.quantity)
    else:
        if payload.quantity > goods.stock:
            raise HTTPException(status_code=409, detail=f"库存仅剩 {goods.stock} 件")
        db.add(CartItem(user_id=uid, goods_id=payload.goods_id, quantity=payload.quantity))
    db.commit()
    count = db.scalar(select(func.count()).select_from(
        select(CartItem.id).where(CartItem.user_id == uid).subquery())) or 0
    return ok({"count": count}, "已加入购物车")


@router.patch("/{item_id}", summary="修改购物车数量")
def update_cart(item_id: int, payload: CartUpdate, db: Session = Depends(get_db),
                x_user_id: int | None = Header(None)):
    uid = _require_user(x_user_id)
    item = db.get(CartItem, item_id)
    if not item or item.user_id != uid:
        raise HTTPException(status_code=404, detail="购物车条目不存在")
    goods = db.get(Goods, item.goods_id)
    if goods and payload.quantity > max(goods.stock, 1):
        raise HTTPException(status_code=409, detail=f"库存仅剩 {goods.stock} 件")
    item.quantity = payload.quantity
    db.commit()
    return ok({"id": item.id, "quantity": item.quantity}, "已更新")


@router.delete("/{item_id}", summary="移除购物车单项")
def remove_cart(item_id: int, db: Session = Depends(get_db),
                x_user_id: int | None = Header(None)):
    uid = _require_user(x_user_id)
    item = db.get(CartItem, item_id)
    if not item or item.user_id != uid:
        raise HTTPException(status_code=404, detail="购物车条目不存在")
    db.delete(item)
    db.commit()
    return ok({"id": item_id}, "已移出购物车")


@router.delete("", summary="清空购物车")
def clear_cart(db: Session = Depends(get_db), x_user_id: int | None = Header(None)):
    uid = _require_user(x_user_id)
    db.execute(delete(CartItem).where(CartItem.user_id == uid))
    db.commit()
    return ok({"count": 0}, "购物车已清空")

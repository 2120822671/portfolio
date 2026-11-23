"""商品模块：列表(搜索/筛选/排序/分页)、发布、详情(浏览量防刷)、点赞、状态管理、留言、统计"""
import time
from datetime import date, datetime

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from database import get_db
from models import Category, Goods, GoodsImage, GoodsLike, GoodsMessage, User
from resp import ok
from risk import acquire_publish_quota
from schemas import GoodsCreate, MessageCreate, StatusUpdate

router = APIRouter(prefix="/goods", tags=["商品"])
stats_router = APIRouter(prefix="/stats", tags=["统计"])
category_router = APIRouter(prefix="/categories", tags=["分类"])


@category_router.get("", summary="商品分类列表（前端下拉与筛选动态渲染，避免前后端 ID 映射不一致）")
def list_categories(db: Session = Depends(get_db)):
    rows = db.scalars(select(Category).order_by(Category.sort_order, Category.id)).all()
    return ok({"items": [{"id": c.id, "name": c.name} for c in rows]})

STATUS_TEXT = {1: "在售", 2: "已售出", 3: "已下架", 4: "已预订"}

# 浏览量防刷：同一客户端(用户ID或IP)对同一商品 60 秒内只计一次
_view_cache: dict[tuple, float] = {}
VIEW_DEDUP_SECONDS = 60


def _client_key(request: Request, uid: int | None) -> tuple:
    return (uid or request.client.host, )


def _touch_view(goods: Goods, request: Request, uid: int | None) -> None:
    key = (_client_key(request, uid)[0], goods.id)
    now = time.time()
    if now - _view_cache.get(key, 0) >= VIEW_DEDUP_SECONDS:
        goods.view_count += 1
        _view_cache[key] = now


def _require_user(x_user_id: int | None) -> int:
    """简化鉴权：写操作要求携带 X-User-Id 头（由登录接口获得）"""
    if not x_user_id:
        raise HTTPException(status_code=401, detail="请先登录")
    return x_user_id


def _cover_url(db: Session, goods: Goods) -> str | None:
    if goods.cover_image:
        return goods.cover_image
    img = db.scalar(
        select(GoodsImage).where(GoodsImage.goods_id == goods.id).order_by(GoodsImage.id)
    )
    return img.url if img else None


def _brief(db: Session, g: Goods) -> dict:
    """列表用精简信息"""
    discount = None
    if g.original_price and g.original_price > 0 and g.price < g.original_price:
        discount = round(float(g.price) / float(g.original_price) * 10, 1)  # 折扣，如 8.5
    return {
        "id": g.id, "title": g.title, "price": str(g.price),
        "original_price": str(g.original_price) if g.original_price else None,
        "discount": discount,
        "category_id": g.category_id, "stock": g.stock, "status": g.status,
        "status_text": STATUS_TEXT.get(g.status, "未知"),
        "view_count": g.view_count, "like_count": g.like_count,
        "cover": _cover_url(db, g), "seller_id": g.seller_id,
        "created_at": g.created_at.isoformat(),
    }


@router.get("", summary="商品列表（分页/关键词/分类/价格区间/排序）")
def list_goods(
    q: str | None = Query(None, max_length=50, description="按标题关键词模糊搜索"),
    category_id: int | None = Query(None, description="分类筛选"),
    min_price: float | None = Query(None, ge=0, description="价格下限"),
    max_price: float | None = Query(None, ge=0, description="价格上限"),
    sort: str = Query("newest", pattern="^(newest|price_asc|price_desc|views)$",
                      description="排序：newest最新 price_asc/price_desc价格 views浏览量"),
    seller_id: int | None = Query(None, description="只看某卖家的商品"),
    status: int | None = Query(None, ge=1, le=4, description="状态筛选：1在售 2已售 3下架 4已预订；不传=全部"),
    page: int = Query(1, ge=1),
    page_size: int = Query(12, ge=1, le=50),
    db: Session = Depends(get_db),
):
    stmt = select(Goods)
    if q:
        stmt = stmt.where(Goods.title.like(f"%{q}%"))
    if category_id is not None:
        stmt = stmt.where(Goods.category_id == category_id)
    if min_price is not None:
        stmt = stmt.where(Goods.price >= min_price)
    if max_price is not None:
        stmt = stmt.where(Goods.price <= max_price)
    if seller_id is not None:
        stmt = stmt.where(Goods.seller_id == seller_id)
    if status is not None:
        stmt = stmt.where(Goods.status == status)

    total = db.scalar(select(func.count()).select_from(stmt.subquery()))
    order = {
        "newest": Goods.id.desc(),
        "price_asc": Goods.price.asc(),
        "price_desc": Goods.price.desc(),
        "views": Goods.view_count.desc(),
    }[sort]
    rows = db.scalars(stmt.order_by(order).offset((page - 1) * page_size).limit(page_size)).all()
    return ok({"total": total, "page": page, "page_size": page_size,
               "items": [_brief(db, g) for g in rows]})


@router.post("", summary="发布商品")
async def create_goods(
    payload: GoodsCreate,
    db: Session = Depends(get_db),
    x_user_id: int | None = Header(None),
):
    # 参数校验由 Pydantic 完成（价格>0、库存>=0、描述必填等），这里做业务校验
    if not db.get(User, payload.seller_id):
        raise HTTPException(status_code=400, detail=f"发布人不存在：seller_id={payload.seller_id}")
    if not db.get(Category, payload.category_id):
        raise HTTPException(status_code=400, detail=f"分类不存在：category_id={payload.category_id}")
    # 增量修复：发布人必须就是登录本人（x_user_id 由 main.py 中间件按签名令牌覆盖，无法伪造）
    uid = _require_user(x_user_id)
    if uid != payload.seller_id:
        raise HTTPException(status_code=403, detail="只能以自己的身份发布商品")

    # 增量新增：发布限流（同一用户 1 小时最多 10 次，ZSET 滑动窗口 + Lua 原子计数）
    allowed, retry_after = await acquire_publish_quota(uid)
    if not allowed:
        raise HTTPException(
            status_code=429,
            detail="发布过于频繁，请稍后再试",
            headers={"Retry-After": str(retry_after)},
        )

    goods = Goods(
        **payload.model_dump(exclude={"images"}),
        cover_image=payload.images[0] if payload.images else None,
    )
    db.add(goods)
    db.flush()  # 先取得 goods.id
    for url in payload.images:
        db.add(GoodsImage(goods_id=goods.id, url=url))
    db.commit()
    db.refresh(goods)
    return ok(_brief(db, goods), "发布成功")


@router.get("/notifications", summary="我的消息通知：我商品收到的留言与点赞")
def notifications(
    db: Session = Depends(get_db),
    x_user_id: int | None = Header(None),
):
    uid = _require_user(x_user_id)
    items = []
    rows = db.execute(
        select(GoodsMessage, Goods.title, User.nickname)
        .join(Goods, GoodsMessage.goods_id == Goods.id)
        .join(User, GoodsMessage.user_id == User.id)
        .where(Goods.seller_id == uid)
    ).all()
    for m, gtitle, nick in rows:
        items.append({"type": "留言", "icon": "💬", "from": nick, "goods_id": m.goods_id,
                      "goods_title": gtitle, "text": m.content,
                      "created_at": m.created_at.isoformat()})
    rows = db.execute(
        select(GoodsLike, Goods.title, User.nickname)
        .join(Goods, GoodsLike.goods_id == Goods.id)
        .join(User, GoodsLike.user_id == User.id)
        .where(Goods.seller_id == uid)
    ).all()
    for lk, gtitle, nick in rows:
        items.append({"type": "点赞", "icon": "❤", "from": nick, "goods_id": lk.goods_id,
                      "goods_title": gtitle, "text": "赞了你的商品",
                      "created_at": lk.created_at.isoformat()})
    items.sort(key=lambda x: x["created_at"], reverse=True)
    return ok({"unread": len(items), "items": items})


@router.get("/{goods_id}", summary="商品详情（含发布人/图片/留言/是否已点赞，自动计浏览）")
def goods_detail(
    goods_id: int,
    request: Request,
    db: Session = Depends(get_db),
    x_user_id: int | None = Header(None),
):
    goods = db.get(Goods, goods_id)
    if not goods:
        raise HTTPException(status_code=404, detail="商品不存在")

    _touch_view(goods, request, x_user_id)  # 60秒防刷窗口
    db.commit()
    db.refresh(goods)

    liked = False
    if x_user_id:
        liked = bool(db.scalar(
            select(GoodsLike).where(GoodsLike.goods_id == goods_id, GoodsLike.user_id == x_user_id)
        ))
    images = db.scalars(select(GoodsImage).where(GoodsImage.goods_id == goods_id).order_by(GoodsImage.id)).all()
    msgs = db.execute(
        select(GoodsMessage, User.nickname)
        .join(User, GoodsMessage.user_id == User.id)
        .where(GoodsMessage.goods_id == goods_id)
        .order_by(GoodsMessage.id.desc())
    ).all()
    category = db.get(Category, goods.category_id)

    data = _brief(db, goods)
    data.update({
        "description": goods.description,
        "location": goods.location,
        "contact": goods.contact,
        "category_name": category.name if category else None,
        "liked": liked,
        "images": [i.url for i in images],
        "seller": {"id": goods.seller.id, "nickname": goods.seller.nickname,
                   "credit_score": goods.seller.credit_score},
        "messages": [{"id": m.id, "content": m.content, "nickname": nick,
                      "created_at": m.created_at.strftime("%Y-%m-%d %H:%M")} for m, nick in msgs],
    })
    return ok(data)


@router.post("/{goods_id}/view", summary="浏览量上报（60秒防刷）")
def add_view(
    goods_id: int,
    request: Request,
    db: Session = Depends(get_db),
    x_user_id: int | None = Header(None),
):
    goods = db.get(Goods, goods_id)
    if not goods:
        raise HTTPException(status_code=404, detail="商品不存在")
    before = goods.view_count
    _touch_view(goods, request, x_user_id)
    db.commit()
    return ok({"view_count": goods.view_count, "counted": goods.view_count > before})


@router.post("/{goods_id}/like", summary="点赞（一人一商品仅一次）")
def like_goods(
    goods_id: int,
    db: Session = Depends(get_db),
    x_user_id: int | None = Header(None),
):
    uid = _require_user(x_user_id)
    goods = db.get(Goods, goods_id)
    if not goods:
        raise HTTPException(status_code=404, detail="商品不存在")
    exists = db.scalar(select(GoodsLike).where(GoodsLike.goods_id == goods_id, GoodsLike.user_id == uid))
    if exists:
        raise HTTPException(status_code=400, detail="已经点过赞了")
    db.add(GoodsLike(goods_id=goods_id, user_id=uid))
    goods.like_count += 1
    db.commit()
    return ok({"like_count": goods.like_count, "liked": True}, "点赞成功")


@router.delete("/{goods_id}/like", summary="取消点赞")
def unlike_goods(
    goods_id: int,
    db: Session = Depends(get_db),
    x_user_id: int | None = Header(None),
):
    uid = _require_user(x_user_id)
    goods = db.get(Goods, goods_id)
    if not goods:
        raise HTTPException(status_code=404, detail="商品不存在")
    record = db.scalar(select(GoodsLike).where(GoodsLike.goods_id == goods_id, GoodsLike.user_id == uid))
    if not record:
        raise HTTPException(status_code=400, detail="尚未点赞")
    db.delete(record)
    goods.like_count = max(0, goods.like_count - 1)
    db.commit()
    return ok({"like_count": goods.like_count, "liked": False}, "已取消点赞")


@router.post("/{goods_id}/status", summary="状态变更：下架/重新上架/标记已售（仅本人商品）")
def change_status(
    goods_id: int,
    payload: StatusUpdate,
    db: Session = Depends(get_db),
    x_user_id: int | None = Header(None),
):
    uid = _require_user(x_user_id)
    goods = db.get(Goods, goods_id)
    if not goods:
        raise HTTPException(status_code=404, detail="商品不存在")
    if goods.seller_id != uid:
        raise HTTPException(status_code=403, detail="只能操作自己发布的商品")

    if payload.action == "off":
        if goods.status != 1:
            raise HTTPException(status_code=400, detail="仅在售商品可下架")
        goods.status = 3
        msg = "已下架"
    elif payload.action == "on":
        if goods.status != 3:
            raise HTTPException(status_code=400, detail="仅已下架商品可重新上架")
        goods.status = 1
        msg = "已重新上架"
    else:  # sold
        if goods.status != 1:
            raise HTTPException(status_code=400, detail="仅在售商品可标记已售")
        goods.status = 2
        msg = "已标记交易完成"
    db.commit()
    return ok({"status": goods.status, "status_text": STATUS_TEXT[goods.status]}, msg)


@router.delete("/{goods_id}", summary="删除商品（仅本人，级联清理图片/点赞/留言）")
def delete_goods(
    goods_id: int,
    db: Session = Depends(get_db),
    x_user_id: int | None = Header(None),
):
    uid = _require_user(x_user_id)
    goods = db.get(Goods, goods_id)
    if not goods:
        raise HTTPException(status_code=404, detail="商品不存在")
    if goods.seller_id != uid:
        raise HTTPException(status_code=403, detail="只能删除自己发布的商品")
    # 先删子表再删主表，避免外键约束报错
    db.query(GoodsMessage).filter(GoodsMessage.goods_id == goods_id).delete()
    db.query(GoodsLike).filter(GoodsLike.goods_id == goods_id).delete()
    db.query(GoodsImage).filter(GoodsImage.goods_id == goods_id).delete()
    db.delete(goods)
    db.commit()
    return ok(None, "商品已删除")


@router.post("/{goods_id}/messages", summary="发表留言")
def add_message(
    goods_id: int,
    payload: MessageCreate,
    db: Session = Depends(get_db),
    x_user_id: int | None = Header(None),
):
    uid = _require_user(x_user_id)
    if not db.get(Goods, goods_id):
        raise HTTPException(status_code=404, detail="商品不存在")
    user = db.get(User, uid)
    msg = GoodsMessage(goods_id=goods_id, user_id=uid, content=payload.content)
    db.add(msg)
    db.commit()
    return ok({"id": msg.id, "nickname": user.nickname, "content": msg.content,
               "created_at": msg.created_at.strftime("%Y-%m-%d %H:%M")}, "留言成功")


@stats_router.get("", summary="首页统计")
def statistics(db: Session = Depends(get_db)):
    today_start = datetime.combine(date.today(), datetime.min.time())
    return ok({
        "total": db.scalar(select(func.count(Goods.id))),
        "on_sale": db.scalar(select(func.count()).select_from(Goods).where(Goods.status == 1)),
        "sold": db.scalar(select(func.count()).select_from(Goods).where(Goods.status == 2)),
        "today_new": db.scalar(select(func.count()).select_from(Goods).where(Goods.created_at >= today_start)),
    })

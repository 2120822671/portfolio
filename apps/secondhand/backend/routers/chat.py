"""聊天模块（增量新增：与商家交流砍价 / 以物换物互动）

会话维度 =（商品, 买卖双方）：
- 买家对某件商品发起聊天，商品卖家即对方；卖家回复同一会话；
- 消息类型：text 文字、bargain 出价、bargain_accept / bargain_reject 卖家回应、
  swap 发起换物、swap_accept / swap_reject 对方回应；
- 回应类消息的 extra.ref 指向被回应的消息ID，用于前端隐藏已处理的按钮。
"""
import json
import logging
from decimal import Decimal, InvalidOperation

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from sqlalchemy import func, or_, select, update
from sqlalchemy.orm import Session

from database import get_db
from models import ChatMessage, Goods, GoodsImage, User
from resp import ok
from schemas import ChatSend

logger = logging.getLogger("campus_secondhand.routers.chat")

router = APIRouter(prefix="/chat", tags=["聊天"])

MSG_PREVIEW = {"bargain": "【砍价】", "bargain_accept": "【同意砍价】", "bargain_reject": "【拒绝砍价】",
               "swap": "【换物】", "swap_accept": "【同意换物】", "swap_reject": "【拒绝换物】"}


def _require_user(x_user_id: int | None) -> int:
    if not x_user_id:
        raise HTTPException(status_code=401, detail="请先登录")
    return x_user_id


def _extra_of(m: ChatMessage) -> dict | None:
    if not m.extra:
        return None
    try:
        return json.loads(m.extra)
    except (ValueError, TypeError):
        return None


def _msg_dict(m: ChatMessage, uid: int, answered: set[int]) -> dict:
    return {
        "id": m.id,
        "goods_id": m.goods_id,
        "sender_id": m.sender_id,
        "receiver_id": m.receiver_id,
        "msg_type": m.msg_type,
        "content": m.content,
        "extra": _extra_of(m),
        "mine": m.sender_id == uid,
        "replied": m.id in answered,
        "created_at": m.created_at.strftime("%Y-%m-%d %H:%M"),
    }


def _goods_brief(db: Session, goods: Goods) -> dict:
    cover = goods.cover_image or db.scalar(
        select(GoodsImage.url).where(GoodsImage.goods_id == goods.id).order_by(GoodsImage.id)
    )
    return {"id": goods.id, "title": goods.title, "price": str(goods.price),
            "cover": cover, "status": goods.status, "seller_id": goods.seller_id}


@router.get("/conversations", summary="聊天会话列表")
def conversations(db: Session = Depends(get_db), x_user_id: int | None = Header(None)):
    uid = _require_user(x_user_id)
    rows = db.execute(
        select(ChatMessage)
        .where(or_(ChatMessage.sender_id == uid, ChatMessage.receiver_id == uid))
        .order_by(ChatMessage.id.desc())
        .limit(500)
    ).scalars().all()

    convs: dict[tuple[int, int], dict] = {}
    for m in rows:
        other = m.receiver_id if m.sender_id == uid else m.sender_id
        key = (m.goods_id, other)
        if key not in convs:
            convs[key] = {"goods_id": m.goods_id, "other_id": other, "last": m, "unread": 0}
        if m.receiver_id == uid and m.read_at is None:
            convs[key]["unread"] += 1

    items = []
    for (goods_id, other_id), conv in convs.items():
        goods = db.get(Goods, goods_id)
        other = db.get(User, other_id)
        last: ChatMessage = conv["last"]
        items.append({
            "goods_id": goods_id,
            "goods_title": goods.title if goods else "商品已删除",
            "goods_cover": (goods.cover_image or db.scalar(
                select(GoodsImage.url).where(GoodsImage.goods_id == goods_id).order_by(GoodsImage.id)
            )) if goods else None,
            "goods_status": goods.status if goods else 0,
            "other_id": other_id,
            "other_nickname": (other.nickname or other.username) if other else "用户已注销",
            "last_content": MSG_PREVIEW.get(last.msg_type, "") + last.content,
            "last_at": last.created_at.strftime("%Y-%m-%d %H:%M"),
            "unread": conv["unread"],
        })
    items.sort(key=lambda x: x["last_at"], reverse=True)
    return ok({"items": items, "unread": sum(i["unread"] for i in items)})


@router.get("/unread", summary="未读消息总数（导航角标）")
def unread(db: Session = Depends(get_db), x_user_id: int | None = Header(None)):
    uid = _require_user(x_user_id)
    n = db.scalar(select(func.count()).select_from(
        select(ChatMessage.id).where(ChatMessage.receiver_id == uid,
                                      ChatMessage.read_at.is_(None)).subquery())) or 0
    return ok({"unread": n})


@router.get("/messages", summary="单个会话的消息列表（自动标记已读）")
def chat_messages(
    goods_id: int = Query(description="商品ID"),
    other_id: int = Query(description="对方用户ID"),
    db: Session = Depends(get_db),
    x_user_id: int | None = Header(None),
):
    uid = _require_user(x_user_id)
    goods = db.get(Goods, goods_id)
    if not goods:
        raise HTTPException(status_code=404, detail="商品不存在")
    other = db.get(User, other_id)
    if not other:
        raise HTTPException(status_code=404, detail="对方用户不存在")
    # 只允许会话双方访问：自己与对方中必须有一人是该商品的卖家
    if other_id == uid or goods.seller_id not in (uid, other_id):
        raise HTTPException(status_code=403, detail="只能查看自己参与的会话")

    rows = db.execute(
        select(ChatMessage)
        .where(ChatMessage.goods_id == goods_id,
               or_(ChatMessage.sender_id == uid, ChatMessage.receiver_id == uid),
               or_(ChatMessage.sender_id == other_id, ChatMessage.receiver_id == other_id))
        .order_by(ChatMessage.id.asc())
        .limit(200)
    ).scalars().all()

    # 先序列化（避免 commit 过期后逐条回查），再统一标记已读
    answered = set()
    for m in rows:
        extra = _extra_of(m) or {}
        if isinstance(extra.get("ref"), int):
            answered.add(extra["ref"])
    items = [_msg_dict(m, uid, answered) for m in rows]

    db.execute(
        update(ChatMessage)
        .where(ChatMessage.goods_id == goods_id, ChatMessage.sender_id == other_id,
               ChatMessage.receiver_id == uid, ChatMessage.read_at.is_(None))
        .values(read_at=func.now())
        .execution_options(synchronize_session=False)
    )
    db.commit()

    return ok({
        "goods": _goods_brief(db, goods),
        "other": {"id": other.id, "nickname": other.nickname or other.username,
                  "credit_score": other.credit_score},
        "items": items,
    })


@router.post("/messages", summary="发送消息（文字 / 砍价 / 换物 / 同意拒绝）")
def send_message(payload: ChatSend, db: Session = Depends(get_db),
                 x_user_id: int | None = Header(None)):
    uid = _require_user(x_user_id)
    if payload.to_user_id == uid:
        raise HTTPException(status_code=400, detail="不能给自己发消息")
    goods = db.get(Goods, payload.goods_id)
    if not goods:
        raise HTTPException(status_code=404, detail="商品不存在")
    if not db.get(User, payload.to_user_id):
        raise HTTPException(status_code=404, detail="对方用户不存在")
    if goods.seller_id not in (uid, payload.to_user_id):
        raise HTTPException(status_code=403, detail="只能在买家与卖家之间聊天")

    # 卖家「同意砍价」时把商品标价调整为约定价，买家随后下单即为该价格
    if payload.msg_type == "bargain_accept":
        if goods.seller_id != uid:
            raise HTTPException(status_code=403, detail="只有卖家可以同意砍价")
        ref_id = (payload.extra or {}).get("ref")
        ref = db.get(ChatMessage, ref_id) if isinstance(ref_id, int) else None
        if (not ref or ref.goods_id != goods.id or ref.msg_type != "bargain"
                or ref.receiver_id != uid or ref.sender_id != payload.to_user_id):
            raise HTTPException(status_code=400, detail="只能回应本会话中买家发起的砍价")
        price = (payload.extra or {}).get("price") or (_extra_of(ref) or {}).get("price")
        try:
            agreed = Decimal(str(price))
        except (InvalidOperation, TypeError, ValueError):
            raise HTTPException(status_code=400, detail="砍价金额格式不正确")
        if agreed <= 0:
            raise HTTPException(status_code=400, detail="砍价金额必须大于 0")
        goods.price = agreed

    msg = ChatMessage(
        goods_id=payload.goods_id,
        sender_id=uid,
        receiver_id=payload.to_user_id,
        msg_type=payload.msg_type,
        content=payload.content,
        extra=json.dumps(payload.extra, ensure_ascii=False) if payload.extra else None,
    )
    db.add(msg)
    db.commit()
    db.refresh(msg)
    return ok(_msg_dict(msg, uid, set()), "已发送")

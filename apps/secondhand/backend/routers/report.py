"""举报接口（增量新增）：同一用户对同一 (target_type, target_id) 24 小时只能举报一次"""
import logging

from fastapi import APIRouter, Depends, Header, HTTPException
from sqlalchemy.orm import Session

from database import get_db
from models import Goods, GoodsMessage, Report, User
from resp import ok
from risk import acquire_report_slot, release_report_slot
from routers.goods import _require_user
from schemas import ReportCreate

router = APIRouter(prefix="/report", tags=["举报"])
logger = logging.getLogger("campus_secondhand.report")

TARGET_TYPES = ("goods", "user", "message")


@router.post("", summary="举报（同一用户同一对象 24 小时限一次）")
async def create_report(
    payload: ReportCreate,
    db: Session = Depends(get_db),
    x_user_id: int | None = Header(None),
):
    uid = _require_user(x_user_id)  # 复用既有鉴权语义：缺少 X-User-Id 返回 401

    # 1) 参数白名单校验（非法类型按需求返回 400，而不是 Pydantic 的 422）
    if payload.target_type not in TARGET_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"不支持的举报类型：{payload.target_type}，仅允许 goods/user/message",
        )

    # 2) 目标存在性校验 + 禁止自举报
    if payload.target_type == "goods":
        if not db.get(Goods, payload.target_id):
            raise HTTPException(status_code=404, detail=f"被举报商品不存在：target_id={payload.target_id}")
    elif payload.target_type == "user":
        if not db.get(User, payload.target_id):
            raise HTTPException(status_code=404, detail=f"被举报用户不存在：target_id={payload.target_id}")
        if payload.target_id == uid:
            raise HTTPException(status_code=400, detail="不能举报自己")
    else:
        if not db.get(GoodsMessage, payload.target_id):
            raise HTTPException(status_code=404, detail=f"被举报留言不存在：target_id={payload.target_id}")

    # 3) Redis 24 小时原子占位（SET NX EX 86400）
    allowed, degraded = await acquire_report_slot(uid, payload.target_type, payload.target_id)
    if not allowed:
        raise HTTPException(status_code=409, detail="24 小时内已举报过该对象，请勿重复提交")

    # 4) 落库；失败必须回滚占位，避免"没落库却锁死 24 小时"
    try:
        report = Report(
            user_id=uid,
            target_type=payload.target_type,
            target_id=payload.target_id,
            reason=payload.reason,
        )
        db.add(report)
        db.commit()
        db.refresh(report)
    except Exception:
        db.rollback()
        await release_report_slot(uid, payload.target_type, payload.target_id)
        raise

    return ok({"id": report.id}, "举报成功（风控降级）" if degraded else "举报成功")

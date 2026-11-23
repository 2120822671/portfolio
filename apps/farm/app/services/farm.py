"""
农场格子状态规则

数据库里 status 只会稳定存 empty / growing / withered，
ready 与"超时枯萎"都由 ready_at 实时推断，避免需要定时任务去改表。
"""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import Optional

from app.config import settings
from app.utils.time_utils import ensure_aware, now_utc


def infer_cell_status(
    status: str,
    ready_at: Optional[datetime],
    now: Optional[datetime] = None,
) -> str:
    """
    推断格子当前对外展示的状态。

    growing + 已到 ready_at                 -> ready
    growing/ready + 超过枯萎宽限期           -> withered
    其余保持数据库原值
    """
    if status not in ("growing", "ready") or ready_at is None:
        return status

    current = now or now_utc()
    ready = ensure_aware(ready_at)
    if ready is None:
        return status

    if current >= ready + timedelta(seconds=settings.WITHER_GRACE_SECONDS):
        return "withered"
    if current >= ready:
        return "ready"
    return "growing"


def seconds_until_wither(ready_at: Optional[datetime], now: Optional[datetime] = None) -> int:
    """成熟后距离枯萎还剩多少秒；尚未成熟或无作物返回 0"""
    ready = ensure_aware(ready_at)
    if ready is None:
        return 0
    current = now or now_utc()
    deadline = ready + timedelta(seconds=settings.WITHER_GRACE_SECONDS)
    return max(0, int((deadline - current).total_seconds()))

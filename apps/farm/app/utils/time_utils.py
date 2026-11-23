"""
时间工具函数 —— 统一时间处理
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional


def now_utc() -> datetime:
    """返回当前 UTC 时间（带 tzinfo）"""
    return datetime.now(timezone.utc)


def now_local() -> datetime:
    """返回当前本地时间"""
    return datetime.now()


def ensure_aware(dt: Optional[datetime]) -> Optional[datetime]:
    """SQLite 读出的时间可能没有时区，统一按 UTC 处理"""
    if dt is not None and dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


def seconds_until(target: Optional[datetime], now: Optional[datetime] = None) -> int:
    """
    计算距离目标时间还剩多少秒。
    target 为 None 或已过期时返回 0；now 不传时取当前 UTC 时间。
    """
    target = ensure_aware(target)
    if target is None:
        return 0
    current = now or now_utc()
    diff = (target - current).total_seconds()
    return max(0, int(diff))


def format_datetime(dt: Optional[datetime]) -> Optional[str]:
    """将 datetime 格式化为 ISO 8601 字符串（None 安全）"""
    if dt is None:
        return None
    return dt.isoformat()

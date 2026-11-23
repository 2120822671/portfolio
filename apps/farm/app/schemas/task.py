"""
任务模块 DTO
"""
from __future__ import annotations

from datetime import date
from typing import List

from pydantic import BaseModel


class DailyTaskResponse(BaseModel):
    """单个任务进度"""
    task_date: date
    task_type: str                  # login / harvest / sell
    task_name: str                  # 人类可读名
    progress: int
    target: int
    reward_gold: int
    is_completed: bool
    is_claimed: bool


class DailyTaskListResponse(BaseModel):
    """今日所有任务"""
    task_date: date
    tasks: List[DailyTaskResponse]
    login_bonus_claimed: bool = False


class DailyTaskClaimResponse(BaseModel):
    """领取奖励响应"""
    task_type: str
    reward_gold: int
    gold_remaining: int
    message: str = "奖励已领取 ✨"

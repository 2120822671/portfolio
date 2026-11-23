"""
每日任务规则

统一维护任务模板，并把"创建今日任务 + 累加进度"从各个 router 中抽离出来，
避免收获、出售、登录三处各写一份相似代码。
"""
from __future__ import annotations

from datetime import date
from typing import Dict, Optional

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.task import DailyTaskProgress


# 任务模板：task_type 必须与每日任务接口返回保持一致
TASK_TEMPLATES = [
    {"task_type": "login", "task_name": "每日签到", "target": 1, "reward_gold": 20},
    {"task_type": "harvest", "task_name": "收获 5 个作物", "target": 5, "reward_gold": 50},
    {"task_type": "sell", "task_name": "出售 10 个产物", "target": 10, "reward_gold": 30},
]
TASK_TEMPLATE_MAP = {t["task_type"]: t for t in TASK_TEMPLATES}


def _new_task(user_id: int, task_type: str, today: date) -> DailyTaskProgress:
    tpl = TASK_TEMPLATE_MAP[task_type]
    # 能走到任务接口说明今天已经登录，签到任务直接算完成
    initial_progress = 1 if task_type == "login" else 0
    is_completed = 1 if task_type == "login" else 0
    return DailyTaskProgress(
        user_id=user_id,
        task_date=today,
        task_type=task_type,
        progress=initial_progress,
        target=tpl["target"],
        reward_gold=tpl["reward_gold"],
        is_completed=is_completed,
        is_claimed=0,
    )


async def ensure_daily_tasks(
    db: AsyncSession,
    user_id: int,
    today: Optional[date] = None,
) -> Dict[str, DailyTaskProgress]:
    """确保今日所有任务记录存在，返回 task_type -> 记录 的映射"""
    today = today or date.today()
    result = await db.execute(
        select(DailyTaskProgress).where(
            and_(
                DailyTaskProgress.user_id == user_id,
                DailyTaskProgress.task_date == today,
            )
        )
    )
    tasks = {t.task_type: t for t in result.scalars().all()}

    created = False
    for tpl in TASK_TEMPLATES:
        task_type = tpl["task_type"]
        if task_type not in tasks:
            task = _new_task(user_id, task_type, today)
            db.add(task)
            tasks[task_type] = task
            created = True

    if created:
        await db.flush()
    return tasks


async def add_task_progress(
    db: AsyncSession,
    user_id: int,
    task_type: str,
    amount: int,
    today: Optional[date] = None,
) -> Optional[DailyTaskProgress]:
    """
    给今日任务累加进度；记录不存在时自动补齐。

    amount 使用实际产出/出售数量，保证任务进度与周收获榜口径一致。
    """
    if task_type not in TASK_TEMPLATE_MAP:
        return None
    if amount <= 0:
        return None

    today = today or date.today()
    result = await db.execute(
        select(DailyTaskProgress).where(
            and_(
                DailyTaskProgress.user_id == user_id,
                DailyTaskProgress.task_date == today,
                DailyTaskProgress.task_type == task_type,
            )
        )
    )
    task = result.scalar_one_or_none()
    if task is None:
        task = _new_task(user_id, task_type, today)
        task.progress = 0
        task.is_completed = 0
        db.add(task)

    task.progress += amount
    if task.progress >= task.target:
        task.is_completed = 1
    return task

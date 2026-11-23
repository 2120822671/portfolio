"""
任务路由 —— 查询每日任务 / 领取奖励

路径前缀: /api/v1/tasks
"""
from __future__ import annotations

from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_user
from app.models.task import DailyTaskProgress
from app.models.user import User
from app.schemas.task import DailyTaskClaimResponse, DailyTaskListResponse
from app.services.daily_tasks import TASK_TEMPLATES, ensure_daily_tasks


router = APIRouter(prefix="/tasks", tags=["任务"])


# ============================================================
# GET /tasks/daily  —— 查询今日任务
# ============================================================
@router.get(
    "/daily",
    response_model=DailyTaskListResponse,
    summary="今日任务",
    description="返回今天所有任务类型及其进度。不存在的任务会自动创建。",
)
async def get_daily_tasks(
    user_id: int = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> DailyTaskListResponse:
    today = date.today()

    # 缺失的任务由服务层统一补齐（签到任务自动记为完成）
    existing_map = await ensure_daily_tasks(db, user_id, today=today)
    await db.commit()

    # 构建响应
    tasks_resp = []
    login_claimed = False
    for tpl in TASK_TEMPLATES:
        task = existing_map.get(tpl["task_type"])
        if task is None:
            continue

        if tpl["task_type"] == "login" and task.is_claimed:
            login_claimed = True

        tasks_resp.append({
            "task_date": task.task_date,
            "task_type": task.task_type,
            "task_name": tpl["task_name"],
            "progress": min(task.progress, task.target),
            "target": task.target,
            "reward_gold": task.reward_gold,
            "is_completed": bool(task.is_completed),
            "is_claimed": bool(task.is_claimed),
        })

    return DailyTaskListResponse(
        task_date=today,
        tasks=tasks_resp,
        login_bonus_claimed=login_claimed,
    )


# ============================================================
# POST /tasks/claim/{task_type}  —— 领取奖励
# ============================================================
@router.post(
    "/claim/{task_type}",
    response_model=DailyTaskClaimResponse,
    summary="领取任务奖励",
    description="完成今日任务后领取金币奖励。重复领取或未完成都会返回错误。",
)
async def claim_task_reward(
    task_type: str,
    user_id: int = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> DailyTaskClaimResponse:
    # 校验 task_type 合法
    valid_types = {t["task_type"] for t in TASK_TEMPLATES}
    if task_type not in valid_types:
        raise HTTPException(
            status_code=400,
            detail=f"无效任务类型，可选值: {list(valid_types)}",
        )

    today = date.today()
    result = await db.execute(
        select(DailyTaskProgress).where(
            and_(
                DailyTaskProgress.user_id == user_id,
                DailyTaskProgress.task_date == today,
                DailyTaskProgress.task_type == task_type,
            )
        )
    )
    task: Optional[DailyTaskProgress] = result.scalar_one_or_none()

    if task is None:
        raise HTTPException(status_code=404, detail="今日无此任务记录")

    if not task.is_completed:
        raise HTTPException(status_code=400, detail="任务尚未完成，无法领取奖励")

    if task.is_claimed:
        raise HTTPException(status_code=400, detail="奖励已领取过了")

    # 发金币
    user_result = await db.execute(select(User).where(User.id == user_id))
    user: Optional[User] = user_result.scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=404, detail="用户不存在")
    user.gold += task.reward_gold

    task.is_claimed = 1
    await db.commit()

    return DailyTaskClaimResponse(
        task_type=task_type,
        reward_gold=task.reward_gold,
        gold_remaining=user.gold,
    )

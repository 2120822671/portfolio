"""
排行榜路由 —— 财富榜 / 周收获榜

路径前缀: /api/v1/rank
"""
from __future__ import annotations

from collections import defaultdict
from datetime import date, timedelta

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.inventory import Inventory
from app.models.shop import ShopItem
from app.models.task import DailyTaskProgress
from app.models.user import User
from app.services.produce import load_produce_catalog, resolve_produce_meta


router = APIRouter(prefix="/rank", tags=["排行榜"])


# ============================================================
# GET /rank/wealth  —— 财富榜 Top N（公开）
# ============================================================
@router.get(
    "/wealth",
    summary="财富榜",
    description="按「金币 + 仓库价值」排名，返回 Top N（默认 50）。封禁玩家不计入。",
)
async def get_wealth_rank(
    limit: int = Query(50, ge=1, le=100, description="返回数量上限"),
    db: AsyncSession = Depends(get_db),
):
    # 1. 取出候选玩家（小型游戏直接取前 500 名，避免对全表做复杂聚合）
    result = await db.execute(
        select(User)
        .where(User.is_banned == 0)
        .order_by(User.gold.desc())
        .limit(min(max(limit * 4, 100), 500))
    )
    users = result.scalars().all()
    user_ids = [u.id for u in users]

    # 2. 计算这些玩家背包里物品的估值
    value_by_user: dict[int, int] = defaultdict(int)
    if user_ids:
        inv_result = await db.execute(
            select(
                Inventory.user_id,
                Inventory.item_type,
                Inventory.template_id,
                Inventory.item_name,
                Inventory.quantity,
            ).where(
                Inventory.user_id.in_(user_ids),
                Inventory.quantity > 0,
            )
        )
        catalog = await load_produce_catalog(db)

        feed_price = (await db.execute(
            select(ShopItem.price)
            .where(ShopItem.item_type == "feed", ShopItem.is_active == 1)
            .order_by(ShopItem.id)
            .limit(1)
        )).scalar_one_or_none() or 5

        for uid, item_type, template_id, item_name, qty in inv_result.all():
            if item_type == "produce":
                meta = resolve_produce_meta(catalog, template_id, item_name)
                if meta:
                    value_by_user[uid] += meta["unit_price"] * qty
            elif item_type == "seed":
                crop = catalog.crops_by_id.get(template_id) if template_id else None
                if crop:
                    value_by_user[uid] += crop.seed_price * qty
            elif item_type == "animal":
                animal = catalog.animals_by_id.get(template_id) if template_id else None
                if animal:
                    value_by_user[uid] += animal.purchase_price * qty
            elif item_type == "feed":
                value_by_user[uid] += feed_price * qty

    # 3. 组装并按总财富排序
    ranked = [
        {
            "user_id": u.id,
            "username": u.username,
            "gold": u.gold,
            "inventory_value": value_by_user.get(u.id, 0),
            "wealth": u.gold + value_by_user.get(u.id, 0),
            "level": u.level,
        }
        for u in users
    ]
    ranked.sort(key=lambda row: (row["wealth"], row["gold"]), reverse=True)
    ranked = ranked[:limit]
    for idx, row in enumerate(ranked, start=1):
        row["rank"] = idx

    return {"type": "wealth", "total": len(ranked), "list": ranked}


# ============================================================
# GET /rank/weekly-harvest  —— 周收获榜 Top N（公开）
# ============================================================
@router.get(
    "/weekly-harvest",
    summary="本周收获榜",
    description="本周累计收获作物数量排名 Top N。每周一 0 点自动重置。",
)
async def get_weekly_harvest_rank(
    limit: int = Query(50, ge=1, le=100, description="返回数量上限"),
    db: AsyncSession = Depends(get_db),
):
    # 计算本周的起始日期（周一）
    today = date.today()
    monday = today - timedelta(days=today.weekday())

    # 每日 harvest 任务的进度已按实际产出数量累计，这里直接求和
    result = await db.execute(
        select(
            DailyTaskProgress.user_id,
            func.sum(DailyTaskProgress.progress).label("total_harvest"),
            User.username,
        )
        .join(User, User.id == DailyTaskProgress.user_id)
        .where(
            DailyTaskProgress.task_type == "harvest",
            DailyTaskProgress.task_date >= monday,
            User.is_banned == 0,
        )
        .group_by(DailyTaskProgress.user_id, User.username)
        .order_by(func.sum(DailyTaskProgress.progress).desc())
        .limit(limit)
    )

    rows = result.all()

    rank_list = []
    for idx, (uid, total, username) in enumerate(rows, start=1):
        if total and total > 0:
            rank_list.append({
                "rank": idx,
                "user_id": uid,
                "username": username,
                "total_harvest": int(total or 0),
            })

    return {
        "type": "weekly_harvest",
        "week_start": monday.isoformat(),
        "total": len(rank_list),
        "list": rank_list,
    }

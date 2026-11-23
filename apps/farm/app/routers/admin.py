"""
管理员路由 —— 用户管理 / 游戏数据 CRUD / 运营统计

路径前缀: /api/v1/admin
⚠️ 所有接口需要管理员权限（role=admin）
"""
from __future__ import annotations

from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_admin_user
from app.models.animal import AnimalTemplate
from app.models.crop import CropTemplate
from app.models.farm import FarmCell
from app.models.shop import ShopItem
from app.models.task import DailyTaskProgress
from app.models.user import User
from app.schemas.admin import (
    AdminAnimalTemplateRequest,
    AdminCropTemplateRequest,
    AdminShopItemRequest,
)
from app.schemas.common import MessageResponse


router = APIRouter(prefix="/admin", tags=["管理员"])


# ============================================================
# 用户管理
# ============================================================
@router.get("/users", summary="玩家列表")
async def admin_list_users(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    keyword: Optional[str] = Query(None, description="用户名模糊搜索"),
    user_id: int = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
):
    query = select(User)
    if keyword:
        query = query.where(User.username.like(f"%{keyword}%"))

    total_result = await db.execute(
        select(func.count()).select_from(query.subquery())
    )
    total = total_result.scalar() or 0

    result = await db.execute(
        query.order_by(User.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    users = result.scalars().all()

    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "users": [
            {
                "id": u.id,
                "username": u.username,
                "gold": u.gold,
                "level": u.level,
                "cell_count": u.cell_count,
                "is_banned": bool(u.is_banned),
                "created_at": u.created_at.isoformat() if u.created_at else None,
            }
            for u in users
        ],
    }


@router.post("/users/{target_id}/ban", summary="封禁玩家")
async def admin_ban_user(
    target_id: int,
    user_id: int = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
) -> MessageResponse:
    result = await db.execute(select(User).where(User.id == target_id))
    user = result.scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=404, detail="玩家不存在")
    if user.role == "admin":
        raise HTTPException(status_code=400, detail="不能封禁管理员")

    user.is_banned = 1
    await db.commit()
    return MessageResponse(message=f"已封禁玩家 {user.username} 🔒")


@router.post("/users/{target_id}/unban", summary="解封玩家")
async def admin_unban_user(
    target_id: int,
    user_id: int = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
) -> MessageResponse:
    result = await db.execute(select(User).where(User.id == target_id))
    user = result.scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=404, detail="玩家不存在")

    user.is_banned = 0
    await db.commit()
    return MessageResponse(message=f"已解封玩家 {user.username} 🔓")


# ============================================================
# 作物模板 CRUD
# ============================================================
@router.get("/crops", summary="作物模板列表")
async def admin_list_crops(
    user_id: int = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(CropTemplate).order_by(CropTemplate.id))
    return {"crops": [
        {
            "id": c.id,
            "name": c.name,
            "emoji": c.emoji,
            "seed_price": c.seed_price,
            "growth_seconds": c.growth_seconds,
            "produce_count": c.produce_count,
            "produce_name": c.produce_name,
            "produce_emoji": c.produce_emoji,
            "sell_price_per_unit": c.sell_price_per_unit,
            "is_active": bool(c.is_active),
        }
        for c in result.scalars().all()
    ]}


@router.post("/crops", summary="新增作物")
async def admin_create_crop(
    body: AdminCropTemplateRequest,
    user_id: int = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
):
    exists = (await db.execute(
        select(CropTemplate).where(CropTemplate.name == body.name)
    )).scalar_one_or_none()
    if exists:
        raise HTTPException(status_code=400, detail=f"作物名 '{body.name}' 已存在")

    crop = CropTemplate(**body.model_dump())
    db.add(crop)
    await db.commit()
    await db.refresh(crop)
    return {"id": crop.id, "message": f"作物 {crop.name} 已创建 ✅"}


@router.put("/crops/{crop_id}", summary="更新作物")
async def admin_update_crop(
    crop_id: int,
    body: AdminCropTemplateRequest,
    user_id: int = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(CropTemplate).where(CropTemplate.id == crop_id))
    crop = result.scalar_one_or_none()
    if crop is None:
        raise HTTPException(status_code=404, detail="作物不存在")

    for key, value in body.model_dump().items():
        setattr(crop, key, value)
    await db.commit()
    return {"message": f"作物 {crop.name} 已更新 ✅"}


@router.delete("/crops/{crop_id}", summary="删除作物")
async def admin_delete_crop(
    crop_id: int,
    user_id: int = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(CropTemplate).where(CropTemplate.id == crop_id))
    crop = result.scalar_one_or_none()
    if crop is None:
        raise HTTPException(status_code=404, detail="作物不存在")

    await db.delete(crop)
    await db.commit()
    return {"message": f"作物已删除 🗑️"}


# ============================================================
# 动物模板 CRUD
# ============================================================
@router.get("/animals", summary="动物模板列表")
async def admin_list_animals(
    user_id: int = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(AnimalTemplate).order_by(AnimalTemplate.id))
    return {"animals": [
        {
            "id": a.id,
            "name": a.name,
            "emoji": a.emoji,
            "purchase_price": a.purchase_price,
            "produce_interval_seconds": a.produce_interval_seconds,
            "produce_name": a.produce_name,
            "produce_emoji": a.produce_emoji,
            "sell_price_per_unit": a.sell_price_per_unit,
            "feed_consumption": a.feed_consumption,
            "is_active": bool(a.is_active),
        }
        for a in result.scalars().all()
    ]}


@router.post("/animals", summary="新增动物")
async def admin_create_animal(
    body: AdminAnimalTemplateRequest,
    user_id: int = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
):
    exists = (await db.execute(
        select(AnimalTemplate).where(AnimalTemplate.name == body.name)
    )).scalar_one_or_none()
    if exists:
        raise HTTPException(status_code=400, detail=f"动物名 '{body.name}' 已存在")

    animal = AnimalTemplate(**body.model_dump())
    db.add(animal)
    await db.commit()
    await db.refresh(animal)
    return {"id": animal.id, "message": f"动物 {animal.name} 已创建 ✅"}


@router.put("/animals/{animal_id}", summary="更新动物")
async def admin_update_animal(
    animal_id: int,
    body: AdminAnimalTemplateRequest,
    user_id: int = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(AnimalTemplate).where(AnimalTemplate.id == animal_id))
    animal = result.scalar_one_or_none()
    if animal is None:
        raise HTTPException(status_code=404, detail="动物不存在")

    for key, value in body.model_dump().items():
        setattr(animal, key, value)
    await db.commit()
    return {"message": f"动物 {animal.name} 已更新 ✅"}


@router.delete("/animals/{animal_id}", summary="删除动物")
async def admin_delete_animal(
    animal_id: int,
    user_id: int = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(AnimalTemplate).where(AnimalTemplate.id == animal_id))
    animal = result.scalar_one_or_none()
    if animal is None:
        raise HTTPException(status_code=404, detail="动物不存在")

    await db.delete(animal)
    await db.commit()
    return {"message": "动物已删除 🗑️"}


# ============================================================
# 商店商品 CRUD
# ============================================================
@router.get("/shop", summary="商店商品列表")
async def admin_list_shop(
    user_id: int = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(ShopItem).order_by(ShopItem.sort_order))
    return {"items": [
        {
            "id": it.id,
            "item_type": it.item_type,
            "template_id": it.template_id,
            "name": it.name,
            "emoji": it.emoji,
            "price": it.price,
            "stock": it.stock,
            "sort_order": it.sort_order,
            "is_active": bool(it.is_active),
        }
        for it in result.scalars().all()
    ]}


@router.post("/shop", summary="新增商品")
async def admin_create_shop(
    body: AdminShopItemRequest,
    user_id: int = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
):
    item = ShopItem(**body.model_dump())
    db.add(item)
    await db.commit()
    await db.refresh(item)
    return {"id": item.id, "message": f"商品 {item.name} 已上架 ✅"}


@router.put("/shop/{item_id}", summary="更新商品")
async def admin_update_shop(
    item_id: int,
    body: AdminShopItemRequest,
    user_id: int = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(ShopItem).where(ShopItem.id == item_id))
    item = result.scalar_one_or_none()
    if item is None:
        raise HTTPException(status_code=404, detail="商品不存在")

    for key, value in body.model_dump().items():
        setattr(item, key, value)
    await db.commit()
    return {"message": f"商品 {item.name} 已更新 ✅"}


@router.delete("/shop/{item_id}", summary="删除商品")
async def admin_delete_shop(
    item_id: int,
    user_id: int = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(ShopItem).where(ShopItem.id == item_id))
    item = result.scalar_one_or_none()
    if item is None:
        raise HTTPException(status_code=404, detail="商品不存在")

    await db.delete(item)
    await db.commit()
    return {"message": "商品已下架 🗑️"}


# ============================================================
# 运营统计
# ============================================================
@router.get("/stats", summary="运营统计")
async def admin_stats(
    user_id: int = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
):
    today = date.today()

    # 1. 总用户数
    total_users = (await db.execute(
        select(func.count()).select_from(User)
    )).scalar() or 0

    # 2. 日活（今天有任意一条 DailyTaskProgress 记录的用户数）
    daa_result = await db.execute(
        select(func.count(func.distinct(DailyTaskProgress.user_id)))
        .select_from(DailyTaskProgress)
        .where(DailyTaskProgress.task_date == today)
    )
    active_24h = daa_result.scalar() or 0

    # 3. 今日总收获数
    harvest_result = await db.execute(
        select(func.coalesce(func.sum(DailyTaskProgress.progress), 0))
        .select_from(DailyTaskProgress)
        .where(
            DailyTaskProgress.task_type == "harvest",
            DailyTaskProgress.task_date == today,
        )
    )
    total_crops = int(harvest_result.scalar() or 0)

    # 4. 今日总销售额（通过任务表反推 sell 进度 * 平均单价，简化：直接 sum progress * 固定值）
    sell_progress = (await db.execute(
        select(func.coalesce(func.sum(DailyTaskProgress.progress), 0))
        .select_from(DailyTaskProgress)
        .where(
            DailyTaskProgress.task_type == "sell",
            DailyTaskProgress.task_date == today,
        )
    )).scalar() or 0
    total_gold_volume = int(sell_progress) * 15  # 粗略估算

    # 5. 热门作物 Top 5（种植次数多）
    top_crop_result = await db.execute(
        select(
            CropTemplate.name,
            func.count(FarmCell.id).label("plant_count"),
        )
        .join(FarmCell, FarmCell.crop_template_id == CropTemplate.id)
        .where(FarmCell.status.in_(["growing", "ready"]))
        .group_by(CropTemplate.name)
        .order_by(func.count(FarmCell.id).desc())
        .limit(5)
    )
    top_crops = [row[0] for row in top_crop_result.all()]

    return {
        "total_users": total_users,
        "active_users_24h": active_24h,
        "total_crops_today": total_crops,
        "total_gold_volume_today": total_gold_volume,
        "top_crops": top_crops,
    }

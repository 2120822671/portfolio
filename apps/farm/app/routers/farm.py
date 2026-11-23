"""
农场路由 —— 查看 / 播种 / 收获 / 清理 / 扩建

路径前缀: /api/v1/farm
"""
from __future__ import annotations

from datetime import date as date_mod
from datetime import timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.dependencies import get_current_user
from app.models.crop import CropTemplate
from app.models.farm import FarmCell
from app.models.inventory import Inventory
from app.models.shop import ShopItem
from app.models.user import User
from app.schemas.common import MessageResponse
from app.schemas.farm import (
    FarmCellResponse,
    FarmExpandResponse,
    FarmHarvestRequest,
    FarmPlantRequest,
    FarmStatusResponse,
)
from app.services.daily_tasks import add_task_progress
from app.services.farm import infer_cell_status, seconds_until_wither
from app.utils.time_utils import now_utc, seconds_until


router = APIRouter(prefix="/farm", tags=["农场"])


# ============================================================
# GET /farm/  —— 查看完整农场状态
# ============================================================
@router.get(
    "/",
    response_model=FarmStatusResponse,
    summary="查看农场",
    description="返回当前玩家所有格子的状态快照（空地/生长中/成熟/枯萎），自动识别已成熟的作物。",
)
async def get_farm_status(
    user_id: int = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> FarmStatusResponse:
    # 1. 查用户
    user_result = await db.execute(select(User).where(User.id == user_id))
    user: Optional[User] = user_result.scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=404, detail="用户不存在")

    # 2. 查所有格子 + 关联作物模板
    cells_result = await db.execute(
        select(FarmCell, CropTemplate).outerjoin(
            CropTemplate, FarmCell.crop_template_id == CropTemplate.id
        ).where(
            FarmCell.user_id == user_id
        ).order_by(FarmCell.cell_index)
    )
    rows = cells_result.all()

    # 3. 构建响应
    cell_responses: list[FarmCellResponse] = []
    total_ready = total_growing = total_withered = 0

    for cell, crop in rows:
        # 统一推断状态（growing -> ready -> withered）
        effective_status = infer_cell_status(cell.status, cell.ready_at)
        seconds = seconds_until(cell.ready_at) if effective_status == "growing" else 0
        wither_left = (
            seconds_until_wither(cell.ready_at)
            if effective_status == "ready"
            else 0
        )

        cell_responses.append(FarmCellResponse(
            cell_index=cell.cell_index,
            status=effective_status,
            crop_name=crop.name if crop else None,
            crop_emoji=crop.emoji if crop else None,
            template_id=cell.crop_template_id,
            planted_at=cell.planted_at,
            ready_at=cell.ready_at,
            seconds_until_ready=seconds,
            seconds_until_wither=wither_left,
        ))

        # 统计
        if effective_status == "ready":
            total_ready += 1
        elif effective_status == "growing":
            total_growing += 1
        elif effective_status == "withered":
            total_withered += 1

    # 如果数据库里格子数 < cell_count（比如扩建过但没建格子），补齐空槽位
    existing_indices = {c.cell_index for c, _ in rows}
    for idx in range(user.cell_count):
        if idx not in existing_indices:
            cell_responses.append(FarmCellResponse(
                cell_index=idx,
                status="empty",
            ))

    # 按 cell_index 排序
    cell_responses.sort(key=lambda c: c.cell_index)

    return FarmStatusResponse(
        user_id=user.id,
        cell_count=user.cell_count,
        max_cell_count=settings.MAX_CELL_COUNT,
        cells=cell_responses,
        total_ready=total_ready,
        total_growing=total_growing,
        total_withered=total_withered,
    )


# ============================================================
# POST /farm/plant  —— 播种
# ============================================================
@router.post(
    "/plant",
    response_model=FarmCellResponse,
    summary="播种作物",
    description="消耗背包中的种子，在指定格子播种。格子必须是 empty 或 withered。",
)
async def plant_crop(
    body: FarmPlantRequest,
    user_id: int = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> FarmCellResponse:
    # 1. 查用户
    user_result = await db.execute(select(User).where(User.id == user_id))
    user: Optional[User] = user_result.scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=404, detail="用户不存在")

    # 2. 校验 cell_index 合法
    if body.cell_index < 0 or body.cell_index >= user.cell_count:
        raise HTTPException(
            status_code=400,
            detail=f"格子坐标越界，有效范围 0 ~ {user.cell_count - 1}",
        )

    # 3. 查格子（如果不存在则自动创建，兜底 admin 等账号漏初始化 FarmCell 的情况）
    cell_result = await db.execute(
        select(FarmCell).where(
            and_(
                FarmCell.user_id == user_id,
                FarmCell.cell_index == body.cell_index,
            )
        )
    )
    cell: Optional[FarmCell] = cell_result.scalar_one_or_none()
    if cell is None:
        cell = FarmCell(
            user_id=user_id,
            cell_index=body.cell_index,
            status="empty",
        )
        db.add(cell)
        await db.flush()

    # 校验格子状态
    effective_status = infer_cell_status(cell.status, cell.ready_at)
    if effective_status not in ("empty", "withered"):
        raise HTTPException(
            status_code=400,
            detail=f"格子当前状态为 '{effective_status}'，无法播种",
        )

    # 4. 查作物模板
    crop_result = await db.execute(
        select(CropTemplate).where(CropTemplate.id == body.template_id)
    )
    crop: Optional[CropTemplate] = crop_result.scalar_one_or_none()
    if crop is None or not crop.is_active:
        raise HTTPException(status_code=400, detail="作物模板不存在或已下架")

    # 5. 查背包种子
    inv_result = await db.execute(
        select(Inventory).where(
            and_(
                Inventory.user_id == user_id,
                Inventory.item_type == "seed",
                Inventory.template_id == body.template_id,
                Inventory.quantity > 0,
            )
        )
    )
    seed_inv: Optional[Inventory] = inv_result.scalar_one_or_none()
    if seed_inv is None or seed_inv.quantity <= 0:
        raise HTTPException(
            status_code=400,
            detail="背包里没有这种作物的种子，请先去商店购买",
        )

    # 6. 扣减种子
    seed_inv.quantity -= 1

    # 7. 更新格子
    now = now_utc()
    cell.status = "growing"
    cell.crop_template_id = crop.id
    cell.planted_at = now
    cell.ready_at = now + timedelta(seconds=crop.growth_seconds)

    await db.commit()
    await db.refresh(cell)

    return FarmCellResponse(
        cell_index=cell.cell_index,
        status="growing",
        crop_name=crop.name,
        crop_emoji=crop.emoji,
        template_id=crop.id,
        planted_at=cell.planted_at,
        ready_at=cell.ready_at,
        seconds_until_ready=crop.growth_seconds,
    )


# ============================================================
# POST /farm/harvest  —— 收获作物
# ============================================================
@router.post(
    "/harvest",
    response_model=MessageResponse,
    summary="收获作物",
    description="收获成熟作物，产出对应数量的产物到背包。",
)
async def harvest_crop(
    body: FarmHarvestRequest,
    user_id: int = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> MessageResponse:
    # 1. 查格子 + 作物
    cell_result = await db.execute(
        select(FarmCell, CropTemplate)
        .outerjoin(CropTemplate, FarmCell.crop_template_id == CropTemplate.id)
        .where(
            and_(
                FarmCell.user_id == user_id,
                FarmCell.cell_index == body.cell_index,
            )
        )
    )
    row = cell_result.first()
    if row is None:
        raise HTTPException(status_code=404, detail="格子不存在")

    cell, crop = row
    if crop is None:
        raise HTTPException(status_code=400, detail="格子是空的，没有作物")

    # 2. 校验状态
    effective_status = infer_cell_status(cell.status, cell.ready_at)
    if effective_status == "growing":
        seconds = seconds_until(cell.ready_at)
        raise HTTPException(
            status_code=400,
            detail=f"作物还在生长中，约 {seconds} 秒后成熟",
        )
    if effective_status == "empty":
        raise HTTPException(status_code=400, detail="格子是空的")
    if effective_status == "withered":
        raise HTTPException(
            status_code=400,
            detail="作物已枯萎，请先清理格子",
        )

    # 3. 往背包加产物（upsert）
    #    同时按名称匹配，兼容历史上动物产物误用作物模板 id 的脏数据
    inv_result = await db.execute(
        select(Inventory).where(
            and_(
                Inventory.user_id == user_id,
                Inventory.item_type == "produce",
                Inventory.template_id == crop.id,
                Inventory.item_name == crop.produce_name,
            )
        )
    )
    inv: Optional[Inventory] = inv_result.scalar_one_or_none()
    if inv:
        inv.quantity += crop.produce_count
    else:
        db.add(Inventory(
            user_id=user_id,
            item_type="produce",
            template_id=crop.id,
            item_name=crop.produce_name,
            quantity=crop.produce_count,
        ))

    # 4. 重置格子
    cell.status = "empty"
    cell.crop_template_id = None
    cell.planted_at = None
    cell.ready_at = None

    # 5. 更新每日任务 harvest 进度（按实际产出数量累计）
    await add_task_progress(
        db, user_id, "harvest", crop.produce_count, today=date_mod.today()
    )

    await db.commit()

    return MessageResponse(
        message=f"🎉 收获成功！获得 {crop.produce_count} 个 {crop.produce_name}",
    )


# ============================================================
# POST /farm/clear/{cell_index}  —— 清理枯萎格子
# ============================================================
@router.post(
    "/clear/{cell_index}",
    response_model=MessageResponse,
    summary="清理枯萎作物",
    description="移除枯萎（withered）状态的作物，释放格子。",
)
async def clear_withered(
    cell_index: int,
    user_id: int = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> MessageResponse:
    cell_result = await db.execute(
        select(FarmCell).where(
            and_(
                FarmCell.user_id == user_id,
                FarmCell.cell_index == cell_index,
            )
        )
    )
    cell: Optional[FarmCell] = cell_result.scalar_one_or_none()
    if cell is None:
        raise HTTPException(status_code=404, detail="格子不存在")

    effective_status = infer_cell_status(cell.status, cell.ready_at)
    if effective_status != "withered":
        raise HTTPException(
            status_code=400,
            detail=f"格子当前状态为 '{effective_status}'，无需清理",
        )

    cell.status = "empty"
    cell.crop_template_id = None
    cell.planted_at = None
    cell.ready_at = None

    await db.commit()
    return MessageResponse(message="已清理枯萎作物 🍂")


# ============================================================
# POST /farm/expand  —— 扩建
# ============================================================
@router.post(
    "/expand",
    response_model=FarmExpandResponse,
    summary="扩建土地",
    description="消耗金币解锁一个新格子，最大上限 settings.MAX_CELL_COUNT (25)。",
)
async def expand_farm(
    user_id: int = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> FarmExpandResponse:
    # 1. 查用户
    user_result = await db.execute(select(User).where(User.id == user_id))
    user: Optional[User] = user_result.scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=404, detail="用户不存在")

    # 2. 检查上限
    if user.cell_count >= settings.MAX_CELL_COUNT:
        raise HTTPException(
            status_code=400,
            detail=f"已达到最大格子数上限 ({settings.MAX_CELL_COUNT})",
        )

    # 3. 查扩建价格（优先从商店取，没有则用配置值）
    shop_result = await db.execute(
        select(ShopItem)
        .where(ShopItem.item_type == "expansion", ShopItem.is_active == 1)
        .order_by(ShopItem.id)
        .limit(1)
    )
    shop_item: Optional[ShopItem] = shop_result.scalars().first()
    cost = shop_item.price if shop_item else settings.EXPAND_COST

    # 4. 检查金币
    if user.gold < cost:
        raise HTTPException(
            status_code=400,
            detail=f"金币不足，扩建需要 {cost} 金币（当前 {user.gold}）",
        )

    # 5. 扣费 + 扩建
    before = user.cell_count
    user.gold -= cost
    user.cell_count += 1

    new_cell_index = before
    db.add(FarmCell(
        user_id=user.id,
        cell_index=new_cell_index,
        status="empty",
    ))

    await db.commit()

    return FarmExpandResponse(
        cell_count_before=before,
        cell_count_after=user.cell_count,
        gold_spent=cost,
        gold_remaining=user.gold,
        new_cell_index=new_cell_index,
    )

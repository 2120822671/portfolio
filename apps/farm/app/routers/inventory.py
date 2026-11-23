"""
背包路由 —— 查询玩家背包

路径前缀: /api/v1/inventory
"""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_user
from app.models.inventory import Inventory
from app.schemas.inventory import InventoryListResponse
from app.services.produce import load_produce_catalog, resolve_produce_meta


router = APIRouter(prefix="/inventory", tags=["背包"])


# ============================================================
# GET /inventory/  —— 查询背包
# ============================================================
@router.get(
    "/",
    response_model=InventoryListResponse,
    summary="查看背包",
    description="返回当前玩家背包中的所有物品（种子/产物/饲料），按类型分组统计总数。",
)
async def get_inventory(
    user_id: int = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> InventoryListResponse:
    # 1. 查询所有数量 > 0 的物品
    result = await db.execute(
        select(Inventory).where(
            and_(
                Inventory.user_id == user_id,
                Inventory.quantity > 0,
            )
        )
    )
    inv_list = result.scalars().all()

    # 2. 一次性加载模板索引，统一解析图标与售价
    catalog = await load_produce_catalog(db)

    # 3. 构建响应
    items = []
    total_seed = total_produce = total_feed = 0

    for inv in inv_list:
        emoji = "📦"
        sell_price = None

        if inv.item_type == "produce":
            meta = resolve_produce_meta(catalog, inv.template_id, inv.item_name)
            if meta:
                emoji = meta["emoji"]
                sell_price = meta["unit_price"]
        elif inv.item_type == "seed":
            crop = catalog.crops_by_id.get(inv.template_id) if inv.template_id else None
            emoji = crop.emoji if crop else "🌰"
        elif inv.item_type == "animal":
            animal = catalog.animals_by_id.get(inv.template_id) if inv.template_id else None
            emoji = animal.emoji if animal else "🐾"
        elif inv.item_type == "feed":
            emoji = "🌾"

        items.append({
            "id": inv.id,
            "item_type": inv.item_type,
            "item_name": inv.item_name,
            "template_id": inv.template_id,
            "quantity": inv.quantity,
            "emoji": emoji,
            "sell_price_per_unit": sell_price,
        })

        if inv.item_type == "seed":
            total_seed += inv.quantity
        elif inv.item_type == "produce":
            total_produce += inv.quantity
        elif inv.item_type == "feed":
            total_feed += inv.quantity

    return InventoryListResponse(
        items=items,
        total_seed=total_seed,
        total_produce=total_produce,
        total_feed=total_feed,
    )

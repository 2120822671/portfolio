"""
商店路由 —— 浏览 / 购买 / 出售产物

路径前缀: /api/v1/shop
"""
from __future__ import annotations

from datetime import date as date_mod
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.dependencies import get_current_user
from app.models.animal import AnimalTemplate, PlayerAnimal
from app.models.crop import CropTemplate
from app.models.farm import FarmCell
from app.models.inventory import Inventory
from app.models.shop import ShopItem
from app.models.user import User
from app.schemas.shop import (
    ShopBuyRequest,
    ShopBuyResponse,
    ShopSellRequest,
    ShopSellResponse,
)
from app.services.daily_tasks import add_task_progress
from app.services.produce import load_produce_catalog, resolve_produce_meta
from app.utils.time_utils import now_utc


router = APIRouter(prefix="/shop", tags=["商店"])


def _duration_text(seconds: int) -> str:
    """把秒数转成适合商店描述的中文时长"""
    if seconds >= 3600:
        hours = seconds / 3600
        return f"{hours:g} 小时"
    return f"{max(1, seconds // 60)} 分钟"


# ============================================================
# GET /shop/items  —— 浏览商店商品（公开，无需登录）
# ============================================================
@router.get(
    "/items",
    summary="浏览商店商品",
    description="返回系统商店所有上架商品（种子/动物/饲料/扩建），无需登录。",
)
async def browse_shop(
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(ShopItem).where(
            and_(
                ShopItem.is_active == 1,
                ShopItem.stock != 0,
            )
        ).order_by(ShopItem.sort_order)
    )
    items = result.scalars().all()

    # 额外信息查询（一次性查出所有模板）
    crop_ids = {it.template_id for it in items if it.item_type == "seed" and it.template_id}
    animal_ids = {it.template_id for it in items if it.item_type == "animal" and it.template_id}

    crops_map = {}
    if crop_ids:
        cr = await db.execute(select(CropTemplate).where(CropTemplate.id.in_(crop_ids)))
        crops_map = {c.id: c for c in cr.scalars().all()}

    animals_map = {}
    if animal_ids:
        ar = await db.execute(select(AnimalTemplate).where(AnimalTemplate.id.in_(animal_ids)))
        animals_map = {a.id: a for a in ar.scalars().all()}

    shop_list = []
    for it in items:
        desc = ""
        if it.item_type == "seed" and it.template_id in crops_map:
            c = crops_map[it.template_id]
            desc = (
                f"🌱 生长约 {_duration_text(c.growth_seconds)} | "
                f"产 {c.produce_count} 个 {c.produce_name}"
            )
        elif it.item_type == "animal" and it.template_id in animals_map:
            a = animals_map[it.template_id]
            desc = (
                f"🐾 每 {_duration_text(a.produce_interval_seconds)}产 {a.produce_name}"
                f" | 每次耗 {a.feed_consumption} 饲料"
            )
        elif it.item_type == "feed":
            desc = "🍚 动物饲料，每轮生产消耗（断粮会停产）"
        elif it.item_type == "expansion":
            desc = "🟩 解锁一块新土地"

        shop_list.append({
            "id": it.id,
            "item_type": it.item_type,
            "name": it.name,
            "emoji": it.emoji,
            "price": it.price,
            "stock": it.stock,
            "template_id": it.template_id,
            "description": desc,
        })

    return {"items": shop_list, "total": len(shop_list)}


# ============================================================
# POST /shop/buy  —— 购买商品
# ============================================================
@router.post(
    "/buy",
    response_model=ShopBuyResponse,
    summary="购买商品",
    description="从商店购买商品，消耗金币。动物会直接进入农场，扩建每次只能买 1 块。",
)
async def buy_item(
    body: ShopBuyRequest,
    user_id: int = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ShopBuyResponse:
    # 1. 查用户
    user_result = await db.execute(select(User).where(User.id == user_id))
    user: Optional[User] = user_result.scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=404, detail="用户不存在")

    # 2. 查商店商品
    shop_result = await db.execute(select(ShopItem).where(ShopItem.id == body.item_id))
    shop_item: Optional[ShopItem] = shop_result.scalar_one_or_none()
    if shop_item is None or shop_item.is_active != 1:
        raise HTTPException(status_code=400, detail="商品不存在或已下架")

    item_type = shop_item.item_type

    # 3. 先做类型相关的业务校验，全部通过后再扣金币，避免部分回滚
    crop: Optional[CropTemplate] = None
    if item_type == "expansion":
        if body.quantity != 1:
            raise HTTPException(status_code=400, detail="土地扩建每次只能购买 1 块")
        if user.cell_count >= settings.MAX_CELL_COUNT:
            raise HTTPException(
                status_code=400,
                detail=f"已达到最大格子数上限 ({settings.MAX_CELL_COUNT})",
            )
    elif item_type == "animal":
        animal_tpl = (await db.execute(
            select(AnimalTemplate).where(AnimalTemplate.id == shop_item.template_id)
        )).scalar_one_or_none()
        if animal_tpl is None or animal_tpl.is_active != 1:
            raise HTTPException(status_code=400, detail="动物模板不存在或已下架")
    elif item_type == "seed":
        crop = (await db.execute(
            select(CropTemplate).where(CropTemplate.id == shop_item.template_id)
        )).scalar_one_or_none()
        if crop is None or crop.is_active != 1:
            raise HTTPException(status_code=400, detail="作物模板不存在或已下架")
    elif item_type != "feed":
        raise HTTPException(status_code=400, detail="未知商品类型")

    # 4. 库存检查
    if shop_item.stock != -1 and shop_item.stock < body.quantity:
        raise HTTPException(
            status_code=400,
            detail=f"库存不足，剩余 {shop_item.stock}",
        )

    # 5. 计算总费用并检查金币
    total_cost = shop_item.price * body.quantity
    if user.gold < total_cost:
        raise HTTPException(
            status_code=400,
            detail=f"金币不足，需要 {total_cost}（当前 {user.gold}）",
        )

    # 6. 扣金币
    user.gold -= total_cost

    # 7. 按类型执行入库逻辑
    if item_type == "expansion":
        db.add(FarmCell(
            user_id=user.id,
            cell_index=user.cell_count,
            status="empty",
        ))
        user.cell_count += 1

    elif item_type == "animal":
        now = now_utc()
        for _ in range(body.quantity):
            db.add(PlayerAnimal(
                user_id=user.id,
                animal_template_id=shop_item.template_id,
                last_produce_at=now,  # 购买后自动开始首轮生产
                is_alive=1,
            ))

    else:  # seed / feed
        inv_result = await db.execute(
            select(Inventory).where(
                and_(
                    Inventory.user_id == user_id,
                    Inventory.item_type == item_type,
                    Inventory.template_id == shop_item.template_id,
                )
            ).order_by(Inventory.id)
        )
        inv: Optional[Inventory] = inv_result.scalars().first()

        if inv:
            inv.quantity += body.quantity
        else:
            if item_type == "seed" and crop is not None:
                item_name = f"{crop.name}种子"
            else:
                item_name = shop_item.name
            db.add(Inventory(
                user_id=user.id,
                item_type=item_type,
                template_id=shop_item.template_id,
                item_name=item_name,
                quantity=body.quantity,
            ))

    # 8. 扣库存（非无限）
    if shop_item.stock != -1:
        shop_item.stock -= body.quantity

    await db.commit()

    return ShopBuyResponse(
        item_id=shop_item.id,
        item_name=shop_item.name,
        quantity=body.quantity,
        gold_spent=total_cost,
        gold_remaining=user.gold,
    )


# ============================================================
# POST /shop/sell  —— 出售产物
# ============================================================
@router.post(
    "/sell",
    response_model=ShopSellResponse,
    summary="出售产物",
    description="将背包中的产物按单价卖给系统，获得金币。",
)
async def sell_produce(
    body: ShopSellRequest,
    user_id: int = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ShopSellResponse:
    # 1. 查背包物品
    inv_result = await db.execute(
        select(Inventory).where(
            and_(
                Inventory.id == body.inventory_id,
                Inventory.user_id == user_id,
                Inventory.item_type == "produce",
            )
        )
    )
    inv: Optional[Inventory] = inv_result.scalar_one_or_none()
    if inv is None:
        raise HTTPException(status_code=404, detail="背包中没有该物品")

    # 2. 校验数量
    if inv.quantity < body.quantity:
        raise HTTPException(
            status_code=400,
            detail=f"数量不足，背包里只有 {inv.quantity}",
        )

    # 3. 统一解析单价（作物产物 / 动物产物）
    catalog = await load_produce_catalog(db)
    meta = resolve_produce_meta(catalog, inv.template_id, inv.item_name)
    if meta is None:
        raise HTTPException(status_code=400, detail="该产物无法出售")

    price_per_unit = meta["unit_price"]
    item_name = inv.item_name

    # 4. 计算收益 + 扣库存
    total_earned = price_per_unit * body.quantity
    user_result = await db.execute(select(User).where(User.id == user_id))
    user: Optional[User] = user_result.scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=404, detail="用户不存在")
    user.gold += total_earned

    inv.quantity -= body.quantity
    if inv.quantity <= 0:
        await db.delete(inv)

    # 5. 更新每日任务 sell 进度
    await add_task_progress(
        db, user_id, "sell", body.quantity, today=date_mod.today()
    )

    await db.commit()

    return ShopSellResponse(
        item_name=item_name,
        quantity=body.quantity,
        gold_earned=total_earned,
        gold_remaining=user.gold,
    )

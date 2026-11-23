"""
动物路由 —— 查看 / 喂养 / 采集 / 出售

路径前缀: /api/v1/animals

养殖规则:
    last_produce_at = 本轮生产的开始时间，NULL 表示停产待喂养。
    - 购买后自动开始首轮生产
    - 达到生产间隔后可采集一次
    - 采集后回到待喂养状态，需要再次消耗饲料
    - 断粮时无法喂养，生产自然停止（不会产出）
"""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_user
from app.models.animal import AnimalTemplate, PlayerAnimal
from app.models.inventory import Inventory
from app.models.user import User
from app.schemas.common import MessageResponse
from app.services.produce import animal_produce_ref
from app.utils.time_utils import ensure_aware, now_utc


router = APIRouter(prefix="/animals", tags=["动物"])


def _animal_state(pa: PlayerAnimal, tpl: Optional[AnimalTemplate], now) -> tuple[str, int]:
    """返回 (状态, 距离可采集剩余秒数)"""
    if not pa.is_alive:
        return "dead", 0
    if tpl is None or pa.last_produce_at is None:
        return "hungry", 0

    start = ensure_aware(pa.last_produce_at)
    if start is None:
        return "hungry", 0

    elapsed = (now - start).total_seconds()
    remain = max(0, int(tpl.produce_interval_seconds - elapsed))
    return ("ready" if remain <= 0 else "producing"), remain


# ============================================================
# GET /animals/  —— 查看玩家所有动物
# ============================================================
@router.get(
    "/",
    summary="查看我的动物",
    description="返回玩家农场里的所有动物，包括生产状态与距离下次可采集的剩余时间。",
)
async def list_animals(
    user_id: int = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(PlayerAnimal, AnimalTemplate)
        .outerjoin(AnimalTemplate, PlayerAnimal.animal_template_id == AnimalTemplate.id)
        .where(PlayerAnimal.user_id == user_id)
        .order_by(PlayerAnimal.id)
    )
    rows = result.all()
    now = now_utc()

    animals = []
    for pa, tpl in rows:
        state, seconds_left = _animal_state(pa, tpl, now)
        animals.append({
            "id": pa.id,
            "name": tpl.name if tpl else "未知",
            "emoji": tpl.emoji if tpl else "🐾",
            "produce_name": tpl.produce_name if tpl else "",
            "produce_emoji": tpl.produce_emoji if tpl else "",
            "produce_sell_price": tpl.sell_price_per_unit if tpl else 0,
            "feed_consumption": tpl.feed_consumption if tpl else 1,
            "ready_in_seconds": seconds_left,
            "state": state,
            "is_alive": bool(pa.is_alive),
        })

    return {
        "animals": animals,
        "total": len(animals),
        "ready_count": sum(1 for a in animals if a["state"] == "ready"),
        "hungry_count": sum(1 for a in animals if a["state"] == "hungry"),
    }


# ============================================================
# POST /animals/feed  —— 喂养待产动物
# ============================================================
@router.post(
    "/feed",
    response_model=MessageResponse,
    summary="喂养动物",
    description="消耗背包中的饲料，让处于停产状态的动物开始新一轮生产。",
)
async def feed_all_animals(
    user_id: int = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> MessageResponse:
    # 1. 查所有存活动物 + 模板
    animals_result = await db.execute(
        select(PlayerAnimal, AnimalTemplate)
        .outerjoin(AnimalTemplate, PlayerAnimal.animal_template_id == AnimalTemplate.id)
        .where(
            and_(
                PlayerAnimal.user_id == user_id,
                PlayerAnimal.is_alive == 1,
            )
        )
    )
    rows = animals_result.all()
    if not rows:
        return MessageResponse(message="农场里还没有动物")

    # 2. 只喂养停产中的动物，避免重置正在生产动物的进度
    idle_rows = [(pa, tpl) for pa, tpl in rows if pa.last_produce_at is None]
    if not idle_rows:
        return MessageResponse(message="所有动物都在生产中，暂时不需要喂养")

    total_needed = sum((tpl.feed_consumption if tpl else 1) for _, tpl in idle_rows)

    # 3. 汇总饲料库存（历史数据可能存在多行饲料记录）
    feed_result = await db.execute(
        select(Inventory).where(
            and_(
                Inventory.user_id == user_id,
                Inventory.item_type == "feed",
                Inventory.quantity > 0,
            )
        ).order_by(Inventory.id)
    )
    feed_rows = feed_result.scalars().all()
    feed_total = sum(inv.quantity for inv in feed_rows)

    if feed_total < total_needed:
        raise HTTPException(
            status_code=400,
            detail=f"饲料不足！需要 {total_needed}，背包里只有 {feed_total}",
        )

    # 4. 扣饲料
    remaining = total_needed
    for inv in feed_rows:
        if remaining <= 0:
            break
        take = min(inv.quantity, remaining)
        inv.quantity -= take
        remaining -= take
        if inv.quantity <= 0:
            await db.delete(inv)

    # 5. 启动新一轮生产
    now = now_utc()
    for pa, _ in idle_rows:
        pa.last_produce_at = now

    await db.commit()
    return MessageResponse(
        message=f"🌾 已喂养 {len(idle_rows)} 只动物，消耗 {total_needed} 份饲料",
    )


# ============================================================
# POST /animals/collect/{animal_id}  —— 采集副产品
# ============================================================
@router.post(
    "/collect/{animal_id}",
    response_model=MessageResponse,
    summary="采集副产品",
    description="采集指定动物的副产品（蛋/毛/奶），加入背包。采集后需要重新喂养。",
)
async def collect_produce(
    animal_id: int,
    user_id: int = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> MessageResponse:
    # 1. 查动物 + 模板
    result = await db.execute(
        select(PlayerAnimal, AnimalTemplate)
        .outerjoin(AnimalTemplate, PlayerAnimal.animal_template_id == AnimalTemplate.id)
        .where(PlayerAnimal.id == animal_id)
    )
    row = result.first()
    if row is None:
        raise HTTPException(status_code=404, detail="动物不存在")

    pa, tpl = row
    if pa.user_id != user_id:
        raise HTTPException(status_code=403, detail="这只动物不属于你")
    if not pa.is_alive:
        raise HTTPException(status_code=400, detail="这只动物已停止生产")
    if tpl is None:
        raise HTTPException(status_code=400, detail="动物模板异常")
    if pa.last_produce_at is None:
        raise HTTPException(status_code=400, detail="动物还没有开始生产，请先喂养")

    # 2. 检查是否到了采集时间
    now = now_utc()
    start = ensure_aware(pa.last_produce_at)
    elapsed = (now - start).total_seconds() if start else 0
    if elapsed < tpl.produce_interval_seconds:
        seconds_left = int(tpl.produce_interval_seconds - elapsed)
        raise HTTPException(
            status_code=400,
            detail=f"距离下次产出还需要 {seconds_left} 秒",
        )

    # 3. 更新背包（动物产物使用负模板 id，与作物产物隔离）
    produce_ref = animal_produce_ref(tpl.id)
    inv_result = await db.execute(
        select(Inventory).where(
            and_(
                Inventory.user_id == user_id,
                Inventory.item_type == "produce",
                Inventory.template_id == produce_ref,
            )
        )
    )
    inv: Optional[Inventory] = inv_result.scalar_one_or_none()
    if inv:
        inv.quantity += 1
    else:
        db.add(Inventory(
            user_id=user_id,
            item_type="produce",
            template_id=produce_ref,
            item_name=tpl.produce_name,
            quantity=1,
        ))

    # 4. 采集后停止生产，等待下一次喂养
    pa.last_produce_at = None

    await db.commit()
    return MessageResponse(
        message=f"✨ 采集成功！获得 1 个 {tpl.produce_name}，下一轮请先喂养",
    )


# ============================================================
# DELETE /animals/{animal_id}  —— 出售动物
# ============================================================
@router.delete(
    "/{animal_id}",
    response_model=MessageResponse,
    summary="出售动物",
    description="以购入价 50% 卖给系统，获得金币。",
)
async def sell_animal(
    animal_id: int,
    user_id: int = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> MessageResponse:
    result = await db.execute(
        select(PlayerAnimal, AnimalTemplate)
        .outerjoin(AnimalTemplate, PlayerAnimal.animal_template_id == AnimalTemplate.id)
        .where(PlayerAnimal.id == animal_id)
    )
    row = result.first()
    if row is None:
        raise HTTPException(status_code=404, detail="动物不存在")

    pa, tpl = row
    if pa.user_id != user_id:
        raise HTTPException(status_code=403, detail="这只动物不属于你")

    refund = (tpl.purchase_price // 2) if tpl else 0

    user_result = await db.execute(select(User).where(User.id == user_id))
    user: Optional[User] = user_result.scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=404, detail="用户不存在")

    user.gold += refund

    await db.delete(pa)
    await db.commit()

    return MessageResponse(message=f"💰 动物已出售，获得 {refund} 金币")

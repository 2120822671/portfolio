"""
种子数据脚本 —— 内置游戏的初始数据

职责:
    1. 内置 5 种基础作物（小麦/胡萝卜/番茄/玉米/草莓）
    2. 内置 3 种动物（鸡/羊/牛）
    3. 自动创建商店商品（种子/动物/饲料/扩建）
    4. 创建默认管理员账号

设计原则:
    - 幂等: 已存在则跳过，不会重复插入
    - 可重复执行: 每次启动都可以安全调用
"""
from __future__ import annotations

import asyncio
import logging

from sqlalchemy import select

from app.config import settings
from app.database import AsyncSessionLocal
from app.models import (
    AnimalTemplate,
    CropTemplate,
    FarmCell,
    ShopItem,
    User,
)
from app.models.inventory import Inventory
from app.utils.security import hash_password

logger = logging.getLogger(__name__)


# ============================================================
# 内置数据
# ============================================================
BUILTIN_CROPS = [
    # (name, emoji, seed_price, growth_seconds, produce_count, produce_name, produce_emoji, sell_price_per_unit)
    ("小麦",     "🌾",  10, 300,   3, "小麦颗粒",  "🌾", 5),
    ("胡萝卜",   "🥕",  20, 600,   2, "胡萝卜",    "🥕", 15),
    ("番茄",     "🍅",  50, 1200,  4, "番茄",      "🍅", 20),
    ("玉米",     "🌽",  80, 1800,  5, "玉米棒",    "🌽", 25),
    ("草莓",     "🍓",  150, 3600, 3, "草莓",      "🍓", 80),
]

BUILTIN_ANIMALS = [
    # (name, emoji, purchase_price, produce_interval, produce_name, produce_emoji, sell_price, feed_consumption)
    ("鸡",   "🐔",  200, 3600,  "鸡蛋", "🥚", 30, 1),
    ("羊",   "🐑",  500, 7200,  "羊毛", "🧶", 60, 2),
    ("牛",   "🐄",  1000, 10800, "牛奶", "🥛", 100, 3),
]

BUILTIN_FEED = {
    "name": "饲料",
    "emoji": "🌾",
    "price": 5,
}

BUILTIN_EXPANSION = {
    "name": "土地扩建 +1 格",
    "emoji": "🟩",
    "price": settings.EXPAND_COST,
}


# ============================================================
# 主入口
# ============================================================
async def run_seed() -> None:
    """一键初始化全部种子数据"""
    # 确保所有 ORM 模型已注册到 Base.metadata
    from app.models import _ensure_all_models_imported  # noqa: F401
    # 先建表（幂等，已存在则跳过）
    from app.database import engine, Base
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with AsyncSessionLocal() as db:
        await _seed_crops(db)
        await _seed_animals(db)
        await _seed_shop(db)
        await _seed_admin(db)
        await _repair_produce_attribution(db)
        await db.commit()
    logger.info("🌱 种子数据初始化完成")


# ============================================================
# 各模块种子函数
# ============================================================
async def _seed_crops(db) -> None:
    """初始化作物模板"""
    for name, emoji, seed_price, growth_s, produce_count, produce_name, produce_emoji, sell_price in BUILTIN_CROPS:
        result = await db.execute(
            select(CropTemplate).where(CropTemplate.name == name)
        )
        existing = result.scalar_one_or_none()
        if existing:
            continue

        crop = CropTemplate(
            name=name,
            emoji=emoji,
            seed_price=seed_price,
            growth_seconds=growth_s,
            produce_count=produce_count,
            produce_name=produce_name,
            produce_emoji=produce_emoji,
            sell_price_per_unit=sell_price,
            is_active=1,
        )
        db.add(crop)
        logger.debug(f"  + 作物: {name}")
    await db.flush()


async def _seed_animals(db) -> None:
    """初始化动物模板"""
    for name, emoji, price, interval, produce, p_emoji, sell_price, feed in BUILTIN_ANIMALS:
        result = await db.execute(
            select(AnimalTemplate).where(AnimalTemplate.name == name)
        )
        if result.scalar_one_or_none():
            continue

        animal = AnimalTemplate(
            name=name,
            emoji=emoji,
            purchase_price=price,
            produce_interval_seconds=interval,
            produce_name=produce,
            produce_emoji=p_emoji,
            sell_price_per_unit=sell_price,
            feed_consumption=feed,
            is_active=1,
        )
        db.add(animal)
        logger.debug(f"  + 动物: {name}")
    await db.flush()


async def _seed_shop(db) -> None:
    """初始化商店商品"""
    # 1. 种子 —— 每个作物模板生成一个 ShopItem
    crop_result = await db.execute(select(CropTemplate))
    crops = crop_result.scalars().all()
    for crop in crops:
        exists = (await db.execute(
            select(ShopItem).where(
                ShopItem.item_type == "seed",
                ShopItem.template_id == crop.id,
            )
        )).scalar_one_or_none()
        if exists:
            continue

        db.add(ShopItem(
            item_type="seed",
            template_id=crop.id,
            name=f"{crop.name}种子",
            emoji="🌰",
            price=crop.seed_price,
            sort_order=crop.id,
            is_active=1,
        ))
        logger.debug(f"  + 商店: {crop.name}种子")

    # 2. 动物 —— 每个动物模板生成一个 ShopItem
    animal_result = await db.execute(select(AnimalTemplate))
    animals = animal_result.scalars().all()
    for animal in animals:
        exists = (await db.execute(
            select(ShopItem).where(
                ShopItem.item_type == "animal",
                ShopItem.template_id == animal.id,
            )
        )).scalar_one_or_none()
        if exists:
            continue

        db.add(ShopItem(
            item_type="animal",
            template_id=animal.id,
            name=f"幼年{animal.name}",
            emoji=animal.emoji,
            price=animal.purchase_price,
            sort_order=50 + animal.id,
            is_active=1,
        ))
        logger.debug(f"  + 商店: 幼年{animal.name}")

    # 3. 饲料
    feed_exists = (await db.execute(
        select(ShopItem).where(ShopItem.item_type == "feed")
    )).scalar_one_or_none()
    if not feed_exists:
        db.add(ShopItem(
            item_type="feed",
            name=BUILTIN_FEED["name"],
            emoji=BUILTIN_FEED["emoji"],
            price=BUILTIN_FEED["price"],
            sort_order=100,
            is_active=1,
        ))
        logger.debug(f"  + 商店: 饲料")

    # 4. 土地扩建
    expansion_exists = (await db.execute(
        select(ShopItem).where(ShopItem.item_type == "expansion")
    )).scalar_one_or_none()
    if not expansion_exists:
        db.add(ShopItem(
            item_type="expansion",
            name=BUILTIN_EXPANSION["name"],
            emoji=BUILTIN_EXPANSION["emoji"],
            price=BUILTIN_EXPANSION["price"],
            sort_order=200,
            is_active=1,
        ))
        logger.debug(f"  + 商店: 土地扩建")

    await db.flush()


async def _seed_admin(db) -> None:
    """确保管理员账号存在，并初始化其 FarmCell"""
    result = await db.execute(
        select(User).where(User.username == settings.ADMIN_USERNAME)
    )
    admin = result.scalar_one_or_none()

    if admin is None:
        admin = User(
            username=settings.ADMIN_USERNAME,
            password_hash=hash_password(settings.ADMIN_PASSWORD),
            gold=999999,
            level=99,
            cell_count=settings.MAX_CELL_COUNT,
            role="admin",
            is_banned=0,
        )
        db.add(admin)
        await db.flush()  # 拿到 admin.id
        logger.info(
            f"  + 管理员账号已创建: {settings.ADMIN_USERNAME} / {settings.ADMIN_PASSWORD}"
        )

    # 确保 admin 有 cell_count 个 FarmCell（幂等，补齐缺失的）
    if admin.cell_count and admin.cell_count > 0:
        existing_result = await db.execute(
            select(FarmCell.cell_index).where(FarmCell.user_id == admin.id)
        )
        existing_indices = {row[0] for row in existing_result.all()}
        for idx in range(admin.cell_count):
            if idx not in existing_indices:
                db.add(FarmCell(
                    user_id=admin.id,
                    cell_index=idx,
                    status="empty",
                ))
        await db.flush()


async def _repair_produce_attribution(db) -> None:
    """
    修复历史动物产物归属错误（幂等）。

    早期版本动物产物直接复用了动物模板 id（正数），会与作物产物撞号。
    现在约定动物产物使用负模板 id，这里把旧数据迁移过去；
    如果同一用户已有正确的负 id 行，则合并数量后删除旧行。
    """
    animal_result = await db.execute(select(AnimalTemplate))
    animals = animal_result.scalars().all()
    ref_by_name = {a.produce_name: -a.id for a in animals}
    if not ref_by_name:
        return

    inv_result = await db.execute(
        select(Inventory).where(Inventory.item_type == "produce")
    )
    rows = inv_result.scalars().all()
    keyed = {(inv.user_id, inv.template_id): inv for inv in rows}

    repaired = 0
    for inv in rows:
        target = ref_by_name.get(inv.item_name)
        if target is None or inv.template_id == target:
            continue

        old_key = (inv.user_id, inv.template_id)
        existing = keyed.get((inv.user_id, target))
        if existing is not None and existing.id != inv.id:
            existing.quantity += inv.quantity
            await db.delete(inv)
        else:
            inv.template_id = target
            keyed[(inv.user_id, target)] = inv
        keyed.pop(old_key, None)
        repaired += 1

    if repaired:
        logger.info(f"  ~ 已修复 {repaired} 条动物产物归属数据")
    await db.flush()


if __name__ == "__main__":
    # 允许直接运行 python scripts/seed_data.py 进行手动初始化
    asyncio.run(run_seed())

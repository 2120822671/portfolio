"""
产物归属与定价解析

背景:
    inventory 表只有 template_id 一个关联字段，但"作物产物"和"动物产物"
    都会写进 item_type='produce'。如果两者共用正数 id，就会出现:
        - 鸡蛋(template_id=1) 被当成小麦产物，图标/售价全错；
        - 小麦产物与鸡蛋落到同一行，互相覆盖数量。

约定:
    作物产物: template_id =  crop_templates.id   （正数）
    动物产物: template_id = -animal_templates.id  （负数）

这样无需新增数据库列即可彻底隔离两类产物；历史错位数据由
scripts/seed_data.py 中的 repair 函数做一次性幂等修复。
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.animal import AnimalTemplate
from app.models.crop import CropTemplate


def animal_produce_ref(animal_id: int) -> int:
    """动物产物在 inventory.template_id 中的引用值（负数）"""
    return -abs(animal_id)


@dataclass(frozen=True)
class ProduceCatalog:
    """一次性加载的作物/动物模板索引，供批量解析使用"""

    crops_by_id: Dict[int, CropTemplate]
    animals_by_id: Dict[int, AnimalTemplate]
    crop_produce_by_name: Dict[str, CropTemplate]
    animal_produce_by_name: Dict[str, AnimalTemplate]


async def load_produce_catalog(db: AsyncSession) -> ProduceCatalog:
    """加载产物解析所需的模板索引（两张模板表都很小，全量读取即可）"""
    crops = (await db.execute(select(CropTemplate))).scalars().all()
    animals = (await db.execute(select(AnimalTemplate))).scalars().all()

    return ProduceCatalog(
        crops_by_id={c.id: c for c in crops},
        animals_by_id={a.id: a for a in animals},
        crop_produce_by_name={c.produce_name: c for c in crops},
        animal_produce_by_name={a.produce_name: a for a in animals},
    )


def resolve_produce_meta(
    catalog: ProduceCatalog,
    template_id: Optional[int],
    item_name: Optional[str],
) -> Optional[Dict[str, Any]]:
    """
    解析一条 produce 背包记录对应的展示信息。

    优先按 template_id 的符号判断归属；名称匹配作为兜底，
    用于兼容修复前写入的历史数据。
    """
    crop: Optional[CropTemplate] = None
    animal: Optional[AnimalTemplate] = None

    if template_id is not None:
        if template_id < 0:
            animal = catalog.animals_by_id.get(-template_id)
        else:
            crop = catalog.crops_by_id.get(template_id)

    # 名称优先兜底：历史数据里鸡蛋可能被写成 crop_template_id=1
    if item_name:
        named_animal = catalog.animal_produce_by_name.get(item_name)
        named_crop = catalog.crop_produce_by_name.get(item_name)
        if named_animal is not None:
            animal, crop = named_animal, None
        elif named_crop is not None and crop is None:
            crop = named_crop

    if animal is not None:
        return {
            "name": animal.produce_name,
            "emoji": animal.produce_emoji,
            "unit_price": animal.sell_price_per_unit,
            "source": "animal",
        }
    if crop is not None:
        return {
            "name": crop.produce_name,
            "emoji": crop.produce_emoji,
            "unit_price": crop.sell_price_per_unit,
            "source": "crop",
        }
    return None

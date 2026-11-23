"""
背包模块 DTO
"""
from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel


class InventoryItemResponse(BaseModel):
    """背包中的单个物品"""
    id: int
    item_type: str                  # seed / produce / animal / feed
    item_name: str
    template_id: Optional[int] = None
    quantity: int
    # 附加信息（方便前端展示）
    emoji: str = "📦"
    # 如果是可出售的产物，附带单价
    sell_price_per_unit: Optional[int] = None


class InventoryListResponse(BaseModel):
    """背包完整列表"""
    items: List[InventoryItemResponse]
    # 按类型分组统计（给前端概览用）
    total_seed: int = 0
    total_produce: int = 0
    total_feed: int = 0

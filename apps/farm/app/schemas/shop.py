"""
商店模块 DTO —— 浏览商品 / 购买 / 出售
"""
from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel, Field


# ============================================================
# 请求体
# ============================================================
class ShopBuyRequest(BaseModel):
    """购买商品"""
    item_id: int = Field(..., gt=0, description="商店商品 ID")
    quantity: int = Field(..., gt=0, description="购买数量")


class ShopSellRequest(BaseModel):
    """出售产物"""
    inventory_id: int = Field(..., gt=0, description="背包物品 ID")
    quantity: int = Field(..., gt=0, description="出售数量")


# ============================================================
# 响应体
# ============================================================
class ShopItemResponse(BaseModel):
    """商店商品详情（浏览时返回）"""
    id: int
    item_type: str                  # seed / animal / feed / expansion
    name: str
    emoji: str
    price: int
    stock: int                      # -1 表示无限
    template_id: Optional[int] = None

    # 商品说明（根据类型自动生成）
    description: str = ""


class ShopBuyResponse(BaseModel):
    """购买成功响应"""
    item_id: int
    item_name: str
    quantity: int
    gold_spent: int
    gold_remaining: int


class ShopSellResponse(BaseModel):
    """出售成功响应"""
    item_name: str
    quantity: int
    gold_earned: int
    gold_remaining: int


class ShopItemListResponse(BaseModel):
    """商品列表"""
    items: List[ShopItemResponse]
    total: int

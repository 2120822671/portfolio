"""
管理员模块 DTO
"""
from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field


# ============================================================
# 用户管理
# ============================================================
class AdminUserListResponse(BaseModel):
    """管理员查看玩家列表"""
    total: int
    page: int
    page_size: int
    users: List["AdminUserBrief"]


class AdminUserBrief(BaseModel):
    id: int
    username: str
    gold: int
    level: int
    cell_count: int
    is_banned: bool
    created_at: datetime


# ============================================================
# 作物 / 动物模板 CRUD
# ============================================================
class AdminCropTemplateRequest(BaseModel):
    """新增/更新作物模板"""
    name: str = Field(..., min_length=1, max_length=32)
    emoji: str = "🌱"
    seed_price: int = Field(..., ge=1)
    growth_seconds: int = Field(..., ge=10, description="至少 10 秒")
    produce_count: int = Field(..., ge=1)
    produce_name: str
    produce_emoji: str = "🌾"
    sell_price_per_unit: int = Field(..., ge=1)
    is_active: int = 1


class AdminAnimalTemplateRequest(BaseModel):
    """新增/更新动物模板"""
    name: str
    emoji: str = "🐔"
    purchase_price: int = Field(..., ge=1)
    produce_interval_seconds: int = Field(..., ge=60)
    produce_name: str
    produce_emoji: str = "🥚"
    sell_price_per_unit: int = Field(..., ge=1)
    feed_consumption: int = Field(default=1, ge=1)
    is_active: int = 1


class AdminShopItemRequest(BaseModel):
    """新增/更新商店商品"""
    item_type: str                   # seed / animal / feed / expansion
    template_id: Optional[int] = None
    name: str
    emoji: str = "📦"
    price: int = Field(..., ge=0)
    stock: int = -1
    sort_order: int = 0
    is_active: int = 1


# ============================================================
# 运营统计
# ============================================================
class AdminStatsResponse(BaseModel):
    """运营数据看板"""
    total_users: int
    active_users_24h: int
    total_crops: int                   # 今日成熟总数
    total_gold_volume: int             # 今日金币交易量
    top_crops: List[str]               # 作物热度 Top5
    top_animals: List[str]

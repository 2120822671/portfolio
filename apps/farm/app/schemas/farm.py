"""
农场模块 DTO —— 土地状态 / 播种 / 收获 / 扩建
"""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import List, Optional

from pydantic import BaseModel, Field


# ============================================================
# 请求体
# ============================================================
class FarmPlantRequest(BaseModel):
    """播种请求"""
    cell_index: int = Field(..., ge=0, description="目标格子坐标")
    template_id: int = Field(..., gt=0, description="作物模板 ID（从背包选种子）")


class FarmHarvestRequest(BaseModel):
    """收获请求"""
    cell_index: int = Field(..., ge=0, description="要收获的格子坐标")


class FarmClearRequest(BaseModel):
    """清理枯萎作物"""
    cell_index: int = Field(..., ge=0)


# ============================================================
# 响应体
# ============================================================
class FarmCellResponse(BaseModel):
    """单个格子的状态快照"""
    cell_index: int
    status: str                          # empty / growing / ready / withered
    crop_name: Optional[str] = None      # 种植的作物名
    crop_emoji: Optional[str] = None
    template_id: Optional[int] = None
    planted_at: Optional[datetime] = None
    ready_at: Optional[datetime] = None
    # 剩余生长秒数（0 表示已成熟）
    seconds_until_ready: int = 0
    # 成熟后距离枯萎的剩余秒数（仅 ready 状态有意义）
    seconds_until_wither: int = 0

    # 便捷计算：剩余时间的人类可读格式
    def remaining_time_text(self) -> str:
        if self.seconds_until_ready <= 0:
            return "已成熟 ✨"
        td = timedelta(seconds=self.seconds_until_ready)
        hours, remainder = divmod(td.seconds, 3600)
        minutes, _ = divmod(remainder, 60)
        if td.days:
            return f"{td.days}天{hours}小时"
        if hours:
            return f"{hours}小时{minutes}分钟"
        return f"{minutes}分钟"


class FarmStatusResponse(BaseModel):
    """完整农场状态"""
    user_id: int
    cell_count: int                          # 已解锁格子数
    max_cell_count: int
    cells: List[FarmCellResponse]
    total_ready: int = 0                     # 成熟格子数量（方便前端高亮）
    total_growing: int = 0
    total_withered: int = 0


class FarmExpandResponse(BaseModel):
    """扩建成功响应"""
    cell_count_before: int
    cell_count_after: int
    gold_spent: int
    gold_remaining: int
    new_cell_index: int

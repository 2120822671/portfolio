"""
作物模板模型 —— crop_templates 表

存储游戏内所有作物的"配方"：种子价格、生长时间、产出数量、售价等。
管理员可在后台维护。
"""
from __future__ import annotations

from sqlalchemy import Integer, SmallInteger, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class CropTemplate(Base):
    """作物模板 —— 小麦、番茄、胡萝卜等"""

    __tablename__ = "crop_templates"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(32), nullable=False, unique=True)
    emoji: Mapped[str] = mapped_column(String(8), nullable=False, default="🌱")

    # 经济参数
    seed_price: Mapped[int] = mapped_column(Integer, nullable=False, default=10)
    growth_seconds: Mapped[int] = mapped_column(
        Integer, nullable=False, default=300, comment="生长时间（秒）"
    )
    produce_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=3, comment="每次成熟产出数量"
    )
    produce_name: Mapped[str] = mapped_column(
        String(32), nullable=False, comment="产出物名称，如 '小麦颗粒'"
    )
    produce_emoji: Mapped[str] = mapped_column(String(8), nullable=False, default="🌾")
    sell_price_per_unit: Mapped[int] = mapped_column(
        Integer, nullable=False, default=5, comment="单个产出物售价"
    )

    is_active: Mapped[int] = mapped_column(
        SmallInteger, nullable=False, default=1, comment="1=上架, 0=下架"
    )

    def __repr__(self) -> str:
        return f"<CropTemplate #{self.id} {self.name} 💰{self.seed_price} ⏱️{self.growth_seconds}s>"

    # ---------- 便捷计算 ----------
    @property
    def growth_minutes(self) -> float:
        return self.growth_seconds / 60

    @property
    def profit_per_harvest(self) -> int:
        """一次成熟的总收入（未扣种子成本）"""
        return self.produce_count * self.sell_price_per_unit

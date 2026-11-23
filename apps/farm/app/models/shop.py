"""
商店商品模型 —— shop_items 表

系统商店的可售卖商品列表。玩家从这里购买种子/动物/饲料。
"""
from __future__ import annotations

from sqlalchemy import ForeignKey, Integer, SmallInteger, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class ShopItem(Base):
    """商店商品"""

    __tablename__ = "shop_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    # item_type: seed | animal | feed | expansion（土地扩建）
    item_type: Mapped[str] = mapped_column(String(16), nullable=False, index=True)

    # 关联模板（seed -> crop_templates, animal -> animal_templates, feed/expansion -> NULL）
    template_id: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # 商品显示信息（冗余，方便直接查询）
    name: Mapped[str] = mapped_column(String(64), nullable=False)
    emoji: Mapped[str] = mapped_column(String(8), nullable=False, default="📦")

    price: Mapped[int] = mapped_column(Integer, nullable=False)

    # 库存: -1 表示无限
    stock: Mapped[int] = mapped_column(Integer, nullable=False, default=-1)

    # 排序权重（值越小越靠前）
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    is_active: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=1)

    def __repr__(self) -> str:
        return f"<ShopItem #{self.id} {self.name} 💰{self.price}>"

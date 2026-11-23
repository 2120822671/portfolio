"""
背包模型 —— inventory 表

玩家背包中的物品，支持:
    - seed:    种子（对应作物模板）
    - produce: 产出物（如小麦颗粒、鸡蛋）
    - animal:  动物（购入的未放养动物）
    - feed:    饲料
"""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import (

    DateTime,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Inventory(Base):
    """玩家背包"""

    __tablename__ = "inventory"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )

    # 物品类型: seed | produce | animal | feed
    item_type: Mapped[str] = mapped_column(String(16), nullable=False, index=True)

    # 关联模板 ID（种子/动物可关联作物或动物模板；产出物可关联作物模板；饲料无关联）
    template_id: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # 物品显示名（冗余存储，方便查询）
    item_name: Mapped[str] = mapped_column(String(64), nullable=False)

    quantity: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # 同一玩家 + 同一物品（类型 + 模板）唯一
    __table_args__ = (
        UniqueConstraint(
            "user_id", "item_type", "template_id",
            name="uq_user_item_unique",
        ),
    )

    # ---------- 关系 ----------
    owner: Mapped["User"] = relationship(back_populates="inventories")  # noqa: F821

    def __repr__(self) -> str:
        return f"<Inventory uid={self.user_id} {self.item_type}:{self.item_name} x{self.quantity}>"

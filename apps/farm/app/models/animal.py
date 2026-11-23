"""
动物相关模型:
    - AnimalTemplate    动物模板表（鸡、羊、牛）
    - PlayerAnimal      玩家实际拥有的动物
"""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import (

    DateTime,
    ForeignKey,
    Integer,
    SmallInteger,
    String,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


# ============================================================
# 动物模板
# ============================================================
class AnimalTemplate(Base):
    """动物模板 —— 定义购买价格、生产周期等"""

    __tablename__ = "animal_templates"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(32), nullable=False, unique=True)
    emoji: Mapped[str] = mapped_column(String(8), nullable=False, default="🐔")

    purchase_price: Mapped[int] = mapped_column(Integer, nullable=False, default=100)
    produce_interval_seconds: Mapped[int] = mapped_column(
        Integer, nullable=False, default=3600, comment="生产间隔（秒）"
    )
    produce_name: Mapped[str] = mapped_column(
        String(32), nullable=False, comment="副产品名称：鸡蛋/羊毛/牛奶"
    )
    produce_emoji: Mapped[str] = mapped_column(String(8), nullable=False, default="🥚")
    sell_price_per_unit: Mapped[int] = mapped_column(Integer, nullable=False, default=20)
    feed_consumption: Mapped[int] = mapped_column(
        Integer, nullable=False, default=1, comment="每次生产消耗饲料数"
    )

    is_active: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=1)

    def __repr__(self) -> str:
        return f"<AnimalTemplate #{self.id} {self.name} 💰{self.purchase_price}>"


# ============================================================
# 玩家动物
# ============================================================
class PlayerAnimal(Base):
    """玩家实际拥有的动物实例"""

    __tablename__ = "player_animals"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    # FK: 所属玩家
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    # FK: 动物模板
    animal_template_id: Mapped[int] = mapped_column(
        ForeignKey("animal_templates.id"), nullable=False
    )

    # 游戏状态
    last_produce_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, comment="上次生产时间"
    )
    is_alive: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=1)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    # ---------- 关系 ----------
    owner: Mapped["User"] = relationship(back_populates="player_animals")  # noqa: F821
    template: Mapped[AnimalTemplate] = relationship()

    def __repr__(self) -> str:
        return f"<PlayerAnimal #{self.id} uid={self.user_id} tpl={self.animal_template_id}>"

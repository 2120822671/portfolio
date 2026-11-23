"""
用户模型 —— users 表
"""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import (
    DateTime,
    Integer,
    String,
    SmallInteger,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class User(Base):
    """玩家账号表"""

    __tablename__ = "users"

    # ---------- 主键 ----------
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    # ---------- 基本信息 ----------
    username: Mapped[str] = mapped_column(
        String(32), unique=True, index=True, nullable=False
    )
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)

    # ---------- 游戏状态 ----------
    gold: Mapped[int] = mapped_column(Integer, nullable=False, default=100)
    level: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    cell_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=3, comment="已解锁格子数"
    )

    # ---------- 权限 ----------
    is_banned: Mapped[int] = mapped_column(
        SmallInteger, nullable=False, default=0, comment="0=正常, 1=封禁"
    )
    # role: player / admin
    role: Mapped[str] = mapped_column(String(16), nullable=False, default="player")

    # ---------- 时间戳 ----------
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # ---------- 关系映射（用于 ORM 关联查询） ----------
    # 一对多: User -> FarmCell / Inventory / PlayerAnimal
    farm_cells: Mapped[list["FarmCell"]] = relationship(  # noqa: F821
        back_populates="owner", cascade="all, delete-orphan"
    )
    inventories: Mapped[list["Inventory"]] = relationship(  # noqa: F821
        back_populates="owner", cascade="all, delete-orphan"
    )
    player_animals: Mapped[list["PlayerAnimal"]] = relationship(  # noqa: F821
        back_populates="owner", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<User id={self.id} username={self.username} gold={self.gold}>"

    # ---------- 便捷属性 ----------
    @property
    def is_admin(self) -> bool:
        return self.role == "admin"

    @property
    def banned(self) -> bool:
        return bool(self.is_banned)

"""
农场格子模型 —— farm_cells 表

每个玩家拥有 N 个格子，每个格子可以处于:
    - empty:    空地，可播种
    - growing:  正在生长，等待成熟
    - ready:    已成熟，可收获
    - withered: 枯萎（超时未收获），需清理
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import (

    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class FarmCell(Base):
    """农场格子"""

    __tablename__ = "farm_cells"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    # FK: 所属玩家
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    # 格子坐标（0 ~ cell_count-1）
    cell_index: Mapped[int] = mapped_column(Integer, nullable=False)

    # 当前状态
    # 枚举值: empty | growing | ready | withered
    status: Mapped[str] = mapped_column(
        String(16), nullable=False, default="empty", index=True
    )

    # 关联的作物（仅 growing/ready/withered 时有值）
    crop_template_id: Mapped[int | None] = mapped_column(
        ForeignKey("crop_templates.id"), nullable=True
    )

    planted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    ready_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, comment="预计成熟时间"
    )

    # ---------- 关系 ----------
    owner: Mapped["User"] = relationship(back_populates="farm_cells")  # noqa: F821
    crop: Mapped["CropTemplate | None"] = relationship()  # noqa: F821

    def __repr__(self) -> str:
        return f"<FarmCell uid={self.user_id} idx={self.cell_index} status={self.status}>"

    # ---------- 便捷方法 ----------
    def is_empty(self) -> bool:
        return self.status == "empty"

    def is_ready(self) -> bool:
        return self.status == "ready"

    def can_plant(self) -> bool:
        return self.status in ("empty", "withered")

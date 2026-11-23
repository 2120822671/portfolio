"""
每日任务进度模型 —— daily_task_progress 表

记录玩家每天的任务完成情况:
    - 每日登录奖励（login）
    - 今日收获作物数量（harvest）
    - 今日出售产品数量（sell）
"""
from __future__ import annotations

from datetime import date, datetime, timezone

from sqlalchemy import (

    Date,
    DateTime,
    ForeignKey,
    Integer,
    SmallInteger,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class DailyTaskProgress(Base):
    """每日任务进度"""

    __tablename__ = "daily_task_progress"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )

    task_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)

    # task_type: login | harvest | sell
    task_type: Mapped[str] = mapped_column(String(32), nullable=False, index=True)

    progress: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    target: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    reward_gold: Mapped[int] = mapped_column(Integer, nullable=False, default=20)

    is_completed: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=0)
    is_claimed: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=0)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    # 同一玩家 + 同一天 + 同一任务类型唯一
    __table_args__ = (
        UniqueConstraint(
            "user_id", "task_date", "task_type",
            name="uq_user_daily_task_unique",
        ),
    )

    def __repr__(self) -> str:
        return (
            f"<DailyTask uid={self.user_id} date={self.task_date} "
            f"type={self.task_type} {self.progress}/{self.target}>"
        )

    @property
    def completed(self) -> bool:
        return bool(self.is_completed)

    @property
    def claimed(self) -> bool:
        return bool(self.is_claimed)

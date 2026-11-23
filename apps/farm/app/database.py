"""
数据库连接模块 —— SQLAlchemy 2.0 异步模式

核心组件:
    - engine:     异步数据库引擎（AsyncEngine）
    - AsyncSessionLocal:  异步 Session 工厂
    - Base:       ORM 模型的 declarative_base
    - get_db():   FastAPI 依赖注入函数 —— 为每个请求提供独立的 session
"""
from __future__ import annotations

from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from app.config import settings


# ============================================================
# ORM 基类
# ============================================================
class Base(DeclarativeBase):
    """所有 ORM 模型的基类"""
    # 可在此统一配置表的默认行为
    pass


# ============================================================
# 异步引擎 & Session 工厂
# ============================================================
def _build_engine() -> AsyncEngine:
    """
    创建异步数据库引擎。

    注意 SQLite 特殊处理:
        - SQLite 不支持多线程并发写，必须设置 connect_args["check_same_thread"] = False
        - 通过 aiomysql 连接 MySQL 时无需此参数
    """
    connect_args: dict = {}

    if settings.is_sqlite:
        # SQLite 异步驱动: aiosqlite
        connect_args["check_same_thread"] = False

    engine = create_async_engine(
        settings.DATABASE_URL,
        echo=settings.SQL_ECHO,                 # 需要排查 SQL 时再打开，避免日志刷屏
        connect_args=connect_args,
        future=True,
        # 连接池参数（MySQL 生产建议调大）
        pool_pre_ping=True,                     # 连接前 ping 一下，自动断开过期连接
    )
    return engine


engine: AsyncEngine = _build_engine()

# 异步 Session 工厂 —— 每次调用生成新的 Session
AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,       # commit 后对象仍可访问，避免额外查询
    autoflush=False,
)


# ============================================================
# 依赖注入 & 生命周期函数
# ============================================================
async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    FastAPI 依赖注入：为每个请求生成独立的 AsyncSession。

    使用方式:
        @app.get("/items")
        async def list_items(db: AsyncSession = Depends(get_db)):
            ...

    工作原理:
        1. 请求进来 → 创建 session
        2. 执行业务逻辑
        3. finally 块中自动关闭 session
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


async def init_db() -> None:
    """
    应用启动时自动建表（开发阶段方案）。

    ⚠️ 重要提醒:
        1. 此函数通过 Base.metadata.create_all() 建表，所有 ORM 模型
           必须已经被导入从而注册到 Base.metadata 中。
           → 请在 app/models/__init__.py 中集中 import 所有模型！

        2. 生产环境推荐使用 Alembic 迁移管理表结构演进。
           此函数仅用于快速启动和开发环境。
    """
    # 延迟 import —— 避免循环导入，同时确保 models 已被注册
    from app.models import _ensure_all_models_imported  # noqa: F401

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    print(f"✅ 数据库初始化完成 | DATABASE_URL={settings.DATABASE_URL}")


async def close_db() -> None:
    """应用关闭时释放数据库连接"""
    await engine.dispose()
    print("🛑 数据库连接已释放")

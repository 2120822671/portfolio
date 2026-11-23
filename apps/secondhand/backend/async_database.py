"""增量新增：管理员看板专用的 async 数据库会话。

主工程仍使用 database.py 的同步 engine / get_db，本文件只服务于新增的
GET /api/v1/admin/dashboard，不改动任何原有模块。
"""
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from config import DATABASE_URL

# 仅把驱动从 pymysql 换成 aiomysql，连接参数完全复用 config.DATABASE_URL
ASYNC_DATABASE_URL = DATABASE_URL.replace("mysql+pymysql://", "mysql+aiomysql://", 1)

async_engine = create_async_engine(ASYNC_DATABASE_URL, echo=False, pool_pre_ping=True)
AsyncSessionLocal = async_sessionmaker(
    bind=async_engine,
    class_=AsyncSession,
    autocommit=False,
    autoflush=False,
    expire_on_commit=False,
)


async def get_async_db():
    """FastAPI 依赖注入：每个请求一个 async Session（仅供看板接口使用）"""
    async with AsyncSessionLocal() as session:
        yield session

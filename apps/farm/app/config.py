"""
环境配置加载模块
使用 pydantic-settings 从 .env 文件读取配置，提供类型安全的访问方式
"""
from typing import List

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """全局配置类 — 字段与 .env 文件一一对应"""

    # ---------- 应用基础 ----------
    APP_NAME: str = "Pixel Farm Online"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = True
    CORS_ORIGINS: str = "http://localhost:3000,http://localhost:5173"

    # ---------- 数据库 ----------
    # 默认使用 SQLite 开发模式（零依赖），生产改为 MySQL
    DATABASE_URL: str = "sqlite+aiosqlite:///./pixel_farm.db"
    # 是否打印每条 SQL（调试用；DEBUG 模式不再默认全量打印，避免日志与 I/O 开销）
    SQL_ECHO: bool = False

    # ---------- JWT ----------
    # 生产环境必须覆盖此项！
    SECRET_KEY: str = "dev-secret-key-change-in-production-please"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 1440  # 24h

    # ---------- 游戏参数 ----------
    INITIAL_GOLD: int = 100
    INITIAL_CELL_COUNT: int = 3
    MAX_CELL_COUNT: int = 25
    EXPAND_COST: int = 500
    # 作物成熟后多少秒仍未收获会枯萎（默认 24 小时）
    WITHER_GRACE_SECONDS: int = 86400

    # ---------- 管理员初始化 ----------
    ADMIN_USERNAME: str = "admin"
    ADMIN_PASSWORD: str = "admin123"

    # pydantic-settings 配置
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )

    @property
    def cors_origins_list(self) -> List[str]:
        """将逗号分隔的 CORS 字符串转为列表"""
        return [o.strip() for o in self.CORS_ORIGINS.split(",") if o.strip()]

    @property
    def is_sqlite(self) -> bool:
        """判断当前是否使用 SQLite（驱动特殊处理）"""
        return self.DATABASE_URL.startswith("sqlite")


# 单例模式：全局共享一份配置实例
settings = Settings()

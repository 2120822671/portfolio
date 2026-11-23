"""
FastAPI 应用入口

职责:
    - 创建 FastAPI app 实例
    - 配置 CORS 中间件
    - 注册所有路由
    - 注册全局异常处理器
    - 管理应用生命周期（启动时建表，关闭时释放资源）
"""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from typing import Any, Dict

from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from app.config import settings
from app.database import close_db, init_db

# 前端静态文件路径
FRONTEND_DIR = Path(__file__).resolve().parent.parent / "frontend"

# ---------- 日志配置 ----------
logging.basicConfig(
    level=logging.DEBUG if settings.DEBUG else logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
# 第三方库在 DEBUG 下会输出大量连接/哈希细节，压到 WARNING，只保留业务日志
for _noisy in ("aiosqlite", "passlib", "asyncio", "sqlalchemy.engine", "httpcore", "httpx"):
    logging.getLogger(_noisy).setLevel(logging.WARNING)

logger = logging.getLogger(__name__)


# ============================================================
# 应用生命周期 —— FastAPI 0.103+ 推荐的 lifespan 方式
# ============================================================
@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    启动时:
        1. 自动建表（开发模式，生产用 Alembic）
        2. 初始化种子数据（内置作物/动物/商店/管理员账号）
    关闭时:
        1. 释放数据库连接池
    """
    logger.info("🚀 应用启动中...")

    # 1. 初始化数据库（建表）
    await init_db()

    # 2. 初始化种子数据（仅开发环境自动执行）
    if settings.DEBUG:
        try:
            from scripts.seed_data import run_seed
            await run_seed()
        except Exception as e:
            logger.warning(f"种子数据初始化失败（非致命）: {e}")

    logger.info(f"✅ {settings.APP_NAME} v{settings.APP_VERSION} 启动完成")
    yield

    # 关闭时清理
    await close_db()
    logger.info("🛑 应用已关闭")


# ============================================================
# 创建 FastAPI App
# ============================================================
app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description=(
        "🎮 像素农场 Online — 轻量级在线休闲农场经营游戏后端。\n\n"
        "基于 FastAPI + SQLAlchemy 2.0 + MySQL 8.0 构建。\n"
        "开发环境默认使用 SQLite，零依赖即可启动。"
    ),
    lifespan=lifespan,
    # API 文档信息
    docs_url="/docs",
    redoc_url="/redoc",
    # 所有 API 路由挂在 /api/v1 前缀下
)


# ============================================================
# CORS 中间件
# ============================================================
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============================================================
# 全局异常处理器
# ============================================================
@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    """统一 HTTP 异常返回格式"""
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "code": exc.status_code,
            "message": exc.detail,
            "path": str(request.url.path),
        },
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    """把 422 参数校验错误也整理成 {code, message} 结构，前端可直接展示"""
    errors = exc.errors()
    first = errors[0] if errors else {}
    loc = ".".join(
        str(part) for part in first.get("loc", []) if part not in ("body", "query", "path")
    )
    raw_message = str(first.get("msg", "参数校验失败"))
    message = f"{loc}: {raw_message}" if loc else raw_message

    return JSONResponse(
        status_code=422,
        content={
            "code": 422,
            "message": message,
            "errors": jsonable_encoder(errors),
            "path": str(request.url.path),
        },
    )


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """未处理异常兜底 —— 返回 500 并记录日志"""
    logger.exception("未处理异常", exc_info=exc)
    return JSONResponse(
        status_code=500,
        content={
            "code": 500,
            "message": "服务器内部错误",
            "detail": str(exc) if settings.DEBUG else None,
            "path": str(request.url.path),
        },
    )


# ============================================================
# 健康检查 & 根路径
# ============================================================
@app.get("/", tags=["系统"])
async def root() -> Any:
    """根路径 —— 返回前端页面（如果存在），否则返回 API 信息"""
    index_file = FRONTEND_DIR / "index.html"
    if index_file.exists():
        return FileResponse(index_file)
    return {
        "name": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "docs": "/docs",
        "status": "running",
    }


@app.get("/api/v1/health", tags=["系统"])
async def health_check() -> Dict[str, Any]:
    """健康检查 —— 用于负载均衡器 / Docker 健康检查"""
    return {
        "status": "ok",
        "database": settings.DATABASE_URL.split("://")[0],  # 只显示驱动名
        "debug": settings.DEBUG,
    }


# ============================================================
# 注册业务路由
# ============================================================
# 统一挂载 /api/v1 前缀，每个模块一个 router
from app.routers.auth import router as auth_router
from app.routers.farm import router as farm_router
from app.routers.animals import router as animals_router
from app.routers.shop import router as shop_router
from app.routers.inventory import router as inventory_router
from app.routers.tasks import router as tasks_router
from app.routers.rank import router as rank_router
from app.routers.admin import router as admin_router

API_PREFIX = "/api/v1"

app.include_router(auth_router,     prefix=API_PREFIX, tags=["认证"])
app.include_router(farm_router,     prefix=API_PREFIX, tags=["农场"])
app.include_router(animals_router,  prefix=API_PREFIX, tags=["动物"])
app.include_router(shop_router,      prefix=API_PREFIX, tags=["商店"])
app.include_router(inventory_router, prefix=API_PREFIX, tags=["背包"])
app.include_router(tasks_router,     prefix=API_PREFIX, tags=["任务"])
app.include_router(rank_router,      prefix=API_PREFIX, tags=["排行榜"])
app.include_router(admin_router,     prefix=API_PREFIX, tags=["管理员"])

logger.info(f"📡 已注册路由: {len(app.routes)} 条")


# ============================================================
# 挂载前端静态资源（js/css/images）
# ============================================================
if FRONTEND_DIR.exists():
    app.mount("/css", StaticFiles(directory=str(FRONTEND_DIR / "css")), name="css")
    app.mount("/js", StaticFiles(directory=str(FRONTEND_DIR / "js")), name="js")
    logger.info("🎨 前端静态资源已挂载 (/css, /js)")

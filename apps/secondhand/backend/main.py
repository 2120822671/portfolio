import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.docs import get_swagger_ui_html
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import text

from database import engine
from paths import FRONTEND_DIR
from redis_client import close_redis, init_redis
from routers import auth, cart, chat, favorite, goods, order, report, upload
from routers import admin  # 增量新增：管理后台统计看板
from security import verify_token
from tasks.close_timeout_orders import start_scheduler, stop_scheduler

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("campus_secondhand")

PROJECT_NAME = "campus_secondhand"
PROJECT_VERSION = "1.0.0"


@asynccontextmanager
async def lifespan(app: FastAPI):
    """启动时验证数据库连通性"""
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        logger.info("数据库连接成功: mysql+pymysql://%s@localhost:3306/campus_secondhand", "root")
    except Exception as e:
        logger.error("数据库连接失败: %s", e)
        raise
    start_scheduler()   # 增量新增：启动超时未支付订单自动关闭任务
    await init_redis()  # 增量新增：初始化 Redis（风控限流/举报去重，不可用时降级）
    yield
    stop_scheduler()    # 增量新增：关闭定时任务
    await close_redis()  # 增量新增：关闭 Redis 连接池
    logger.info("服务已关闭，数据库连接池已释放")


app = FastAPI(
    title=PROJECT_NAME,
    description="校园二手交易平台 API",
    version=PROJECT_VERSION,
    lifespan=lifespan,
    docs_url=None,   # 关闭默认 /docs（默认从 jsdelivr CDN 加载脚本，离线/被墙时白屏）
)


@app.get("/docs", include_in_schema=False)
def custom_swagger_ui():
    """Swagger UI：改用本地 static/swagger 资源，离线也能打开"""
    return get_swagger_ui_html(
        openapi_url=app.openapi_url,
        title=f"{app.title} - Swagger UI",
        swagger_js_url="/secondhand/static/swagger/swagger-ui-bundle.js",
        swagger_css_url="/secondhand/static/swagger/swagger-ui.css",
    )


# CORS：允许前端静态页（如 http://127.0.0.1:5500）跨域调用 API
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.middleware("http")
async def identity_middleware(request: Request, call_next):
    """增量修复：用服务端签名令牌覆盖客户端自报的 X-User-Id，堵住身份伪造（BUG-01）

    - 令牌合法 → 用服务端解出的 uid 覆盖请求头，业务代码读到的是可信身份；
    - 令牌缺失/伪造 → 移除 X-User-Id，写接口自然返回 401，无法冒用他人身份。
    """
    raw = request.headers.get("authorization", "")
    token = raw[7:].strip() if raw.lower().startswith("bearer ") else raw.strip()
    uid = verify_token(token) if token else None

    headers = [(k, v) for k, v in request.scope["headers"] if k != b"x-user-id"]
    if uid is not None:
        headers.append((b"x-user-id", str(uid).encode()))
    request.scope["headers"] = headers
    return await call_next(request)


@app.middleware("http")
async def static_no_cache(request: Request, call_next):
    """静态资源禁止强缓存：前端改完刷新即生效（保留 ETag 协商，命中时仍返回 304）"""
    response = await call_next(request)
    if request.url.path.startswith("/static/"):
        response.headers["Cache-Control"] = "no-cache, must-revalidate"
    return response


# 静态前端页面：/secondhand/static/index.html
# 前端代码已拆分到项目根的 frontend/ 目录，挂载路径保持不变
app.mount("/static", StaticFiles(directory=str(FRONTEND_DIR)), name="static")

app.include_router(auth.router)
app.include_router(goods.router)
app.include_router(goods.stats_router)
app.include_router(goods.category_router)
app.include_router(upload.router)
# 增量新增：收藏统计补偿接口
app.include_router(favorite.router)
# 增量新增：订单接口（下单/支付/取消/详情/购物车批量结算）
app.include_router(order.router)
# 增量新增：购物车接口（加入/列表/改数量/移除/清空）
app.include_router(cart.router)
# 增量新增：聊天接口（会话/消息/未读数，支持砍价与换物互动）
app.include_router(chat.router)
# 增量新增：举报接口（24 小时内同一用户对同一对象只能举报一次）
app.include_router(report.router)
# 增量新增：管理后台统计看板
app.include_router(admin.router)


# 统一异常返回：{code, msg, data}，错误信息友好
@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    return JSONResponse(
        status_code=exc.status_code,
        content={"code": exc.status_code, "msg": exc.detail, "data": None},
        headers=exc.headers or None,  # 增量：透传 Retry-After 等响应头（无头时为 None，行为不变）
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    first = exc.errors()[0] if exc.errors() else {}
    field = ".".join(str(x) for x in first.get("loc", [])[1:]) or "参数"
    return JSONResponse(
        status_code=422,
        content={"code": 422, "msg": f"参数校验失败：{field} {first.get('msg', '')}", "data": None},
    )


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    """兜底：未预料的服务端异常也返回统一格式，避免泄露堆栈"""
    logger.exception("未处理异常: %s", exc)
    return JSONResponse(
        status_code=500,
        content={"code": 500, "msg": "服务器开小差了，请稍后重试", "data": None},
    )


@app.get("/")
def root():
    """根路由：返回项目名称与版本"""
    return {"project": PROJECT_NAME, "version": PROJECT_VERSION}


# 增量新增：全局异常处理（错误码枚举 + 统一返回 + Loguru 堆栈），旧 handler 函数体保留不动
from core.exception_handlers import register_exception_handlers  # noqa: E402

register_exception_handlers(app)

# 增量新增：管理后台管理功能（用户/审核/举报/订单监管）
from routers import admin_manage  # noqa: E402

app.include_router(admin_manage.router)

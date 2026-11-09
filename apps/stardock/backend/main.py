"""
main.py —— 入口三件套
1. 中间件：SessionMiddleware + CORSMiddleware
2. 全局异常处理器（统一 JSON 返回）
3. 路由注册（API 路由必须在 StaticFiles mount 之前！）
4. 最后挂载静态文件（放最后！否则会吞掉 /api/* 请求）
"""
import os
import traceback
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.sessions import SessionMiddleware
from starlette.staticfiles import StaticFiles
from starlette.responses import JSONResponse

# ============== 创建 FastAPI 实例 ==============
app = FastAPI(title="星坞 StarDock", version="1.0.0")


# ============== 中间件 ==============
app.add_middleware(
    SessionMiddleware,
    secret_key="stardock-secret-key-change-in-production",
    session_cookie="stardock_session",
    max_age=60 * 60 * 24 * 7,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============== 全局异常处理器 ==============
@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    if exc.status_code in (401, 403):
        code = exc.status_code
    elif exc.status_code == 404:
        code = 1
    else:
        code = exc.status_code
    return JSONResponse(
        status_code=200,
        content={"code": code, "msg": exc.detail, "data": None},
    )


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    traceback.print_exc()
    # 临时：落盘日志便于排查（后续可删）
    import os
    from datetime import datetime as _dt
    _log = os.path.join(os.path.dirname(__file__), "error.log")
    with open(_log, "a", encoding="utf-8") as f:
        f.write(f"\n===== {_dt.now()} {request.url.path} =====\n")
        traceback.print_exc(file=f)
    return JSONResponse(
        status_code=200,
        content={"code": 500, "msg": "服务器内部错误", "data": None},
    )


# ============== API 路由（必须在 StaticFiles mount 之前！）==============
from routers import auth, users, celebrities, fan_clubs, chat, gacha, activities, recharge

app.include_router(auth.router)
app.include_router(users.router)
app.include_router(celebrities.router)
app.include_router(fan_clubs.router)
app.include_router(chat.router)
app.include_router(gacha.router)
app.include_router(activities.router)
app.include_router(recharge.router)


# 健康检查（也是 API 路由，放 mount 之前）
@app.get("/api/health")
async def health():
    return {"code": 0, "msg": "ok", "data": None}


# ============== 静态资源禁缓存中间件 ==============
# 保证浏览器每次都拿最新的 HTML/JS/CSS，避免改了代码前端还是旧版
from starlette.middleware.base import BaseHTTPMiddleware


class NoCacheStaticMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        response = await call_next(request)
        path = request.url.path
        if not path.startswith("/api") and (
            path.endswith(".html") or path.endswith(".js")
            or path.endswith(".css") or path == "/"
        ):
            response.headers["Cache-Control"] = "no-cache, must-revalidate"
        return response


app.add_middleware(NoCacheStaticMiddleware)


# ============== 根路径跳转（作品集整合） ==============
from fastapi.responses import RedirectResponse


@app.get("/")
async def index_redirect():
    return RedirectResponse(url="/stardock/home.html")


# ============== 挂载静态文件（必须放最后！）==============
_static_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "htdocs")
app.mount("/", StaticFiles(directory=_static_dir, html=True), name="static")


# ============== 启动入口 ==============
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)

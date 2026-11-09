"""
求职作品集 · 聚合入口
把四个项目作为子应用挂载在统一前缀下，单端口启动：

  /          门户首页 + 简历页
  /mall      蛋糕线上商城
  /account   招财记账 · 个人记账小系统
  /club      学生社团活动登记系统
  /stardock  星坞 StarDock

启动：python main.py    访问：http://127.0.0.1:8000
"""
import asyncio
import importlib.util
import os
import sys

BASE = os.path.dirname(os.path.abspath(__file__))
APPS = os.path.join(BASE, "apps")

# 星坞 backend 内部使用顶层导入（routers / database / deps），需要加入 sys.path
sys.path.insert(0, os.path.join(APPS, "stardock", "backend"))


def load_app(module_name: str, file_path: str):
    """以独立模块名加载子项目的 FastAPI 应用（避免同名 main 冲突）"""
    spec = importlib.util.spec_from_file_location(module_name, file_path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = mod
    spec.loader.exec_module(mod)
    return mod


from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

# ---------- 加载四个子应用 ----------
mall_app = load_app("mall_app", os.path.join(APPS, "mall", "backend", "main.py")).app
account_app = load_app("account_app", os.path.join(APPS, "account", "main.py")).app
club_app = load_app("club_app", os.path.join(APPS, "club", "main.py")).app
stardock_app = load_app("stardock_app", os.path.join(APPS, "stardock", "backend", "main.py")).app

app = FastAPI(title="求职作品集", version="1.0.0")

# ---------- 挂载子应用 ----------
app.mount("/mall", mall_app)
app.mount("/account", account_app)
app.mount("/club", club_app)
app.mount("/stardock", stardock_app)

# 蛋糕商城前端使用 /static/... 绝对路径（含数据库里存的图片地址），
# 在门户根下再挂一份，保证商城页面从任意入口进入资源都可用
app.mount("/static", StaticFiles(directory=os.path.join(APPS, "mall", "frontend", "static")),
          name="mall-static")


# ---------- 门户页面 ----------
@app.get("/")
async def portal():
    return FileResponse(os.path.join(BASE, "index.html"))


@app.get("/resume.html")
async def resume_page():
    return FileResponse(os.path.join(BASE, "resume.html"))


@app.get("/resume.docx")
async def resume_docx():
    return FileResponse(os.path.join(BASE, "resume", "个人简历.docx"),
                        filename="陈振华-个人简历.docx")


# ---------- 生命周期：启动蛋糕商城的订单超时自动取消后台任务 ----------
# 子应用挂载后其 startup 事件不会触发，这里手动启动
@app.on_event("startup")
async def start_background_tasks():
    from mall_app import _auto_cancel_expired_orders  # noqa
    asyncio.create_task(_auto_cancel_expired_orders())


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

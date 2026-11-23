"""
求职作品集 · 聚合入口
四个项目以独立 FastAPI 子应用挂载在统一前缀下，单端口启动：

  /               门户首页 + 简历页
  /book           墨香书阁 · 图书借阅（JSON 文件存储）
  /secondhand     校淘集市 · 校园二手交易（SQLAlchemy + MySQL + Redis）
  /account        招财记账 · 个人记账小系统（MySQL + APScheduler）
  /stardock       星坞 StarDock · 明星粉丝社区（PyMySQL + DBUtils + WebSocket）

启动：python main.py    访问：http://127.0.0.1:8000
"""
import asyncio
import importlib.util
import os
import sys

BASE = os.path.dirname(os.path.abspath(__file__))
APPS = os.path.join(BASE, "apps")

# 像素农场使用 SQLite，数据库文件固定放在 apps/farm 下（先于子应用导入设置）
os.environ.setdefault(
    "DATABASE_URL",
    "sqlite+aiosqlite:///" + os.path.join(APPS, "farm", "pixel_farm.db").replace("\\", "/"),
)

# 各子项目使用顶层模块导入，加载前把各自目录加入 sys.path
for extra in (
    os.path.join(APPS, "farm"),
    os.path.join(APPS, "book"),
    os.path.join(APPS, "secondhand", "backend"),
    os.path.join(APPS, "account"),
    os.path.join(APPS, "stardock", "backend"),
):
    if extra not in sys.path:
        sys.path.insert(0, extra)


def load_app(module_name: str, file_path: str):
    """以独立模块名加载子项目的 FastAPI 应用（避免同名 main 冲突）"""
    spec = importlib.util.spec_from_file_location(module_name, file_path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = mod
    spec.loader.exec_module(mod)
    return mod


# ---------- 加载五个子应用 ----------
farm_mod = load_app("farm_app", os.path.join(APPS, "farm", "app", "main.py"))
book_mod = load_app("book_app", os.path.join(APPS, "book", "main.py"))
sh_mod = load_app("secondhand_app", os.path.join(APPS, "secondhand", "backend", "main.py"))
acc_mod = load_app("account_app", os.path.join(APPS, "account", "main.py"))
sd_mod = load_app("stardock_app", os.path.join(APPS, "stardock", "backend", "main.py"))

farm_app = farm_mod.app
book_app = book_mod.app
secondhand_app = sh_mod.app
account_app = acc_mod.app
stardock_app = sd_mod.app

from fastapi import FastAPI
from fastapi.responses import FileResponse

app = FastAPI(title="求职作品集", version="2.0.0")

# ---------- 挂载子应用 ----------
app.mount("/farm", farm_app)
app.mount("/book", book_app)
app.mount("/secondhand", secondhand_app)
app.mount("/account", account_app)
app.mount("/stardock", stardock_app)


# ---------- 门户页面 ----------
@app.get("/")
async def portal():
    return FileResponse(os.path.join(BASE, "index.html"))


@app.get("/resume.html")
async def resume_page():
    return FileResponse(os.path.join(BASE, "resume.html"))


@app.get("/resume-photo")
async def resume_photo():
    return FileResponse(os.path.join(BASE, "static", "images", "photo.png"))


@app.get("/resume.docx")
async def resume_docx():
    return FileResponse(os.path.join(BASE, "resume", "个人简历.docx"),
                        filename="陈振华-个人简历.docx")


# ---------- 生命周期：子应用挂载后其 lifespan/startup 不会自动触发，这里手动启动 ----------
@app.on_event("startup")
async def start_background_tasks():
    # 像素农场：建表 + 种子数据（挂载的子应用 lifespan 不会自动触发）
    try:
        await farm_mod.init_db()
        from scripts.seed_data import run_seed
        await run_seed()
    except Exception as e:  # noqa: BLE001
        print(f"[farm] 数据库初始化失败：{e}")

    # 图书：确保 JSON 数据文件存在
    try:
        book_mod.book_storage._ensure_file()
    except Exception as e:  # noqa: BLE001
        print(f"[book] 数据目录初始化失败：{e}")

    # 二手交易：Redis 风控连接池 + 超时订单自动关闭任务
    try:
        await sh_mod.init_redis()
    except Exception as e:  # noqa: BLE001
        print(f"[secondhand] Redis 初始化失败（降级放行）：{e}")
    try:
        sh_mod.start_scheduler()
    except Exception as e:  # noqa: BLE001
        print(f"[secondhand] 定时任务启动失败：{e}")

    # 招财记账：建表 + 自动化调度器
    try:
        acc_mod.init_db()
    except Exception as e:  # noqa: BLE001
        print(f"[account] 数据库初始化失败：{e}")
    try:
        acc_mod.automation.start_scheduler()
    except Exception as e:  # noqa: BLE001
        print(f"[account] 调度器启动失败：{e}")


@app.on_event("shutdown")
async def stop_background_tasks():
    for fn, label in (
        (lambda: sh_mod.stop_scheduler(), "secondhand 定时任务"),
        (lambda: acc_mod.automation.shutdown_scheduler(), "account 调度器"),
    ):
        try:
            fn()
        except Exception as e:  # noqa: BLE001
            print(f"[shutdown] {label} 关闭失败：{e}")
    try:
        await sh_mod.close_redis()
    except Exception as e:  # noqa: BLE001
        print(f"[shutdown] Redis 关闭失败：{e}")
    try:
        await farm_mod.close_db()
    except Exception as e:  # noqa: BLE001
        print(f"[shutdown] 农场数据库关闭失败：{e}")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

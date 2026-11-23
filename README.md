# 求职作品集 · 五个全栈项目 + 个人简历

一个入口，完整体验五个可运行的 Python 全栈项目与个人简历页。所有项目基于 **FastAPI** 开发，由单一 FastAPI 聚合应用挂载，单端口启动。

> 各项目独立文档见 [docs/](./docs/README.md)。

## 项目清单

| 项目 | 入口 | 存储 | 功能亮点 |
|------|------|------|----------|
| 🕹 像素农场 Online | `/farm/` | SQLite（异步 SQLAlchemy） | 种植生长收获、动物养殖、商店买卖、背包、每日任务与签到、财富榜/周榜、管理后台、JWT 鉴权 |
| 📖 墨香书阁 | `/book/` | JSON 文件 | 图书录入/编辑、借阅归还与库存联动、多条件筛选分页、CSV 导出、答题完书验证、10 枚成就徽章 |
| 🛒 校淘集市 | `/secondhand/static/index.html` | MySQL `campus_secondhand` | 商品发布审核、购物车、订单与模拟支付、超时自动关单、收藏/聊天砍价、举报风控、管理后台 |
| 🐱 招财记账 | `/account/` | MySQL `account_db` | 多账本、流水筛选分页、周期账单、分类预算与 Canvas 看板、大模型意图解析（规则兜底）、日报与打卡成就 |
| ⭐ 星坞 StarDock | `/stardock/home.html` | MySQL `stardock` | 三角色权限、明星主页与粉丝团、WebSocket 实时聊天、抽卡系统、积分充值、活动管理 |
| 📄 个人简历 | `/resume.html` | — | 在线简历页，可下载 `/resume.docx` 原件 |

## 快速开始

```bash
# 1. 安装依赖
pip install -r requirements.txt

# 2. 启动 MySQL 8.0（root / 123456，与各项目配置一致）

# 3. 一键初始化三个 MySQL 数据库（幂等，可重复执行；图书项目无需数据库）
python init_db.py

# 4. 启动作品集
python main.py
```

浏览器访问 <http://127.0.0.1:8000> 即门户首页。也可直接双击 `启动作品集.bat` 一键启动。

> Redis 为可选项：校淘集市的限流/举报去重依赖 Redis，未安装时自动降级放行，不影响主流程。

## 目录结构

```
portfolio/
├── main.py              # 聚合入口（唯一启动文件）
├── init_db.py           # 一键初始化三个 MySQL 数据库
├── index.html           # 门户首页（全新设计）
├── resume.html          # 个人简历页
├── requirements.txt
├── static/images/       # 简历证件照
├── resume/              # 简历原件 docx
├── docs/                # 五个项目的独立文档
└── apps/
    ├── farm/            # 像素农场 Online（SQLite，零配置）
    │   ├── app/         # models / routers / schemas / services
    │   ├── frontend/    # index.html + css + js
    │   └── scripts/     # 种子数据
    ├── book/            # 墨香书阁（JSON 文件存储，免数据库）
    │   ├── main.py, book_models.py, book_storage.py
    │   ├── static/      # 前端页面 + 封面图
    │   └── data/        # JSON 数据文件（自动创建）
    ├── secondhand/      # 校淘集市
    │   ├── backend/     # FastAPI + SQLAlchemy + Redis
    │   ├── frontend/    # 原生前端页面
    │   └── sql/         # 建表与升级脚本
    ├── account/         # 招财记账
    │   └── main.py, db.py, llm.py, automation.py, index.html ...
    └── stardock/        # 星坞 StarDock
        ├── backend/     # sd_database / sd_routers（命名空间隔离）
        └── htdocs/      # 前端页面
```

## 整合说明

- 每个子项目作为独立 FastAPI 子应用挂载到前缀 `/farm` `/book` `/secondhand` `/account` `/stardock`，Session、路由、数据库互不干扰。
- 所有前端 API 与静态资源路径已改为带前缀的路径（如 `/account/api/records`、`/book/static/covers/...`），页面底部/侧边均有「← 作品集」返回入口。
- 为避免模块名冲突，子应用内部模块已重命名隔离：`book_models`/`book_storage`、`sd_database`/`sd_deps`/`sd_routers`。
- 子应用挂载后其 lifespan 不会自动触发，聚合入口手动启动后台任务（订单超时关单、Redis、记账调度器）。
- 简历页与证件照路由 `/resume.html` `/resume-photo` `/resume.docx` 保持不变。

## 测试账号

| 项目 | 账号 | 密码 | 说明 |
|------|------|------|------|
| 像素农场 | 注册任意账号 | — | 注册即玩；管理员 `admin` / `admin123`（可在 `apps/farm/app/config.py` 修改） |
| 校淘集市 | `test001` ～ `test004` | `test123` | 普通用户；管理员账号在 `admin_role` 表配置 |
| 星坞 StarDock | 注册任意账号 | — | 默认粉丝角色；管理员/明星可在 `users.role` 改（2=管理员，3=明星） |
| 墨香书阁 / 招财记账 | 无需登录 | — | 打开即用 |

## 数据库

| 库名 | 所属项目 | 初始化来源 |
|------|----------|-----------|
| `apps/farm/pixel_farm.db` | 像素农场 | SQLite 文件，启动时自动建表 + 种子数据 |
| — | 墨香书阁 | JSON 文件，启动时自动创建 |
| `account_db` | 招财记账 | `apps/account/建表SQL.sql` + `db.py` 的 `init_db()` |
| `campus_secondhand` | 校淘集市 | `apps/secondhand/sql/` 下建表/升级/种子脚本 |
| `stardock` | 星坞 | `apps/stardock/backend/init.sql`（已改为幂等，不再 DROP 库） |

> 修改数据库密码请同步修改各项目的配置：`apps/account/db.py`、`apps/secondhand/backend/config.py`、`apps/stardock/backend/sd_database.py` 以及根目录 `init_db.py`。

## 可选的 Redis

校淘集市使用 Redis 做发布限流与举报去重（`RISK_FAIL_OPEN=True`，未启动 Redis 时自动放行）。本机安装并启动 Redis 后无需改配置即可生效。

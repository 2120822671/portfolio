# 求职作品集 · 四合一全栈项目集合

一个入口，完整体验四个可运行的 Python 全栈项目 + 个人简历页。所有项目均基于 **FastAPI + MySQL 8.0 + 原生 HTML/CSS/JavaScript（fetch API）** 开发，由单一 FastAPI 聚合应用挂载，单端口启动。

## 项目清单

| 项目 | 入口 | 功能亮点 |
|------|------|----------|
| 🍰 蛋糕线上商城 | `/mall` | 电商闭环：购物车、下单防超卖（事务+行锁）、模拟支付、订单超时自动取消、评价收藏、管理员后台 |
| 🐱 招财记账 | `/account` | 单页记账：分类统计、区间筛选、分页查询、预留大模型记账接口、招财猫/木鱼交互 |
| 🏫 社团活动登记 | `/club` | 活动登记与查询：Pydantic 参数校验、参数化查询防注入、XSS 防护 |
| ⭐ 星坞 StarDock | `/stardock` | 粉丝社区：三角色权限、WebSocket 实时聊天、抽卡系统、积分充值、活动管理 |
| 📄 个人简历 | `/resume.html` | 求职简历页（内容确认后展示） |

## 快速开始

```bash
# 1. 安装依赖
pip install -r requirements.txt

# 2. 启动 MySQL 8.0（root / 123456，与各项目配置一致）

# 3. 一键初始化四个项目的数据库（幂等，可重复执行）
python init_db.py

# 4. 启动作品集
python main.py
```

浏览器访问 <http://127.0.0.1:8000> 即门户首页。

## 目录结构

```
portfolio/
├── main.py              # 聚合入口（唯一启动文件）
├── init_db.py           # 一键初始化四个项目的 MySQL 数据库
├── index.html           # 门户首页
├── resume.html          # 个人简历页（占位，内容待确认）
├── requirements.txt
├── resume/              # 简历资料（简历模板.md 待手动更新）
└── apps/
    ├── mall/            # 蛋糕线上商城（backend + frontend + 文档 + db/schema.sql）
    ├── account/         # 招财记账（main.py + index.html + 建表SQL.sql）
    ├── club/            # 社团活动登记（main.py + static/）
    └── stardock/        # 星坞 StarDock（backend + htdocs + init.sql）
```

## 整合说明

- 每个子项目作为独立 FastAPI 子应用挂载到前缀：`/mall` `/account` `/club` `/stardock`，各自的 Session、路由、业务逻辑互不干扰。
- 子项目前端 API 调用已统一改为带前缀的路径（如 `/mall/api/...`），页面顶部均有「🏠 作品集」返回入口。
- 蛋糕商城的商品图片路径挂载在门户根 `/static`，保证从任意入口进入均正常显示。

## 测试账号

| 项目 | 账号 | 密码 | 说明 |
|------|------|------|------|
| 蛋糕商城 | admin | 123456 | 管理员；注册任意用户可体验顾客流程 |
| 星坞 StarDock | 注册任意账号 | — | 注册默认粉丝角色；管理员/明星账号可在 `users` 表改 `role`（2=管理员，3=明星） |
| 招财记账 / 社团登记 | 无需登录 | — | 打开即用 |

## 数据库

| 库名 | 所属项目 | 初始化来源 |
|------|----------|-----------|
| `cakeshop` | 蛋糕商城 | `apps/mall/backend/db/init_db.py`（含样例数据与商品图） |
| `account_db` | 招财记账 | `apps/account/建表SQL.sql` |
| `test_db` | 社团登记 | `init_db.py` 内置建表（原项目无 SQL 文件） |
| `stardock` | 星坞 | `apps/stardock/backend/init.sql` |

> 修改数据库密码请同步修改各项目 `main.py` / `database.py` 中的 `DB_CONFIG`。

# 🎮 像素农场 Online

> 一款轻量级在线休闲农场经营游戏，基于 **FastAPI + SQLAlchemy + MySQL** 构建。

## ✨ 功能特性

- 🔐 用户注册登录 / 金币经济系统
- 🌾 作物种植、生长、收获全循环（实时计时）
- 🐔 动物养殖：鸡产蛋、羊产毛、牛产奶
- 🛒 商店买卖、背包管理
- 🎁 每日任务 & 登录奖励
- 🏆 财富排行榜
- 🛠️ 管理员后台数据维护

## 🛠️ 技术栈

| 层级 | 技术 |
|------|------|
| **Web 框架** | FastAPI · Uvicorn |
| **ORM** | SQLAlchemy 2.0（异步） |
| **数据库** | MySQL 8.0（生产） / SQLite（开发） |
| **认证** | JWT (python-jose + passlib[bcrypt]) |
| **数据校验** | Pydantic v2 |
| **配置** | pydantic-settings + python-dotenv |
| **迁移** | Alembic（可选） |
| **测试** | pytest + pytest-asyncio + httpx |

## 🚀 快速开始

### 环境要求

- Python **3.11+**
- MySQL 8.0+（仅生产环境需要）
- Docker（可选）

### 本地运行（开发模式 — SQLite 零依赖）

```powershell
# 1. 进入项目目录
cd D:\xiangmu\agent试用\pixel-farm-online

# 2. 创建虚拟环境
python -m venv venv
.\venv\Scripts\activate

# 3. 安装依赖
pip install -r requirements.txt

# 4. 配置环境变量
Copy-Item .env.example .env
# 编辑 .env，确认 DATABASE_URL 指向 SQLite（默认已配好）

# 5. 启动开发服务
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# 6. 打开浏览器
#    Swagger 交互式文档:  http://localhost:8000/docs
#    ReDoc 文档:           http://localhost:8000/redoc
#    健康检查:             http://localhost:8000/api/v1/health
```

### 切换到 MySQL（生产）

编辑 `.env`：

```env
DATABASE_URL=mysql+aiomysql://root:your_password@localhost:3306/pixel_farm?charset=utf8mb4
```

创建数据库：

```sql
CREATE DATABASE pixel_farm CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
```

重启服务即可，应用会自动检测数据库类型并建表。

### Docker 部署

```bash
docker-compose up -d --build
```

## 📁 项目结构

```
pixel-farm-online/
├── app/
│   ├── __init__.py
│   ├── main.py              # FastAPI 应用入口 + 生命周期
│   ├── config.py            # 环境配置加载
│   ├── database.py          # SQLAlchemy 异步引擎 & Session
│   ├── dependencies.py      # 依赖注入（get_db, get_current_user）
│   ├── models/              # ORM 模型层
│   │   ├── __init__.py      # ⚠️ 集中导入所有模型（重要！）
│   │   ├── user.py
│   │   ├── crop.py
│   │   ├── animal.py
│   │   ├── farm.py
│   │   ├── inventory.py
│   │   ├── task.py
│   │   └── shop.py
│   ├── schemas/             # Pydantic DTO（接口契约）
│   │   ├── __init__.py
│   │   ├── common.py
│   │   ├── user.py
│   │   ├── farm.py
│   │   ├── shop.py
│   │   ├── inventory.py
│   │   ├── task.py
│   │   └── admin.py
│   ├── routers/             # 路由层
│   │   ├── __init__.py
│   │   ├── auth.py
│   │   ├── farm.py
│   │   ├── animals.py
│   │   ├── shop.py
│   │   ├── inventory.py
│   │   ├── tasks.py
│   │   ├── rank.py
│   │   └── admin.py
│   └── utils/               # 工具函数
│       ├── __init__.py
│       ├── security.py      # JWT / 密码哈希
│       └── time_utils.py
├── scripts/
│   └── seed_data.py         # 种子数据（内置作物/动物/商店）
├── tests/
├── requirements.txt
├── .env.example
├── .gitignore
└── README.md
```

## 📖 API 文档

启动后访问 `/docs` 查看完整的 **Swagger 交互式文档**，支持直接在浏览器里测试每个接口。

认证方式：登录接口返回 `access_token`，在其他接口的 Header 中携带：

```
Authorization: Bearer <your_token>
```

## 🗄️ 数据库设计

核心表：

| 表名 | 说明 |
|------|------|
| `users` | 玩家账号 & 金币 |
| `crop_templates` | 作物模板（小麦、番茄…） |
| `animal_templates` | 动物模板（鸡、羊、牛） |
| `farm_cells` | 玩家土地格子状态 |
| `player_animals` | 玩家拥有的动物 |
| `inventory` | 玩家背包 |
| `shop_items` | 系统商店商品 |
| `daily_task_progress` | 每日任务进度 |

详细设计见 [PRD.md](../PRD.md) 第四章。

## 🧪 测试

```powershell
pytest tests/ -v
```

## 📌 开发规范

1. **模型必须集中导入** — `app/models/__init__.py` 中必须 import 所有模型，否则 `Base.metadata` 无法识别新表（会导致建表失败）
2. **路由分层** — 每个业务模块一个 router 文件，在 `app/main.py` 统一注册
3. **DTO 分离** — schemas 只定义接口契约，models 只定义数据库结构，绝不混用
4. **工具函数隔离** — JWT、密码哈希等通用逻辑放在 `utils/`，业务逻辑放在 `services/`（后续实现）

## 📄 License

MIT License

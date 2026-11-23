# 项目文档总览

本目录为求职作品集中五个子项目的独立文档，每个项目一份，便于面试时按项目讲解。

统一约定：

- **单一入口**：根目录 `main.py` 聚合启动，`python main.py` 后访问 `http://127.0.0.1:8000`
- **路由前缀**：`/farm` `/stardock` `/secondhand` `/account` `/book`
- **返回入口**：每个子项目页面均可返回作品集首页
- **技术底座**：全部为 Python FastAPI，前端为原生 HTML/CSS/JavaScript + fetch

| # | 项目 | 前缀 | 存储 | 文档 |
|---|------|------|------|------|
| 01 | 像素农场 Online | `/farm` | SQLite（异步 SQLAlchemy） | [01-像素农场.md](./01-像素农场.md) |
| 02 | 星坞 StarDock | `/stardock` | MySQL `stardock` | [02-星坞StarDock.md](./02-星坞StarDock.md) |
| 03 | 校淘集市 | `/secondhand` | MySQL `campus_secondhand` + Redis | [03-校淘集市.md](./03-校淘集市.md) |
| 04 | 招财记账 | `/account` | MySQL `account_db` | [04-招财记账.md](./04-招财记账.md) |
| 05 | 墨香书阁 | `/book` | JSON 文件 | [05-墨香书阁.md](./05-墨香书阁.md) |

## 依赖与初始化

```bash
pip install -r requirements.txt   # 安装聚合依赖
python init_db.py                 # 初始化三个 MySQL 库（幂等）
python main.py                    # 启动作品集
```

- 像素农场的 SQLite 文件位于 `apps/farm/pixel_farm.db`，首次启动自动建表并写入种子数据
- 墨香书阁的 JSON 数据位于 `apps/book/data/`，首次启动自动创建
- Redis 为可选项，未启动时校淘集市的限流/举报去重自动降级放行

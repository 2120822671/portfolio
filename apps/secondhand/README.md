# 校淘集市 campus_secondhand · 校园二手交易平台

面向校园场景的二手交易平台，包含商品发布/搜索/详情、点赞留言、购物车与模拟支付、订单与超时自动关单、买家卖家聊天砍价与以物换物、图片上传等完整链路，前端为手账风格的静态页面（无框架，纯 HTML/CSS/JS），后端为 FastAPI + SQLAlchemy 2.0 + MySQL 8.0。

| 项目 | 内容 |
| --- | --- |
| 项目名称 | campus_secondhand（校淘集市） |
| 版本 | 1.0.0 |
| 技术栈 | FastAPI + SQLAlchemy 2.0 + MySQL 8.0 + PyMySQL + APScheduler + 原生 HTML/CSS/JS |
| 服务地址 | http://127.0.0.1:8001 |
| 接口文档 | http://127.0.0.1:8001/docs （Swagger UI，使用本地静态资源，离线可用） |
| 前端首页 | http://127.0.0.1:8001/static/index.html |

## 一、目录结构

```
二手交易/
├── backend/                    # 后端 FastAPI 代码
│   ├── main.py                 # 应用入口：路由注册、CORS、静态资源挂载、全局异常处理
│   ├── config.py               # 数据库连接配置
│   ├── database.py             # 引擎与 Session 管理
│   ├── models.py               # ORM 模型（user/category/goods/订单等）
│   ├── schemas.py              # Pydantic 校验规则
│   ├── security.py             # 密码 bcrypt 哈希与校验
│   ├── resp.py                 # 统一响应格式 {code,msg,data}
│   ├── paths.py                # 项目路径常量（解析 frontend 绝对路径）
│   ├── redis_client.py         # Redis 单例客户端（连接池、生命周期、降级）
│   ├── risk.py                 # 风控：发布限流（ZSET 滑动窗口）+ 举报去重（SET NX EX）
│   ├── routers/                # auth / goods / order / cart / chat / upload / favorite / report
│   ├── tasks/                  # APScheduler 定时关单任务
│   └── requirements.txt
├── frontend/                   # 前端 HTML/CSS/JS 代码（挂载为 /static）
│   ├── index.html              # 首页：商品列表、搜索筛选、盲盒/漂流瓶入口
│   ├── detail.html             # 商品详情：画廊、留言、砍价贴纸、立即购买/加购/找卖家聊
│   ├── publish.html            # 发布商品：多图上传预览
│   ├── cart.html               # 购物车：勾选/改数量/模拟支付方式结算
│   ├── orders.html             # 我的交易：在售/已售/已预订/下架、我买到的/我卖出的
│   ├── messages.html           # 消息与聊天：会话气泡、砍价、以物换物；通知聚合
│   ├── css/style.css           # 手账风样式
│   ├── js/app.js               # 公共请求封装与交互逻辑
│   ├── swagger/                # 本地 Swagger UI 资源
│   └── uploads/                # 上传图片落盘目录（含种子数据图片）
├── sql/                        # 建表脚本 + 测试数据 SQL
│   ├── create_tables.sql       # 建库建表（含索引、外键）
│   ├── upgrade_step04.sql      # 增量：多图/点赞/留言表
│   ├── upgrade_add_favorite_count.sql
│   ├── upgrade_add_orders.sql  # 增量：订单表与订单日志表
│   ├── upgrade_add_report.sql  # 增量：举报表（24 小时去重由 Redis 控制）
│   ├── upgrade_add_cart_chat.sql # 增量：购物车表、聊天表、订单支付方式字段
│   └── seed_test_data.sql      # 测试数据
├── docs/                       # 报告草稿、设计文档
│   ├── 后端接口文档.md          # 接口清单、表结构、联调故障记录
│   ├── 任务2_增量提示词_定时关单.md
│   ├── 任务2_增量提示词_发布限流与重复举报.md
│   ├── 任务4_提交材料.md
│   ├── 任务4_风控测试记录.md      # BUG-01 缺陷报告
│   ├── 任务5_定时关单缺陷排查对话.md
│   ├── 任务5_风控缺陷修复对话.md   # BUG-01 修复 diff
│   ├── 任务6_回归测试记录.md      # 24 个用例回归
│   ├── 任务7_增量开发经验笔记.md
│   ├── 任务7_APScheduler定时任务事务与并发风险笔记.md
│   ├── 任务7_Redis限流风控实操经验笔记.md
│   ├── 历史备份/                # 早期版本的设计与缺陷报告草稿
│   └── tools/                  # 截图辅助脚本（Playwright/CDP）
├── screenshots/                # 所有运行截图、对话截图
│   ├── 任务4_定时关单/          # 定时任务关单结果、缺陷复现
│   ├── 任务4_风控测试/          # 发布限流 429、重复举报 409、身份绕过缺陷
│   ├── 任务5_缺陷排查/          # 401 报错与修复验证
│   ├── 任务6_接口联调/          # 注册/登录/发布/订单/数据库表截图
│   ├── 任务6_回归测试/          # 24 张 Swagger 接口响应截图（原有业务 + 两条风控）
│   ├── 功能演示/               # 首页、详情、刮刮乐、漂流瓶、集章卡等
│   └── 其他截图/               # 过程性零散截图
├── start.bat                   # 一键启动脚本（自动装依赖并拉起服务）
└── README.md                   # 本文件：项目说明、一键启动步骤
```

## 二、环境要求

- Python 3.10+（本机验证版本 3.14）
- MySQL 8.0，服务名一般为 `mysql8` / `MySQL80`
- Redis 5.0+（风控限流与举报去重使用），默认 `127.0.0.1:6379/0`，可在 `backend/config.py` 的 `REDIS_HOST/REDIS_PORT/REDIS_DB` 调整
- 数据库账号在 `backend/config.py` 中配置，默认 `root / 123456`，库名 `campus_secondhand`

## 三、一键启动

双击项目根目录的 `start.bat`，或在本目录执行：

```powershell
.\start.bat
```

脚本会依次完成：检查 Python → 校验/安装 `backend/requirements.txt` 依赖 → 在 `backend` 目录启动 uvicorn（127.0.0.1:8001）。

手动启动等价命令：

```powershell
cd backend
python -m pip install -r requirements.txt
python -m uvicorn main:app --host 127.0.0.1 --port 8001
```

启动成功的标志（日志）：

```
数据库连接成功: mysql+pymysql://root@localhost:3306/campus_secondhand
定时任务已启动：close_timeout_orders（interval=1 分钟，批量上限 200）
Redis 连接成功: redis://127.0.0.1:6379/0
Application startup complete.
```

停止服务：终端内按 `Ctrl+C`；后台进程可用 `Get-Process python | Stop-Process` 或 `Stop-Process -Id <PID>`。

## 四、数据库初始化

首次部署时按顺序执行 `sql/` 下的脚本（`create_tables.sql` 会创建库与基础表）：

```powershell
cd sql
mysql -u root -p --default-character-set=utf8mb4 < create_tables.sql
mysql -u root -p --default-character-set=utf8mb4 campus_secondhand < upgrade_step04.sql
mysql -u root -p --default-character-set=utf8mb4 campus_secondhand < upgrade_add_favorite_count.sql
mysql -u root -p --default-character-set=utf8mb4 campus_secondhand < upgrade_add_orders.sql
mysql -u root -p --default-character-set=utf8mb4 campus_secondhand < upgrade_add_report.sql
mysql -u root -p --default-character-set=utf8mb4 campus_secondhand < upgrade_add_cart_chat.sql
mysql -u root -p --default-character-set=utf8mb4 campus_secondhand < seed_test_data.sql
```

初始化后共 11 张表：`user`、`category`、`goods`、`goods_image`、`goods_like`、`goods_message`、`orders`、`order_logs`、`report`、`cart_item`、`chat_message`。

## 五、接口速览

全部接口统一返回 `{"code": 0, "msg": "...", "data": ...}`；失败时 `code` 为对应 HTTP 状态码。写操作需登录，并携带登录接口返回的签名令牌 `Authorization: Bearer <token>`；服务端以令牌解析出的身份为准（`X-User-Id` 仅作兼容，会被令牌身份覆盖）。

| 接口 | 方法 | 路径 |
| --- | --- | --- |
| 用户注册 | POST | `/auth/register` |
| 用户登录 | POST | `/auth/login` |
| 商品列表（搜索/筛选/排序/分页） | GET | `/goods` |
| 发布商品 | POST | `/goods` |
| 商品详情（浏览量防刷） | GET | `/goods/{id}` |
| 浏览上报 | POST | `/goods/{id}/view` |
| 点赞 / 取消点赞 | POST / DELETE | `/goods/{id}/like` |
| 状态变更（下架/上架/售出） | POST | `/goods/{id}/status` |
| 删除商品 | DELETE | `/goods/{id}` |
| 发表留言 | POST | `/goods/{id}/messages` |
| 消息通知聚合 | GET | `/goods/notifications` |
| 举报（24 小时内同一用户对同一对象限一次） | POST | `/report` |
| 首页统计 | GET | `/stats` |
| 收藏统计补偿 | GET/POST | `/favorite/...` |
| 订单（下单/支付/取消/详情/订单列表） | POST/GET | `/orders...` |
| 购物车批量结算（模拟支付） | POST | `/orders/batch` |
| 购物车（列表/加入/改数量/移除/清空） | GET/POST/PATCH/DELETE | `/cart` |
| 聊天会话与消息（砍价/换物互动） | GET/POST | `/chat/conversations`、`/chat/messages` |
| 图片上传（多图） | POST | `/upload` |

字段级说明与错误码见 `docs/后端接口文档.md`。

## 六、特色玩法

| 玩法 | 入口 | 说明 |
| --- | --- | --- |
| 🎁 刮刮乐盲盒 | 首页 hero 按钮 | 随机在售商品，canvas 刮开 45% 自动显形 |
| 🍾 商品漂流瓶 | 首页 hero / 我的交易 | 卖家下架投放，他人随机捞瓶捡漏 |
| 🔪 砍价贴纸 | 详情页留言框上方 | 5 个快捷贴纸一键填入留言 |
| 🧺 购物车 + 模拟支付 | 导航「购物车」/ 详情页「加入购物车」 | 多件勾选结算，可选校园一卡通/微信/支付宝/线下当面交易四种模拟方式 |
| 💬 聊天砍价 | 详情页「聊聊 / 砍价」 | 会话内出价，卖家同意后商品标价自动调整为约定价，买家可按此价下单 |
| 🔁 以物换物 | 详情页「用我的宝贝换它」/ 聊天页「换物」 | 会话内选自己的在售宝贝发起换物，对方可同意或拒绝 |
| 🎖️ 集章卡 | 我的交易页顶部 | 每成交一笔盖章，3/5/10 章解锁称号 |
| 🌙 深夜 emo | 首页自动 | 23:00~05:00 切换夜色皮肤与文案 |
| ✨ 贴纸彩蛋 | 连点导航 logo 3 次 | 掉落 26 个手账贴纸动画 |

## 七、文档与截图索引

| 内容 | 位置 |
| --- | --- |
| 表结构、接口清单、CORS 故障记录 | `docs/后端接口文档.md` |
| 定时关单实现与并发风险分析 | `docs/任务2_增量提示词_定时关单.md`、`docs/任务7_APScheduler定时任务事务与并发风险笔记.md` |
| 风控增量提示词（发布限流 / 重复举报，含 Redis key 设计） | `docs/任务2_增量提示词_发布限流与重复举报.md` |
| 风控测试记录与缺陷报告（BUG-01 身份绕过限流） | `docs/任务4_风控测试记录.md`、`screenshots/任务4_风控测试/` |
| BUG-01 修复对话（签名令牌 + 中间件，局部 diff） | `docs/任务5_风控缺陷修复对话.md` |
| 回归测试记录（24 个用例 + 接口响应截图） | `docs/任务6_回归测试记录.md`、`screenshots/任务6_回归测试/` |
| Redis 限流风控实操经验（踩坑笔记） | `docs/任务7_Redis限流风控实操经验笔记.md` |
| 缺陷排查全过程对话 | `docs/任务5_定时关单缺陷排查对话.md` |
| 任务提交材料汇总 | `docs/任务4_提交材料.md` |
| 运行截图（按任务分类） | `screenshots/` |

## 八、常见问题

| 现象 | 原因与处理 |
| --- | --- |
| 启动报 `Unknown database 'campus_secondhand'` | 未初始化数据库，按第四节执行 `sql/` 脚本 |
| 启动报数据库连接失败 | MySQL 服务未启动或 `backend/config.py` 账号密码不符 |
| 页面能开但列表空、控制台 CORS 报错 | 确认通过 8001 端口访问（`/static/index.html`），后端已开启 CORS |
| `/docs` 白屏 | 使用项目内置的 `frontend/swagger` 本地资源，无需外网；确认该目录未被删改 |
| 上传图片 404 | 确认 `frontend/uploads` 目录存在且可写（`backend/paths.py` 已指向该目录） |
| 日志出现“风控降级：Redis 不可用，本次放行” | Redis 未启动或端口不符，风控按 `RISK_FAIL_OPEN` 放行；启动 Redis 后自动恢复，无需重启服务 |
| 发布第 11 次未被限流 | 说明处于降级状态（Redis 不可用），或等待 1 小时后 ZSET 窗口自然释放 |
| 已登录却提示“请先登录”、或一直弹登录框 | localStorage 里是旧版登录态（没有签名令牌）或令牌已过期，后端会返回 401；前端现已自动清理并弹出登录框，重新登录一次即可 |
| 改了前端代码但页面没变化 | 后端对 `/static` 已返回 `Cache-Control: no-cache`，普通刷新即可；个别浏览器仍缓存时按 `Ctrl+F5`，或递增 HTML 里的 `?v=2026111625` |

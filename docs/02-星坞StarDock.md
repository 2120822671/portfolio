# 02 · 星坞 StarDock

> 多模块明星粉丝社区平台。粉丝、管理员、明星三角色协同，覆盖内容浏览、粉丝团、实时聊天与互动娱乐。

- **前缀**：`/stardock/`
- **代码位置**：`apps/stardock/`（后端 `backend/`，前端 `htdocs/`）
- **技术栈**：FastAPI · PyMySQL · DBUtils 连接池 · WebSocket · Starlette Session 登录 · MySQL 8.0

## 功能模块

| 模块 | 说明 |
|------|------|
| 用户与认证 | 注册 / 登录 / 会话保持，角色区分（1 粉丝、2 管理员、3 明星） |
| 明星 | 明星列表与详情、主页资料维护 |
| 粉丝团 | 创建 / 加入 / 退出，成员与团长信息 |
| 实时聊天 | WebSocket 房间广播、历史消息、在线状态 |
| 抽卡 | 卡池与权重配置、抽卡记录、我的卡牌 |
| 充值 | 积分充值套餐、余额与流水 |
| 活动 | 活动列表、报名参与 |
| 管理后台 | 用户管理、抽卡配置、活动维护、数据统计 |

## 目录结构

```
apps/stardock/
├── backend/
│   ├── main.py          # 应用入口、路由与 WebSocket 注册
│   ├── init.sql         # 建库建表 + 初始数据
│   ├── sd_database.py   # DBUtils 连接池与查询封装
│   ├── sd_deps.py       # 登录态 / 角色依赖
│   └── sd_routers/      # auth / users / celebrities / fan_clubs / chat / gacha / recharge / activities
└── htdocs/              # 前端页面
    ├── login.html register.html home.html profile.html
    ├── celebrity.html  → 明星详情 / 粉丝团
    ├── chat.html       → 实时聊天
    ├── gacha.html my-cards.html recharge.html
    ├── admin/          → users / gacha / activities 后台
    ├── css/style.css js/common.js
    └── 启动星坞.bat
```

## 接口分组

统一在 `/stardock/api/...` 下，按 `sd_routers` 分包：

- `auth`：注册、登录、登出、当前会话
- `users`：个人资料、余额、我的卡牌
- `celebrities`：列表、详情
- `fan_clubs`：创建、加入、退出、成员列表
- `chat`：`WebSocket /ws/chat`、历史消息
- `gacha`：卡池、抽卡、记录
- `recharge`：套餐、下单、到账
- `activities`：列表、报名

## 运行说明

- 数据库：`stardock`，可用 `apps/stardock/backend/init.sql` 初始化
- 登录使用 Session（Cookie），与作品集内其他项目的 JWT 互不干扰
- 聊天为 WebSocket 长连接，需通过聚合入口 `/stardock` 前缀访问
- 入口页面：`/stardock/login.html`、`/stardock/home.html`

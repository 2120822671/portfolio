# 图书借阅系统（基线版本）

Python + FastAPI 实现的图书借阅系统基线代码：图书录入、图书列表查询，使用 JSON 文件模拟存储，附带简单前端页面。

## 项目结构

```
book-lending-system/
├── main.py              # FastAPI 入口与路由
├── storage.py           # JSON 文件读写模块
├── models.py            # Pydantic 数据模型
├── static/
│   └── index.html       # 前端页面
├── data/
│   └── books.json       # 模拟存储文件（启动时不存在会自动创建）
└── requirements.txt     # 依赖清单
```

## 启动说明

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

### 2. 启动服务

```bash
uvicorn main:app --reload
```

启动后访问：

- 前端页面：<http://127.0.0.1:8000/>
- 接口自测文档（Swagger UI）：<http://127.0.0.1:8000/docs>

## 接口说明

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| POST | `/books` | 图书录入，参数：`title`（书名）、`author`（作者）、`isbn`、`stock`（库存，≥0），必填校验 |
| GET | `/books` | 图书列表查询，可选参数 `keyword` 按书名模糊搜索 |
| GET | `/health` | 健康检查 |

### 录入示例

```bash
curl -X POST http://127.0.0.1:8000/books \
  -H "Content-Type: application/json" \
  -d "{\"title\": \"Python 编程从入门到实践\", \"author\": \"Eric Matthes\", \"isbn\": \"9787115428028\", \"stock\": 5}"
```

### 查询示例

```bash
curl "http://127.0.0.1:8000/books?keyword=Python"
```

## 存储方式

数据保存在 `data/books.json`，以 JSON 文件模拟数据库持久化；项目启动或首次读写时文件不存在会自动创建。

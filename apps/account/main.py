"""
个人记账小系统 · FastAPI 后端
端口：8005
"""

import sys
import os

# 把本地 libs 目录加入搜索路径（pymysql 安装在这里）
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "libs"))

from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from typing import Optional
import pymysql
from datetime import datetime, timedelta, time

# ==========================================
# 数据库连接配置（根据实际情况修改）
# ==========================================
DB_CONFIG = {
    "host": "localhost",
    "port": 3306,
    "user": "root",
    "password": "123456",
    "database": "account_db",
    "charset": "utf8mb4",
    "cursorclass": pymysql.cursors.DictCursor,
}

app = FastAPI(title="个人记账小系统 API")

# 允许跨域（前端页面打开时可以直接调接口）
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ==========================================
# 静态页面挂载（作品集整合：前端文件在本目录下）
# ==========================================
_BASE_DIR = os.path.dirname(os.path.abspath(__file__))


@app.get("/")
async def index_redirect():
    return RedirectResponse(url="/account/static/index.html")


app.mount("/static", StaticFiles(directory=_BASE_DIR, html=True), name="static")


# ==========================================
# 数据库连接工具
# ==========================================
def get_conn():
    return pymysql.connect(**DB_CONFIG)


# ==========================================
# 请求模型
# ==========================================
class RecordCreate(BaseModel):
    """新增 / 更新记账记录的入参"""
    type: int                          # 1=收入, 2=支出
    amount: float                      # 金额
    category: str                      # 分类名称
    remark: Optional[str] = None       # 备注，可空
    recordTime: str                    # 账目发生时间 "2026-11-04 12:30:00"


class ChatIn(BaseModel):
    """POST /api/chat 入参（大模型解析预留接口）"""
    text: str


# ==========================================
# 工具函数
# ==========================================
def row_to_dict(row: dict) -> dict:
    """把数据库行（record_time）转成 API 返回（recordTime）"""
    if row is None:
        return None
    return {
        "id": row["id"],
        "type": row["type"],
        "amount": float(row["amount"]),
        "category": row["category"],
        "remark": row["remark"],
        "recordTime": row["record_time"].strftime("%Y-%m-%d %H:%M:%S")
                       if row["record_time"] else None,
        "createTime": row["create_time"].strftime("%Y-%m-%d %H:%M:%S")
                       if row["create_time"] else None,
    }


def validate_record(req: RecordCreate) -> datetime:
    """校验账目字段，返回解析后的 record_time（新增与更新共用）"""
    if req.type is None:
        raise HTTPException(status_code=400, detail="type 不能为空")
    if req.amount is None or req.amount <= 0:
        raise HTTPException(status_code=400, detail="amount 不能为空且必须大于 0")
    if not req.category or not req.category.strip():
        raise HTTPException(status_code=400, detail="category 不能为空")
    if not req.recordTime or not req.recordTime.strip():
        raise HTTPException(status_code=400, detail="recordTime 不能为空")
    if req.type not in (1, 2):
        raise HTTPException(status_code=400, detail="type 必须是 1(收入) 或 2(支出)")

    try:
        return datetime.strptime(req.recordTime, "%Y-%m-%d %H:%M:%S")
    except ValueError:
        raise HTTPException(status_code=400, detail="recordTime 格式错误，应为 yyyy-MM-dd HH:mm:ss")


def parse_date(value: str, field: str) -> datetime:
    """把 yyyy-MM-dd 解析为当天 00:00，失败抛 400"""
    try:
        return datetime.strptime(value, "%Y-%m-%d")
    except ValueError:
        raise HTTPException(status_code=400, detail=f"{field} 格式错误，应为 yyyy-MM-dd")


def fetch_one(cursor, record_id: int) -> Optional[dict]:
    cursor.execute("SELECT * FROM account_record WHERE id = %s", (record_id,))
    return cursor.fetchone()


# ==========================================
# 接口 1：新增一条记账记录
# POST /api/records
# ==========================================
@app.post("/api/records")
def create_record(req: RecordCreate):
    record_time = validate_record(req)

    conn = get_conn()
    try:
        with conn.cursor() as cursor:
            cursor.execute("""
                INSERT INTO account_record
                (type, amount, category, remark, record_time)
                VALUES (%s, %s, %s, %s, %s)
            """, (req.type, req.amount, req.category, req.remark, record_time))
            conn.commit()
            row = fetch_one(cursor, cursor.lastrowid)
    finally:
        conn.close()

    return JSONResponse(status_code=200, content={
        "code": 200,
        "message": "添加成功",
        "data": row_to_dict(row),
    })


# ==========================================
# 接口 2：查询收支流水列表
# GET /api/records?pageNum=1&pageSize=10&type=&keyword=&startDate=&endDate=
# ==========================================
@app.get("/api/records")
def list_records(
    pageNum: int = 1,
    pageSize: int = 10,
    type: Optional[int] = None,
    keyword: Optional[str] = None,
    startDate: Optional[str] = None,
    endDate: Optional[str] = None,
):
    if pageNum < 1:
        pageNum = 1
    if pageSize < 1:
        pageSize = 10
    if pageSize > 100:
        pageSize = 100
    if type is not None and type not in (1, 2):
        raise HTTPException(status_code=400, detail="type 必须是 1(收入) 或 2(支出)")

    # 动态拼接筛选条件（全部使用参数化，防注入）
    where = []
    params = []

    if type is not None:
        where.append("type = %s")
        params.append(type)

    if keyword and keyword.strip():
        where.append("(category LIKE %s OR remark LIKE %s)")
        kw = f"%{keyword.strip()}%"
        params.extend([kw, kw])

    if startDate:
        where.append("record_time >= %s")
        params.append(parse_date(startDate, "startDate"))

    if endDate:
        # 结束日期当天也算，用 < 次日零点
        where.append("record_time < %s")
        params.append(parse_date(endDate, "endDate") + timedelta(days=1))

    where_sql = ("WHERE " + " AND ".join(where)) if where else ""
    offset = (pageNum - 1) * pageSize

    conn = get_conn()
    try:
        with conn.cursor() as cursor:
            cursor.execute(f"SELECT COUNT(*) AS cnt FROM account_record {where_sql}", params)
            total = cursor.fetchone()["cnt"]

            cursor.execute(f"""
                SELECT * FROM account_record
                {where_sql}
                ORDER BY record_time DESC, id DESC
                LIMIT %s OFFSET %s
            """, params + [pageSize, offset])
            rows = cursor.fetchall()
    finally:
        conn.close()

    return JSONResponse(status_code=200, content={
        "code": 200,
        "message": "查询成功",
        "data": {
            "total": total,
            "list": [row_to_dict(r) for r in rows],
        },
    })


# ==========================================
# 接口 3：按日期汇总（招财猫播报 / 概览卡）
# GET /api/records/summary?date=2026-11-08
# 注意：必须定义在 /api/records/{record_id} 之前
# ==========================================
@app.get("/api/records/summary")
def records_summary(date: Optional[str] = None):
    if date:
        day = parse_date(date, "date").date()
    else:
        day = datetime.now().date()

    start = datetime.combine(day, time.min)
    end = start + timedelta(days=1)

    conn = get_conn()
    try:
        with conn.cursor() as cursor:
            cursor.execute("""
                SELECT
                  COALESCE(SUM(CASE WHEN type = 1 THEN amount END), 0) AS income,
                  COALESCE(SUM(CASE WHEN type = 2 THEN amount END), 0) AS expense,
                  COUNT(*) AS cnt
                FROM account_record
                WHERE record_time >= %s AND record_time < %s
            """, (start, end))
            stat = cursor.fetchone()

            cursor.execute("""
                SELECT * FROM account_record
                WHERE record_time >= %s AND record_time < %s
                ORDER BY record_time DESC, id DESC
                LIMIT 3
            """, (start, end))
            recent = cursor.fetchall()
    finally:
        conn.close()

    income = float(stat["income"])
    expense = float(stat["expense"])

    return JSONResponse(status_code=200, content={
        "code": 200,
        "message": "查询成功",
        "data": {
            "date": day.strftime("%Y-%m-%d"),
            "income": income,
            "expense": expense,
            "balance": round(income - expense, 2),
            "count": stat["cnt"],
            "recent": [row_to_dict(r) for r in recent],
        },
    })


# ==========================================
# 接口 4：查询单条记录（抽屉回显）
# GET /api/records/{record_id}
# ==========================================
@app.get("/api/records/{record_id}")
def get_record(record_id: int):
    conn = get_conn()
    try:
        with conn.cursor() as cursor:
            row = fetch_one(cursor, record_id)
    finally:
        conn.close()

    if row is None:
        raise HTTPException(status_code=404, detail="记录不存在")

    return JSONResponse(status_code=200, content={
        "code": 200,
        "message": "查询成功",
        "data": row_to_dict(row),
    })


# ==========================================
# 接口 5：更新一条记录
# PUT /api/records/{record_id}
# ==========================================
@app.put("/api/records/{record_id}")
def update_record(record_id: int, req: RecordCreate):
    record_time = validate_record(req)

    conn = get_conn()
    try:
        with conn.cursor() as cursor:
            if fetch_one(cursor, record_id) is None:
                raise HTTPException(status_code=404, detail="记录不存在")

            cursor.execute("""
                UPDATE account_record
                SET type = %s, amount = %s, category = %s, remark = %s, record_time = %s
                WHERE id = %s
            """, (req.type, req.amount, req.category, req.remark, record_time, record_id))
            conn.commit()
            row = fetch_one(cursor, record_id)
    finally:
        conn.close()

    return JSONResponse(status_code=200, content={
        "code": 200,
        "message": "修改成功",
        "data": row_to_dict(row),
    })


# ==========================================
# 接口 6：删除一条记录
# DELETE /api/records/{record_id}
# ==========================================
@app.delete("/api/records/{record_id}")
def delete_record(record_id: int):
    conn = get_conn()
    try:
        with conn.cursor() as cursor:
            if fetch_one(cursor, record_id) is None:
                raise HTTPException(status_code=404, detail="记录不存在")

            cursor.execute("DELETE FROM account_record WHERE id = %s", (record_id,))
            conn.commit()
    finally:
        conn.close()

    return JSONResponse(status_code=200, content={
        "code": 200,
        "message": "删除成功",
        "data": {"id": record_id},
    })


# ==========================================
# 接口 7：自然语言解析（预留大模型开关）
# POST /api/chat
# 未配置 LLM_API_KEY 时返回 mode=rule，由前端用本地规则解析
# ==========================================
@app.post("/api/chat")
def chat(req: ChatIn):
    if not req.text or not req.text.strip():
        raise HTTPException(status_code=400, detail="text 不能为空")

    if not os.getenv("LLM_API_KEY"):
        return JSONResponse(status_code=200, content={
            "code": 200,
            "mode": "rule",
            "message": "未启用大模型解析，请使用前端规则解析",
            "data": None,
        })

    # 配置 Key 后在此接入大模型，返回结构需与前端约定一致：
    # {"type": 1|2, "amount": float, "category": str, "remark": str, "recordTime": "yyyy-MM-dd HH:mm:ss"}
    raise HTTPException(status_code=501, detail="大模型解析尚未实现")


# ==========================================
# 启动入口：端口 8005
# ==========================================
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8005)

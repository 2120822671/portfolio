"""
个人记账小系统 · FastAPI 后端
端口：8005

模块划分：
  db.py         数据库连接与表结构初始化
  llm.py        大模型增强层（规则兜底 + 大模型增强）
  automation.py 自动化流程引擎（APScheduler）
  main.py       本文件：HTTP 接口层
"""

import sys
import os
import re
import json
import random
from datetime import datetime, timedelta, date, time as dtime
from calendar import monthrange

# 把本地 libs 目录加入搜索路径（pymysql 安装在这里）
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "libs"))

from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse, HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from typing import Optional, List

from db import get_conn, init_db
import llm as llm_mod
import automation


@asynccontextmanager
async def lifespan(_app: FastAPI):
    """启动时初始化数据库并启停调度器"""
    init_db()
    automation.start_scheduler()
    yield
    automation.shutdown_scheduler()


app = FastAPI(title="个人记账小系统 API", lifespan=lifespan)

# 允许跨域（前端页面用 file:// 打开时仍可调接口）
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ==========================================
# 静态页面托管：让前端与接口同源（http://localhost:8005）
# 好处：预览面板 / iframe / 任何嵌入环境都不会再出现跨域或混合内容问题
# ==========================================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# 前端静态文件名（根路径与 /static/ 双挂载，保证两种打开方式都能加载）
FRONTEND_FILES = ["app.js", "dashboard.js", "modal.js", "style.css"]


@app.get("/", include_in_schema=False)
def serve_index():
    """首页：直接返回前端页面（必须用 HTMLResponse，否则换行会变成字面 \\n）"""
    index_path = os.path.join(BASE_DIR, "index.html")
    if os.path.exists(index_path):
        with open(index_path, "r", encoding="utf-8") as f:
            return HTMLResponse(content=f.read())
    return JSONResponse(status_code=404, content={"detail": "index.html 不存在"})


def _serve_file(filename: str):
    """读取前端文件并按类型返回"""
    path = os.path.join(BASE_DIR, filename)
    if not os.path.exists(path):
        return JSONResponse(status_code=404, content={"detail": filename + " 不存在"})
    ctype = {
        ".js": "application/javascript; charset=utf-8",
        ".css": "text/css; charset=utf-8",
        ".html": "text/html; charset=utf-8",
    }.get(os.path.splitext(filename)[1].lower(), "application/octet-stream")
    with open(path, "r", encoding="utf-8") as f:
        return HTMLResponse(content=f.read(), media_type=ctype)


# 根路径静态文件（/app.js、/style.css …）——与 /static/ 等价
for _fname in FRONTEND_FILES:
    app.get(f"/{_fname}", include_in_schema=False)(
        lambda _f=_fname: _serve_file(_f)
    )

# 挂载前端静态资源（app.js / dashboard.js / modal.js / style.css）
app.mount("/static", StaticFiles(directory=BASE_DIR), name="static")


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
    accountId: int = 1                 # 归属账本ID


class ChatIn(BaseModel):
    """POST /api/chat 入参"""
    text: str
    accountId: int = 1


class BookIn(BaseModel):
    name: str
    bookType: str = "现金"
    initBalance: float = 0
    icon: str = "💰"


class RecurringIn(BaseModel):
    name: str
    type: int
    amount: float
    category: str
    remark: Optional[str] = None
    accountId: int = 1
    cycleType: str = "monthly"         # daily/weekly/monthly
    cycleValue: int = 1
    startDate: str
    endDate: Optional[str] = None
    autoPost: int = 1                  # 1=自动入账 0=只提醒
    enabled: int = 1


class BudgetIn(BaseModel):
    category: str
    period: str                        # YYYY-MM
    amount: float
    enabled: int = 1


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
        "accountId": row.get("account_id", 1) if isinstance(row, dict) else 1,
    }


def ok(data=None, message="操作成功", **extra):
    payload = {"code": 200, "message": message, "data": data}
    payload.update(extra)
    return JSONResponse(status_code=200, content=payload)


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


def resolve_account(account_id: int) -> int:
    """校验账本是否存在，不存在回落到默认账本"""
    conn = get_conn()
    try:
        with conn.cursor() as cursor:
            cursor.execute("SELECT id FROM account_book WHERE id = %s", (account_id,))
            if cursor.fetchone():
                return account_id
            cursor.execute("SELECT id FROM account_book WHERE is_default = 1 ORDER BY id LIMIT 1")
            row = cursor.fetchone()
            return row["id"] if row else 1
    finally:
        conn.close()


# ==========================================
# 接口 1：新增一条记账记录
# POST /api/records
# ==========================================
@app.post("/api/records")
def create_record(req: RecordCreate):
    record_time = validate_record(req)
    account_id = resolve_account(req.accountId)

    conn = get_conn()
    try:
        with conn.cursor() as cursor:
            cursor.execute("""
                INSERT INTO account_record
                (type, amount, category, remark, record_time, account_id)
                VALUES (%s, %s, %s, %s, %s, %s)
            """, (req.type, req.amount, req.category, req.remark, record_time, account_id))
            conn.commit()
            row = fetch_one(cursor, cursor.lastrowid)
            automation.touch_checkin(conn, record_time.date())
            conn.commit()
    finally:
        conn.close()

    return ok(row_to_dict(row), "添加成功")


# ==========================================
# 接口 2：查询收支流水列表
# GET /api/records?pageNum=1&pageSize=10&type=&keyword=&startDate=&endDate=&accountId=
# ==========================================
@app.get("/api/records")
def list_records(
    pageNum: int = 1,
    pageSize: int = 10,
    type: Optional[int] = None,
    keyword: Optional[str] = None,
    startDate: Optional[str] = None,
    endDate: Optional[str] = None,
    accountId: Optional[int] = None,
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

    if accountId:
        where.append("account_id = %s")
        params.append(accountId)

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

    return ok({
        "total": total,
        "list": [row_to_dict(r) for r in rows],
    }, "查询成功")


# ==========================================
# 接口 3：按日期汇总（招财猫播报 / 概览卡）
# GET /api/records/summary?date=2026-11-08&accountId=
# 注意：必须定义在 /api/records/{record_id} 之前
# ==========================================
@app.get("/api/records/summary")
def records_summary(date: Optional[str] = None, accountId: Optional[int] = None):
    if date:
        day = parse_date(date, "date").date()
    else:
        day = datetime.now().date()

    start = datetime.combine(day, dtime.min)
    end = start + timedelta(days=1)

    conn = get_conn()
    try:
        with conn.cursor() as cursor:
            params = [start, end]
            acc_sql = ""
            if accountId:
                acc_sql = " AND account_id = %s"
                params.append(accountId)

            cursor.execute(f"""
                SELECT
                  COALESCE(SUM(CASE WHEN type = 1 THEN amount END), 0) AS income,
                  COALESCE(SUM(CASE WHEN type = 2 THEN amount END), 0) AS expense,
                  COUNT(*) AS cnt
                FROM account_record
                WHERE record_time >= %s AND record_time < %s{acc_sql}
            """, params)
            stat = cursor.fetchone()

            cursor.execute(f"""
                SELECT * FROM account_record
                WHERE record_time >= %s AND record_time < %s{acc_sql}
                ORDER BY record_time DESC, id DESC
                LIMIT 3
            """, params)
            recent = cursor.fetchall()
    finally:
        conn.close()

    income = float(stat["income"])
    expense = float(stat["expense"])

    return ok({
        "date": day.strftime("%Y-%m-%d"),
        "income": income,
        "expense": expense,
        "balance": round(income - expense, 2),
        "count": stat["cnt"],
        "recent": [row_to_dict(r) for r in recent],
    }, "查询成功")


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

    return ok(row_to_dict(row), "查询成功")


# ==========================================
# 接口 5：更新一条记录
# PUT /api/records/{record_id}
# ==========================================
@app.put("/api/records/{record_id}")
def update_record(record_id: int, req: RecordCreate):
    record_time = validate_record(req)
    account_id = resolve_account(req.accountId)

    conn = get_conn()
    try:
        with conn.cursor() as cursor:
            if fetch_one(cursor, record_id) is None:
                raise HTTPException(status_code=404, detail="记录不存在")

            cursor.execute("""
                UPDATE account_record
                SET type = %s, amount = %s, category = %s, remark = %s,
                    record_time = %s, account_id = %s
                WHERE id = %s
            """, (req.type, req.amount, req.category, req.remark, record_time,
                  account_id, record_id))
            conn.commit()
            row = fetch_one(cursor, record_id)
    finally:
        conn.close()

    return ok(row_to_dict(row), "修改成功")


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

    return ok({"id": record_id}, "删除成功")


# ==========================================
# 账本相关
# ==========================================
@app.get("/api/books")
def list_books():
    """账本列表 + 各自余额（余额实时计算，不落库）"""
    conn = get_conn()
    try:
        with conn.cursor() as cursor:
            cursor.execute("""
                SELECT b.*,
                  COALESCE(SUM(CASE WHEN r.type = 1 THEN r.amount END), 0) AS income,
                  COALESCE(SUM(CASE WHEN r.type = 2 THEN r.amount END), 0) AS expense,
                  COUNT(r.id) AS cnt
                FROM account_book b
                LEFT JOIN account_record r ON r.account_id = b.id
                GROUP BY b.id
                ORDER BY b.sort_order, b.id
            """)
            rows = cursor.fetchall()
    finally:
        conn.close()

    out = []
    for b in rows:
        income = float(b["income"])
        expense = float(b["expense"])
        out.append({
            "id": b["id"],
            "name": b["name"],
            "bookType": b["book_type"],
            "icon": b["icon"],
            "initBalance": float(b["init_balance"]),
            "income": round(income, 2),
            "expense": round(expense, 2),
            "balance": round(float(b["init_balance"]) + income - expense, 2),
            "count": int(b["cnt"]),
            "isDefault": bool(b["is_default"]),
        })
    return ok(out, "查询成功")


@app.post("/api/books")
def create_book(req: BookIn):
    if not req.name or not req.name.strip():
        raise HTTPException(status_code=400, detail="账本名称不能为空")

    conn = get_conn()
    try:
        with conn.cursor() as cursor:
            # 先查排序值再插入（不能在 INSERT 的 VALUES 里子查询同一张表）
            cursor.execute("SELECT COALESCE(MAX(sort_order), 0) + 1 AS nxt FROM account_book")
            nxt = cursor.fetchone()["nxt"]
            cursor.execute("""
                INSERT INTO account_book (name, book_type, init_balance, icon, sort_order)
                VALUES (%s, %s, %s, %s, %s)
            """, (req.name.strip(), req.bookType, req.initBalance, req.icon, nxt))
            conn.commit()
            cursor.execute("SELECT * FROM account_book WHERE id = %s", (cursor.lastrowid,))
            row = cursor.fetchone()
    finally:
        conn.close()

    return ok({
        "id": row["id"], "name": row["name"], "bookType": row["book_type"],
        "icon": row["icon"], "initBalance": float(row["init_balance"]),
    }, "账本创建成功")


@app.put("/api/books/{book_id}")
def update_book(book_id: int, req: BookIn):
    if not req.name or not req.name.strip():
        raise HTTPException(status_code=400, detail="账本名称不能为空")

    conn = get_conn()
    try:
        with conn.cursor() as cursor:
            cursor.execute("SELECT id FROM account_book WHERE id = %s", (book_id,))
            if not cursor.fetchone():
                raise HTTPException(status_code=404, detail="账本不存在")
            cursor.execute("""
                UPDATE account_book
                SET name = %s, book_type = %s, init_balance = %s, icon = %s
                WHERE id = %s
            """, (req.name.strip(), req.bookType, req.initBalance, req.icon, book_id))
            conn.commit()
    finally:
        conn.close()

    return ok({"id": book_id}, "账本更新成功")


@app.delete("/api/books/{book_id}")
def delete_book(book_id: int):
    """删除账本：账本下的流水不删，转移到默认账本，避免数据丢失"""
    conn = get_conn()
    try:
        with conn.cursor() as cursor:
            cursor.execute("SELECT * FROM account_book WHERE id = %s", (book_id,))
            row = cursor.fetchone()
            if not row:
                raise HTTPException(status_code=404, detail="账本不存在")
            if row["is_default"]:
                raise HTTPException(status_code=400, detail="默认账本不可删除")

            cursor.execute("SELECT id FROM account_book WHERE is_default = 1 ORDER BY id LIMIT 1")
            dflt = cursor.fetchone()
            default_id = dflt["id"] if dflt else 1

            cursor.execute("UPDATE account_record SET account_id = %s WHERE account_id = %s",
                           (default_id, book_id))
            moved = cursor.rowcount
            cursor.execute("UPDATE recurring_rule SET account_id = %s WHERE account_id = %s",
                           (default_id, book_id))
            cursor.execute("DELETE FROM account_book WHERE id = %s", (book_id,))
            conn.commit()
    finally:
        conn.close()

    return ok({"id": book_id, "movedRecords": moved, "defaultId": default_id},
              f"账本已删除，{moved} 笔流水已转移到默认账本")


# ==========================================
# 周期账单
# ==========================================
@app.get("/api/recurring")
def list_recurring(enabled: Optional[int] = None):
    conn = get_conn()
    try:
        with conn.cursor() as cursor:
            sql = "SELECT * FROM recurring_rule"
            params = []
            if enabled is not None:
                sql += " WHERE enabled = %s"
                params.append(enabled)
            sql += " ORDER BY enabled DESC, id"
            cursor.execute(sql, params)
            rows = cursor.fetchall()

            cursor.execute("SELECT * FROM recurring_run ORDER BY id DESC LIMIT 50")
            runs = cursor.fetchall()
    finally:
        conn.close()

    out = [{
        "id": r["id"], "name": r["name"], "type": r["type"],
        "amount": float(r["amount"]), "category": r["category"],
        "remark": r["remark"], "accountId": r["account_id"],
        "cycleType": r["cycle_type"], "cycleValue": r["cycle_value"],
        "startDate": r["start_date"].strftime("%Y-%m-%d") if r["start_date"] else None,
        "endDate": r["end_date"].strftime("%Y-%m-%d") if r["end_date"] else None,
        "autoPost": bool(r["auto_post"]), "enabled": bool(r["enabled"]),
    } for r in rows]

    runs_out = [{
        "id": r["id"], "ruleId": r["rule_id"], "periodKey": r["period_key"],
        "recordId": r["record_id"], "status": r["status"], "message": r["message"],
        "createdAt": r["created_at"].strftime("%Y-%m-%d %H:%M:%S") if r["created_at"] else None,
    } for r in runs]

    return ok({"rules": out, "runs": runs_out}, "查询成功")


@app.post("/api/recurring")
def create_recurring(req: RecurringIn):
    if req.type not in (1, 2):
        raise HTTPException(status_code=400, detail="type 必须是 1(收入) 或 2(支出)")
    if req.amount is None or req.amount <= 0:
        raise HTTPException(status_code=400, detail="amount 必须大于 0")
    if req.cycleType not in ("daily", "weekly", "monthly"):
        raise HTTPException(status_code=400, detail="cycleType 必须是 daily/weekly/monthly")
    if not req.name or not req.name.strip():
        raise HTTPException(status_code=400, detail="name 不能为空")

    start = parse_date(req.startDate, "startDate").date()
    end = parse_date(req.endDate, "endDate").date() if req.endDate else None
    if end and end < start:
        raise HTTPException(status_code=400, detail="endDate 不能早于 startDate")
    account_id = resolve_account(req.accountId)

    conn = get_conn()
    try:
        with conn.cursor() as cursor:
            cursor.execute("""
                INSERT INTO recurring_rule
                (name, type, amount, category, remark, account_id, cycle_type, cycle_value,
                 start_date, end_date, auto_post, enabled)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, (req.name.strip(), req.type, req.amount, req.category, req.remark,
                  account_id, req.cycleType, max(1, req.cycleValue), start, end,
                  req.autoPost, req.enabled))
            conn.commit()
            new_id = cursor.lastrowid
    finally:
        conn.close()

    return ok({"id": new_id}, "周期账单创建成功")


@app.put("/api/recurring/{rule_id}")
def update_recurring(rule_id: int, req: RecurringIn):
    start = parse_date(req.startDate, "startDate").date()
    end = parse_date(req.endDate, "endDate").date() if req.endDate else None

    conn = get_conn()
    try:
        with conn.cursor() as cursor:
            cursor.execute("SELECT id FROM recurring_rule WHERE id = %s", (rule_id,))
            if not cursor.fetchone():
                raise HTTPException(status_code=404, detail="规则不存在")
            cursor.execute("""
                UPDATE recurring_rule
                SET name = %s, type = %s, amount = %s, category = %s, remark = %s,
                    account_id = %s, cycle_type = %s, cycle_value = %s,
                    start_date = %s, end_date = %s, auto_post = %s, enabled = %s
                WHERE id = %s
            """, (req.name.strip(), req.type, req.amount, req.category, req.remark,
                  resolve_account(req.accountId), req.cycleType, max(1, req.cycleValue),
                  start, end, req.autoPost, req.enabled, rule_id))
            conn.commit()
    finally:
        conn.close()

    return ok({"id": rule_id}, "周期账单已更新")


@app.delete("/api/recurring/{rule_id}")
def delete_recurring(rule_id: int):
    conn = get_conn()
    try:
        with conn.cursor() as cursor:
            cursor.execute("DELETE FROM recurring_rule WHERE id = %s", (rule_id,))
            if cursor.rowcount == 0:
                raise HTTPException(status_code=404, detail="规则不存在")
            conn.commit()
    finally:
        conn.close()

    return ok({"id": rule_id}, "周期账单已删除")


@app.post("/api/recurring/{rule_id}/run")
def run_one_recurring(rule_id: int):
    """手动执行单条规则（调试用，force=True 会忽略幂等）"""
    conn = get_conn()
    try:
        with conn.cursor() as cursor:
            cursor.execute("SELECT * FROM recurring_rule WHERE id = %s", (rule_id,))
            row = cursor.fetchone()
    finally:
        conn.close()

    if not row:
        raise HTTPException(status_code=404, detail="规则不存在")

    today = date.today()
    if not automation._is_due(row, today):
        return ok({"ran": False, "reason": "今天不在该规则的执行周期内"}, "今天无需执行")

    result = automation.run_recurring(target=today, force=True)
    return ok(result, "执行完成")


@app.post("/api/recurring/run")
def run_all_recurring():
    """手动触发全部周期账单（幂等，已处理的周期不重复入账）"""
    result = automation.run_recurring()
    return ok(result, "周期账单处理完成")


# ==========================================
# 预算
# ==========================================
@app.get("/api/budgets")
def list_budgets(period: Optional[str] = None):
    period = period or date.today().strftime("%Y-%m")
    if not re.match(r"^\d{4}-\d{2}$", period):
        raise HTTPException(status_code=400, detail="period 格式错误，应为 YYYY-MM")

    start = datetime.strptime(period + "-01", "%Y-%m-%d")
    last = monthrange(start.year, start.month)[1]
    end = start + timedelta(days=last)

    conn = get_conn()
    try:
        with conn.cursor() as cursor:
            cursor.execute("""
                SELECT * FROM budget_rule WHERE period = %s ORDER BY amount DESC
            """, (period,))
            rules = cursor.fetchall()

            cursor.execute("""
                SELECT category, COALESCE(SUM(amount), 0) AS used
                FROM account_record
                WHERE type = 2 AND record_time >= %s AND record_time < %s
                GROUP BY category
            """, (start, end))
            used_map = {r["category"]: float(r["used"]) for r in cursor.fetchall()}
    finally:
        conn.close()

    out = []
    for r in rules:
        limit = float(r["amount"])
        used = round(used_map.get(r["category"], 0), 2)
        rate = round(used / limit * 100, 1) if limit > 0 else 0
        out.append({
            "id": r["id"], "category": r["category"], "period": r["period"],
            "amount": limit, "used": used, "rate": rate,
            "remain": round(limit - used, 2), "over": used > limit,
            "enabled": bool(r["enabled"]),
        })
    return ok({"period": period, "budgets": out}, "查询成功")


@app.post("/api/budgets")
def create_budget(req: BudgetIn):
    if not req.category or not req.category.strip():
        raise HTTPException(status_code=400, detail="category 不能为空")
    if not re.match(r"^\d{4}-\d{2}$", req.period):
        raise HTTPException(status_code=400, detail="period 格式错误，应为 YYYY-MM")
    if req.amount is None or req.amount <= 0:
        raise HTTPException(status_code=400, detail="amount 必须大于 0")

    conn = get_conn()
    try:
        with conn.cursor() as cursor:
            cursor.execute("""
                INSERT INTO budget_rule (category, period, amount, enabled)
                VALUES (%s, %s, %s, %s)
                ON DUPLICATE KEY UPDATE amount = VALUES(amount), enabled = VALUES(enabled)
            """, (req.category.strip(), req.period, req.amount, req.enabled))
            conn.commit()
            new_id = cursor.lastrowid
    finally:
        conn.close()

    return ok({"id": new_id}, "预算已保存")


@app.delete("/api/budgets/{budget_id}")
def delete_budget(budget_id: int):
    conn = get_conn()
    try:
        with conn.cursor() as cursor:
            cursor.execute("DELETE FROM budget_rule WHERE id = %s", (budget_id,))
            if cursor.rowcount == 0:
                raise HTTPException(status_code=404, detail="预算不存在")
            conn.commit()
    finally:
        conn.close()

    return ok({"id": budget_id}, "预算已删除")


# ==========================================
# 统计（看板图表数据源）
# GET /api/stats/overview?months=6
# ==========================================
@app.get("/api/stats/overview")
def stats_overview(months: int = 6, accountId: Optional[int] = None):
    """返回看板所需的全部聚合数据"""
    months = max(1, min(months, 12))
    today = date.today()

    # 近 months 个月的自然月区间
    month_ends = []
    y, m = today.year, today.month
    for _ in range(months):
        month_ends.append((y, m))
        m -= 1
        if m == 0:
            m = 12
            y -= 1
    month_ends.reverse()

    first = datetime(month_ends[0][0], month_ends[0][1], 1)

    conn = get_conn()
    try:
        with conn.cursor() as cursor:
            acc_sql = " AND account_id = %s" if accountId else ""
            acc_params = [accountId] if accountId else []

            # 分类占比（本月）
            month_start = datetime(today.year, today.month, 1)
            cursor.execute(f"""
                SELECT category, COALESCE(SUM(amount), 0) AS amt
                FROM account_record
                WHERE type = 2 AND record_time >= %s{acc_sql}
                GROUP BY category ORDER BY amt DESC
            """, [month_start] + acc_params)
            category = [{"name": r["category"], "value": round(float(r["amt"]), 2)}
                        for r in cursor.fetchall()]

            # 月度趋势（注意：pymysql 用 % 占位，SQL 里的 % 必须写成 %%）
            cursor.execute(f"""
                SELECT DATE_FORMAT(record_time, '%%Y-%%m') AS ym,
                       COALESCE(SUM(CASE WHEN type = 1 THEN amount END), 0) AS income,
                       COALESCE(SUM(CASE WHEN type = 2 THEN amount END), 0) AS expense
                FROM account_record
                WHERE record_time >= %s{acc_sql}
                GROUP BY ym ORDER BY ym
            """, [first] + acc_params)
            trend_map = {r["ym"]: r for r in cursor.fetchall()}
            trend = []
            for (yy, mm) in month_ends:
                key = f"{yy}-{mm:02d}"
                r = trend_map.get(key)
                trend.append({
                    "month": key,
                    "income": round(float(r["income"]), 2) if r else 0,
                    "expense": round(float(r["expense"]), 2) if r else 0,
                })

            # 近 7 日支出
            cursor.execute(f"""
                SELECT DATE(record_time) AS d,
                       COALESCE(SUM(CASE WHEN type = 2 THEN amount END), 0) AS amt
                FROM account_record
                WHERE type = 2 AND record_time >= %s{acc_sql}
                GROUP BY d ORDER BY d
            """, [datetime.combine(today - timedelta(days=6), dtime.min)] + acc_params)
            day_map = {str(r["d"]): float(r["amt"]) for r in cursor.fetchall()}
            last7 = []
            for i in range(7):
                d = today - timedelta(days=6 - i)
                ds = d.strftime("%Y-%m-%d")
                last7.append({
                    "date": ds,
                    "label": f"{d.month}/{d.day}",
                    "amount": round(day_map.get(ds, 0), 2),
                })
    finally:
        conn.close()

    return ok({"category": category, "trend": trend, "last7": last7}, "查询成功")


# ==========================================
# 日报 / 消息中心
# ==========================================
@app.get("/api/reports")
def list_reports(limit: int = 30, unreadOnly: bool = False):
    limit = max(1, min(limit, 100))
    conn = get_conn()
    try:
        with conn.cursor() as cursor:
            sql = "SELECT * FROM daily_report"
            params = []
            if unreadOnly:
                sql += " WHERE is_read = 0"
            sql += " ORDER BY report_date DESC, id DESC LIMIT %s"
            params.append(limit)
            cursor.execute(sql, params)
            rows = cursor.fetchall()

            cursor.execute("SELECT COUNT(*) AS cnt FROM daily_report WHERE is_read = 0")
            unread = cursor.fetchone()["cnt"]
    finally:
        conn.close()

    out = []
    for r in rows:
        data = None
        try:
            data = json.loads(r["data_json"]) if r["data_json"] else None
        except (ValueError, TypeError):
            data = None
        out.append({
            "id": r["id"],
            "date": r["report_date"].strftime("%Y-%m-%d") if r["report_date"] else None,
            "type": r["report_type"],
            "title": r["title"],
            "content": r["content"],
            "data": data,
            "level": r["level"],
            "isRead": bool(r["is_read"]),
            "createdAt": r["created_at"].strftime("%Y-%m-%d %H:%M:%S") if r["created_at"] else None,
        })
    return ok({"reports": out, "unread": unread}, "查询成功")


@app.post("/api/reports/{report_id}/read")
def mark_report_read(report_id: int):
    conn = get_conn()
    try:
        with conn.cursor() as cursor:
            cursor.execute("UPDATE daily_report SET is_read = 1 WHERE id = %s", (report_id,))
            conn.commit()
    finally:
        conn.close()

    return ok({"id": report_id}, "已标记为已读")


@app.post("/api/reports/read-all")
def mark_all_read():
    conn = get_conn()
    try:
        with conn.cursor() as cursor:
            cursor.execute("UPDATE daily_report SET is_read = 1 WHERE is_read = 0")
            changed = cursor.rowcount
            conn.commit()
    finally:
        conn.close()

    return ok({"changed": changed}, "全部标记为已读")


# ==========================================
# 打卡 / 成就
# ==========================================
@app.get("/api/checkin")
def get_checkin():
    """连续记账天数 + 打卡日历"""
    conn = get_conn()
    try:
        with conn.cursor() as cursor:
            cursor.execute("""
                SELECT check_date, record_cnt FROM checkin_log
                ORDER BY check_date DESC LIMIT 120
            """)
            rows = cursor.fetchall()
    finally:
        conn.close()

    days = {r["check_date"].strftime("%Y-%m-%d"): int(r["record_cnt"]) for r in rows}

    # 连续天数：从今天（或昨天）往回数
    streak = 0
    cur = date.today()
    if cur.strftime("%Y-%m-%d") not in days:
        cur = cur - timedelta(days=1)  # 今天还没记，不算断
    while cur.strftime("%Y-%m-%d") in days:
        streak += 1
        cur = cur - timedelta(days=1)

    total_days = len(days)
    total_records = sum(days.values())

    # 成就徽章
    badges = [
        {"name": "开张大吉", "desc": "完成第一次记账", "got": total_records >= 1},
        {"name": "勤勉小账房", "desc": "累计记录 100 笔", "got": total_records >= 100},
        {"name": "七日连击", "desc": "连续记账 7 天", "got": streak >= 7},
        {"name": "月度常客", "desc": "累计打卡 30 天", "got": total_days >= 30},
        {"name": "存钱有道", "desc": "本月结余为正", "got": False},
    ]

    # 本月结余 → 替换最后一个徽章的判定
    now = datetime.now()
    month_start = datetime(now.year, now.month, 1)
    conn2 = get_conn()
    try:
        with conn2.cursor() as cursor:
            cursor.execute("""
                SELECT COALESCE(SUM(CASE WHEN type = 1 THEN amount END), 0) AS income,
                       COALESCE(SUM(CASE WHEN type = 2 THEN amount END), 0) AS expense
                FROM account_record WHERE record_time >= %s
            """, (month_start,))
            m = cursor.fetchone()
        positive = float(m["income"]) > float(m["expense"])
    finally:
        conn2.close()
    badges[-1]["got"] = positive

    return ok({
        "streak": streak,
        "totalDays": total_days,
        "totalRecords": total_records,
        "days": days,
        "badges": badges,
    }, "查询成功")


# ==========================================
# 调度器状态
# ==========================================
@app.get("/api/scheduler/jobs")
def scheduler_jobs():
    return ok({
        "jobs": automation.get_jobs_status(),
        "llmEnabled": llm_mod.llm_enabled(),
        "llmModel": llm_mod.MODEL if llm_mod.llm_enabled() else None,
        "timezone": automation.TZ,
    }, "查询成功")


# ==========================================
# 自动化流程：手动触发
# ==========================================
@app.post("/api/automation/run-summary")
def trigger_summary():
    result = automation.run_daily_summary(force=True)
    return ok(result, "日终汇总已生成")


@app.post("/api/automation/run-review")
def trigger_review():
    result = automation.run_daily_review(force=True)
    return ok(result, "每日复盘已生成")


# ==========================================
# 接口 7：招财猫对话（规则兜底 + 大模型增强）
# POST /api/chat
# ==========================================
CAT_RULES = [
    (["午饭", "午餐", "晚饭", "晚餐", "早餐", "早饭", "吃饭", "火锅", "外卖", "餐饮",
      "奶茶", "咖啡", "零食", "面条", "米饭", "food"], "餐饮"),
    (["打车", "出租", "地铁", "公交", "车费", "加油", "停车", "交通", "高铁", "机票"], "交通"),
    (["购物", "衣服", "鞋", "淘宝", "京东", "超市", "日用", "买"], "购物"),
    (["电影", "游戏", "娱乐", "唱歌", "旅游", "ktv", "演唱会"], "娱乐"),
    (["房租", "水电", "物业", "话费", "宽带", "生活"], "生活"),
    (["医院", "药", "看病", "体检", "医疗"], "医疗"),
]

INCOME_RULES = [
    (["工资", "薪水"], "工资"),
    (["奖金", "年终奖"], "奖金"),
    (["报销"], "报销"),
    (["红包", "转账", "收款", "到账", "兼职", "利息", "收入", "进账"], "其他收入"),
]


def rule_parse(text: str) -> dict:
    """
    规则解析（后端兜底版，与前端逻辑对齐）。
    返回 {"intent": "record|query|analysis|chat", "records": [...], "reply": str}
    """
    raw = (text or "").strip()
    if not raw:
        return {"intent": "chat", "records": [], "reply": "喵？说什么呢～"}

    # 问句意图
    if re.search(r"(今天|今日|本月|这个月|上周|最近).*(花了|支出|流水|收支|消费|记账|账|多少钱)", raw) \
       or re.search(r"(花了多少|支出多少|流水多少|今天怎么样|分析|建议|复盘|账单)", raw):
        intent = "analysis" if re.search(r"(分析|建议|复盘|账单|怎么样)", raw) else "query"
        return {"intent": intent, "records": [], "reply": ""}

    # 金额
    m = re.search(r"(\d+(?:\.\d{1,2})?)", raw)
    if not m:
        return {"intent": "chat", "records": [], "reply": ""}
    amount = float(m.group(1))
    if amount <= 0:
        return {"intent": "chat", "records": [], "reply": ""}

    # 收支类型 + 分类
    rtype, category = 2, None
    for kws, cat in INCOME_RULES:
        if any(k in raw for k in kws):
            rtype, category = 1, cat
            break
    if rtype == 2:
        for kws, cat in CAT_RULES:
            if any(k in raw for k in kws):
                category = cat
                break
    category = category or ("其他收入" if rtype == 1 else "其他")

    # 时间
    when = datetime.now()
    if "前天" in raw:
        when -= timedelta(days=2)
    elif "昨天" in raw:
        when -= timedelta(days=1)

    return {
        "intent": "record",
        "records": [{
            "type": rtype,
            "amount": round(amount, 2),
            "category": category,
            "remark": raw[:255],
            "recordTime": when.strftime("%Y-%m-%d %H:%M:%S"),
        }],
        "reply": "",
    }


def _query_reply(text: str, accountId: int) -> str:
    """查询类意图：直接查库生成播报"""
    today = date.today()
    if "本月" in text or "这个月" in text:
        start = datetime(today.year, today.month, 1)
        label = "本月"
    elif "上周" in text:
        start = datetime.combine(today - timedelta(days=today.weekday() + 7), dtime.min)
        label = "上周"
    elif "昨天" in text:
        start = datetime.combine(today - timedelta(days=1), dtime.min)
        label = "昨天"
    else:
        start = datetime.combine(today, dtime.min)
        label = "今天"
    end = start + timedelta(days=1)

    conn = get_conn()
    try:
        with conn.cursor() as cursor:
            params = [start, end]
            acc_sql = ""
            if accountId:
                acc_sql = " AND account_id = %s"
                params.append(accountId)
            cursor.execute(f"""
                SELECT COALESCE(SUM(CASE WHEN type = 1 THEN amount END), 0) AS income,
                       COALESCE(SUM(CASE WHEN type = 2 THEN amount END), 0) AS expense,
                       COUNT(*) AS cnt
                FROM account_record WHERE record_time >= %s AND record_time < %s{acc_sql}
            """, params)
            s = cursor.fetchone()
    finally:
        conn.close()

    income, expense = float(s["income"]), float(s["expense"])
    if s["cnt"] == 0:
        return f"{label}还没有记账喵～"
    return (f"{label}支出 ¥{expense:.2f}，收入 ¥{income:.2f}，结余 ¥{income - expense:.2f}，"
            f"共 {s['cnt']} 笔喵。")


def _analysis_reply(text: str, accountId: int) -> str:
    """分析类意图：用统计引擎生成复盘（优先大模型）"""
    stats = automation.build_day_stats(account_id=accountId)
    if llm_mod.llm_enabled():
        try:
            content = llm_mod.daily_review(stats)
            if content:
                return content
        except Exception:  # noqa: BLE001
            pass
    return automation._rule_review_text(stats)


@app.post("/api/chat")
def chat(req: ChatIn):
    """
    招财猫对话入口。
    优先级：大模型（可用时）→ 后端规则 → 返回 mode=rule 让前端用本地规则
    """
    if not req.text or not req.text.strip():
        raise HTTPException(status_code=400, detail="text 不能为空")

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # 1. 大模型优先
    if llm_mod.llm_enabled():
        try:
            result = llm_mod.detect_intent(req.text, now)
            intent = result["intent"]

            if intent == "record" and result["records"]:
                # 规范化记录
                records = []
                for r in result["records"]:
                    try:
                        t = int(r.get("type", 2))
                        amt = float(r.get("amount", 0))
                        if t not in (1, 2) or amt <= 0:
                            continue
                        records.append({
                            "type": t,
                            "amount": round(amt, 2),
                            "category": str(r.get("category") or "其他"),
                            "remark": str(r.get("remark") or req.text)[:255],
                            "recordTime": str(r.get("recordTime") or now),
                        })
                    except (TypeError, ValueError):
                        continue
                if records:
                    return ok({
                        "intent": "record",
                        "records": records,
                        "reply": result.get("reply") or "",
                    }, "解析成功", mode="llm")

            if intent == "query":
                return ok({
                    "intent": "query",
                    "records": [],
                    "reply": result.get("reply") or _query_reply(req.text, req.accountId),
                }, "解析成功", mode="llm")

            if intent == "analysis":
                reply = result.get("reply") or ""
                # 问句的 reply 若是泛泛而谈，用数据驱动的复盘替换
                stats_reply = _analysis_reply(req.text, req.accountId)
                if len(stats_reply) > len(reply):
                    reply = stats_reply
                return ok({
                    "intent": "analysis",
                    "records": [],
                    "reply": reply,
                }, "解析成功", mode="llm")

            # chat 意图
            return ok({
                "intent": "chat",
                "records": [],
                "reply": result.get("reply") or "喵～我在呢，随时可以帮你记账。",
            }, "解析成功", mode="llm")
        except Exception as e:  # noqa: BLE001 - 任何大模型异常都回落规则
            print(f"[chat] 大模型回落规则：{e}")

    # 2. 后端规则兜底
    parsed = rule_parse(req.text)
    if parsed["intent"] == "query":
        parsed["reply"] = _query_reply(req.text, req.accountId)
    elif parsed["intent"] == "analysis":
        parsed["reply"] = _analysis_reply(req.text, req.accountId)

    return ok({
        "intent": parsed["intent"],
        "records": parsed["records"],
        "reply": parsed.get("reply", ""),
    }, "使用规则解析", mode="rule")


# ==========================================
# 每日鼓励语（趣味功能）
# ==========================================
DAILY_QUOTES = [
    "喵～今天的每一笔都算数。",
    "会记账的人，运气都不会太差。",
    "钱要花在让你眼睛发亮的地方喵。",
    "存钱不是抠门，是给未来的自己发红包。",
    "记录本身就是一种温柔喵。",
    "小小一笔，大大安心。",
    "你不是在花钱，你是在挑选想要的生活喵。",
    "今天的克制，是明天的底气。",
]

@app.get("/api/quote")
def daily_quote():
    idx = date.today().toordinal() % len(DAILY_QUOTES)
    return ok({"quote": DAILY_QUOTES[idx]}, "查询成功")


# ==========================================
# 启动入口：端口 8005
# ==========================================
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8005)

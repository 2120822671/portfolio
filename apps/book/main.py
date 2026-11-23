import os
from typing import Optional

from fastapi import FastAPI, HTTPException, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException as StarletteHTTPException

import book_storage
from book_models import Book, BookCreate, BookUpdate, Borrow, BorrowCreate, CompletionSubmit

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

app = FastAPI(title="墨香书阁", description="图书管理 / 借阅归还 / 统计看板（JSON 文件模拟存储）",
              version="2.1.0")

# 挂载静态资源目录（封面图片 + 前端页面）
app.mount("/static", StaticFiles(directory=os.path.join(BASE_DIR, "static")), name="static")


# ==================== 统一返回格式 ====================
# 所有接口返回 {code, msg, data}：code=0 成功；其余为 HTTP 状态码
# HTTP 状态码保持 REST 语义（200/201/400/404/422），前端按 code 判断业务结果

def ok(data=None, status_code: int = 200):
    """成功响应包装（data 统一做 JSON 序列化，兼容 Pydantic 模型）"""
    body = {"code": 0, "msg": "ok", "data": jsonable_encoder(data)}
    if status_code == 200:
        return body
    return JSONResponse(status_code=status_code, content=body)


def fail(status_code: int, msg: str):
    """失败响应包装"""
    return JSONResponse(status_code=status_code,
                        content={"code": status_code, "msg": msg, "data": None})


@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request: Request, exc: StarletteHTTPException):
    """HTTP 异常统一转为 {code, msg, data} 格式，错误信息直接透出给前端提示"""
    return fail(exc.status_code, str(exc.detail))


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """参数校验失败：取第一条错误的中文提示，避免前端展示原始堆栈"""
    first = exc.errors()[0] if exc.errors() else {}
    field = ".".join(str(p) for p in first.get("loc", [])[1:]) or "参数"
    msg = f"参数校验失败：{field} {first.get('msg', '不合法')}"
    return fail(422, msg)


@app.exception_handler(Exception)
async def unexpected_exception_handler(request: Request, exc: Exception):
    """兜底异常：不向前端暴露内部细节"""
    return fail(500, "服务器内部错误，请稍后重试")


@app.on_event("startup")
def on_startup() -> None:
    """启动时确保 JSON 数据文件存在"""
    book_storage._ensure_file()


@app.get("/", include_in_schema=False)
def index():
    """返回前端页面"""
    return FileResponse(os.path.join(BASE_DIR, "static", "index.html"))


@app.get("/health")
def health():
    """健康检查（保留原始格式，供运维探活）"""
    return {"status": "ok"}


# ==================== 图书管理 ====================

@app.post("/books", status_code=201)
def create_book(payload: BookCreate):
    """图书录入"""
    book = Book(id=0, **payload.model_dump())
    return ok(book_storage.add_book(book), status_code=201)


@app.get("/books")
def list_books(keyword: Optional[str] = None, page: int = 1, page_size: int = 10):
    """图书分页列表：按书名关键字模糊搜索，附带各书未归还记录数（控制按钮置灰）"""
    if page < 1 or page_size < 1 or page_size > 100:
        raise HTTPException(status_code=400, detail="分页参数不合法：page / page_size 需在合理范围内")
    books = book_storage.load_books()
    if keyword:
        kw = keyword.lower()
        books = [b for b in books if kw in b.title.lower()]
    counts = book_storage.active_borrow_counts()
    items = [
        {**b.model_dump(), "active_borrows": counts.get(b.id, 0)}
        for b in books
    ]
    return ok(book_storage.paginate(items, page, page_size))


@app.put("/books/{book_id}")
def edit_book(book_id: int, payload: BookUpdate):
    """编辑图书（只更新传入字段）"""
    try:
        book = book_storage.update_book(book_id, payload.model_dump(exclude_none=True))
        return ok(book)
    except book_storage.StorageError as e:
        raise HTTPException(status_code=404, detail=str(e))


@app.delete("/books/{book_id}")
def remove_book(book_id: int):
    """删除图书：存在未归还借阅记录时禁止删除"""
    try:
        book_storage.delete_book(book_id)
        return ok({"id": book_id})
    except book_storage.StorageError as e:
        # 业务冲突（有未归还记录）返回 400，图书不存在返回 404
        code = 404 if f"id={book_id}" in str(e) else 400
        raise HTTPException(status_code=code, detail=str(e))


# ==================== 借阅 / 归还 ====================

@app.post("/books/{book_id}/borrow", status_code=201)
def borrow_book(book_id: int, payload: BorrowCreate):
    """借阅图书：校验库存与幂等（同一人同书未归还不可重复借）后，库存减 1 并生成记录"""
    try:
        return ok(book_storage.borrow_book(book_id, payload.borrower), status_code=201)
    except book_storage.StorageError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/books/{book_id}/return")
def return_book(book_id: int, borrower: Optional[str] = None):
    """归还图书：可指定借阅人；校验存在未归还记录后库存加 1 并写入归还时间"""
    try:
        return ok(book_storage.return_book(book_id, borrower))
    except book_storage.StorageError as e:
        raise HTTPException(status_code=400, detail=str(e))


# ==================== 借阅记录 ====================

@app.get("/borrows")
def list_borrows(
    borrower: Optional[str] = None,
    book: Optional[str] = None,
    status: Optional[str] = None,
    start: Optional[str] = None,
    end: Optional[str] = None,
    page: int = 1,
    page_size: int = 10,
):
    """借阅记录分页查询：支持借阅人（精确）/ 书名（模糊）/ 状态 / 起止日期多条件筛选"""
    if page < 1 or page_size < 1 or page_size > 100:
        raise HTTPException(status_code=400, detail="分页参数不合法：page / page_size 需在合理范围内")
    if status not in (None, "", "active", "returned"):
        raise HTTPException(status_code=400, detail="状态筛选仅支持 active（未归还）/ returned（已归还）")
    borrows = book_storage.filter_borrows(
        book_storage.load_borrows(), borrower, book, status, start, end
    )
    return ok(book_storage.paginate(borrows, page, page_size))


@app.get("/borrows/export")
def export_borrows(
    borrower: Optional[str] = None,
    book: Optional[str] = None,
    status: Optional[str] = None,
    start: Optional[str] = None,
    end: Optional[str] = None,
):
    """按当前筛选条件导出借阅记录 CSV（带 BOM，Excel 直接打开不乱码）"""
    borrows = book_storage.filter_borrows(
        book_storage.load_borrows(), borrower, book, status, start, end
    )
    import csv
    import io

    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(["记录ID", "图书ID", "图书名称", "借阅人", "借阅时间", "归还时间", "状态"])
    for r in borrows:
        writer.writerow([
            r.id, r.book_id, r.book_title, r.borrower,
            r.borrowed_at, r.returned_at or "",
            "已归还" if r.returned_at else "未归还",
        ])
    # utf-8-sig 带 BOM，Excel 打开中文不乱码
    content = "\ufeff" + buf.getvalue()
    return Response(
        content=content,
        media_type="text/csv; charset=utf-8-sig",
        headers={"Content-Disposition": "attachment; filename=borrow_records.csv"},
    )


# ==================== 统计看板 ====================

@app.get("/stats")
def stats():
    """数据看板：总图书数（种）/ 在借数量 / 可借数量（库存总和）"""
    return ok(book_storage.get_stats())


# ==================== 成就系统 ====================

@app.get("/books/{book_id}/quiz")
def get_book_quiz(book_id: int):
    """获取某本书的问答题（隐藏答案，供前端展示）"""
    quiz = book_storage.get_quiz_public(book_id)
    if quiz is None:
        raise HTTPException(status_code=404, detail=f"该书暂无问答题库")
    return ok(quiz)


@app.post("/books/{book_id}/complete")
def complete_book(book_id: int, payload: CompletionSubmit):
    """提交完书验证（带答案），正确率 ≥ 60% 才算读完"""
    try:
        completion = book_storage.complete_book(book_id, payload.borrower, payload.answers)
        return ok(completion, status_code=201)
    except book_storage.StorageError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/achievements")
def get_achievements():
    """获取所有成就徽章及其解锁状态"""
    return ok(book_storage.get_achievements())


@app.get("/completions")
def get_completions(borrower: Optional[str] = None):
    """获取完书记录（可按完书人筛选）"""
    records = book_storage.load_completions()
    if borrower:
        records = [r for r in records if r.borrower == borrower]
    return ok([r.model_dump() for r in records])

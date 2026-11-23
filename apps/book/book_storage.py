import json
import os
import threading
from datetime import datetime
from typing import List, Optional

from book_models import Book, Borrow, Completion, Achievement, QuizBook

DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
DATA_FILE = os.path.join(DATA_DIR, "books.json")
# 本次增量新增：借阅记录存储文件
BORROW_FILE = os.path.join(DATA_DIR, "borrows.json")
# 成就系统新增：完书记录 / 成就状态 / 问答题库
COMPLETION_FILE = os.path.join(DATA_DIR, "completions.json")
ACHIEVEMENT_STATE_FILE = os.path.join(DATA_DIR, "achievement_state.json")
QUIZ_FILE = os.path.join(DATA_DIR, "quizzes.json")

# 优化（任务7）：改用 RLock，允许 load_books/save_books 内部加锁，
# 与 add_book/borrow_book/return_book 外层锁嵌套调用而不死锁
_lock = threading.RLock()


def _ensure_file() -> None:
    """项目启动 / 首次读写时，若数据文件不存在则自动创建"""
    os.makedirs(DATA_DIR, exist_ok=True)
    if not os.path.exists(DATA_FILE):
        with open(DATA_FILE, "w", encoding="utf-8") as f:
            json.dump([], f, ensure_ascii=False, indent=2)


def load_books() -> List[Book]:
    """读取全部图书（utf-8-sig 兼容带 BOM 的文件）

    优化（任务7）：读路径同样加锁，避免与写路径产生读写竞态。
    """
    with _lock:
        _ensure_file()
        with open(DATA_FILE, "r", encoding="utf-8-sig") as f:
            raw = json.load(f)
        return [Book(**item) for item in raw]


def save_books(books: List[Book]) -> None:
    """写入全部图书

    优化（任务7）：写入改为「临时文件 + os.replace 原子替换」，
    任何时候读取到的都是完整数据，进程中途崩溃也不会留下半截文件。
    """
    with _lock:
        _ensure_file()
        tmp = DATA_FILE + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump([b.model_dump() for b in books], f, ensure_ascii=False, indent=2)
        os.replace(tmp, DATA_FILE)


def next_id(books: List[Book]) -> int:
    """生成自增 id"""
    return max((b.id for b in books), default=0) + 1


def add_book(book: Book) -> Book:
    """新增图书（线程安全）"""
    with _lock:
        books = load_books()
        book.id = next_id(books)
        books.append(book)
        save_books(books)
    return book


# ==================== 以下为本次增量新增（借阅 / 归还） ====================

class StorageError(Exception):
    """业务校验失败（库存不足 / 记录不存在等），错误信息为中文提示"""


def _ensure_borrow_file() -> None:
    """若借阅记录文件不存在则自动创建"""
    os.makedirs(DATA_DIR, exist_ok=True)
    if not os.path.exists(BORROW_FILE):
        with open(BORROW_FILE, "w", encoding="utf-8") as f:
            json.dump([], f, ensure_ascii=False, indent=2)


def load_borrows() -> List[Borrow]:
    """读取全部借阅记录（优化：读路径加锁）"""
    with _lock:
        _ensure_borrow_file()
        with open(BORROW_FILE, "r", encoding="utf-8-sig") as f:
            raw = json.load(f)
        return [Borrow(**item) for item in raw]


def save_borrows(borrows: List[Borrow]) -> None:
    """写入全部借阅记录（优化：临时文件 + 原子替换）"""
    with _lock:
        _ensure_borrow_file()
        tmp = BORROW_FILE + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump([b.model_dump() for b in borrows], f, ensure_ascii=False, indent=2)
        os.replace(tmp, BORROW_FILE)


def _now() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def borrow_book(book_id: int, borrower: str) -> Borrow:
    """借阅图书：库存减 1 并生成借阅记录（线程安全）

    事务性说明：库存扣减与借阅记录写入在同一把可重入锁内完成，
    两个数据文件均以「临时文件 + os.replace」原子落盘，任一步骤失败
    都不会留下半截数据，从而防止并发超借与数据不一致。
    """
    with _lock:
        books = load_books()
        book = next((b for b in books if b.id == book_id), None)
        if book is None:
            raise StorageError(f"图书不存在（id={book_id}）")
        if book.stock <= 0:
            raise StorageError(f"《{book.title}》库存不足，无法借阅")

        borrows = load_borrows()
        # 幂等校验：同一借阅人同一本书存在未归还记录时，拒绝重复借阅
        dup = next(
            (r for r in borrows
             if r.book_id == book_id and r.borrower == borrower
             and r.returned_at is None),
            None,
        )
        if dup is not None:
            raise StorageError(
                f"借阅人「{borrower}」的《{book.title}》尚有未归还记录，不能重复借阅"
            )

        record = Borrow(
            id=next_id(borrows),
            book_id=book.id,
            book_title=book.title,
            borrower=borrower,
            borrowed_at=_now(),
            returned_at=None,
        )
        book.stock -= 1
        save_books(books)
        borrows.append(record)
        save_borrows(borrows)
    return record


def return_book(book_id: int, borrower: Optional[str] = None) -> Borrow:
    """归还图书：库存加 1 并标记借阅记录为已归还（线程安全）

    borrower 指定时仅归还该借阅人的未归还记录；为 None 时归还最早一条。
    """
    with _lock:
        books = load_books()
        book = next((b for b in books if b.id == book_id), None)
        if book is None:
            raise StorageError(f"图书不存在（id={book_id}）")

        borrows = load_borrows()
        record = next(
            (
                r for r in borrows
                if r.book_id == book_id
                and r.returned_at is None
                and (borrower is None or r.borrower == borrower)
            ),
            None,
        )
        if record is None:
            if borrower:
                raise StorageError(
                    f"《{book.title}》没有找到借阅人「{borrower}」的未归还记录，无法归还"
                )
            raise StorageError(f"《{book.title}》没有未归还的借阅记录，无法归还")

        book.stock += 1
        save_books(books)
        record.returned_at = _now()
        save_borrows(borrows)
    return record


# ==================== 以下为本次增量新增（页面优化迭代） ====================

def update_book(book_id: int, changes: dict) -> Book:
    """编辑图书：仅更新传入的非空字段，校验存在性（线程安全）"""
    with _lock:
        books = load_books()
        book = next((b for b in books if b.id == book_id), None)
        if book is None:
            raise StorageError(f"图书不存在（id={book_id}）")
        for field, value in changes.items():
            if value is not None:
                setattr(book, field, value)
        save_books(books)
    return book


def delete_book(book_id: int) -> None:
    """删除图书：存在未归还借阅记录时禁止删除，防止库存与记录失配（线程安全）"""
    with _lock:
        books = load_books()
        book = next((b for b in books if b.id == book_id), None)
        if book is None:
            raise StorageError(f"图书不存在（id={book_id}）")

        active = next(
            (r for r in load_borrows()
             if r.book_id == book_id and r.returned_at is None),
            None,
        )
        if active is not None:
            raise StorageError(
                f"《{book.title}》尚有未归还的借阅记录，删除后会导致数据不一致，已禁止"
            )
        save_books([b for b in books if b.id != book_id])


def active_borrow_counts() -> dict:
    """统计各图书的未归还记录数，供列表页控制「归还」按钮的置灰状态"""
    counts = {}
    for r in load_borrows():
        if r.returned_at is None:
            counts[r.book_id] = counts.get(r.book_id, 0) + 1
    return counts


def get_stats() -> dict:
    """首页数据看板：图书种数 / 在借数量 / 可借数量（库存总和）"""
    books = load_books()
    return {
        "total_books": len(books),
        "borrowed": sum(1 for r in load_borrows() if r.returned_at is None),
        "available": sum(b.stock for b in books),
    }


def paginate(items: list, page: int, page_size: int) -> dict:
    """通用内存分页，返回分页元数据供前端渲染分页组件"""
    total = len(items)
    pages = (total + page_size - 1) // page_size
    start = (page - 1) * page_size
    return {
        "list": items[start:start + page_size],
        "total": total,
        "page": page,
        "page_size": page_size,
        "pages": max(pages, 1),
    }


def filter_borrows(
    borrows: List[Borrow],
    borrower: Optional[str] = None,
    book_keyword: Optional[str] = None,
    status: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
) -> List[Borrow]:
    """借阅记录多条件筛选

    - borrower：借阅人精确匹配
    - book_keyword：书名模糊匹配
    - status：active=未归还 / returned=已归还
    - start_date / end_date：借阅时间起止（含当天，格式 YYYY-MM-DD）
    """
    result = borrows
    if borrower:
        # 精确匹配，避免子串误命中
        result = [r for r in result if r.borrower == borrower]
    if book_keyword:
        kw = book_keyword.lower()
        result = [r for r in result if kw in r.book_title.lower()]
    if status == "active":
        result = [r for r in result if r.returned_at is None]
    elif status == "returned":
        result = [r for r in result if r.returned_at is not None]
    if start_date:
        result = [r for r in result if r.borrowed_at >= start_date]
    if end_date:
        # 借阅时间存储到秒，比较时补齐当天结束时刻
        result = [r for r in result if r.borrowed_at <= f"{end_date} 23:59:59"]
    return result


# ==================== 成就系统 ====================

# 成就定义表（id, 名称, 图标, 描述, 提示, 目标值, 类别）
ACHIEVEMENT_DEFS = [
    {"id": "first_book",     "name": "开卷有益",    "icon": "📖", "description": "读完第一本书",
     "hint": "通过完书验证即可解锁", "target": 1,  "category": "起点"},
    {"id": "three_books",    "name": "小有所成",    "icon": "📚", "description": "累计读完 3 本书",
     "hint": "坚持阅读即可达成",     "target": 3,  "category": "累计"},
    {"id": "five_books",     "name": "博览群书",    "icon": "🏆", "description": "累计读完 5 本书",
     "hint": "墨香渐浓",             "target": 5,  "category": "累计"},
    {"id": "ten_books",      "name": "书虫达人",    "icon": "🎖️", "description": "累计读完 10 本书",
     "hint": "真正的读书人",         "target": 10, "category": "累计"},
    {"id": "all_books",      "name": "书香门第",    "icon": "👑", "description": "读完馆藏全部 15 本",
     "hint": "典藏尽收",             "target": 15, "category": "终极"},
    {"id": "perfect_streak", "name": "过目不忘",    "icon": "🧠", "description": "连续 3 次答题全对",
     "hint": "考验真功夫",           "target": 3,  "category": "智慧"},
    {"id": "day_double",     "name": "一气呵成",    "icon": "⚡", "description": "同一天读完 2 本书",
     "hint": "效率惊人",             "target": 2,  "category": "效率"},
    {"id": "night_owl",      "name": "烛火夜读",    "icon": "🕯️", "description": "晚上 20:00 后完书一本",
     "hint": "夜深正是读书时",       "target": 1,  "category": "趣味"},
    {"id": "return_promise", "name": "信守承诺",    "icon": "🔄", "description": "先读完再归还（按时履约）",
     "hint": "先读后还，言出必行",   "target": 1,  "category": "品格"},
    {"id": "classic_reader", "name": "经典收藏",    "icon": "💎", "description": "读完任一经典文学",
     "hint": "红楼 / 围城 / 小王子…", "target": 1, "category": "品位"},
]

# 经典文学书目（book_id 列表）
CLASSIC_IDS = {8, 10, 12, 13}  # 小王子、红楼梦、苏菲的世界、围城


def _ensure_completion_file() -> None:
    os.makedirs(DATA_DIR, exist_ok=True)
    if not os.path.exists(COMPLETION_FILE):
        with open(COMPLETION_FILE, "w", encoding="utf-8") as f:
            json.dump([], f, ensure_ascii=False, indent=2)


def _ensure_state_file() -> None:
    os.makedirs(DATA_DIR, exist_ok=True)
    if not os.path.exists(ACHIEVEMENT_STATE_FILE):
        with open(ACHIEVEMENT_STATE_FILE, "w", encoding="utf-8") as f:
            json.dump({}, f, ensure_ascii=False, indent=2)


# ---- 问答题库 ----

def load_quizzes() -> list:
    """加载问答题库"""
    with _lock:
        os.makedirs(DATA_DIR, exist_ok=True)
        if not os.path.exists(QUIZ_FILE):
            return []
        with open(QUIZ_FILE, "r", encoding="utf-8") as f:
            return json.load(f)


def get_quiz_for_book(book_id: int) -> Optional[dict]:
    """获取某本书的问答题（含正确答案，仅后端内部使用）"""
    for qz in load_quizzes():
        if qz.get("book_id") == book_id:
            return qz
    return None


def get_quiz_public(book_id: int) -> Optional[dict]:
    """获取某本书的问答题（前端用，隐藏正确答案）"""
    qz = get_quiz_for_book(book_id)
    if not qz:
        return None
    return {
        "book_id": qz["book_id"],
        "questions": [
            {"question": q["question"], "options": q["options"]}
            for q in qz["questions"]
        ],
    }


# ---- 完书记录 ----

def load_completions() -> List[Completion]:
    with _lock:
        _ensure_completion_file()
        with open(COMPLETION_FILE, "r", encoding="utf-8-sig") as f:
            raw = json.load(f)
        return [Completion(**item) for item in raw]


def save_completions(completions: List[Completion]) -> None:
    with _lock:
        _ensure_completion_file()
        tmp = COMPLETION_FILE + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump([c.model_dump() for c in completions], f, ensure_ascii=False, indent=2)
        os.replace(tmp, COMPLETION_FILE)


def complete_book(book_id: int, borrower: str, answers: list[int]) -> Completion:
    """提交完书验证，校验答案，通过后写入完书记录"""
    with _lock:
        books = load_books()
        book = next((b for b in books if b.id == book_id), None)
        if book is None:
            raise StorageError(f"图书不存在（id={book_id}）")

        # 防重复完书：同一本书 + 同一人已经完书过，拒绝
        existing = next(
            (c for c in load_completions()
             if c.book_id == book_id and c.borrower == borrower),
            None,
        )
        if existing is not None:
            raise StorageError(f"借阅人「{borrower}」已标记完《{book.title}》，不可重复")

        qz = get_quiz_for_book(book_id)
        if qz is None:
            raise StorageError(f"《{book.title}》暂无问答题库，暂不支持完书验证")

        questions = qz["questions"]
        if len(answers) != len(questions):
            raise StorageError(f"答案数量与题目数量不匹配（需要 {len(questions)} 个）")

        correct = sum(1 for i, q in enumerate(questions) if answers[i] == q["answer"])
        score = correct / len(questions)

        # 及格线：60%（至少答对 2/3）
        if score < 0.6:
            raise StorageError(
                f"答题正确率不足（{correct}/{len(questions)}），60% 以上才算读完，再接再厉！"
            )

        completions = load_completions()
        now = _now()
        record = Completion(
            id=max((c.id for c in completions), default=0) + 1,
            book_id=book.id,
            book_title=book.title,
            borrower=borrower,
            correct_count=correct,
            total_count=len(questions),
            score=round(score * 100, 1),
            completed_at=now,
        )
        completions.append(record)
        save_completions(completions)

        # 检查成就解锁
        _check_achievements(record)

        return record


# ---- 成就解锁检测 ----

def _load_achievement_state() -> dict:
    with _lock:
        _ensure_state_file()
        with open(ACHIEVEMENT_STATE_FILE, "r", encoding="utf-8-sig") as f:
            return json.load(f)


def _save_achievement_state(state: dict) -> None:
    with _lock:
        _ensure_state_file()
        tmp = ACHIEVEMENT_STATE_FILE + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(state, f, ensure_ascii=False, indent=2)
        os.replace(tmp, ACHIEVEMENT_STATE_FILE)


def _check_achievements(latest: Completion) -> None:
    """每次完书后检查所有成就是否该解锁"""
    with _lock:
        state = _load_achievement_state()
        completions = load_completions()

        # 历史全部全对的连续记录（用于过目不忘）
        all_correct_streak = 0
        max_streak = 0
        for c in sorted(completions, key=lambda x: x.id):
            if c.correct_count == c.total_count:
                all_correct_streak += 1
                max_streak = max(max_streak, all_correct_streak)
            else:
                all_correct_streak = 0

        # 同一天完书数（用于一气呵成）
        latest_day = latest.completed_at[:10]
        day_count = sum(1 for c in completions if c.completed_at[:10] == latest_day)

        # 晚间完书（用于烛火夜读）
        hour = int(latest.completed_at[11:13])
        is_night = hour >= 20

        # 先读后还（用于信守承诺）：如果有这本的借阅记录，且归还时间在完书时间之后
        return_promise = False
        borrows = load_borrows()
        related_borrow = next(
            (b for b in borrows if b.book_id == latest.book_id
             and b.borrower == latest.borrower),
            None,
        )
        if related_borrow and related_borrow.returned_at:
            return_promise = related_borrow.returned_at >= latest.completed_at

        # 经典文学（用于经典收藏）
        is_classic = latest.book_id in CLASSIC_IDS

        total_unique_books = len({c.book_id for c in completions})

        # 更新/解锁每个成就
        for defn in ACHIEVEMENT_DEFS:
            aid = defn["id"]
            if state.get(aid, {}).get("unlocked"):
                continue  # 已解锁就不重复处理

            if aid == "first_book":
                progress = 1 if total_unique_books >= 1 else 0
                unlock = total_unique_books >= 1
            elif aid in ("three_books", "five_books", "ten_books", "all_books"):
                progress = total_unique_books
                unlock = total_unique_books >= defn["target"]
            elif aid == "perfect_streak":
                progress = max_streak
                unlock = max_streak >= 3
            elif aid == "day_double":
                progress = day_count
                unlock = day_count >= 2
            elif aid == "night_owl":
                progress = 1 if is_night else 0
                unlock = is_night
            elif aid == "return_promise":
                progress = 1 if return_promise else 0
                unlock = return_promise
            elif aid == "classic_reader":
                classic_done = {c.book_id for c in completions if c.book_id in CLASSIC_IDS}
                progress = len(classic_done)
                unlock = len(classic_done) >= 1
            else:
                progress = 0
                unlock = False

            if progress > 0 or unlock:
                state[aid] = {
                    "unlocked": unlock,
                    "unlocked_at": latest.completed_at if unlock else None,
                    "progress": progress,
                }

        _save_achievement_state(state)


def get_achievements() -> list:
    """获取所有成就及其当前解锁状态（用于前端展示）"""
    state = _load_achievement_state()
    completions = load_completions()
    total_unique = len({c.book_id for c in completions})

    results = []
    for defn in ACHIEVEMENT_DEFS:
        aid = defn["id"]
        info = state.get(aid, {})
        unlocked = info.get("unlocked", False)
        progress = info.get("progress", 0)

        # 首次请求时补算 progress（老存档没有）
        if progress == 0 and not unlocked:
            if aid in ("first_book", "three_books", "five_books", "ten_books", "all_books"):
                progress = total_unique

        results.append({
            **defn,
            "unlocked": unlocked,
            "unlocked_at": info.get("unlocked_at"),
            "progress": progress,
            "target": defn["target"],
            "category": defn["category"],
        })
    return results

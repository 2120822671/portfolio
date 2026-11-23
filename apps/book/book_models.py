from typing import Optional

from pydantic import BaseModel, Field


class BookCreate(BaseModel):
    """图书录入请求模型"""
    title: str = Field(..., min_length=1, description="书名")
    author: str = Field(..., min_length=1, description="作者")
    isbn: str = Field(..., min_length=1, description="ISBN")
    stock: int = Field(..., ge=0, description="库存数量")
    cover_url: Optional[str] = Field(None, description="书籍封面图片 URL")


class Book(BaseModel):
    """图书完整模型（含自增 id）"""
    id: int
    title: str
    author: str
    isbn: str
    stock: int
    cover_url: Optional[str] = None


class BookUpdate(BaseModel):
    """图书编辑请求模型（只传需要修改的字段）"""
    title: Optional[str] = Field(None, min_length=1, description="书名")
    author: Optional[str] = Field(None, min_length=1, description="作者")
    isbn: Optional[str] = Field(None, min_length=1, description="ISBN")
    stock: Optional[int] = Field(None, ge=0, description="库存数量")
    cover_url: Optional[str] = Field(None, description="书籍封面图片 URL")


# ==================== 以下为本次增量新增（借阅 / 归还） ====================

class BorrowCreate(BaseModel):
    """借阅请求模型"""
    borrower: str = Field(..., min_length=1, description="借阅人姓名")


class Borrow(BaseModel):
    """借阅记录完整模型"""
    id: int
    book_id: int = Field(..., description="图书 id")
    book_title: str = Field(..., description="书名快照")
    borrower: str = Field(..., description="借阅人姓名")
    borrowed_at: str = Field(..., description="借阅时间")
    returned_at: Optional[str] = Field(None, description="归还时间，未归还为 null")


# ==================== 成就系统（完书 + 徽章） ====================

class QuizQuestion(BaseModel):
    """单道问答题"""
    question: str
    options: list[str]
    answer: int  # 正确选项索引


class QuizBook(BaseModel):
    """某本书的完整问答题"""
    book_id: int
    questions: list[QuizQuestion]


class Completion(BaseModel):
    """完书记录"""
    id: int
    book_id: int
    book_title: str
    borrower: str
    correct_count: int
    total_count: int
    score: float  # 百分比
    completed_at: str


class CompletionSubmit(BaseModel):
    """完书提交请求"""
    borrower: str = Field(..., min_length=1, description="完书人")
    answers: list[int] = Field(..., description="每题的选项索引")


class Achievement(BaseModel):
    """成就徽章定义 + 解锁状态"""
    id: str
    name: str
    icon: str
    description: str
    hint: str
    unlocked: bool = False
    unlocked_at: Optional[str] = None
    progress: int = 0
    target: int = 1
    category: str = "通用"

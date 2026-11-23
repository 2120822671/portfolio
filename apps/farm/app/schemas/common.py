"""
通用响应包装 —— 所有 API 返回统一的 JSON 结构
"""
from __future__ import annotations

from typing import Any, Generic, Optional, TypeVar

from pydantic import BaseModel, ConfigDict

T = TypeVar("T")


class ApiResponse(BaseModel, Generic[T]):
    """
    统一 API 响应结构:
        {
            "code": 200,          # 业务状态码（200=成功）
            "message": "ok",      # 提示信息
            "data": { ... }       # 实际业务数据（泛型）
        }
    """
    code: int = 200
    message: str = "ok"
    data: Optional[T] = None

    model_config = ConfigDict(arbitrary_types_allowed=True)


class MessageResponse(BaseModel):
    """仅返回消息的轻量响应（如操作成功/失败）"""
    message: str
    code: int = 200


# ---------- 便捷工厂函数 ----------
def success(data: Any = None, message: str = "ok") -> ApiResponse:
    """快速构建成功响应"""
    return ApiResponse(code=200, message=message, data=data)


def fail(code: int = 400, message: str = "error", data: Any = None) -> ApiResponse:
    """快速构建失败响应"""
    return ApiResponse(code=code, message=message, data=data)

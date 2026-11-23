"""增量新增：业务异常类型，供路由主动抛出、全局 handler 统一捕获。"""
from core.error_codes import ErrorCode


class BizError(Exception):
    """业务异常：携带错误码、对外提示、附加数据与 HTTP 状态码。"""

    def __init__(self, code: ErrorCode | int, message: str, data=None, http_status: int = 400):
        super().__init__(message)
        self.code = int(code)
        self.message = message
        self.data = data
        self.http_status = http_status

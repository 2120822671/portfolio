"""增量新增：全局异常处理处理器集合。

- 统一返回 {code, message, msg, data, trace_id}，其中 msg 与 message 同值以兼容前端；
- Loguru 记录完整异常堆栈（logger.opt(exception=True)），堆栈不进响应体；
- 通过 register_exception_handlers(app) 在 main.py 末尾追加注册，不改已有 handler 函数体。
"""
import uuid

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from loguru import logger

from core.business_error import BizError
from core.error_codes import ErrorCode

log = logger.bind(module="global_exception")


def build_response(code: int, message: str, data, trace_id: str, http_status: int) -> JSONResponse:
    """构造统一异常响应：msg 与 message 同值，兼容前端 json.msg 读取路径。"""
    return JSONResponse(
        status_code=http_status,
        content={
            "code": code,
            "message": message,
            "msg": message,
            "data": data,
            "trace_id": trace_id,
        },
    )


def _new_trace_id() -> str:
    return uuid.uuid4().hex


async def biz_error_handler(request: Request, exc: BizError):
    """业务异常：记录堆栈 + 返回异常自带的 code/message/data。"""
    trace_id = _new_trace_id()
    log.opt(exception=True).error(
        "BizError trace_id={} method={} path={} code={} message={}",
        trace_id, request.method, request.url.path, exc.code, exc.message,
    )
    return build_response(exc.code, exc.message, exc.data, trace_id, exc.http_status)


async def validation_error_handler(request: Request, exc: RequestValidationError):
    """请求校验异常：沿用旧口径取第一条错误拼字段名，code=422。"""
    trace_id = _new_trace_id()
    first = exc.errors()[0] if exc.errors() else {}
    field = ".".join(str(x) for x in first.get("loc", [])[1:]) or "参数"
    message = f"参数校验失败：{field} {first.get('msg', '')}"
    log.opt(exception=True).error(
        "ValidationError trace_id={} method={} path={} message={}",
        trace_id, request.method, request.url.path, message,
    )
    return build_response(ErrorCode.VALIDATION_ERROR, message, None, trace_id, 422)


async def unhandled_error_handler(request: Request, exc: Exception):
    """兜底 500：堆栈只进日志，对外文案沿用旧提示。"""
    trace_id = _new_trace_id()
    message = "服务器开小差了，请稍后重试"
    log.opt(exception=True).error(
        "UnhandledError trace_id={} method={} path={}",
        trace_id, request.method, request.url.path,
    )
    return build_response(ErrorCode.INTERNAL_ERROR, message, None, trace_id, 500)


def register_exception_handlers(app: FastAPI) -> None:
    """注册到 FastAPI：同类型后注册覆盖旧 handler，旧函数保留不动便于回退。"""
    app.add_exception_handler(BizError, biz_error_handler)
    app.add_exception_handler(RequestValidationError, validation_error_handler)
    app.add_exception_handler(Exception, unhandled_error_handler)

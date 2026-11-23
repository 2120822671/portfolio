"""增量新增：业务错误码枚举。

0 / 4xx / 5xx 段与工程既有的 HTTP 状态码语义保持一致，不改写旧码含义；
1000+ 段留给自定义业务错误。
"""
from enum import IntEnum


class ErrorCode(IntEnum):
    """统一错误码：通用段兼容既有状态码，1000+ 为业务自定义段。"""

    SUCCESS = 0            # 成功（沿用 resp.ok 的 code=0）
    BAD_REQUEST = 400      # 请求参数/语义错误
    UNAUTHORIZED = 401     # 未登录（沿用旧 401）
    FORBIDDEN = 403        # 无权限（沿用旧 403）
    NOT_FOUND = 404        # 资源不存在
    CONFLICT = 409         # 资源冲突（如用户名重复、重复举报）
    VALIDATION_ERROR = 422 # 请求校验失败（沿用旧 422）
    RATE_LIMITED = 429     # 触发限流
    INTERNAL_ERROR = 500   # 服务器内部错误（沿用旧 500）

    # ---- 1000+ 业务自定义段 ----
    BIZ_GOODS_NOT_FOUND = 1001   # 商品不存在
    BIZ_ORDER_INVALID = 1002     # 订单状态不合法
    BIZ_PAY_FAILED = 1003        # 模拟支付失败

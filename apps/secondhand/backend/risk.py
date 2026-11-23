"""风控核心（增量新增）

两条规则：
1. 商品发布限流：同一用户 1 小时（3600s）最多发布 10 次，ZSET 滑动窗口 + Lua 原子执行；
2. 举报去重：同一用户对同一 (target_type, target_id) 24 小时只能举报一次，SET NX EX 原子占位。

约定：
- 所有 key 统一 cs: 前缀，禁止在业务代码里手拼字符串，一律走本模块的 key 构造函数；
- Redis 异常时按 config.RISK_FAIL_OPEN 放行（fail-open），并打 warning，避免风控拖垮主业务；
- ZSET 与去重 key 都带 TTL，Redis 恢复后无需人工清理。
"""
import logging
import time
import uuid
from math import ceil

from redis.exceptions import RedisError

from config import RISK_FAIL_OPEN
from redis_client import get_redis

logger = logging.getLogger("campus_secondhand.risk")

# ---------- 规则参数 ----------
PUBLISH_WINDOW_MS = 3600 * 1000   # 1 小时窗口（毫秒）
PUBLISH_LIMIT = 10                # 窗口内最多发布次数
REPORT_TTL_SECONDS = 86400        # 举报去重 24 小时

# ---------- Lua 脚本：清理过期 + 计数 + 写入，单次原子完成 ----------
# KEYS[1] = 限流 ZSET；ARGV[1] = now_ms；ARGV[2] = window_ms；ARGV[3] = limit；ARGV[4] = member
PUBLISH_LIMIT_LUA = """
redis.call('ZREMRANGEBYSCORE', KEYS[1], 0, tonumber(ARGV[1]) - tonumber(ARGV[2]))
local count = redis.call('ZCARD', KEYS[1])
if count >= tonumber(ARGV[3]) then
    local oldest = redis.call('ZRANGE', KEYS[1], 0, 0, 'WITHSCORES')
    local retry = 0
    if oldest[2] then
        retry = math.ceil((tonumber(oldest[2]) + tonumber(ARGV[2]) - tonumber(ARGV[1])) / 1000)
        if retry < 1 then retry = 1 end
    end
    return {0, count, retry}
end
redis.call('ZADD', KEYS[1], ARGV[1], ARGV[4])
redis.call('PEXPIRE', KEYS[1], ARGV[2])
return {1, count + 1, 0}
"""


# ---------- key 设计 ----------
def publish_limit_key(user_id: int) -> str:
    """发布限流 key：ZSET 滑动窗口，key 只按用户维度，不按时间片切分"""
    return f"cs:rl:goods:publish:{user_id}"


def report_dedup_key(user_id: int, target_type: str, target_id: int) -> str:
    """举报去重 key：TTL 24 小时由 Redis 自动解禁"""
    return f"cs:report:dedup:{user_id}:{target_type}:{target_id}"


def report_count_key(target_type: str, target_id: int) -> str:
    """被举报累计次数（可选统计，当前未启用，保留设计）"""
    return f"cs:report:cnt:{target_type}:{target_id}"


def _degrade(action: str, err: Exception | None = None) -> bool:
    """Redis 不可用时的降级判断：RISK_FAIL_OPEN=True 放行，否则由调用方拦截"""
    if RISK_FAIL_OPEN:
        logger.warning("风控降级：Redis 不可用，本次放行（%s）%s", action, f": {err}" if err else "")
        return True
    logger.error("风控拒绝：Redis 不可用且 RISK_FAIL_OPEN=false（%s）: %s", action, err)
    return False


async def acquire_publish_quota(user_id: int) -> tuple[bool, int]:
    """发布限流：返回 (是否放行, 建议等待秒数)

    - 放行时同时写入本次发布记录，窗口内第 11 次起返回 False；
    - 只有真正进入 INSERT 的发布才消耗配额（校验失败在调用点之前已返回）。
    """
    client = get_redis()
    if client is None:
        return _degrade("发布限流"), 0

    now_ms = int(time.time() * 1000)
    member = f"{now_ms}-{uuid.uuid4().hex[:8]}"  # 防止同毫秒多次发布 member 覆盖
    try:
        allowed, _count, retry = await client.eval(
            PUBLISH_LIMIT_LUA,
            1,
            publish_limit_key(user_id),
            now_ms,
            PUBLISH_WINDOW_MS,
            PUBLISH_LIMIT,
            member,
        )
        return bool(allowed), int(ceil(retry))
    except RedisError as e:
        return _degrade("发布限流", e), 0
    except Exception as e:  # noqa: BLE001 - 任何 Redis 侧异常都不阻断发布
        return _degrade("发布限流", e), 0


async def acquire_report_slot(user_id: int, target_type: str, target_id: int) -> tuple[bool, bool]:
    """举报占位：返回 (是否允许提交, 是否处于降级状态)

    使用 SET NX EX 单命令原子占位，避免 GET 后 SET 的并发穿透。
    """
    client = get_redis()
    if client is None:
        return _degrade("举报去重"), True

    try:
        acquired = await client.set(
            report_dedup_key(user_id, target_type, target_id),
            "1",
            nx=True,
            ex=REPORT_TTL_SECONDS,
        )
        return bool(acquired), False
    except RedisError as e:
        return _degrade("举报去重", e), True
    except Exception as e:  # noqa: BLE001
        return _degrade("举报去重", e), True


async def release_report_slot(user_id: int, target_type: str, target_id: int) -> None:
    """落库失败时回滚占位，避免「举报没落库却锁死 24 小时」"""
    client = get_redis()
    if client is None:
        return
    try:
        await client.delete(report_dedup_key(user_id, target_type, target_id))
    except Exception as e:  # noqa: BLE001 - 回滚失败仅告警，由 TTL 兜底
        logger.warning("举报占位回滚失败（%s 秒后由 TTL 自动释放）: %s", REPORT_TTL_SECONDS, e)

"""Redis 客户端（增量新增：风控限流与举报去重）

全局单例 + 连接池，禁止每个请求新建连接。
生命周期由 main.py 的 lifespan 管理：yield 前 init_redis()，yield 后 close_redis()。
Redis 不可用时本模块不抛异常向上冒泡，由 risk.py 按 RISK_FAIL_OPEN 决定是否放行。
"""
import logging

from redis import asyncio as aioredis

from config import REDIS_DB, REDIS_HOST, REDIS_PORT

logger = logging.getLogger("campus_secondhand.redis")

_client: "aioredis.Redis | None" = None


async def init_redis() -> None:
    """创建连接池并探活；探活失败只告警，不阻断服务启动（风控降级）"""
    global _client
    if _client is not None:
        return
    _client = aioredis.Redis(
        host=REDIS_HOST,
        port=REDIS_PORT,
        db=REDIS_DB,
        protocol=2,  # 显式 RESP2：兼容 Redis 5/6/7，本项目只用基础命令，无需 RESP3
        decode_responses=True,
        max_connections=20,
        health_check_interval=30,
        socket_timeout=0.3,
        socket_connect_timeout=0.3,
    )
    try:
        await _client.ping()
        logger.info("Redis 连接成功: redis://%s:%s/%s", REDIS_HOST, REDIS_PORT, REDIS_DB)
    except Exception as e:  # noqa: BLE001 - 启动阶段任何连接异常都只降级
        logger.warning("Redis 连接失败（风控将按 RISK_FAIL_OPEN 降级）: %s", e)


async def close_redis() -> None:
    """关闭连接池，释放端口与协程资源"""
    global _client
    if _client is None:
        return
    try:
        await _client.aclose()
    except Exception as e:  # noqa: BLE001 - 关闭失败不影响进程退出
        logger.warning("Redis 关闭异常: %s", e)
    finally:
        _client = None
        logger.info("Redis 连接已关闭")


def get_redis() -> "aioredis.Redis | None":
    """获取单例客户端；未初始化或已关闭时返回 None（调用方据此降级）"""
    return _client

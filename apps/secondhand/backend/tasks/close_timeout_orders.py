"""超时未支付订单自动关闭定时任务（增量新增）

规则：
- 扫描 orders.status = 10（待付款）且 pay_deadline < 数据库 NOW() 的订单，每轮最多 BATCH_LIMIT 单；
- 关闭订单：status 10 → 40，close_type='timeout'，closed_at=NOW()（条件更新，防并发重复关闭）；
- 商品恢复：goods.status 4（已预订）→ 1（在售），stock +1；
- 写 order_logs 流水（auto_close）；
- 单条订单一个事务，异常只记日志不中断整轮；重复执行幂等。
"""
import logging
import os
from datetime import datetime, timedelta

from apscheduler.schedulers.background import BackgroundScheduler
from sqlalchemy import func, select, update

from database import SessionLocal
from models import Goods, Order, OrderLog

logger = logging.getLogger("campus_secondhand.tasks.close_timeout_orders")

BATCH_LIMIT = int(os.getenv("CLOSE_ORDER_BATCH", "200"))
JOB_ID = "close_timeout_orders"

_scheduler: BackgroundScheduler | None = None


def close_timeout_orders(db=None) -> dict:
    """关闭所有已超时未支付的订单，返回本轮统计。可手工调用，便于测试。"""
    own_session = db is None
    if own_session:
        db = SessionLocal()

    stats = {"scanned": 0, "closed": 0, "skipped": 0, "failed": 0}
    try:
        rows = db.execute(
            select(Order.id, Order.goods_id)
            .where(Order.status == 10, Order.pay_deadline < func.now())
            .order_by(Order.pay_deadline.asc())
            .limit(BATCH_LIMIT)
        ).all()
        stats["scanned"] = len(rows)

        for order_id, goods_id in rows:
            try:
                # 1) 条件关闭：只有仍是「待付款」的订单才会被关闭，已被支付/取消的 rowcount=0
                closed = db.execute(
                    update(Order)
                    .where(Order.id == order_id, Order.status == 10)
                    .values(status=40, close_type="timeout", closed_at=func.now())
                    .execution_options(synchronize_session=False)
                )
                if closed.rowcount != 1:
                    db.rollback()
                    stats["skipped"] += 1
                    logger.info("[close_timeout_orders] 订单 %s 状态已变更，跳过", order_id)
                    continue

                # 2) 商品恢复：仅当商品仍处于「已预订」时才恢复，避免覆盖人工处理结果
                restored = db.execute(
                    update(Goods)
                    .where(Goods.id == goods_id, Goods.status == 4)
                    .values(status=1, stock=Goods.stock + 1)
                    .execution_options(synchronize_session=False)
                )
                if restored.rowcount == 0:
                    logger.warning("[close_timeout_orders] 订单 %s 的商品 %s 非预订态，未恢复在售",
                                   order_id, goods_id)

                # 3) 写流水
                db.add(OrderLog(order_id=order_id, from_status=10, to_status=40,
                                action="auto_close", remark="超时未支付自动关闭"))
                db.commit()
                stats["closed"] += 1
            except Exception:
                db.rollback()
                stats["failed"] += 1
                logger.exception("[close_timeout_orders] 订单 %s 处理失败", order_id)
    finally:
        if own_session:
            db.close()

    logger.info("[close_timeout_orders] 扫描=%s 关闭=%s 跳过=%s 异常=%s",
                stats["scanned"], stats["closed"], stats["skipped"], stats["failed"])
    return stats


def start_scheduler() -> BackgroundScheduler | None:
    """注册定时任务（每 1 分钟一次）。多 worker 部署时用 ENABLE_SCHEDULER=0 关掉多余进程"""
    global _scheduler
    if os.getenv("ENABLE_SCHEDULER", "1") != "1":
        logger.info("ENABLE_SCHEDULER != 1，本进程不启用定时任务")
        return None
    if _scheduler and _scheduler.running:
        return _scheduler

    _scheduler = BackgroundScheduler(
        job_defaults={"max_instances": 1, "coalesce": True, "misfire_grace_time": 60}
    )
    _scheduler.add_job(
        close_timeout_orders,
        trigger="interval",
        minutes=1,
        id=JOB_ID,
        replace_existing=True,
        next_run_time=datetime.now() + timedelta(seconds=15),
    )
    _scheduler.start()
    logger.info("定时任务已启动：%s（interval=1 分钟，批量上限 %s）", JOB_ID, BATCH_LIMIT)
    return _scheduler


def stop_scheduler() -> None:
    """关闭定时任务（FastAPI lifespan 退出时调用）"""
    global _scheduler
    if _scheduler and _scheduler.running:
        _scheduler.shutdown(wait=False)
        logger.info("定时任务已停止：%s", JOB_ID)
    _scheduler = None

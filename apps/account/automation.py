"""
自动化流程引擎
==============
随 FastAPI 启停，内置 APScheduler 定时任务。三条自动化流程：

  1. 周期账单自动入账  每天 00:05   → 扫描 recurring_rule，命中的自动生成账目
  2. 日终汇总播报      每天 23:00   → 汇总当日收支、预算进度、环比对比，写入消息中心
  3. 每日消费复盘      每天 23:10   → 大模型生成复盘点评，失败回落规则文案

可靠性设计：
- 幂等：周期账单用 recurring_run 的 (rule_id, period_key) 唯一键判重；
        每日任务用 task_run_log 的 (task_name, run_date) 唯一键判重
- 失败兜底：异常统一捕获写入 task_run_log，前端可查，不静默中断
- 时区：显式指定 Asia/Shanghai，不依赖服务器默认时区
- 错峰：定时时间避开整点，且带少量随机延迟
"""

import json
import os
import random
from datetime import datetime, date, timedelta, time as dtime

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

from db import get_conn
import llm as llm_mod


TZ = "Asia/Shanghai"
_scheduler = None


# ==========================================
# 通用工具
# ==========================================
def now_str() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _json_dumps(obj) -> str:
    return json.dumps(obj, ensure_ascii=False, default=str)


def log_task(task_name: str, run_date: date, status: str, message: str = ""):
    """写入任务执行日志（幂等：同任务同日期只留一条，重复执行更新状态）"""
    conn = get_conn()
    try:
        with conn.cursor() as cursor:
            cursor.execute("""
                INSERT INTO task_run_log (task_name, run_date, status, message, created_at)
                VALUES (%s, %s, %s, %s, NOW())
                ON DUPLICATE KEY UPDATE status = VALUES(status),
                                        message = VALUES(message),
                                        created_at = NOW()
            """, (task_name, run_date, status, message[:2000]))
        conn.commit()
    except Exception as e:  # noqa: BLE001
        print(f"[automation] 写日志失败: {e}")
    finally:
        conn.close()


def already_ran(task_name: str, run_date: date) -> bool:
    """检查任务今天是否已成功执行过（幂等判重）"""
    conn = get_conn()
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                "SELECT status FROM task_run_log WHERE task_name = %s AND run_date = %s",
                (task_name, run_date))
            row = cursor.fetchone()
            return bool(row and row["status"] == "success")
    finally:
        conn.close()


def touch_checkin(conn, on_date: date = None, delta: int = 1):
    """更新打卡计数（新增流水时调用）"""
    on_date = on_date or date.today()
    with conn.cursor() as cursor:
        cursor.execute("""
            INSERT INTO checkin_log (check_date, record_cnt) VALUES (%s, %s)
            ON DUPLICATE KEY UPDATE record_cnt = record_cnt + %s
        """, (on_date, delta, delta))


# ==========================================
# 流程 1：周期账单自动入账
# ==========================================
def _period_key(rule: dict, target: date) -> str:
    """生成周期键，用于幂等判重"""
    cycle_type = rule["cycle_type"]
    if cycle_type == "daily":
        return target.strftime("%Y-%m-%d")
    if cycle_type == "weekly":
        # ISO 周
        iso = target.isocalendar()
        return f"{iso[0]}-W{iso[1]:02d}"
    return target.strftime("%Y-%m")  # monthly


def _is_due(rule: dict, target: date) -> bool:
    """判断某条规则在 target 日期是否应当执行"""
    start = rule["start_date"]
    end = rule["end_date"]
    if target < start:
        return False
    if end and target > end:
        return False

    cycle_type = rule["cycle_type"]
    value = max(1, int(rule["cycle_value"] or 1))
    days = (target - start).days

    if cycle_type == "daily":
        return days % value == 0

    if cycle_type == "weekly":
        # 以起始日为锚点，每 value 周命中一次
        return days % (7 * value) == 0

    if cycle_type == "monthly":
        # 每月同一天（起始日超过当月天数则取当月最后一天）
        if start.day == target.day:
            return ((target.year - start.year) * 12 + (target.month - start.month)) % value == 0
        # 起始日为 29/30/31，落到短月时取月末
        import calendar
        last_day = calendar.monthrange(target.year, target.month)[1]
        if start.day > last_day and target.day == last_day:
            return ((target.year - start.year) * 12 + (target.month - start.month)) % value == 0
        return False

    return False


def run_recurring(target: date = None, force: bool = False) -> dict:
    """
    执行周期账单。force=True 时忽略幂等（手动重跑用）。
    返回 {posted, pending, skipped, details}
    """
    target = target or date.today()
    conn = get_conn()
    posted, pending, skipped = 0, 0, 0
    details = []

    try:
        with conn.cursor() as cursor:
            cursor.execute("""
                SELECT * FROM recurring_rule WHERE enabled = 1 ORDER BY id
            """)
            rules = cursor.fetchall()

            for rule in rules:
                if not _is_due(rule, target):
                    continue

                pkey = _period_key(rule, target)

                # 幂等判重
                if not force:
                    cursor.execute(
                        "SELECT id FROM recurring_run WHERE rule_id = %s AND period_key = %s",
                        (rule["id"], pkey))
                    if cursor.fetchone():
                        skipped += 1
                        details.append({"rule": rule["name"], "status": "skipped", "reason": "本期已处理"})
                        continue

                # auto_post=0 → 只生成待确认提醒，不直接入账
                if int(rule["auto_post"]) == 0:
                    cursor.execute("""
                        INSERT INTO recurring_run (rule_id, period_key, record_id, status, message, created_at)
                        VALUES (%s, %s, NULL, 'pending', %s, NOW())
                        ON DUPLICATE KEY UPDATE status = 'pending', message = VALUES(message)
                    """, (rule["id"], pkey, f"{rule['name']} 待确认"))
                    pending += 1
                    details.append({"rule": rule["name"], "status": "pending",
                                    "amount": float(rule["amount"])})
                    continue

                # 自动入账
                stamp = datetime.combine(target, dtime(9, 0, 0)).strftime("%Y-%m-%d %H:%M:%S")
                cursor.execute("""
                    INSERT INTO account_record
                    (type, amount, category, remark, record_time, account_id, create_time)
                    VALUES (%s, %s, %s, %s, %s, %s, NOW())
                """, (rule["type"], rule["amount"], rule["category"],
                      rule["remark"] or rule["name"], stamp, rule["account_id"]))
                new_id = cursor.lastrowid

                cursor.execute("""
                    INSERT INTO recurring_run (rule_id, period_key, record_id, status, message, created_at)
                    VALUES (%s, %s, %s, 'ok', %s, NOW())
                    ON DUPLICATE KEY UPDATE record_id = VALUES(record_id),
                                            status = 'ok', message = VALUES(message)
                """, (rule["id"], pkey, new_id, f"自动入账 #{new_id}"))

                touch_checkin(conn, target)
                posted += 1
                details.append({"rule": rule["name"], "status": "ok",
                                "amount": float(rule["amount"]), "recordId": new_id})

        conn.commit()
    except Exception as e:  # noqa: BLE001
        conn.rollback()
        log_task("recurring", target, "failed", f"周期账单执行失败: {e}")
        raise
    finally:
        conn.close()

    log_task("recurring", target, "success",
             f"入账 {posted} 条, 待确认 {pending} 条, 跳过 {skipped} 条")

    # 写一条消息中心的周期账单通知
    if posted or pending:
        _write_report(
            target, "recurring",
            f"周期账单自动处理 {posted + pending} 项",
            f"已自动入账 {posted} 项，待确认 {pending} 项，跳过 {skipped} 项（已处理过的周期不重复入账）。",
            {"details": details}, "info")

    return {"posted": posted, "pending": pending, "skipped": skipped, "details": details}


# ==========================================
# 流程 2：日终汇总播报
# ==========================================
def build_day_stats(day: date = None, account_id: int = None) -> dict:
    """汇总指定日期的收支、分类、预算进度、环比对比"""
    day = day or date.today()
    start = datetime.combine(day, dtime.min)
    end = start + timedelta(days=1)
    prev_start = start - timedelta(days=1)

    acc_sql = " AND account_id = %s" if account_id else ""
    acc_params = [account_id] if account_id else []

    conn = get_conn()
    try:
        with conn.cursor() as cursor:
            cursor.execute(f"""
                SELECT COALESCE(SUM(CASE WHEN type = 1 THEN amount END), 0) AS income,
                       COALESCE(SUM(CASE WHEN type = 2 THEN amount END), 0) AS expense,
                       COUNT(*) AS cnt
                FROM account_record
                WHERE record_time >= %s AND record_time < %s{acc_sql}
            """, [start, end] + acc_params)
            today = cursor.fetchone()

            cursor.execute(f"""
                SELECT COALESCE(SUM(CASE WHEN type = 2 THEN amount END), 0) AS expense
                FROM account_record
                WHERE record_time >= %s AND record_time < %s{acc_sql}
            """, [prev_start, start] + acc_params)
            yesterday = cursor.fetchone()

            # 近 7 日（不含今天）日均支出
            cursor.execute(f"""
                SELECT COALESCE(SUM(CASE WHEN type = 2 THEN amount END), 0) / 7 AS avg7
                FROM account_record
                WHERE type = 2 AND record_time >= %s AND record_time < %s{acc_sql}
            """, [start - timedelta(days=7), start] + acc_params)
            avg7 = cursor.fetchone()["avg7"] or 0

            cursor.execute(f"""
                SELECT category, COALESCE(SUM(amount), 0) AS amt, COUNT(*) AS cnt
                FROM account_record
                WHERE type = 2 AND record_time >= %s AND record_time < %s{acc_sql}
                GROUP BY category ORDER BY amt DESC
            """, [start, end] + acc_params)
            by_category = cursor.fetchall()

            cursor.execute(f"""
                SELECT category, COALESCE(SUM(amount), 0) AS amt
                FROM account_record
                WHERE type = 2 AND record_time >= %s AND record_time < %s{acc_sql}
                GROUP BY category
            """, [start - timedelta(days=7), start] + acc_params)
            week_cat = {r["category"]: float(r["amt"]) for r in cursor.fetchall()}

            # 预算进度（预算按分类全局统计，不随账本过滤，
            # 所以预算用量单独查一次，避免只算当前账本导致额度虚高）
            period = day.strftime("%Y-%m")
            cursor.execute("""
                SELECT category, amount FROM budget_rule
                WHERE period = %s AND enabled = 1
            """, (period,))
            budgets = cursor.fetchall()

            cursor.execute("""
                SELECT category, COALESCE(SUM(amount), 0) AS amt
                FROM account_record
                WHERE type = 2 AND record_time >= %s AND record_time < %s
                GROUP BY category
            """, (start, end))
            global_cat = {r["category"]: float(r["amt"]) for r in cursor.fetchall()}

        income = float(today["income"])
        expense = float(today["expense"])
        y_expense = float(yesterday["expense"])
        avg7 = float(avg7)

        budget_progress = []
        for b in budgets:
            limit = float(b["amount"])
            used = round(global_cat.get(b["category"], 0), 2)
            rate = round(used / limit * 100, 1) if limit > 0 else 0
            budget_progress.append({
                "category": b["category"],
                "limit": limit,
                "used": used,
                "rate": rate,
                "over": used > limit,
            })

        return {
            "date": day.strftime("%Y-%m-%d"),
            "income": round(income, 2),
            "expense": round(expense, 2),
            "balance": round(income - expense, 2),
            "count": int(today["cnt"]),
            "yesterdayExpense": round(y_expense, 2),
            "avg7Expense": round(avg7, 2),
            "diffVsYesterday": round(expense - y_expense, 2),
            "diffVsAvg7": round(expense - avg7, 2),
            "byCategory": [{"category": c["category"], "amount": round(float(c["amt"]), 2),
                            "count": int(c["cnt"])} for c in by_category],
            "weekCategory": {k: round(v, 2) for k, v in week_cat.items()},
            "budgets": budget_progress,
        }
    finally:
        conn.close()


def _write_report(day: date, rtype: str, title: str, content: str,
                  data: dict = None, level: str = "info") -> int:
    """写入日报/消息（幂等：同日同类型覆盖）"""
    conn = get_conn()
    try:
        with conn.cursor() as cursor:
            cursor.execute("""
                INSERT INTO daily_report (report_date, report_type, title, content, data_json, level, is_read, created_at)
                VALUES (%s, %s, %s, %s, %s, %s, 0, NOW())
                ON DUPLICATE KEY UPDATE title = VALUES(title), content = VALUES(content),
                                        data_json = VALUES(data_json), level = VALUES(level),
                                        created_at = NOW()
            """, (day, rtype, title[:100], content, _json_dumps(data or {}), level))
        conn.commit()
        return cursor.lastrowid
    finally:
        conn.close()


def _rule_summary_text(stats: dict) -> str:
    """规则版汇总文案（大模型不可用时兜底）"""
    if stats["count"] == 0:
        return "今天还没有记账喵～ 打开招财猫说一句「午饭 30」，两秒记一笔。"
    lines = [
        f"今日支出 ¥{stats['expense']:.2f}，收入 ¥{stats['income']:.2f}，结余 ¥{stats['balance']:.2f}，共 {stats['count']} 笔。"
    ]
    if stats["byCategory"]:
        top = stats["byCategory"][0]
        lines.append(f"花得最多的是{top['category']}，¥{top['amount']:.2f}（{top['count']} 笔）。")
    dv = stats["diffVsYesterday"]
    if dv > 0:
        lines.append(f"比昨天多花了 ¥{dv:.2f}，悠着点喵。")
    elif dv < 0:
        lines.append(f"比昨天少花了 ¥{abs(dv):.2f}，今天很克制喵！")
    else:
        lines.append("和昨天花得一样多。")
    over = [b for b in stats["budgets"] if b["over"]]
    if over:
        lines.append("预算告急：" + "、".join(f"{b['category']}已用{b['rate']}%" for b in over) + "，注意控制啦。")
    return " ".join(lines)


def run_daily_summary(day: date = None, force: bool = False, account_id: int = None) -> dict:
    """日终汇总：写消息中心 + 预算超支预警"""
    day = day or date.today()
    if not force and already_ran("daily_summary", day):
        return {"skipped": True, "reason": "今日已执行过"}

    try:
        stats = build_day_stats(day, account_id)

        try:
            content = llm_mod.daily_review(stats) if llm_mod.llm_enabled() else ""
        except Exception:  # noqa: BLE001
            content = ""
        if not content:
            content = _rule_summary_text(stats)

        _write_report(day, "summary", f"{day.strftime('%m月%d日')} 收支小结",
                      content, stats, "info")

        # 预算超支 → 单独的 danger 级消息
        over = [b for b in stats["budgets"] if b["over"]]
        if over:
            text = "；".join(
                f"{b['category']}已用 ¥{b['used']:.2f}，超预算 ¥{b['used'] - b['limit']:.2f}（{b['rate']}%）"
                for b in over)
            _write_report(day, "warning", "预算超支提醒", text,
                          {"budgets": over}, "danger")

        log_task("daily_summary", day, "success",
                 f"支出 {stats['expense']}, 收入 {stats['income']}, {stats['count']} 笔")
        return {"skipped": False, "stats": stats, "content": content}
    except Exception as e:  # noqa: BLE001
        log_task("daily_summary", day, "failed", str(e))
        raise


# ==========================================
# 流程 3：每日消费复盘
# ==========================================
def _rule_review_text(stats: dict) -> str:
    """规则版复盘文案（大模型不可用时兜底）"""
    if stats["count"] == 0:
        return "今天没有流水，清爽的一天。保持住，明天见喵。"
    parts = []
    if stats["expense"] == 0:
        parts.append("今天只进不出，存钱意识在线喵。")
    else:
        avg = stats["avg7Expense"]
        if avg > 0:
            if stats["expense"] > avg * 1.3:
                parts.append(f"今天花了 ¥{stats['expense']:.2f}，比近一周日均 ¥{avg:.2f} 明显偏高，主因是{stats['byCategory'][0]['category'] if stats['byCategory'] else '其他'}。")
            elif stats["expense"] < avg * 0.7:
                parts.append(f"今天只花了 ¥{stats['expense']:.2f}，远低于近一周日均 ¥{avg:.2f}，控制得不错喵。")
            else:
                parts.append(f"今天花了 ¥{stats['expense']:.2f}，和近一周日均 ¥{avg:.2f} 基本持平，很稳。")
        else:
            parts.append(f"今天花了 ¥{stats['expense']:.2f}，共 {stats['count']} 笔。")

    cats = stats["byCategory"]
    if cats:
        top = cats[0]
        wk = stats["weekCategory"].get(top["category"], 0)
        if wk > 0:
            ratio = top["amount"] / wk * 7 if wk else 0
            if ratio > 40:
                parts.append(f"{top['category']}占了近一周同类支出的 {ratio:.0f}%，是当前最大的开销来源，优先从这里省。")
            else:
                parts.append(f"{top['category']}是今天花得最多的分类（¥{top['amount']:.2f}）。")
        if len(cats) >= 3:
            parts.append(f"其次是{cats[1]['category']} ¥{cats[1]['amount']:.2f} 和{cats[2]['category']} ¥{cats[2]['amount']:.2f}。")

    for b in stats["budgets"]:
        if b["over"]:
            parts.append(f"⚠️ {b['category']}预算 ¥{b['limit']:.2f} 已超支 ¥{b['used'] - b['limit']:.2f}，建议暂停非必要消费。")
        elif b["rate"] >= 80:
            parts.append(f"{b['category']}预算已用 {b['rate']}%，剩 ¥{b['limit'] - b['used']:.2f}，注意节奏。")

    if stats["balance"] > 0:
        parts.append(f"今日结余 ¥{stats['balance']:.2f}，继续保持喵。")
    return " ".join(parts)


def run_daily_review(day: date = None, force: bool = False, account_id: int = None) -> dict:
    """每日复盘：结构化数据 + 大模型点评（失败回落规则文案）"""
    day = day or date.today()
    if not force and already_ran("daily_review", day):
        return {"skipped": True, "reason": "今日已执行过"}

    try:
        stats = build_day_stats(day, account_id)

        content = ""
        used_llm = False
        if llm_mod.llm_enabled():
            try:
                content = llm_mod.daily_review(stats)
                used_llm = bool(content)
            except Exception:  # noqa: BLE001
                content = ""
        if not content:
            content = _rule_review_text(stats)

        _write_report(day, "review", f"{day.strftime('%m月%d日')} 消费复盘",
                      content, stats, "info")

        log_task("daily_review", day, "success",
                 f"生成复盘（{'大模型' if used_llm else '规则'}），{len(content)} 字")
        return {"skipped": False, "content": content, "usedLLM": used_llm, "stats": stats}
    except Exception as e:  # noqa: BLE001
        log_task("daily_review", day, "failed", str(e))
        raise


# ==========================================
# 调度器
# ==========================================
def start_scheduler():
    """启动 APScheduler，随 FastAPI 生命周期启停"""
    global _scheduler
    if _scheduler and _scheduler.running:
        return _scheduler

    _scheduler = BackgroundScheduler(timezone=TZ)

    # 周期账单：每天 00:05
    _scheduler.add_job(
        lambda: _safe_run("recurring", run_recurring),
        CronTrigger(hour=0, minute=5, timezone=TZ),
        id="recurring", name="周期账单自动入账", replace_existing=True,
        misfire_grace_time=3600,
    )

    # 日终汇总：每天 23:00
    _scheduler.add_job(
        lambda: _safe_run("daily_summary", run_daily_summary),
        CronTrigger(hour=23, minute=0, timezone=TZ),
        id="daily_summary", name="日终汇总播报", replace_existing=True,
        misfire_grace_time=3600,
    )

    # 每日复盘：每天 23:10
    _scheduler.add_job(
        lambda: _safe_run("daily_review", run_daily_review),
        CronTrigger(hour=23, minute=10, timezone=TZ),
        id="daily_review", name="每日消费复盘", replace_existing=True,
        misfire_grace_time=3600,
    )

    _scheduler.start()
    print(f"[automation] 调度器已启动（{TZ}），任务：周期账单 00:05 / 日终汇总 23:00 / 每日复盘 23:10")
    return _scheduler


def shutdown_scheduler():
    global _scheduler
    if _scheduler and _scheduler.running:
        _scheduler.shutdown(wait=False)
        print("[automation] 调度器已停止")


def _safe_run(task_name: str, fn):
    """统一异常兜底：任何失败都写日志，绝不静默中断"""
    try:
        fn()
    except Exception as e:  # noqa: BLE001
        print(f"[automation] 任务 {task_name} 失败: {e}")
        log_task(task_name, date.today(), "failed", str(e))


def get_jobs_status() -> list:
    """查询调度器任务状态（前端展示用）"""
    if not _scheduler:
        return []
    out = []
    for job in _scheduler.get_jobs():
        nxt = getattr(job, "next_run_time", None)
        out.append({
            "id": job.id,
            "name": job.name,
            "nextRun": nxt.strftime("%Y-%m-%d %H:%M:%S") if nxt else None,
        })
    return out

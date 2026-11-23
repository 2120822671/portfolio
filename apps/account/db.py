"""
数据库连接与表结构初始化
- 统一 get_conn()，供 main.py / automation.py / llm.py 复用
- 建表语句全部使用 IF NOT EXISTS，可重复执行
- 增量迁移：account_record 增加 account_id（老数据归属默认账本）

账号密码等敏感项支持用环境变量覆盖，不修改原默认值，保证开箱即用。
"""

import os
import sys

# 把本地 libs 目录加入搜索路径（pymysql 安装在这里）
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "libs"))

import pymysql
from pymysql.cursors import DictCursor


# ==========================================
# 数据库连接配置（可用环境变量覆盖）
# ==========================================
DB_CONFIG = {
    "host": os.getenv("DB_HOST", "localhost"),
    "port": int(os.getenv("DB_PORT", "3306")),
    "user": os.getenv("DB_USER", "root"),
    "password": os.getenv("DB_PASSWORD", "123456"),
    "database": os.getenv("DB_NAME", "account_db"),
    "charset": "utf8mb4",
    "cursorclass": DictCursor,
}


def get_conn():
    return pymysql.connect(**DB_CONFIG)


# ==========================================
# 建表语句（全部 IF NOT EXISTS，可重复执行）
# ==========================================
SCHEMA_SQL = [
    # 1. 账本（多账户）
    """
    CREATE TABLE IF NOT EXISTS account_book (
      id          BIGINT       NOT NULL AUTO_INCREMENT COMMENT '账本ID',
      name        VARCHAR(50) NOT NULL                COMMENT '账本名称，如 现金/支付宝/微信',
      book_type   VARCHAR(20) NOT NULL DEFAULT '现金'  COMMENT '账本类型：现金/支付宝/微信/银行卡/信用卡',
      init_balance DECIMAL(12,2) NOT NULL DEFAULT 0   COMMENT '初始余额（余额由流水实时计算，不落库避免双写冲突）',
      icon        VARCHAR(20) NOT NULL DEFAULT '💰'    COMMENT '图标 emoji',
      sort_order  INT          NOT NULL DEFAULT 0    COMMENT '排序，小的在前',
      is_default  TINYINT      NOT NULL DEFAULT 0    COMMENT '是否默认账本',
      created_at  DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
      PRIMARY KEY (id)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='账本表'
    """,

    # 2. 周期账单规则
    """
    CREATE TABLE IF NOT EXISTS recurring_rule (
      id          BIGINT       NOT NULL AUTO_INCREMENT COMMENT '规则ID',
      name        VARCHAR(100) NOT NULL                COMMENT '规则名称，如 房租',
      type        TINYINT      NOT NULL                COMMENT '收支类型：1=收入 2=支出',
      amount      DECIMAL(10,2) NOT NULL               COMMENT '金额',
      category    VARCHAR(50)  NOT NULL                COMMENT '分类',
      remark      VARCHAR(255) NULL                   COMMENT '备注',
      account_id  BIGINT       NOT NULL DEFAULT 1      COMMENT '归属账本ID',
      cycle_type  VARCHAR(20)  NOT NULL                COMMENT '周期类型：daily/weekly/monthly',
      cycle_value INT          NOT NULL DEFAULT 1      COMMENT '周期间隔：daily=每N天 weekly=每N周 monthly=每N月',
      start_date  DATE         NOT NULL                COMMENT '起始日期',
      end_date    DATE         NULL                   COMMENT '截止日期，NULL=长期',
      auto_post   TINYINT      NOT NULL DEFAULT 1      COMMENT '1=自动入账 0=只生成待确认提醒',
      enabled     TINYINT      NOT NULL DEFAULT 1      COMMENT '是否启用',
      created_at  DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
      PRIMARY KEY (id),
      KEY idx_enabled (enabled, cycle_type)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='周期账单规则表'
    """,

    # 3. 周期账单执行记录（幂等判重用）
    """
    CREATE TABLE IF NOT EXISTS recurring_run (
      id          BIGINT      NOT NULL AUTO_INCREMENT,
      rule_id     BIGINT      NOT NULL                COMMENT '规则ID',
      period_key  VARCHAR(20) NOT NULL                COMMENT '周期键，如 2026-11 / 2026-W45 / 2026-11-16',
      record_id   BIGINT      NULL                    COMMENT '生成的账目ID',
      status      VARCHAR(20) NOT NULL DEFAULT 'ok'  COMMENT 'ok=已入账 pending=待确认 skipped=跳过',
      message     VARCHAR(255) NULL,
      created_at  DATETIME    NOT NULL DEFAULT CURRENT_TIMESTAMP,
      PRIMARY KEY (id),
      UNIQUE KEY uk_rule_period (rule_id, period_key)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='周期账单执行记录（幂等）'
    """,

    # 4. 预算规则
    """
    CREATE TABLE IF NOT EXISTS budget_rule (
      id         BIGINT       NOT NULL AUTO_INCREMENT,
      category   VARCHAR(50)  NOT NULL                COMMENT '预算分类',
      period     VARCHAR(7)   NOT NULL                COMMENT '预算月份 YYYY-MM',
      amount     DECIMAL(10,2) NOT NULL               COMMENT '预算金额',
      enabled    TINYINT      NOT NULL DEFAULT 1,
      created_at DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
      PRIMARY KEY (id),
      UNIQUE KEY uk_category_period (category, period)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='分类预算表'
    """,

    # 5. 日报 / 消息中心
    """
    CREATE TABLE IF NOT EXISTS daily_report (
      id          BIGINT       NOT NULL AUTO_INCREMENT,
      report_date DATE         NOT NULL                COMMENT '报告日期',
      report_type VARCHAR(20)  NOT NULL                COMMENT 'summary=日终汇总 review=每日复盘 recurring=周期账单 warning=预算预警',
      title       VARCHAR(100) NOT NULL                COMMENT '标题',
      content     TEXT         NULL                    COMMENT '正文（可直接展示的文案）',
      data_json   LONGTEXT     NULL                    COMMENT '结构化数据 JSON',
      level       VARCHAR(10)  NOT NULL DEFAULT 'info' COMMENT 'info/warn/danger',
      is_read     TINYINT      NOT NULL DEFAULT 0      COMMENT '是否已读',
      created_at  DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
      PRIMARY KEY (id),
      UNIQUE KEY uk_date_type (report_date, report_type),
      KEY idx_date (report_date)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='日报与消息表'
    """,

    # 6. 任务执行日志（失败可查 / 死信留痕）
    """
    CREATE TABLE IF NOT EXISTS task_run_log (
      id          BIGINT      NOT NULL AUTO_INCREMENT,
      task_name   VARCHAR(50) NOT NULL                COMMENT '任务名',
      run_date    DATE        NOT NULL                COMMENT '运行日期',
      status      VARCHAR(20) NOT NULL                COMMENT 'success/failed/skipped',
      message     TEXT        NULL,
      created_at  DATETIME    NOT NULL DEFAULT CURRENT_TIMESTAMP,
      PRIMARY KEY (id),
      UNIQUE KEY uk_task_date (task_name, run_date)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='自动任务执行日志'
    """,

    # 7. 记账打卡（连续天数）
    """
    CREATE TABLE IF NOT EXISTS checkin_log (
      id          BIGINT   NOT NULL AUTO_INCREMENT,
      check_date  DATE     NOT NULL                COMMENT '打卡日期',
      record_cnt  INT      NOT NULL DEFAULT 0      COMMENT '当日记账笔数',
      created_at  DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
      PRIMARY KEY (id),
      UNIQUE KEY uk_check_date (check_date)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='记账打卡表'
    """,
]


def _column_exists(cursor, table: str, column: str) -> bool:
    """检查某表某列是否存在（用于幂等迁移）"""
    cursor.execute("""
        SELECT COUNT(*) AS cnt FROM information_schema.COLUMNS
        WHERE TABLE_SCHEMA = %s AND TABLE_NAME = %s AND COLUMN_NAME = %s
    """, (DB_CONFIG["database"], table, column))
    return cursor.fetchone()["cnt"] > 0


def init_db():
    """建表 + 增量迁移。可重复调用，不破坏已有数据。"""
    conn = get_conn()
    try:
        with conn.cursor() as cursor:
            for sql in SCHEMA_SQL:
                cursor.execute(sql)

            # 迁移：account_record 增加 account_id，老数据归入默认账本
            if not _column_exists(cursor, "account_record", "account_id"):
                cursor.execute("""
                    ALTER TABLE account_record
                    ADD COLUMN account_id BIGINT NOT NULL DEFAULT 1
                    COMMENT '归属账本ID' AFTER id
                """)

            # 建索引（已存在会报错，忽略即可）
            for idx_sql in [
                "CREATE INDEX idx_acc_account ON account_record (account_id)",
                "CREATE INDEX idx_acc_time ON account_record (record_time)",
            ]:
                try:
                    cursor.execute(idx_sql)
                except pymysql.err.OperationalError:
                    pass  # 索引已存在

            # 默认账本
            cursor.execute("SELECT COUNT(*) AS cnt FROM account_book WHERE id = 1")
            if cursor.fetchone()["cnt"] == 0:
                cursor.execute("""
                    INSERT INTO account_book (id, name, book_type, init_balance, icon, sort_order, is_default)
                    VALUES (1, '日常账本', '现金', 0, '💰', 0, 1)
                """)

            conn.commit()
    finally:
        conn.close()


if __name__ == "__main__":
    init_db()
    print("✅ 数据库初始化完成")

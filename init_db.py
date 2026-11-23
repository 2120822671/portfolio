# -*- coding: utf-8 -*-
"""
作品集 · 一键初始化三个 MySQL 数据库（幂等，可重复执行）
前置条件：本机 MySQL 8.0 已启动，root 密码为 123456（与各项目配置一致）

  account_db         招财记账
  campus_secondhand  校淘集市（二手交易）
  stardock           星坞 StarDock

图书借阅（墨香书阁）使用 JSON 文件存储，无需 MySQL，启动时自动建文件。

运行：python init_db.py
"""
import io
import os
import re
import subprocess
import sys

import pymysql

BASE = os.path.dirname(os.path.abspath(__file__))
CFG = dict(host="localhost", port=3306, user="root", password="123456", charset="utf8mb4")

# 重复执行时允许跳过的 MySQL 错误（表/列/索引已存在）
IGNORE_MSG = ("already exists", "duplicate column name", "duplicate key name",
              "duplicate entry", "can't drop", "check that column/key exists")


def run_sql_file(path: str, *, transform=None, seed=False):
    """按分号切分执行 SQL 文件；已存在的对象自动跳过，保证幂等。"""
    cfg = dict(CFG)
    conn = pymysql.connect(**cfg)
    sql = io.open(path, encoding="utf-8").read()
    if transform:
        sql = transform(sql)
    skipped = 0
    with conn.cursor() as cur:
        for stmt in sql.split(";"):
            lines = [l for l in stmt.splitlines()
                     if not l.strip().startswith("--") and l.strip()]
            s = "\n".join(lines).strip()
            if not s:
                continue
            try:
                cur.execute(s)
            except pymysql.MySQLError as e:
                if any(k in str(e).lower() for k in IGNORE_MSG):
                    skipped += 1
                    continue
                # 种子数据里的显式 ID 在不同库状态下可能冲突，非种子文件照常抛出
                if seed and e.args and e.args[0] in (1062, 1452):
                    skipped += 1
                    continue
                raise
    conn.commit()
    conn.close()
    extra = f"（跳过 {skipped} 条已存在记录）" if skipped else ""
    print(f"✅ {os.path.basename(path)} 执行完成{extra}")


def init_account():
    """招财记账：建库建表（db.py 内建表语句会自动补建其他表）"""
    run_sql_file(os.path.join(BASE, "apps", "account", "建表SQL.sql"), seed=True)
    # 调用项目自身的初始化，补齐多账本 / 周期账单 / 预算等新表
    sys.path.insert(0, os.path.join(BASE, "apps", "account"))
    from db import init_db  # noqa: E402
    init_db()
    print("✅ account_db（招财记账）初始化完成")


def init_secondhand():
    """校淘集市：按依赖顺序执行建表、升级、索引、种子脚本"""
    base = os.path.join(BASE, "apps", "secondhand", "sql")
    files = [
        "create_tables.sql",
        "upgrade_step04.sql",
        "upgrade_add_orders.sql",
        "upgrade_add_cart_chat.sql",
        "upgrade_add_favorite_count.sql",
        "upgrade_add_report.sql",
        "upgrade_add_admin_role.sql",
        "upgrade_add_admin_manage.sql",
        "upgrade_add_goods_list_index.sql",
        "seed_test_data.sql",
    ]
    for i, fn in enumerate(files):
        run_sql_file(os.path.join(base, fn), seed=(fn == "seed_test_data.sql"))
    print("✅ campus_secondhand（校淘集市）初始化完成")


def init_stardock():
    """星坞：原脚本会 DROP 库，这里改为幂等建表，保留已有数据"""
    path = os.path.join(BASE, "apps", "stardock", "backend", "init.sql")

    def make_idempotent(sql: str) -> str:
        sql = re.sub(r"DROP DATABASE IF EXISTS\s+\w+\s*;", "", sql, flags=re.I)
        sql = re.sub(r"CREATE DATABASE\s+(\w+)", r"CREATE DATABASE IF NOT EXISTS \1", sql, flags=re.I)
        sql = re.sub(r"CREATE TABLE\s+(\w+)", r"CREATE TABLE IF NOT EXISTS \1", sql, flags=re.I)
        return sql

    run_sql_file(path, transform=make_idempotent, seed=True)
    print("✅ stardock（星坞）初始化完成")


if __name__ == "__main__":
    print("===== 1/3 招财记账 account_db =====")
    init_account()
    print("===== 2/3 校淘集市 campus_secondhand =====")
    init_secondhand()
    print("===== 3/3 星坞 StarDock stardock =====")
    init_stardock()
    print("\n🎉 三个项目数据库全部就绪（图书项目无需数据库），可运行 python main.py 启动作品集")

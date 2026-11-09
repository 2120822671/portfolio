# -*- coding: utf-8 -*-
"""
作品集 · 一键初始化四个项目的 MySQL 数据库（幂等，可重复执行）
前置条件：本机 MySQL 8.0 已启动，root 密码为 123456（与各项目配置一致）
运行：python init_db.py
"""
import io
import os
import subprocess
import sys

import pymysql

BASE = os.path.dirname(os.path.abspath(__file__))
CFG = dict(host="localhost", port=3306, user="root", password="123456", charset="utf8mb4")


def run_sql_file(path: str):
    """按分号切分执行 SQL 文件（过滤纯注释行）"""
    cfg = dict(CFG)
    conn = pymysql.connect(**cfg)
    sql = io.open(path, encoding="utf-8").read()
    with conn.cursor() as cur:
        for stmt in sql.split(";"):
            lines = [l for l in stmt.splitlines() if not l.strip().startswith("--")]
            s = "\n".join(lines).strip()
            if s:
                cur.execute(s)
    conn.commit()
    conn.close()
    print(f"✅ {os.path.basename(path)} 执行完成")


def init_club():
    """社团活动登记系统没有现成 SQL 文件，这里按其代码字段建库建表"""
    conn = pymysql.connect(**CFG)
    with conn.cursor() as cur:
        cur.execute("CREATE DATABASE IF NOT EXISTS test_db DEFAULT CHARSET utf8mb4 COLLATE utf8mb4_general_ci")
        cur.execute("USE test_db")
        cur.execute("""
            CREATE TABLE IF NOT EXISTS activity (
                id INT AUTO_INCREMENT PRIMARY KEY,
                activity_name VARCHAR(100) NOT NULL COMMENT '活动名称',
                activity_type VARCHAR(50) NOT NULL COMMENT '活动类型',
                join_num INT NOT NULL COMMENT '参与人数'
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='社团活动表'
        """)
    conn.commit()
    conn.close()
    print("✅ test_db（社团活动）初始化完成")


if __name__ == "__main__":
    print("===== 1/4 蛋糕线上商城 cakeshop =====")
    subprocess.run([sys.executable, os.path.join(BASE, "apps", "mall", "backend", "db", "init_db.py")], check=True)

    print("===== 2/4 招财记账 account_db =====")
    run_sql_file(os.path.join(BASE, "apps", "account", "建表SQL.sql"))

    print("===== 3/4 社团活动登记 test_db =====")
    init_club()

    print("===== 4/4 星坞 StarDock stardock =====")
    run_sql_file(os.path.join(BASE, "apps", "stardock", "backend", "init.sql"))

    print("\n🎉 四个项目数据库全部就绪，可运行 python main.py 启动作品集")

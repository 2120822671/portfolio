"""
database.py —— 数据库连接池 + 统一工具函数
V2 加固版：连接池、参数绑定、事务保护
"""
import pymysql
from dbutils.pooled_db import PooledDB

# ============== 连接池配置 ==============
DB_CONFIG = {
    "host": "127.0.0.1",
    "port": 3306,
    "user": "root",
    "password": "123456",
    "database": "stardock",
    "charset": "utf8mb4",
    "cursorclass": pymysql.cursors.DictCursor,
    "maxconnections": 20,     # 最大连接数
    "mincached": 2,           # 初始空闲连接数
    "maxcached": 10,          # 最大空闲连接数
    "blocking": True,         # 连接池耗尽时阻塞等待
}

# 懒加载：避免 import 时就连接数据库
_pool: PooledDB | None = None


def get_pool() -> PooledDB:
    """获取连接池单例"""
    global _pool
    if _pool is None:
        _pool = PooledDB(
            creator=pymysql,
            maxconnections=DB_CONFIG["maxconnections"],
            mincached=DB_CONFIG["mincached"],
            maxcached=DB_CONFIG["maxcached"],
            blocking=DB_CONFIG["blocking"],
            host=DB_CONFIG["host"],
            port=DB_CONFIG["port"],
            user=DB_CONFIG["user"],
            password=DB_CONFIG["password"],
            database=DB_CONFIG["database"],
            charset=DB_CONFIG["charset"],
            cursorclass=DB_CONFIG["cursorclass"],
        )
    return _pool


def _get_conn():
    """从连接池取一个连接"""
    return get_pool().connection()


# ============== 统一工具函数 ==============

def query_one(sql: str, args=None) -> dict | None:
    """查单条，返回 dict 或 None"""
    conn = _get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(sql, args)
            return cur.fetchone()
    finally:
        conn.close()


def query_all(sql: str, args=None) -> list[dict]:
    """查多条，返回 list[dict]"""
    conn = _get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(sql, args)
            return cur.fetchall()
    finally:
        conn.close()


def execute(sql: str, args=None) -> int:
    """
    执行写操作（INSERT / UPDATE / DELETE）
    内部 try-except：异常 rollback，正常 commit
    返回受影响行数
    """
    conn = _get_conn()
    try:
        with conn.cursor() as cur:
            affected = cur.execute(sql, args)
        conn.commit()
        return affected
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def execute_return_id(sql: str, args=None) -> int:
    """
    插入语句，返回自增 ID
    同样做事务保护
    """
    conn = _get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(sql, args)
            last_id = cur.lastrowid
        conn.commit()
        return last_id
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

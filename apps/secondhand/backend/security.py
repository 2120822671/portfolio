import hashlib
import hmac
import time

import bcrypt

from config import TOKEN_SECRET, TOKEN_TTL_SECONDS


def hash_password(plain: str) -> str:
    """密码哈希：bcrypt 加盐单向散列，数据库不存明文"""
    return bcrypt.hashpw(plain.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    """校验密码：用存储的哈希（内含盐）重算比对"""
    try:
        return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))
    except ValueError:
        return False


def sign_token(user_id: int) -> str:
    """签发登录令牌：{uid}.{签发时间}.{HMAC-SHA256 签名}

    身份由服务端签名保证，客户端只能保存令牌、无法伪造其内容。
    """
    issued = int(time.time())
    payload = f"{user_id}.{issued}"
    sig = hmac.new(TOKEN_SECRET.encode(), payload.encode(), hashlib.sha256).hexdigest()
    return f"{payload}.{sig}"


def verify_token(token: str | None) -> int | None:
    """校验登录令牌：合法返回 uid，签名不符/格式错误/已过期返回 None"""
    if not token:
        return None
    parts = token.split(".")
    if len(parts) != 3:
        return None
    try:
        uid, issued = int(parts[0]), int(parts[1])
    except ValueError:
        return None
    payload = f"{uid}.{issued}"
    expect = hmac.new(TOKEN_SECRET.encode(), payload.encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(parts[2], expect):
        return None
    if time.time() - issued > TOKEN_TTL_SECONDS:
        return None
    return uid

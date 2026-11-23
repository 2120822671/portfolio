"""
安全工具 —— JWT 令牌签发/解析 + 密码哈希

使用:
    - python-jose: JWT 编码与解码
    - passlib[bcrypt]: bcrypt 密码哈希
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional, Union

from jose import JWTError, jwt
from passlib.context import CryptContext

from app.config import settings


# ---------- 密码哈希上下文 ----------
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    """
    对明文密码进行 bcrypt 哈希。

    兼容性处理: bcrypt 5.0+ 不再自动截断超过 72 字节的密码，
    这里手动编码为 UTF-8 并截取前 72 字节，避免 ValueError。
    """
    truncated = password.encode("utf-8")[:72]
    return pwd_context.hash(truncated)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    验证明文密码与哈希值是否匹配。
    同样需要手动截断以配合 hash_password 的处理。
    """
    truncated = plain_password.encode("utf-8")[:72]
    try:
        return pwd_context.verify(truncated, hashed_password)
    except Exception:
        return False


# ---------- JWT ----------
def create_access_token(
    subject: Union[str, int],
    extra_data: Optional[Dict[str, Any]] = None,
    expires_delta: Optional[timedelta] = None,
) -> str:
    """
    签发 JWT Access Token。

    Args:
        subject:   主题，通常是 user_id（放入 payload 的 "sub" 字段）
        extra_data: 额外数据（如 role）会被合并进 payload
        expires_delta: 过期时间偏移，默认使用配置的 ACCESS_TOKEN_EXPIRE_MINUTES

    Returns:
        JWT token 字符串
    """
    expire = datetime.now(timezone.utc) + (
        expires_delta
        if expires_delta is not None
        else timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    )

    payload: Dict[str, Any] = {
        "sub": str(subject),
        "exp": expire,
        "iat": datetime.now(timezone.utc),
    }
    if extra_data:
        payload.update(extra_data)

    token = jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    return token


def decode_access_token(token: str) -> Dict[str, Any]:
    """
    解析并验证 JWT Token。

    Returns:
        payload 字典

    Raises:
        JWTError: Token 无效/过期/签名错误时抛出
    """
    payload = jwt.decode(
        token,
        settings.SECRET_KEY,
        algorithms=[settings.ALGORITHM],
    )
    return payload

"""
auth.py —— 认证：注册 / 登录 / me / logout
V2 加固：注册后端硬编码 role=1，忽略前端传入
"""
import hashlib
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, field_validator

from database import query_one, execute_return_id
from deps import get_current_user

router = APIRouter(prefix="/api/auth", tags=["auth"])


# ============== Schema ==============
class RegisterBody(BaseModel):
    username: str
    password: str
    nickname: str
    # 注意：故意不接受 role 字段！注册一律 role=1


class LoginBody(BaseModel):
    username: str
    password: str

    @field_validator("username", "password")
    @classmethod
    def not_empty(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("账号和密码不能为空")
        return v.strip()


# ============== 接口 ==============
@router.post("/register")
async def register(body: RegisterBody):
    """注册 —— 后端硬编码 role=1（粉丝），防止越权"""
    if not body.username.strip() or not body.password.strip():
        raise HTTPException(status_code=400, detail="账号和密码不能为空")
    if len(body.password) < 6:
        raise HTTPException(status_code=400, detail="密码至少 6 位")
    if len(body.username) < 3:
        raise HTTPException(status_code=400, detail="账号至少 3 位")

    # 检查重名
    exists = query_one("SELECT id FROM users WHERE username=%s", (body.username,))
    if exists:
        raise HTTPException(status_code=400, detail="账号已存在")

    # 后端硬编码 role=1，不信前端
    md5_pwd = hashlib.md5(body.password.encode()).hexdigest()
    uid = execute_return_id(
        """INSERT INTO users (username, password, nickname, role, create_time)
           VALUES (%s, %s, %s, 1, %s)""",
        (body.username, md5_pwd, body.nickname.strip(), datetime.now())
    )
    return {"code": 0, "msg": "注册成功，请登录", "data": {"user_id": uid}}


@router.post("/login")
async def login(body: LoginBody, request: Request):
    """登录 —— Session 写入 user_id"""
    md5_pwd = hashlib.md5(body.password.encode()).hexdigest()
    user = query_one(
        "SELECT id, username, nickname, avatar, role, status FROM users WHERE username=%s AND password=%s",
        (body.username, md5_pwd)
    )
    if not user:
        raise HTTPException(status_code=400, detail="账号或密码错误")
    if user["status"] != 1:
        raise HTTPException(status_code=403, detail="账号已被禁用")

    request.session["user_id"] = user["id"]
    return {
        "code": 0, "msg": "登录成功",
        "data": {k: v for k, v in user.items() if k != "status"}
    }


@router.get("/me")
async def me(current_user: dict = Depends(get_current_user)):
    """获取当前登录用户信息"""
    return {"code": 0, "msg": "ok", "data": current_user}


@router.post("/logout")
async def logout(request: Request):
    """退出登录 —— 清 Session"""
    request.session.pop("user_id", None)
    return {"code": 0, "msg": "已退出", "data": None}

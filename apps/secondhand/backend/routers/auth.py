from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from database import get_db
from models import User
from resp import ok
from schemas import UserLogin, UserRegister
from security import hash_password, sign_token, verify_password

router = APIRouter(prefix="/auth", tags=["用户"])


@router.post("/register", status_code=201, summary="用户注册")
def register(payload: UserRegister, db: Session = Depends(get_db)):
    exists = db.scalar(select(User).where(User.username == payload.username))
    if exists:
        raise HTTPException(status_code=409, detail="用户名已存在")
    user = User(
        username=payload.username,
        password=hash_password(payload.password),  # 只存哈希，不存明文
        nickname=payload.nickname or payload.username,
        phone=payload.phone,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return ok({"id": user.id, "username": user.username,
               "nickname": user.nickname, "credit_score": user.credit_score}, "注册成功")


@router.post("/login", summary="用户登录")
def login(payload: UserLogin, db: Session = Depends(get_db)):
    user = db.scalar(select(User).where(User.username == payload.username))
    if not user or not verify_password(payload.password, user.password):
        raise HTTPException(status_code=401, detail="用户名或密码错误")
    return ok({"token": sign_token(user.id),   # 增量修复：改为服务端签名令牌，客户端无法伪造身份
               "user": {"id": user.id, "username": user.username,
                        "nickname": user.nickname, "credit_score": user.credit_score}}, "登录成功")

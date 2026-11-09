"""
users.py —— 用户管理
V2 加固：UPDATE 字段白名单、防越权操作、永不返回 password
"""
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Optional

from database import query_one, query_all, execute, execute_return_id
from deps import get_current_user, require_role

router = APIRouter(prefix="/api/users", tags=["users"])

# UPDATE 硬编码白名单，禁止拿前端 key 直接拼 SQL
_ALLOWED_UPDATE_FIELDS = {"nickname", "avatar"}


# ============== Schema ==============
class UpdateProfileBody(BaseModel):
    nickname: Optional[str] = None
    avatar: Optional[str] = None


class UpdateStatusBody(BaseModel):
    status: int  # 0 禁用 / 1 正常


class UpdateRoleBody(BaseModel):
    role: int  # 1/2/3


class ResetPasswordBody(BaseModel):
    new_password: str


# ============== 接口 ==============
@router.put("/me")
async def update_my_profile(body: UpdateProfileBody, current_user: dict = Depends(get_current_user)):
    """更新自己的资料（仅 nickname / avatar 两个字段允许改）"""
    fields = body.model_dump(exclude_none=True)
    if not fields:
        raise HTTPException(status_code=400, detail="没有可更新的字段")

    # 白名单校验
    invalid = set(fields.keys()) - _ALLOWED_UPDATE_FIELDS
    if invalid:
        raise HTTPException(status_code=400, detail=f"不允许更新字段: {invalid}")

    set_clause = ", ".join(f"{k}=%s" for k in fields.keys())
    args = list(fields.values()) + [current_user["id"]]
    execute(f"UPDATE users SET {set_clause} WHERE id=%s", args)
    return {"code": 0, "msg": "更新成功", "data": None}


@router.get("")
async def list_users(
    role: Optional[int] = None,
    status: Optional[int] = None,
    keyword: Optional[str] = None,
    current_user: dict = Depends(require_role(2)),  # 仅管理员
):
    """用户列表（管理员）"""
    where = ["1=1"]
    args = []
    if role is not None:
        where.append("role=%s")
        args.append(role)
    if status is not None:
        where.append("status=%s")
        args.append(status)
    if keyword:
        where.append("(username LIKE %s OR nickname LIKE %s)")
        args.extend([f"%{keyword}%", f"%{keyword}%"])

    sql = (
        "SELECT id, username, nickname, avatar, role, score, status, create_time "
        f"FROM users WHERE {' AND '.join(where)} ORDER BY id DESC"
    )
    rows = query_all(sql, args)
    return {"code": 0, "msg": "ok", "data": rows}


@router.put("/{user_id}/status")
async def update_user_status(
    user_id: int, body: UpdateStatusBody,
    current_user: dict = Depends(require_role(2)),
):
    """启用/禁用用户"""
    if body.status not in (0, 1):
        raise HTTPException(status_code=400, detail="status 只能是 0 或 1")
    execute("UPDATE users SET status=%s WHERE id=%s", (body.status, user_id))
    return {"code": 0, "msg": "操作成功", "data": None}


@router.put("/{user_id}/role")
async def update_user_role(
    user_id: int, body: UpdateRoleBody,
    current_user: dict = Depends(require_role(2)),
):
    """修改用户角色（注意：升级为明星时要同步建 celebrities 档案）"""
    if body.role not in (1, 2, 3):
        raise HTTPException(status_code=400, detail="role 只能是 1/2/3")

    execute("UPDATE users SET role=%s WHERE id=%s", (body.role, user_id))

    # 升级为明星 → 自动创建 celebrities 档案 + 粉丝团
    if body.role == 3:
        exists = query_one("SELECT id FROM celebrities WHERE user_id=%s", (user_id,))
        if not exists:
            user = query_one("SELECT nickname FROM users WHERE id=%s", (user_id,))
            now = datetime.now()
            cid = execute_return_id(
                """INSERT INTO celebrities (user_id, stage_name, category, bio, status, create_time)
                   VALUES (%s, %s, '其他', '这位明星很神秘~', 1, %s)""",
                (user_id, user["nickname"], now)
            )
            execute_return_id(
                """INSERT INTO fan_clubs (celebrity_id, name, description, create_time)
                   VALUES (%s, %s, %s, %s)""",
                (cid, f"{user['nickname']}粉丝团", "欢迎加入粉丝团！", now)
            )

    return {"code": 0, "msg": "角色已更新", "data": None}


@router.put("/{user_id}/reset-password")
async def reset_password(
    user_id: int, body: ResetPasswordBody,
    current_user: dict = Depends(require_role(2)),
):
    """重置用户密码"""
    import hashlib
    if len(body.new_password) < 6:
        raise HTTPException(status_code=400, detail="密码至少 6 位")
    md5 = hashlib.md5(body.new_password.encode()).hexdigest()
    execute("UPDATE users SET password=%s WHERE id=%s", (md5, user_id))
    return {"code": 0, "msg": "密码已重置", "data": None}

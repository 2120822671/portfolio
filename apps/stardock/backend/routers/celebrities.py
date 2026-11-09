"""
celebrities.py —— 明星中心
"""
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Optional

from database import query_one, query_all, execute, execute_return_id
from deps import get_current_user, require_role

router = APIRouter(prefix="/api/celebrities", tags=["celebrities"])


# ============== Schema ==============
class CelebrityCreate(BaseModel):
    user_id: int           # 关联已存在的 role=3 用户
    stage_name: str
    category: str
    bio: Optional[str] = None
    cover_image: Optional[str] = None


class CelebrityUpdate(BaseModel):
    stage_name: Optional[str] = None
    category: Optional[str] = None
    bio: Optional[str] = None
    cover_image: Optional[str] = None
    status: Optional[int] = None


_ALLOWED_UPDATE_FIELDS = {"stage_name", "category", "bio", "cover_image", "status"}


# ============== 接口 ==============
@router.get("")
async def list_celebrities(
    keyword: Optional[str] = None,
    category: Optional[str] = None,
):
    """明星列表（公开）"""
    where = ["c.status=1"]
    args = []
    if keyword:
        where.append("(c.stage_name LIKE %s OR c.bio LIKE %s)")
        args.extend([f"%{keyword}%", f"%{keyword}%"])
    if category:
        where.append("c.category=%s")
        args.append(category)

    sql = f"""
        SELECT c.id, c.stage_name, c.category, c.bio, c.cover_image, c.fan_count,
               u.nickname, u.id AS user_id,
               fc.id AS club_id, fc.name AS club_name, fc.member_count
        FROM celebrities c
        JOIN users u ON u.id = c.user_id
        LEFT JOIN fan_clubs fc ON fc.celebrity_id = c.id
        WHERE {' AND '.join(where)}
        ORDER BY c.fan_count DESC, c.id DESC
    """
    rows = query_all(sql, args)
    return {"code": 0, "msg": "ok", "data": rows}


@router.get("/{cid}")
async def get_celebrity(cid: int):
    """明星详情"""
    row = query_one(
        """SELECT c.id, c.stage_name, c.category, c.bio, c.cover_image, c.fan_count, c.user_id,
                  u.nickname,
                  fc.id AS club_id, fc.name AS club_name, fc.description AS club_desc, fc.member_count
           FROM celebrities c
           JOIN users u ON u.id = c.user_id
           LEFT JOIN fan_clubs fc ON fc.celebrity_id = c.id
           WHERE c.id=%s AND c.status=1""",
        (cid,)
    )
    if not row:
        raise HTTPException(status_code=404, detail="明星不存在")
    return {"code": 0, "msg": "ok", "data": row}


@router.post("")
async def create_celebrity(body: CelebrityCreate, current_user: dict = Depends(require_role(2))):
    """新增明星（自动建粉丝团）"""
    # 确认用户存在且是明星角色
    user = query_one("SELECT id, nickname, role FROM users WHERE id=%s", (body.user_id,))
    if not user:
        raise HTTPException(status_code=400, detail="用户不存在")
    if user["role"] != 3:
        execute("UPDATE users SET role=3 WHERE id=%s", (body.user_id,))

    # 检查是否已有档案
    exists = query_one("SELECT id FROM celebrities WHERE user_id=%s", (body.user_id,))
    if exists:
        raise HTTPException(status_code=400, detail="该用户已有明星档案")

    now = datetime.now()
    cid = execute_return_id(
        """INSERT INTO celebrities (user_id, stage_name, category, bio, cover_image, create_time)
           VALUES (%s, %s, %s, %s, %s, %s)""",
        (body.user_id, body.stage_name, body.category, body.bio or "", body.cover_image, now)
    )
    execute_return_id(
        """INSERT INTO fan_clubs (celebrity_id, name, description, create_time)
           VALUES (%s, %s, %s, %s)""",
        (cid, f"{body.stage_name}粉丝团", body.bio or "欢迎加入粉丝团！", now)
    )
    return {"code": 0, "msg": "明星档案创建成功", "data": {"celebrity_id": cid}}


@router.put("/{cid}")
async def update_celebrity(
    cid: int, body: CelebrityUpdate,
    current_user: dict = Depends(get_current_user),
):
    """更新明星档案 —— 管理员可改所有；本人只能改自己的"""
    celeb = query_one("SELECT user_id FROM celebrities WHERE id=%s", (cid,))
    if not celeb:
        raise HTTPException(status_code=404, detail="明星不存在")

    # 权限：管理员 或 本人
    if current_user["role"] != 2 and current_user["id"] != celeb["user_id"]:
        raise HTTPException(status_code=403, detail="无权限")

    # 白名单
    fields = body.model_dump(exclude_none=True)
    invalid = set(fields.keys()) - _ALLOWED_UPDATE_FIELDS
    if invalid:
        raise HTTPException(status_code=400, detail=f"不允许更新字段: {invalid}")
    if not fields:
        raise HTTPException(status_code=400, detail="没有可更新的字段")

    set_clause = ", ".join(f"{k}=%s" for k in fields.keys())
    args = list(fields.values()) + [cid]
    execute(f"UPDATE celebrities SET {set_clause} WHERE id=%s", args)
    return {"code": 0, "msg": "更新成功", "data": None}

"""
activities.py —— 活动 / 通知
发布权限：管理员(role=2) 或 明星本人(role=3)
查看权限：
  scope=1 全体可见
  scope=2 只有指定粉丝团成员可见（管理员/发布者本人可见所有）
"""
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from typing import Optional

from database import query_one, query_all, execute, execute_return_id
from deps import get_current_user, require_role

router = APIRouter(prefix="/api/activities", tags=["activities"])


# ============== Schema ==============
class ActivityCreate(BaseModel):
    title: str
    content: str
    activity_type: int = 1      # 1通知/2活动
    scope: int = 1              # 1全体/2指定粉丝团
    target_club_id: Optional[int] = None


class ActivityUpdate(BaseModel):
    title: Optional[str] = None
    content: Optional[str] = None
    status: Optional[int] = None


_ALLOWED_UPDATE = {"title", "content", "status"}


# ============== 发布 ==============
@router.post("")
async def create_activity(body: ActivityCreate, current_user: dict = Depends(get_current_user)):
    """管理员 或 明星本人 发布"""
    if current_user["role"] not in (2, 3):
        raise HTTPException(status_code=403, detail="无权限发布活动")

    if body.activity_type not in (1, 2):
        raise HTTPException(status_code=400, detail="activity_type 只能是 1 或 2")
    if body.scope not in (1, 2):
        raise HTTPException(status_code=400, detail="scope 只能是 1 或 2")
    if body.scope == 2 and not body.target_club_id:
        raise HTTPException(status_code=400, detail="scope=2 必须指定 target_club_id")

    # 明星发布 scope=2：只能发自己的粉丝团
    if current_user["role"] == 3 and body.scope == 2:
        my_club = query_one(
            """SELECT fc.id FROM fan_clubs fc
               JOIN celebrities c ON c.id = fc.celebrity_id
               WHERE c.user_id = %s""",
            (current_user["id"],)
        )
        if not my_club or body.target_club_id != my_club["id"]:
            raise HTTPException(status_code=403, detail="明星只能发自己的粉丝团")

    now = datetime.now()
    aid = execute_return_id(
        """INSERT INTO activities
           (title, content, activity_type, scope, target_club_id,
            poster_id, poster_name, create_time)
           VALUES (%s, %s, %s, %s, %s, %s, %s, %s)""",
        (body.title[:100], body.content, body.activity_type, body.scope,
         body.target_club_id, current_user["id"], current_user["nickname"], now)
    )
    return {"code": 0, "msg": "发布成功", "data": {"activity_id": aid}}


# ============== 列表（带权限过滤）==============
@router.get("")
async def list_activities(
    page: int = Query(1, ge=1),
    size: int = Query(10, ge=1, le=50),
    current_user: dict = Depends(get_current_user),
):
    """列表：管理员/明星能看全部；粉丝只看全局+自己粉丝团的"""
    offset = (page - 1) * size

    if current_user["role"] == 2:
        # 管理员：全部
        where = ["status=1"]
        args = []
    elif current_user["role"] == 3:
        # 明星：全局 + 自己粉丝团的
        my_club = query_one(
            """SELECT fc.id FROM fan_clubs fc
               JOIN celebrities c ON c.id = fc.celebrity_id
               WHERE c.user_id = %s""",
            (current_user["id"],)
        )
        if my_club:
            where = ["status=1 AND (scope=1 OR (scope=2 AND target_club_id=%s))"]
            args = [my_club["id"]]
        else:
            where = ["status=1 AND scope=1"]
            args = []
    else:
        # 粉丝：全局 + 自己加入的粉丝团
        where = ["status=1 AND scope=1"]
        member_clubs = query_all(
            "SELECT club_id FROM fan_club_members WHERE user_id=%s",
            (current_user["id"],)
        )
        club_ids = [m["club_id"] for m in member_clubs]
        if club_ids:
            placeholders = ",".join(["%s"] * len(club_ids))
            where[0] = f"(status=1 AND scope=1) OR (status=1 AND scope=2 AND target_club_id IN ({placeholders}))"
            args = club_ids
        else:
            args = []

    sql = f"""
        SELECT a.*, fc.name AS club_name
        FROM activities a
        LEFT JOIN fan_clubs fc ON fc.id = a.target_club_id
        WHERE {' AND '.join(where) if len(where) > 1 else where[0]}
        ORDER BY a.id DESC
        LIMIT %s OFFSET %s
    """
    args.extend([size, offset])
    rows = query_all(sql, args)
    return {"code": 0, "msg": "ok", "data": rows}


# ============== 单条 ==============
@router.get("/{aid}")
async def get_activity(aid: int, current_user: dict = Depends(get_current_user)):
    row = query_one("SELECT * FROM activities WHERE id=%s", (aid,))
    if not row:
        raise HTTPException(status_code=404, detail="活动不存在")
    if row["status"] != 1 and row["poster_id"] != current_user["id"] and current_user["role"] != 2:
        raise HTTPException(status_code=403, detail="无权查看")
    return {"code": 0, "msg": "ok", "data": row}


# ============== 撤回 / 更新 ==============
@router.put("/{aid}")
async def update_activity(aid: int, body: ActivityUpdate, current_user: dict = Depends(get_current_user)):
    row = query_one("SELECT * FROM activities WHERE id=%s", (aid,))
    if not row:
        raise HTTPException(status_code=404, detail="活动不存在")
    if current_user["role"] != 2 and row["poster_id"] != current_user["id"]:
        raise HTTPException(status_code=403, detail="只有发布者或管理员可以修改")

    fields = body.model_dump(exclude_none=True)
    invalid = set(fields.keys()) - _ALLOWED_UPDATE
    if invalid:
        raise HTTPException(status_code=400, detail=f"不允许更新字段: {invalid}")
    if not fields:
        raise HTTPException(status_code=400, detail="没有可更新的字段")

    set_clause = ", ".join(f"{k}=%s" for k in fields.keys())
    args = list(fields.values()) + [aid]
    execute(f"UPDATE activities SET {set_clause} WHERE id=%s", args)
    return {"code": 0, "msg": "更新成功", "data": None}


@router.delete("/{aid}")
async def delete_activity(aid: int, current_user: dict = Depends(get_current_user)):
    """软删除：把 status 设成 0"""
    row = query_one("SELECT * FROM activities WHERE id=%s", (aid,))
    if not row:
        raise HTTPException(status_code=404, detail="活动不存在")
    if current_user["role"] != 2 and row["poster_id"] != current_user["id"]:
        raise HTTPException(status_code=403, detail="只有发布者或管理员可以撤回")
    execute("UPDATE activities SET status=0 WHERE id=%s", (aid,))
    return {"code": 0, "msg": "已撤回", "data": None}

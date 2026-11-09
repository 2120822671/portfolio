"""
fan_clubs.py —— 粉丝团：详情、加入、退出
"""
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse

from database import query_one, query_all, execute, execute_return_id
from deps import get_current_user

router = APIRouter(prefix="/api/fan-clubs", tags=["fan_clubs"])


@router.get("/{club_id}")
async def get_fan_club(club_id: int):
    """粉丝团详情 + 成员列表"""
    club = query_one(
        """SELECT fc.id, fc.name, fc.description, fc.member_count, fc.create_time,
                  c.stage_name, c.category, c.cover_image, c.id AS celebrity_id
           FROM fan_clubs fc
           JOIN celebrities c ON c.id = fc.celebrity_id
           WHERE fc.id=%s""",
        (club_id,)
    )
    if not club:
        raise HTTPException(status_code=404, detail="粉丝团不存在")

    members = query_all(
        """SELECT u.id, u.nickname, u.avatar, u.role,
                  fcm.nick_in_club, fcm.join_time
           FROM fan_club_members fcm
           JOIN users u ON u.id = fcm.user_id
           WHERE fcm.club_id=%s
           ORDER BY fcm.join_time ASC""",
        (club_id,)
    )
    club["members"] = members
    return {"code": 0, "msg": "ok", "data": club}


@router.post("/{club_id}/join")
async def join_club(club_id: int, current_user: dict = Depends(get_current_user)):
    """加入粉丝团"""
    club = query_one("SELECT id, member_count FROM fan_clubs WHERE id=%s", (club_id,))
    if not club:
        raise HTTPException(status_code=404, detail="粉丝团不存在")

    exists = query_one(
        "SELECT id FROM fan_club_members WHERE club_id=%s AND user_id=%s",
        (club_id, current_user["id"])
    )
    if exists:
        raise HTTPException(status_code=400, detail="你已经在这个粉丝团里了")

    now = datetime.now()
    execute_return_id(
        """INSERT INTO fan_club_members (club_id, user_id, join_time)
           VALUES (%s, %s, %s)""",
        (club_id, current_user["id"], now)
    )
    # 冗余字段 +1
    execute("UPDATE fan_clubs SET member_count = member_count + 1 WHERE id=%s", (club_id,))
    # 明星粉丝数 +1
    execute(
        """UPDATE celebrities SET fan_count = fan_count + 1
           WHERE id=(SELECT celebrity_id FROM fan_clubs WHERE id=%s)""",
        (club_id,)
    )
    return {"code": 0, "msg": "加入成功", "data": None}


@router.post("/{club_id}/leave")
async def leave_club(club_id: int, current_user: dict = Depends(get_current_user)):
    """退出粉丝团 —— 带 user_id 防越权"""
    club = query_one("SELECT id FROM fan_clubs WHERE id=%s", (club_id,))
    if not club:
        raise HTTPException(status_code=404, detail="粉丝团不存在")

    affected = execute(
        "DELETE FROM fan_club_members WHERE club_id=%s AND user_id=%s",
        (club_id, current_user["id"])
    )
    if affected == 0:
        raise HTTPException(status_code=400, detail="你不在这个粉丝团里")

    execute("UPDATE fan_clubs SET member_count = GREATEST(member_count - 1, 0) WHERE id=%s", (club_id,))
    execute(
        """UPDATE celebrities SET fan_count = GREATEST(fan_count - 1, 0)
           WHERE id=(SELECT celebrity_id FROM fan_clubs WHERE id=%s)""",
        (club_id,)
    )
    return {"code": 0, "msg": "已退出", "data": None}

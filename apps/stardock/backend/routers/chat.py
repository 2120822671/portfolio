"""
chat.py —— 历史消息 + WebSocket 实时聊天
"""
import asyncio
import json
from datetime import datetime
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, WebSocket, WebSocketDisconnect
from pydantic import BaseModel

from database import query_one, query_all, execute, execute_return_id
from deps import get_current_user, ws_get_current_user

router = APIRouter(tags=["chat"])

# ============== WebSocket 房间管理（内存版）==============
# 简化实现：按 club_id 分房间，存 set[WebSocket]
# 生产环境可以换 Redis Pub/Sub
_rooms: dict[int, set[WebSocket]] = {}


def _get_or_create_room(club_id: int) -> set[WebSocket]:
    if club_id not in _rooms:
        _rooms[club_id] = set()
    return _rooms[club_id]


# ============== HTTP：历史消息 ==============
@router.get("/api/chat/{club_id}/history")
async def get_history(
    club_id: int,
    page: int = Query(1, ge=1),
    size: int = Query(50, ge=1, le=200),
    current_user: dict = Depends(get_current_user),
):
    """拉取历史消息（需要是粉丝团成员 或 管理员）"""
    club = query_one("SELECT id FROM fan_clubs WHERE id=%s", (club_id,))
    if not club:
        raise HTTPException(status_code=404, detail="粉丝团不存在")

    # 鉴权：管理员可看所有；其他角色必须是成员
    if current_user["role"] != 2:
        is_member = query_one(
            "SELECT id FROM fan_club_members WHERE club_id=%s AND user_id=%s",
            (club_id, current_user["id"])
        )
        if not is_member:
            raise HTTPException(status_code=403, detail="你不是该粉丝团成员")

    offset = (page - 1) * size
    msgs = query_all(
        """SELECT m.id, m.content, m.msg_type, m.create_time,
                  u.id AS user_id, u.nickname, u.avatar
           FROM chat_messages m
           JOIN users u ON u.id = m.user_id
           WHERE m.club_id=%s
           ORDER BY m.id DESC
           LIMIT %s OFFSET %s""",
        (club_id, size, offset)
    )
    # 翻回正序方便前端渲染
    msgs.reverse()
    return {"code": 0, "msg": "ok", "data": msgs}


# ============== WebSocket：实时聊天 ==============
@router.websocket("/ws/chat/{club_id}")
async def ws_chat(websocket: WebSocket, club_id: int):
    await websocket.accept()

    # 鉴权（从 query 里带 user_id，简化版）
    try:
        user = await ws_get_current_user(websocket)
    except Exception:
        await websocket.close()
        return

    # 检查粉丝团
    club = query_one("SELECT id FROM fan_clubs WHERE id=%s", (club_id,))
    if not club:
        await websocket.close()
        return

    # 成员校验（管理员可进所有）
    if user["role"] != 2:
        is_member = query_one(
            "SELECT id FROM fan_club_members WHERE club_id=%s AND user_id=%s",
            (club_id, user["id"])
        )
        if not is_member:
            await websocket.close()
            return

    # 加入房间
    room = _get_or_create_room(club_id)
    room.add(websocket)

    try:
        while True:
            raw = await websocket.receive_text()
            try:
                data = json.loads(raw)
            except Exception:
                continue

            content = (data.get("content") or "").strip()
            if not content or len(content) > 1000:
                continue

            # 落库
            now = datetime.now()
            msg_id = execute_return_id(
                """INSERT INTO chat_messages (club_id, user_id, content, msg_type, create_time)
                   VALUES (%s, %s, %s, 1, %s)""",
                (club_id, user["id"], content, now)
            )

            # 广播
            payload = json.dumps({
                "type": "message",
                "data": {
                    "id": msg_id,
                    "content": content,
                    "msg_type": 1,
                    "create_time": now.strftime("%Y-%m-%d %H:%M:%S"),
                    "user_id": user["id"],
                    "nickname": user["nickname"],
                    "avatar": user.get("avatar"),
                }
            }, ensure_ascii=False)

            for conn in list(room):
                try:
                    await conn.send_text(payload)
                except Exception:
                    pass

    except WebSocketDisconnect:
        pass
    finally:
        room.discard(websocket)
        if not room:
            _rooms.pop(club_id, None)

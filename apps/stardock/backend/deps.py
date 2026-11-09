"""
deps.py —— 依赖注入：获取当前用户、角色鉴权
"""
from fastapi import Depends, HTTPException, Request, WebSocket, WebSocketException, status

from database import query_one


# ============== HTTP 接口鉴权 ==============

def get_current_user(request: Request) -> dict:
    """
    从 Session 读取登录用户
    未登录抛 401
    """
    user_id = request.session.get("user_id")
    if not user_id:
        raise HTTPException(status_code=401, detail="未登录")

    user = query_one(
        "SELECT id, username, nickname, avatar, role, score, status FROM users WHERE id=%s",
        (user_id,)
    )
    if not user:
        raise HTTPException(status_code=401, detail="用户不存在")
    if user["status"] != 1:
        raise HTTPException(status_code=403, detail="账号已被禁用")
    return user


def require_role(*roles: int):
    """
    角色校验装饰器工厂
    用法：Depends(require_role(2, 3))  允许管理员和明星
    """
    def _check(current_user: dict = Depends(get_current_user)) -> dict:
        if current_user["role"] not in roles:
            raise HTTPException(status_code=403, detail="权限不足")
        return current_user
    return _check


# ============== WebSocket 鉴权 ==============

async def ws_get_current_user(websocket: WebSocket) -> dict:
    """
    WebSocket 鉴权：从 query 参数读 token（或复用 Cookie Session）
    这里简化处理：读取 query ?user_id=xxx （生产环境应该验证 token）
    """
    user_id = websocket.query_params.get("user_id")
    if not user_id:
        raise WebSocketException(code=status.WS_1008_POLICY_VIOLATION)

    user = query_one(
        "SELECT id, username, nickname, avatar, role, status FROM users WHERE id=%s AND status=1",
        (int(user_id),)
    )
    if not user:
        raise WebSocketException(code=status.WS_1008_POLICY_VIOLATION)
    return user

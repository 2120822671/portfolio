"""
gacha.py —— 抽卡游戏 + 管理员卡池配置
"""
import json
import random
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from typing import Optional

from database import query_one, query_all, execute, execute_return_id
from deps import get_current_user, require_role

router = APIRouter(prefix="/api/gacha", tags=["gacha"])

# rarity 显示名
_RARITY_NAMES = {1: "N", 2: "R", 3: "SR", 4: "SSR"}


# ============== Schema ==============
class DrawBody(BaseModel):
    pool_id: int
    count: int = 1  # 1 或 10


class PoolCreate(BaseModel):
    name: str
    celebrity_id: Optional[int] = None
    description: Optional[str] = None
    cost_per_draw: int = 100
    cost_per_ten: int = 900
    is_active: int = 1


class PoolUpdate(BaseModel):
    name: Optional[str] = None
    celebrity_id: Optional[int] = None
    description: Optional[str] = None
    cost_per_draw: Optional[int] = None
    cost_per_ten: Optional[int] = None
    is_active: Optional[int] = None


_POOL_ALLOWED_UPDATE = {"name", "celebrity_id", "description", "cost_per_draw", "cost_per_ten", "is_active"}


class CardCreate(BaseModel):
    pool_id: int
    celebrity_id: Optional[int] = None
    name: str
    image_url: str
    rarity: int
    weight: int = 100
    description: Optional[str] = None


class CardUpdate(BaseModel):
    pool_id: Optional[int] = None
    celebrity_id: Optional[int] = None
    name: Optional[str] = None
    image_url: Optional[str] = None
    rarity: Optional[int] = None
    weight: Optional[int] = None
    description: Optional[str] = None


_CARD_ALLOWED_UPDATE = {"pool_id", "celebrity_id", "name", "image_url", "rarity", "weight", "description"}


# ============== 工具：按权重抽一张卡 ==============
def _weighted_pick(cards: list[dict]) -> dict:
    """按 weight 权重随机选一张"""
    total = sum(c["weight"] for c in cards)
    r = random.randint(1, total)
    acc = 0
    for c in cards:
        acc += c["weight"]
        if r <= acc:
            return c
    return cards[-1]


# ============== 公开：卡池列表 / 详情 ==============
@router.get("/pools")
async def list_pools():
    rows = query_all(
        """SELECT p.id, p.name, p.description, p.cost_per_draw, p.cost_per_ten,
                  p.is_active, p.celebrity_id,
                  c.stage_name AS celebrity_name
           FROM card_pools p
           LEFT JOIN celebrities c ON c.id = p.celebrity_id
           ORDER BY p.is_active DESC, p.id DESC"""
    )
    return {"code": 0, "msg": "ok", "data": rows}


@router.get("/pools/{pool_id}")
async def get_pool(pool_id: int):
    pool = query_one(
        """SELECT p.*, c.stage_name AS celebrity_name
           FROM card_pools p
           LEFT JOIN celebrities c ON c.id = p.celebrity_id
           WHERE p.id=%s""",
        (pool_id,)
    )
    if not pool:
        raise HTTPException(status_code=404, detail="卡池不存在")

    cards = query_all(
        "SELECT * FROM cards WHERE pool_id=%s ORDER BY rarity DESC, weight DESC",
        (pool_id,)
    )
    # 给卡片加 rarity_name
    for c in cards:
        c["rarity_name"] = _RARITY_NAMES.get(c["rarity"], "?")
    pool["cards"] = cards
    return {"code": 0, "msg": "ok", "data": pool}


# ============== 抽卡核心 ==============
@router.post("/draw")
async def draw(body: DrawBody, current_user: dict = Depends(get_current_user)):
    """
    执行抽卡（事务保护）
    - 查卡池 → 查积分 → 扣积分 → 抽卡 → 写记录 → 更新 user_cards
    """
    if body.count not in (1, 10):
        raise HTTPException(status_code=400, detail="count 只能是 1 或 10")

    pool = query_one("SELECT * FROM card_pools WHERE id=%s", (body.pool_id,))
    if not pool:
        raise HTTPException(status_code=404, detail="卡池不存在")
    if pool["is_active"] != 1:
        raise HTTPException(status_code=400, detail="卡池已关闭")

    # 查该卡池的所有卡片
    cards_in_pool = query_all(
        "SELECT id, name, image_url, rarity, weight FROM cards WHERE pool_id=%s",
        (body.pool_id,)
    )
    if not cards_in_pool:
        raise HTTPException(status_code=400, detail="卡池里没有卡片")

    # 算消耗
    cost = pool["cost_per_ten"] if body.count == 10 else pool["cost_per_draw"]

    # 查积分（需要事务内再查一次校验，防止并发扣超）
    user = query_one("SELECT id, score FROM users WHERE id=%s", (current_user["id"],))
    if user["score"] < cost:
        raise HTTPException(status_code=400, detail=f"积分不足，需要 {cost}，当前 {user['score']}")

    # 执行抽卡（伪事务：先扣积分再抽，失败回滚）
    # 注意：生产环境应该用真正的数据库事务，这里简化处理
    try:
        # 1. 扣积分
        execute(
            "UPDATE users SET score = score - %s WHERE id=%s AND score >= %s",
            (cost, current_user["id"], cost)
        )

        # 2. 抽 body.count 次
        drawn_cards = []
        results_json = []
        for _ in range(body.count):
            picked = _weighted_pick(cards_in_pool)
            drawn_cards.append(picked)
            results_json.append({
                "card_id": picked["id"],
                "name": picked["name"],
                "image_url": picked["image_url"],
                "rarity": picked["rarity"],
                "rarity_name": _RARITY_NAMES.get(picked["rarity"], "?"),
            })

        # 3. 更新 user_cards（ON DUPLICATE KEY UPDATE count）
        for picked in drawn_cards:
            affected = execute(
                """INSERT INTO user_cards (user_id, card_id, count, obtain_time)
                   VALUES (%s, %s, 1, %s)
                   ON DUPLICATE KEY UPDATE count = count + 1""",
                (current_user["id"], picked["id"], datetime.now())
            )

        # 4. 写抽卡记录 —— draw_type: 1=单抽, 2=十连（不是 count 本身！）
        draw_type = 2 if body.count == 10 else 1
        execute_return_id(
            """INSERT INTO gacha_records (user_id, pool_id, draw_type, total_cost, results_json, create_time)
               VALUES (%s, %s, %s, %s, %s, %s)""",
            (current_user["id"], body.pool_id, draw_type, cost, json.dumps(results_json, ensure_ascii=False), datetime.now())
        )

        # 5. 返回（注意前端展示顺序：SSR 放最后比较有悬念）
        results_json.reverse()
        return {
            "code": 0, "msg": "抽卡成功",
            "data": {
                "cost": cost,
                "drawn": results_json,
                "remain_score": user["score"] - cost,
            }
        }

    except Exception as e:
        # 回滚积分（如果扣了的话）
        try:
            execute(
                "UPDATE users SET score = score + %s WHERE id=%s",
                (cost, current_user["id"])
            )
        except Exception:
            pass
        raise HTTPException(status_code=500, detail=f"抽卡失败：{str(e)}")


# ============== 我的图鉴 / 抽卡记录 ==============
@router.get("/my-cards")
async def my_cards(
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    rarity: Optional[int] = None,
    current_user: dict = Depends(get_current_user),
):
    offset = (page - 1) * size
    where = ["uc.user_id=%s"]
    args: list = [current_user["id"]]
    if rarity:
        where.append("c.rarity=%s")
        args.append(rarity)

    sql = f"""
        SELECT uc.card_id, uc.count, uc.obtain_time,
               c.name, c.image_url, c.rarity, c.pool_id
        FROM user_cards uc
        JOIN cards c ON c.id = uc.card_id
        WHERE {' AND '.join(where)}
        ORDER BY c.rarity DESC, uc.obtain_time DESC
        LIMIT %s OFFSET %s
    """
    args.extend([size, offset])
    rows = query_all(sql, args)
    for r in rows:
        r["rarity_name"] = _RARITY_NAMES.get(r["rarity"], "?")
    return {"code": 0, "msg": "ok", "data": rows}


@router.get("/my-cards/{card_id}")
async def my_card_detail(card_id: int, current_user: dict = Depends(get_current_user)):
    """我的某张卡详情 —— 带 user_id 防越权"""
    row = query_one(
        """SELECT uc.count, uc.obtain_time,
                  c.*, p.name AS pool_name
           FROM user_cards uc
           JOIN cards c ON c.id = uc.card_id
           JOIN card_pools p ON p.id = c.pool_id
           WHERE uc.card_id=%s AND uc.user_id=%s""",
        (card_id, current_user["id"])
    )
    if not row:
        raise HTTPException(status_code=404, detail="没有这张卡")
    row["rarity_name"] = _RARITY_NAMES.get(row["rarity"], "?")
    return {"code": 0, "msg": "ok", "data": row}


@router.get("/records")
async def my_records(
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    current_user: dict = Depends(get_current_user),
):
    offset = (page - 1) * size
    rows = query_all(
        """SELECT r.id, r.pool_id, r.draw_type, r.total_cost, r.results_json, r.create_time,
                  p.name AS pool_name
           FROM gacha_records r
           JOIN card_pools p ON p.id = r.pool_id
           WHERE r.user_id=%s
           ORDER BY r.id DESC
           LIMIT %s OFFSET %s""",
        (current_user["id"], size, offset)
    )
    for r in rows:
        r["results_json"] = json.loads(r["results_json"])
    return {"code": 0, "msg": "ok", "data": rows}


# ============== 管理员：卡池配置 ==============
@router.post("/pools")
async def admin_create_pool(body: PoolCreate, current_user: dict = Depends(require_role(2))):
    pid = execute_return_id(
        """INSERT INTO card_pools (name, celebrity_id, description, cost_per_draw, cost_per_ten, is_active, create_time)
           VALUES (%s, %s, %s, %s, %s, %s, %s)""",
        (body.name, body.celebrity_id, body.description, body.cost_per_draw, body.cost_per_ten, body.is_active, datetime.now())
    )
    return {"code": 0, "msg": "卡池创建成功", "data": {"pool_id": pid}}


@router.put("/pools/{pool_id}")
async def admin_update_pool(pool_id: int, body: PoolUpdate, current_user: dict = Depends(require_role(2))):
    pool = query_one("SELECT id FROM card_pools WHERE id=%s", (pool_id,))
    if not pool:
        raise HTTPException(status_code=404, detail="卡池不存在")

    fields = body.model_dump(exclude_none=True)
    invalid = set(fields.keys()) - _POOL_ALLOWED_UPDATE
    if invalid:
        raise HTTPException(status_code=400, detail=f"不允许更新字段: {invalid}")
    if not fields:
        raise HTTPException(status_code=400, detail="没有可更新的字段")

    set_clause = ", ".join(f"{k}=%s" for k in fields.keys())
    args = list(fields.values()) + [pool_id]
    execute(f"UPDATE card_pools SET {set_clause} WHERE id=%s", args)
    return {"code": 0, "msg": "更新成功", "data": None}


@router.post("/cards")
async def admin_create_card(body: CardCreate, current_user: dict = Depends(require_role(2))):
    if body.rarity not in (1, 2, 3, 4):
        raise HTTPException(status_code=400, detail="rarity 只能是 1/2/3/4")

    cid = execute_return_id(
        """INSERT INTO cards (pool_id, celebrity_id, name, image_url, rarity, weight, description, create_time)
           VALUES (%s, %s, %s, %s, %s, %s, %s, %s)""",
        (body.pool_id, body.celebrity_id, body.name, body.image_url, body.rarity, body.weight, body.description, datetime.now())
    )
    return {"code": 0, "msg": "卡片创建成功", "data": {"card_id": cid}}


@router.put("/cards/{card_id}")
async def admin_update_card(card_id: int, body: CardUpdate, current_user: dict = Depends(require_role(2))):
    card = query_one("SELECT id FROM cards WHERE id=%s", (card_id,))
    if not card:
        raise HTTPException(status_code=404, detail="卡片不存在")

    fields = body.model_dump(exclude_none=True)
    invalid = set(fields.keys()) - _CARD_ALLOWED_UPDATE
    if invalid:
        raise HTTPException(status_code=400, detail=f"不允许更新字段: {invalid}")
    if not fields:
        raise HTTPException(status_code=400, detail="没有可更新的字段")

    set_clause = ", ".join(f"{k}=%s" for k in fields.keys())
    args = list(fields.values()) + [card_id]
    execute(f"UPDATE cards SET {set_clause} WHERE id=%s", args)
    return {"code": 0, "msg": "更新成功", "data": None}


@router.delete("/cards/{card_id}")
async def admin_delete_card(card_id: int, current_user: dict = Depends(require_role(2))):
    execute("DELETE FROM cards WHERE id=%s", (card_id,))
    return {"code": 0, "msg": "删除成功", "data": None}

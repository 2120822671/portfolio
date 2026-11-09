"""
recharge.py —— 模拟充值系统
- 三种方式：微信 / 支付宝 / 兑换码
- 微信/支付宝：生成订单 → 模拟支付成功（点"立即支付"即到账）
- 兑换码：输入码后立即到账
"""
import random
import string
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from typing import Optional

from database import query_one, query_all, execute, execute_return_id
from deps import get_current_user, require_role

router = APIRouter(prefix="/api/recharge", tags=["recharge"])


# ============== 预置兑换码（模拟运营发放）==============
# 真实项目应该存数据库做核销，这里做内存字典 + 已使用集合
_VALID_CODES = {
    "STAR1000": 1000,
    "STAR5000": 5000,
    "STAR10000": 10000,
    "STAR_NEW":  2000,  # 新用户礼包
    "LUNA_FAN": 3000,   # Luna粉丝团专属
}
_USED_CODES: set[str] = set()


# ============== 套餐配置（前端也用）==============
RECHARGE_PLANS = [
    {"id": 1, "name": "新手礼包",  "amount": 1000, "price": 10,  "bonus": 0},
    {"id": 2, "name": "经典套餐",  "amount": 3000, "price": 25,  "bonus": 0},
    {"id": 3, "name": "热门套餐",  "amount": 5000, "price": 48,  "bonus": 200},
    {"id": 4, "name": "尊享套餐",  "amount": 10000,"price": 88,  "bonus": 600},
    {"id": 5, "name": "传说套餐",  "amount": 30000,"price": 238, "bonus": 3000},
]


# ============== Schema ==============
class CreateOrderBody(BaseModel):
    plan_id: int        # 套餐 id
    pay_type: int       # 1微信/2支付宝


class SimulatePayBody(BaseModel):
    order_no: str


class RedeemBody(BaseModel):
    code: str


# ============== 工具 ==============
def _gen_order_no() -> str:
    ts = datetime.now().strftime("%Y%m%d%H%M%S")
    rand = "".join(random.choices(string.digits, k=6))
    return f"SD{ts}{rand}"


def _add_score(user_id: int, amount: int, reason: str) -> None:
    """给用户加积分（带日志）"""
    execute("UPDATE users SET score = score + %s WHERE id=%s", (amount, user_id))


# ============== 接口 ==============
@router.get("/plans")
async def get_plans():
    """前端用的套餐列表（纯静态，不需要鉴权）"""
    return {"code": 0, "msg": "ok", "data": RECHARGE_PLANS}


@router.post("/order")
async def create_order(body: CreateOrderBody, current_user: dict = Depends(get_current_user)):
    """创建充值订单"""
    plan = next((p for p in RECHARGE_PLANS if p["id"] == body.plan_id), None)
    if not plan:
        raise HTTPException(status_code=400, detail="套餐不存在")
    if body.pay_type not in (1, 2):
        raise HTTPException(status_code=400, detail="pay_type 只能是 1 或 2")

    order_no = _gen_order_no()
    # amount = 基础 + 赠送
    total = plan["amount"] + plan["bonus"]
    execute_return_id(
        """INSERT INTO recharge_orders (order_no, user_id, amount, pay_type, status, create_time)
           VALUES (%s, %s, %s, %s, 0, %s)""",
        (order_no, current_user["id"], total, body.pay_type, datetime.now())
    )
    pay_names = {1: "微信支付", 2: "支付宝"}
    return {
        "code": 0, "msg": "订单创建成功",
        "data": {
            "order_no": order_no,
            "amount": total,
            "plan_name": plan["name"],
            "pay_name": pay_names[body.pay_type],
            "price": plan["price"],
        }
    }


@router.post("/pay")
async def simulate_pay(body: SimulatePayBody, current_user: dict = Depends(get_current_user)):
    """模拟支付成功 —— 充值到账"""
    order = query_one(
        "SELECT * FROM recharge_orders WHERE order_no=%s AND user_id=%s",
        (body.order_no, current_user["id"])
    )
    if not order:
        raise HTTPException(status_code=404, detail="订单不存在")
    if order["status"] == 1:
        raise HTTPException(status_code=400, detail="订单已支付")
    if order["status"] == 2:
        raise HTTPException(status_code=400, detail="订单已取消")

    # 标记订单已支付 + 给用户加积分
    execute("UPDATE recharge_orders SET status=1, pay_time=%s WHERE id=%s", (datetime.now(), order["id"]))
    _add_score(current_user["id"], order["amount"], "充值到账")

    # 查最新余额（前端不用再额外调 /api/auth/me）
    user_now = query_one("SELECT score FROM users WHERE id=%s", (current_user["id"],))

    return {
        "code": 0, "msg": f"充值成功！到账 {order['amount']} 积分",
        "data": {
            "amount": order["amount"],
            "remain_balance": user_now["score"],
        }
    }


@router.post("/redeem")
async def redeem(body: RedeemBody, current_user: dict = Depends(get_current_user)):
    """兑换码充值"""
    code = body.code.strip().upper()
    if code in _USED_CODES:
        raise HTTPException(status_code=400, detail="兑换码已被使用")
    if code not in _VALID_CODES:
        raise HTTPException(status_code=400, detail="兑换码无效")

    amount = _VALID_CODES[code]
    _USED_CODES.add(code)

    # 写一条订单记录便于追踪
    execute_return_id(
        """INSERT INTO recharge_orders (order_no, user_id, amount, pay_type, pay_code, status, create_time, pay_time)
           VALUES (%s, %s, %s, 3, %s, 1, %s, %s)""",
        (_gen_order_no(), current_user["id"], amount, code, datetime.now(), datetime.now())
    )
    _add_score(current_user["id"], amount, "兑换码到账")
    user_now = query_one("SELECT score FROM users WHERE id=%s", (current_user["id"],))
    return {
        "code": 0, "msg": f"兑换成功！到账 {amount} 积分",
        "data": {"amount": amount, "remain_balance": user_now["score"]}
    }


@router.get("/my-orders")
async def my_orders(
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    current_user: dict = Depends(get_current_user),
):
    """我的充值记录"""
    offset = (page - 1) * size
    rows = query_all(
        """SELECT * FROM recharge_orders
           WHERE user_id=%s
           ORDER BY id DESC
           LIMIT %s OFFSET %s""",
        (current_user["id"], size, offset)
    )
    return {"code": 0, "msg": "ok", "data": rows}


# ============== 管理员：生成兑换码 ==============
@router.post("/admin/gen-code")
async def admin_gen_code(body: dict, current_user: dict = Depends(require_role(2))):
    """管理员生成兑换码（临时：直接往 _VALID_CODES 里加）"""
    amount = body.get("amount", 1000)
    count = body.get("count", 1)
    if amount < 100 or count > 20:
        raise HTTPException(status_code=400, detail="参数不合法")

    new_codes = {}
    for _ in range(count):
        while True:
            c = "SD" + "".join(random.choices(string.ascii_uppercase + string.digits, k=8))
            if c not in _VALID_CODES:
                break
        _VALID_CODES[c] = amount
        new_codes[c] = amount

    return {"code": 0, "msg": f"已生成 {count} 个兑换码", "data": new_codes}

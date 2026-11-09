"""
蛋糕线上商城 —— FastAPI 后端
启动：uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload
"""
from __future__ import annotations
import os, uuid, time, secrets, re, asyncio, datetime
from decimal import Decimal
from hashlib import md5
from typing import Any

from fastapi import FastAPI, Request, HTTPException, Form, UploadFile, File, Path
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware
from starlette.config import Config
from pymysql.cursors import DictCursor
import pymysql

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FRONTEND_STATIC = os.path.join(ROOT, "frontend", "static")
DB_NAME = "cakeshop"
DB_CONFIG = dict(host="localhost", port=3306, user="root", password="123456",
                 charset="utf8mb4", cursorclass=DictCursor)


# ---------- DB ----------
def get_conn():
    conn = pymysql.connect(database=DB_NAME, **DB_CONFIG)
    return conn


def q(sql: str, args=None):
    """只读查询，返回 list[dict]"""
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(sql, args or ())
            return cur.fetchall()
    finally:
        conn.close()


def q_one(sql: str, args=None):
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(sql, args or ())
            return cur.fetchone()
    finally:
        conn.close()


def exec_(sql: str, args=None, autocommit=True):
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(sql, args or ())
            if autocommit:
                conn.commit()
            return cur.lastrowid
    finally:
        if autocommit:
            conn.close()


# ---------- App ----------
app = FastAPI(title="蛋糕线上商城 API")
# session secret
app.add_middleware(
    SessionMiddleware,
    secret_key=secrets.token_urlsafe(32),
    session_cookie="cake_session",
    same_site="lax",
    max_age=86400 * 7,
)

# 静态页面（前端）
app.mount("/static", StaticFiles(directory=os.path.join(ROOT, "frontend", "static")), name="static")


# ---------- Helpers ----------
def ok(**kwargs):
    return {"code": 0, "msg": "ok", **kwargs}


def fail(msg: str, code: int = 1, status_code: int = 400):
    return JSONResponse(status_code=status_code, content={"code": code, "msg": msg})


def hash_pwd(p: str) -> str:
    return md5(p.encode()).hexdigest()


def current_user(request: Request) -> dict | None:
    uid = request.session.get("uid")
    if not uid:
        return None
    u = q_one("SELECT id, username, nickname, phone, role, status FROM user WHERE id=%s", (uid,))
    return u


def must_login(request: Request) -> dict:
    u = current_user(request)
    if not u:
        raise HTTPException(status_code=401, detail="未登录")
    if not u["status"]:
        raise HTTPException(status_code=403, detail="账号已被冻结")
    return u


def must_admin(request: Request) -> dict:
    u = must_login(request)
    if u["role"] != 1:
        raise HTTPException(status_code=403, detail="需要管理员权限")
    return u


def _strip_none(d: dict) -> dict:
    return {k: v for k, v in d.items() if v is not None}


def _public_user(u: dict) -> dict:
    return {k: u.get(k) for k in ("id", "username", "nickname", "phone", "role", "status", "create_time")}


def _serialize(v):
    if isinstance(v, Decimal):
        return float(v)
    if isinstance(v, (datetime.datetime, datetime.date, datetime.time)):
        return v.isoformat(sep=" ") if isinstance(v, datetime.datetime) else v.isoformat()
    if isinstance(v, (bytes, bytearray)):
        return v.decode("utf-8", errors="replace")
    return v


def json_friendly(obj):
    """递归把 datetime/bytes 换掉"""
    if isinstance(obj, dict):
        return {k: json_friendly(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [json_friendly(v) for v in obj]
    return _serialize(obj)


class FF(JSONResponse):
    """Fast-Friendly 响应：自动 json_friendly"""
    def render(self, content: Any) -> bytes:
        return super().render(json_friendly(content))


# ---------- 页面路由 ----------
@app.get("/")
async def index():
    return RedirectResponse(url="/static/index.html")


# ============================================================
#                    用户认证
# ============================================================
@app.post("/api/auth/register")
async def register(body: dict, request: Request):
    username = (body.get("username") or "").strip()
    phone = (body.get("phone") or "").strip()
    password = body.get("password") or ""
    if not username or not phone or not password:
        return fail("用户名/手机号/密码必填")
    if not re.fullmatch(r"\d{11}", phone):
        return fail("手机号格式错误")
    if len(password) < 6:
        return fail("密码至少 6 位")
    exist = q_one("SELECT id FROM user WHERE phone=%s OR username=%s", (phone, username))
    if exist:
        return fail("用户名或手机号已被占用")
    exec_("INSERT INTO user (username, nickname, phone, password) VALUES (%s,%s,%s,%s)",
          (username, username, phone, hash_pwd(password)))
    return ok()


@app.post("/api/auth/login")
async def login(body: dict, request: Request):
    account = (body.get("account") or "").strip()  # 用户名或手机号
    password = body.get("password") or ""
    u = q_one("SELECT * FROM user WHERE username=%s OR phone=%s", (account, account))
    if not u or u["password"] != hash_pwd(password):
        return fail("账号或密码错误")
    if not u["status"]:
        return fail("账号已被冻结")
    request.session["uid"] = u["id"]
    request.session.permanent = True
    return ok(user=_public_user(u))


@app.post("/api/auth/logout")
async def logout(request: Request):
    request.session.pop("uid", None)
    return ok()


@app.get("/api/auth/me")
async def me(request: Request):
    u = current_user(request)
    return ok(user=_public_user(u) if u else None)


@app.post("/api/profile/update")
async def profile_update(body: dict, request: Request):
    """修改昵称/手机号"""
    u = must_login(request)
    nickname = (body.get("nickname") or "").strip()
    phone = (body.get("phone") or "").strip()
    fields, args = [], []
    if nickname:
        fields.append("nickname=%s"); args.append(nickname)
    if phone and phone != u["phone"]:
        if not re.fullmatch(r"\d{11}", phone):
            return fail("手机号格式错误")
        # 检查手机号是否被占用
        if q_one("SELECT id FROM user WHERE phone=%s AND id!=%s", (phone, u["id"])):
            return fail("手机号已被他人使用")
        fields.append("phone=%s"); args.append(phone)
    if not fields:
        return fail("没有需要修改的内容")
    args.append(u["id"])
    exec_(f"UPDATE user SET {','.join(fields)} WHERE id=%s", args)
    return ok()


@app.post("/api/profile/password")
async def profile_password(body: dict, request: Request):
    """修改密码"""
    u = must_login(request)
    old_pwd = body.get("old_password") or ""
    new_pwd = body.get("new_password") or ""
    if len(new_pwd) < 6:
        return fail("新密码至少 6 位")
    cur = q_one("SELECT password FROM user WHERE id=%s", (u["id"],))
    if cur["password"] != hash_pwd(old_pwd):
        return fail("原密码错误")
    exec_("UPDATE user SET password=%s WHERE id=%s", (hash_pwd(new_pwd), u["id"]))
    return ok()


# ============================================================
#                    后台定时任务：自动取消超时未支付订单
# ============================================================
ORDER_EXPIRE_MINUTES = 30  # 超过 30 分钟未支付自动取消


async def _auto_cancel_expired_orders():
    """独立协程：每分钟扫一次，把超过 ORDER_EXPIRE_MINUTES 仍为待支付的订单取消并回补库存"""
    while True:
        try:
            conn = get_conn()
            now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT id, order_no FROM orders
                    WHERE order_status = 0
                      AND create_time < DATE_SUB(NOW(), INTERVAL %s MINUTE)
                """, (ORDER_EXPIRE_MINUTES,))
                expired = cur.fetchall()
                for o in expired:
                    cur.execute("UPDATE orders SET order_status=3 WHERE id=%s AND order_status=0", (o["id"],))
                    cur.execute("SELECT cake_id, buy_num FROM order_item WHERE order_id=%s", (o["id"],))
                    items = cur.fetchall()
                    for it in items:
                        cur.execute("UPDATE cake SET stock = stock + %s WHERE id=%s",
                                    (it["buy_num"], it["cake_id"]))
                if expired:
                    conn.commit()
                    print(f"[定时任务 {now_str}] 自动取消 {len(expired)} 笔超时订单：{[e['order_no'] for e in expired]}")
            conn.close()
        except Exception as e:
            print(f"[定时任务] auto_cancel error: {e}")
        await asyncio.sleep(60)  # 每 60 秒检查一次


@app.on_event("startup")
async def on_startup():
    asyncio.create_task(_auto_cancel_expired_orders())


# ============================================================
#                    分类
# ============================================================
@app.get("/api/category/list")
async def category_list():
    data = q("SELECT * FROM cake_category ORDER BY sort ASC, id ASC")
    return FF(content={"code": 0, "msg": "ok", "data": data})


@app.post("/api/admin/category/add")
async def admin_cat_add(body: dict, request: Request):
    must_admin(request)
    name = (body.get("category_name") or "").strip()
    sort = body.get("sort", 0)
    if not name:
        return fail("分类名必填")
    exec_("INSERT INTO cake_category (category_name, sort) VALUES (%s,%s)", (name, sort))
    return ok()


@app.post("/api/admin/category/update")
async def admin_cat_update(body: dict, request: Request):
    must_admin(request)
    cid = body.get("id")
    if not cid:
        return fail("参数缺失")
    fields = []
    args = []
    if body.get("category_name") is not None:
        fields.append("category_name=%s"); args.append(body["category_name"])
    if body.get("sort") is not None:
        fields.append("sort=%s"); args.append(body["sort"])
    if not fields:
        return fail("无更新内容")
    args.append(cid)
    exec_(f"UPDATE cake_category SET {','.join(fields)} WHERE id=%s", args)
    return ok()


@app.post("/api/admin/category/delete")
async def admin_cat_delete(body: dict, request: Request):
    must_admin(request)
    cid = body.get("id")
    # 有蛋糕的分类不能删
    if q_one("SELECT COUNT(*) AS c FROM cake WHERE category_id=%s", (cid,))["c"] > 0:
        return fail("该分类下还有蛋糕，无法删除")
    exec_("DELETE FROM cake_category WHERE id=%s", (cid,))
    return ok()


# ============================================================
#                    蛋糕
# ============================================================
@app.get("/api/cake/list")
async def cake_list(category_id: int | None = None, keyword: str | None = None,
                    sort_by: str | None = None, page: int = 1, page_size: int = 8):
    where = ["on_shelf=1"]
    args: list[Any] = []
    if category_id:
        where.append("category_id=%s"); args.append(category_id)
    if keyword:
        where.append("cake_name LIKE %s"); args.append(f"%{keyword}%")
    w = " AND ".join(where)
    total = q_one(f"SELECT COUNT(*) AS c FROM cake WHERE {w}", args)["c"]
    order = "id DESC"
    if sort_by == "price_asc": order = "price ASC"
    elif sort_by == "price_desc": order = "price DESC"
    limit = max(0, page - 1) * page_size
    rows = q(f"""
        SELECT c.*, cat.category_name FROM cake c
        LEFT JOIN cake_category cat ON cat.id = c.category_id
        WHERE {w} ORDER BY {order} LIMIT %s,%s
    """, args + [limit, page_size])
    # 用真实图片 URL（本地有就用本地，否则生成占位）
    for r in rows:
        img_path = (r["image"] or "").removeprefix("/static/")
        local = os.path.join(FRONTEND_STATIC, img_path) if img_path else ""
        if not r["image"] or not os.path.exists(local):
            r["image"] = f"https://trae-api-cn.mchost.guru/api/ide/v1/text_to_image?prompt={r['cake_name']} 蛋糕&image_size=square_hd"
    return FF(content={"code": 0, "msg": "ok", "data": {"total": total, "list": rows, "page": page, "page_size": page_size}})


@app.get("/api/cake/{cid}")
async def cake_detail(cid: int, request: Request):
    row = q_one("SELECT * FROM cake WHERE id=%s", (cid,))
    if not row:
        return fail("蛋糕不存在", status_code=404)
    img_path = (row["image"] or "").removeprefix("/static/")
    local = os.path.join(FRONTEND_STATIC, img_path) if img_path else ""
    if not row["image"] or not os.path.exists(local):
        row["image"] = f"https://trae-api-cn.mchost.guru/api/ide/v1/text_to_image?prompt={row['cake_name']} 蛋糕&image_size=square_hd"
    # 评论
    comments = q("""
        SELECT c.id, c.content, c.create_time, u.nickname FROM comment c
        LEFT JOIN user u ON u.id = c.user_id
        WHERE c.cake_id=%s ORDER BY c.id DESC
    """, (cid,))
    # 收藏状态
    faved = False
    u = current_user(request)
    if u:
        faved = bool(q_one("SELECT 1 FROM favorite WHERE user_id=%s AND cake_id=%s", (u["id"], cid)))
    return FF(content={"code": 0, "msg": "ok", "data": {"cake": row, "comments": comments, "faved": faved}})


@app.post("/api/admin/cake/add")
async def admin_cake_add(body: dict, request: Request):
    must_admin(request)
    need = ("cake_name", "price", "stock", "category_id")
    if any(body.get(k) in (None, "") for k in need):
        return fail("字段不完整")
    image = body.get("image") or ""
    spec = body.get("spec") or ""
    exec_("""INSERT INTO cake (cake_name, price, stock, category_id, image, description, spec, on_shelf)
             VALUES (%s,%s,%s,%s,%s,%s,%s,%s)""",
          (body["cake_name"], float(body["price"]), int(body["stock"]), int(body["category_id"]),
           image, body.get("description", ""), spec, int(body.get("on_shelf", 1))))
    return ok()


@app.post("/api/admin/cake/update")
async def admin_cake_update(body: dict, request: Request):
    must_admin(request)
    cid = body.get("id")
    if not cid:
        return fail("参数缺失")
    fields, args = [], []
    for k in ("cake_name", "price", "stock", "category_id", "image", "description", "spec", "on_shelf"):
        if body.get(k) is not None:
            fields.append(f"{k}=%s"); args.append(body[k])
    if not fields:
        return fail("无更新内容")
    args.append(cid)
    exec_(f"UPDATE cake SET {','.join(fields)} WHERE id=%s", args)
    return ok()


@app.post("/api/admin/cake/delete")
async def admin_cake_delete(body: dict, request: Request):
    must_admin(request)
    cid = body.get("id")
    exec_("UPDATE cake SET on_shelf=0 WHERE id=%s", (cid,))
    return ok()


@app.get("/api/admin/cake/list")
async def admin_cake_list(request: Request, keyword: str | None = None, category_id: int | None = None,
                          page: int = 1, page_size: int = 10):
    must_admin(request)
    where = []; args: list[Any] = []
    if keyword:
        where.append("cake_name LIKE %s"); args.append(f"%{keyword}%")
    if category_id:
        where.append("category_id=%s"); args.append(category_id)
    w = (" WHERE " + " AND ".join(where)) if where else ""
    total = q_one(f"SELECT COUNT(*) AS c FROM cake{w}", args)["c"]
    limit = max(0, page - 1) * page_size
    rows = q(f"SELECT c.*, cat.category_name FROM cake c LEFT JOIN cake_category cat ON cat.id=c.category_id"
             f" {w} ORDER BY c.id DESC LIMIT %s,%s", args + [limit, page_size])
    return FF(content={"code": 0, "msg": "ok", "data": {"total": total, "list": rows}})


# ============================================================
#                    购物车 / 收藏
# ============================================================
@app.get("/api/cart/list")
async def cart_list(request: Request):
    u = must_login(request)
    rows = q("""
        SELECT ca.id AS cart_id, ca.buy_num, c.* FROM cart ca
        LEFT JOIN cake c ON c.id = ca.cake_id
        WHERE ca.user_id=%s ORDER BY ca.id DESC
    """, (u["id"],))
    # 过滤下架
    valid = [r for r in rows if r.get("on_shelf")]
    return FF(content={"code": 0, "msg": "ok", "data": valid})


@app.post("/api/cart/add")
async def cart_add(body: dict, request: Request):
    u = must_login(request)
    cid = int(body.get("cake_id", 0))
    num = int(body.get("buy_num", 1))
    if cid <= 0 or num <= 0:
        return fail("参数错误")
    c = q_one("SELECT * FROM cake WHERE id=%s AND on_shelf=1", (cid,))
    if not c:
        return fail("蛋糕不存在或已下架")
    exist = q_one("SELECT id, buy_num FROM cart WHERE user_id=%s AND cake_id=%s", (u["id"], cid))
    if exist:
        exec_("UPDATE cart SET buy_num=%s WHERE id=%s", (exist["buy_num"] + num, exist["id"]))
    else:
        exec_("INSERT INTO cart (user_id, cake_id, buy_num) VALUES (%s,%s,%s)", (u["id"], cid, num))
    return ok()


@app.post("/api/cart/update")
async def cart_update(body: dict, request: Request):
    u = must_login(request)
    cart_id = body.get("cart_id"); num = int(body.get("buy_num", 1))
    if num <= 0:
        return fail("数量错误")
    exec_("UPDATE cart SET buy_num=%s WHERE id=%s AND user_id=%s", (num, cart_id, u["id"]))
    return ok()


@app.post("/api/cart/delete")
async def cart_delete(body: dict, request: Request):
    u = must_login(request)
    exec_("DELETE FROM cart WHERE id=%s AND user_id=%s", (body.get("cart_id"), u["id"]))
    return ok()


@app.get("/api/favorite/list")
async def fav_list(request: Request):
    u = must_login(request)
    rows = q("""SELECT f.id, c.* FROM favorite f
                LEFT JOIN cake c ON c.id=f.cake_id
                WHERE f.user_id=%s ORDER BY f.id DESC""", (u["id"],))
    return FF(content={"code": 0, "msg": "ok", "data": rows})


@app.post("/api/favorite/toggle")
async def fav_toggle(body: dict, request: Request):
    u = must_login(request)
    cid = int(body.get("cake_id", 0))
    exist = q_one("SELECT id FROM favorite WHERE user_id=%s AND cake_id=%s", (u["id"], cid))
    if exist:
        exec_("DELETE FROM favorite WHERE id=%s", (exist["id"],))
        return ok(action="removed")
    exec_("INSERT INTO favorite (user_id, cake_id) VALUES (%s,%s)", (u["id"], cid))
    return ok(action="added")


# ============================================================
#                    收货地址
# ============================================================
@app.get("/api/address/list")
async def address_list(request: Request):
    u = must_login(request)
    rows = q("SELECT * FROM address WHERE user_id=%s ORDER BY is_default DESC, id DESC", (u["id"],))
    return FF(content={"code": 0, "msg": "ok", "data": rows})


@app.post("/api/address/add")
async def address_add(body: dict, request: Request):
    u = must_login(request)
    need = ("receiver_name", "receiver_phone", "address")
    if any(not body.get(k) for k in need):
        return fail("字段不完整")
    is_default = int(body.get("is_default", 0))
    if is_default:
        exec_("UPDATE address SET is_default=0 WHERE user_id=%s", (u["id"],))
    exec_("INSERT INTO address (user_id, receiver_name, receiver_phone, address, is_default) VALUES (%s,%s,%s,%s,%s)",
          (u["id"], body["receiver_name"], body["receiver_phone"], body["address"], is_default))
    return ok()


@app.post("/api/address/update")
async def address_update(body: dict, request: Request):
    u = must_login(request)
    aid = body.get("id")
    fields, args = [], []
    for k in ("receiver_name", "receiver_phone", "address", "is_default"):
        if body.get(k) is not None:
            fields.append(f"{k}=%s"); args.append(body[k])
    if not fields:
        return fail("无更新")
    args.append(aid)
    exec_(f"UPDATE address SET {','.join(fields)} WHERE id=%s AND user_id=%s", args + [u["id"]])
    if body.get("is_default") == 1:
        exec_("UPDATE address SET is_default=0 WHERE user_id=%s AND id!=%s", (u["id"], aid))
    return ok()


@app.post("/api/address/delete")
async def address_delete(body: dict, request: Request):
    u = must_login(request)
    exec_("DELETE FROM address WHERE id=%s AND user_id=%s", (body.get("id"), u["id"]))
    return ok()


# ============================================================
#                    订单（事务 + 防超卖）
# ============================================================
@app.post("/api/order/create")
async def order_create(body: dict, request: Request):
    """body: { cart_ids: [..], address_id 或 receiver_* 三项, remark }"""
    u = must_login(request)
    cart_ids = body.get("cart_ids") or []
    if not cart_ids:
        return fail("请先勾选购物车商品")
    receiver_name = body.get("receiver_name")
    receiver_phone = body.get("receiver_phone")
    receiver_address = body.get("receiver_address")
    address_id = body.get("address_id")
    if address_id and not receiver_address:
        addr = q_one("SELECT * FROM address WHERE id=%s AND user_id=%s", (address_id, u["id"]))
        if not addr:
            return fail("收货地址不存在")
        receiver_name = receiver_name or addr["receiver_name"]
        receiver_phone = receiver_phone or addr["receiver_phone"]
        receiver_address = receiver_address or addr["address"]
    if not receiver_name or not receiver_phone or not receiver_address:
        return fail("收货信息不完整")

    # —— 事务 ——
    conn = get_conn()
    try:
        conn.begin()
        with conn.cursor() as cur:
            # 锁定购物车行 + 蛋糕库存行
            placeholders = ",".join(["%s"] * len(cart_ids))
            cur.execute(f"""
                SELECT ca.id, ca.cake_id, ca.buy_num, c.price, c.stock, c.on_shelf, c.cake_name
                FROM cart ca LEFT JOIN cake c ON c.id = ca.cake_id
                WHERE ca.id IN ({placeholders}) AND ca.user_id=%s
                FOR UPDATE
            """, tuple(cart_ids) + (u["id"],))
            items = cur.fetchall()
            if not items:
                conn.rollback()
                return fail("购物车为空")
            total = 0.0
            details = []
            for it in items:
                if not it["on_shelf"]:
                    conn.rollback()
                    return fail(f"{it['cake_name']} 已下架")
                if it["buy_num"] > it["stock"]:
                    conn.rollback()
                    return fail(f"{it['cake_name']} 库存不足（剩余 {it['stock']}）")
                total += float(it["price"]) * it["buy_num"]
                details.append(it)
            # 扣库存
            for it in details:
                cur.execute("UPDATE cake SET stock = stock - %s WHERE id=%s AND stock >= %s",
                            (it["buy_num"], it["cake_id"], it["buy_num"]))
                if cur.rowcount != 1:
                    conn.rollback()
                    return fail(f"{it['cake_name']} 扣库存失败，请重试")
            # 建订单
            order_no = datetime.datetime.now().strftime("%Y%m%d%H%M%S") + secrets.token_hex(4)
            cur.execute("""INSERT INTO orders
                (order_no, user_id, total_amount, order_status, receiver_name, receiver_phone, receiver_address, remark)
                VALUES (%s,%s,%s,0,%s,%s,%s,%s)""",
                (order_no, u["id"], round(total, 2), receiver_name, receiver_phone, receiver_address, body.get("remark", "")))
            order_id = cur.lastrowid
            for it in details:
                cur.execute("INSERT INTO order_item (order_id, cake_id, buy_num, buy_price) VALUES (%s,%s,%s,%s)",
                            (order_id, it["cake_id"], it["buy_num"], it["price"]))
            # 清购物车
            cur.execute(f"DELETE FROM cart WHERE id IN ({placeholders}) AND user_id=%s",
                        tuple(cart_ids) + (u["id"],))
        conn.commit()
        return ok(order_no=order_no, total=round(total, 2))
    except Exception as e:
        conn.rollback()
        return fail(f"下单失败：{e}")
    finally:
        conn.close()


@app.get("/api/order/list")
async def order_list(request: Request, status: int | None = None):
    u = must_login(request)
    where = ["user_id=%s"]; args: list[Any] = [u["id"]]
    if status is not None:
        where.append("order_status=%s"); args.append(int(status))
    w = " AND ".join(where)
    rows = q(f"SELECT * FROM orders WHERE {w} ORDER BY id DESC", args)
    # 每条订单带明细
    for r in rows:
        r["items"] = q("""SELECT oi.*, c.cake_name FROM order_item oi
                           LEFT JOIN cake c ON c.id=oi.cake_id WHERE oi.order_id=%s""", (r["id"],))
    return FF(content={"code": 0, "msg": "ok", "data": rows})


@app.post("/api/order/pay")
async def order_pay(body: dict, request: Request):
    """模拟支付"""
    u = must_login(request)
    order_no = body.get("order_no")
    o = q_one("SELECT * FROM orders WHERE order_no=%s AND user_id=%s", (order_no, u["id"]))
    if not o:
        return fail("订单不存在")
    if o["order_status"] != 0:
        return fail("当前状态不可支付")
    exec_("UPDATE orders SET order_status=1 WHERE order_no=%s AND order_status=0", (order_no,))
    return ok()


@app.post("/api/order/confirm")
async def order_confirm(body: dict, request: Request):
    u = must_login(request)
    exec_("UPDATE orders SET order_status=2 WHERE order_no=%s AND user_id=%s AND order_status=1",
          (body.get("order_no"), u["id"]))
    return ok()


@app.post("/api/order/cancel")
async def order_cancel(body: dict, request: Request):
    """取消待支付订单，并回补库存"""
    u = must_login(request)
    order_no = body.get("order_no")
    o = q_one("SELECT * FROM orders WHERE order_no=%s AND user_id=%s", (order_no, u["id"]))
    if not o:
        return fail("订单不存在")
    if o["order_status"] not in (0, 1):
        return fail("当前状态不可取消")
    conn = get_conn()
    try:
        conn.begin()
        with conn.cursor() as cur:
            cur.execute("UPDATE orders SET order_status=3 WHERE order_no=%s AND order_status IN (0,1)", (order_no,))
            items = cur.execute("SELECT cake_id, buy_num FROM order_item WHERE order_id=%s", (o["id"],)) or cur.fetchall()
            for it in items:
                cur.execute("UPDATE cake SET stock = stock + %s WHERE id=%s", (it["buy_num"], it["cake_id"]))
        conn.commit()
    finally:
        conn.close()
    return ok()


# ============================================================
#                    评价
# ============================================================
@app.post("/api/comment/add")
async def comment_add(body: dict, request: Request):
    u = must_login(request)
    cake_id = int(body.get("cake_id", 0))
    content = (body.get("content") or "").strip()
    order_no = body.get("order_no")  # 可选：强制只对已完成订单评价
    if not cake_id or not content:
        return fail("参数不完整")
    if order_no:
        o = q_one("SELECT * FROM orders WHERE order_no=%s AND user_id=%s AND order_status=2", (order_no, u["id"]))
        if not o:
            return fail("只有已完成订单才能评价")
        already = q_one("SELECT id FROM comment WHERE user_id=%s AND cake_id=%s", (u["id"], cake_id))
        if already:
            return fail("已评价过此蛋糕")
    exec_("INSERT INTO comment (user_id, cake_id, content) VALUES (%s,%s,%s)", (u["id"], cake_id, content))
    return ok()


# ============================================================
#                    管理员
# ============================================================
@app.get("/api/admin/user/list")
async def admin_user_list(request: Request, keyword: str | None = None, page: int = 1, page_size: int = 10):
    must_admin(request)
    where = []; args: list[Any] = []
    if keyword:
        where.append("(username LIKE %s OR phone LIKE %s OR nickname LIKE %s)")
        args += [f"%{keyword}%"] * 3
    w = (" WHERE " + " AND ".join(where)) if where else ""
    total = q_one(f"SELECT COUNT(*) AS c FROM user{w}", args)["c"]
    limit = max(0, page - 1) * page_size
    rows = q(f"SELECT id, username, nickname, phone, role, status, create_time FROM user{w} ORDER BY id DESC LIMIT %s,%s",
             args + [limit, page_size])
    return FF(content={"code": 0, "msg": "ok", "data": {"total": total, "list": rows}})


@app.post("/api/admin/user/status")
async def admin_user_status(body: dict, request: Request):
    must_admin(request)
    if body.get("id") == request.session.get("uid"):
        return fail("不能冻结自己")
    exec_("UPDATE user SET status=%s WHERE id=%s", (int(body.get("status", 1)), body.get("id")))
    return ok()


@app.get("/api/admin/order/list")
async def admin_order_list(request: Request, status: int | None = None, keyword: str | None = None,
                           page: int = 1, page_size: int = 10):
    must_admin(request)
    where = []; args: list[Any] = []
    if status is not None:
        where.append("order_status=%s"); args.append(int(status))
    if keyword:
        where.append("(order_no LIKE %s OR receiver_phone LIKE %s OR receiver_name LIKE %s)")
        args += [f"%{keyword}%"] * 3
    w = (" WHERE " + " AND ".join(where)) if where else ""
    total = q_one(f"SELECT COUNT(*) AS c FROM orders{w}", args)["c"]
    limit = max(0, page - 1) * page_size
    rows = q(f"SELECT o.*, u.username FROM orders o LEFT JOIN user u ON u.id=o.user_id{w}"
             f" ORDER BY o.id DESC LIMIT %s,%s", args + [limit, page_size])
    for r in rows:
        r["items"] = q("""SELECT oi.*, c.cake_name FROM order_item oi
                           LEFT JOIN cake c ON c.id=oi.cake_id WHERE oi.order_id=%s""", (r["id"],))
    return FF(content={"code": 0, "msg": "ok", "data": {"total": total, "list": rows}})


@app.post("/api/admin/order/status")
async def admin_order_status(body: dict, request: Request):
    must_admin(request)
    order_no = body.get("order_no")
    status = int(body.get("order_status", 0))
    exec_("UPDATE orders SET order_status=%s WHERE order_no=%s", (status, order_no))
    return ok()


@app.get("/api/admin/comment/list")
async def admin_comment_list(request: Request, page: int = 1, page_size: int = 10):
    must_admin(request)
    total = q_one("SELECT COUNT(*) AS c FROM comment")["c"]
    limit = max(0, page - 1) * page_size
    rows = q("""SELECT c.*, u.nickname, ck.cake_name FROM comment c
                LEFT JOIN user u ON u.id=c.user_id
                LEFT JOIN cake ck ON ck.id=c.cake_id
                ORDER BY c.id DESC LIMIT %s,%s""", (limit, page_size))
    return FF(content={"code": 0, "msg": "ok", "data": {"total": total, "list": rows}})


@app.post("/api/admin/comment/delete")
async def admin_comment_delete(body: dict, request: Request):
    must_admin(request)
    exec_("DELETE FROM comment WHERE id=%s", (body.get("id"),))
    return ok()


@app.get("/api/admin/stats")
async def admin_stats(request: Request):
    must_admin(request)
    users = q_one("SELECT COUNT(*) AS c FROM user")["c"]
    cakes = q_one("SELECT COUNT(*) AS c FROM cake WHERE on_shelf=1")["c"]
    orders = q_one("SELECT COUNT(*) AS c FROM orders")["c"]
    amount = q_one("SELECT IFNULL(SUM(total_amount),0) AS t FROM orders WHERE order_status=2")["t"]
    return ok(users=users, cakes=cakes, orders=orders, amount=float(amount))


# ============================================================
#                    错误兜底
# ============================================================
@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    return JSONResponse(status_code=exc.status_code, content={"code": exc.status_code, "msg": exc.detail})


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("backend.main:app", host="0.0.0.0", port=8000, reload=True)

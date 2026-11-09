"""
建库建表 + 样例数据 + 下载真实蛋糕图
运行：python backend/db/init_db.py
"""
import os, ssl, urllib.request
import pymysql
from pymysql.cursors import DictCursor
from hashlib import md5

DB_CONFIG = dict(host="localhost", port=3306, user="root", password="123456", charset="utf8mb4")
DB_NAME = "cakeshop"

# 6 张 Unsplash 真实蛋糕图（下载到 frontend/static/images/）
IMG_URLS = {
    1: "https://images.unsplash.com/photo-1565958011703-44f9829ba187?w=600&q=80&auto=format",
    2: "https://images.unsplash.com/photo-1578985545062-69928b1d9587?w=600&q=80&auto=format",
    3: "https://images.unsplash.com/photo-1488477181946-6428a0291777?w=600&q=80&auto=format",
    4: "https://images.unsplash.com/photo-1464195244916-405fa0a82545?w=600&q=80&auto=format",
    5: "https://images.unsplash.com/photo-1533134242443-d4fd215305ad?w=600&q=80&auto=format",
    6: "https://images.unsplash.com/photo-1558961363-fa8fdf82db35?w=600&q=80&auto=format",
}

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
IMG_DIR = os.path.join(ROOT, "frontend", "static", "images")


def get_conn(db=None):
    cfg = dict(DB_CONFIG)
    if db:
        cfg["database"] = db
    cfg["cursorclass"] = DictCursor
    return pymysql.connect(**cfg)


def download_images():
    os.makedirs(IMG_DIR, exist_ok=True)
    for cid, url in IMG_URLS.items():
        dst = os.path.join(IMG_DIR, f"cake{cid}.jpg")
        if os.path.exists(dst) and os.path.getsize(dst) > 3000:
            print(f"  已有 cake{cid}.jpg，跳过")
            continue
        print(f"  下载 cake{cid} ...")
        try:
            ctx = ssl._create_unverified_context()
            with urllib.request.urlopen(url, context=ctx, timeout=15) as r, open(dst, "wb") as f:
                f.write(r.read())
            if os.path.getsize(dst) > 3000:
                print(f"    ✅ OK {os.path.getsize(dst)}B")
            else:
                os.remove(dst)
                print(f"    ⚠️ 文件过小，丢弃")
        except Exception as e:
            print(f"    ❌ {e}")


def init():
    # 1. 建库
    conn = get_conn()
    with conn.cursor() as cur:
        cur.execute(f"CREATE DATABASE IF NOT EXISTS `{DB_NAME}` DEFAULT CHARSET utf8mb4 COLLATE utf8mb4_general_ci")
    conn.close()

    conn = get_conn(DB_NAME)

    # 2. 建表（与 schema.sql 保持一致）
    tables = [
        """CREATE TABLE IF NOT EXISTS `user` (
            `id` int(11) NOT NULL AUTO_INCREMENT COMMENT '用户ID',
            `username` varchar(50) NOT NULL COMMENT '用户名',
            `nickname` varchar(50) DEFAULT NULL COMMENT '昵称',
            `phone` varchar(20) NOT NULL COMMENT '手机号',
            `password` varchar(100) NOT NULL COMMENT '密码',
            `role` tinyint NOT NULL DEFAULT 0 COMMENT '0顾客 1管理员',
            `status` tinyint NOT NULL DEFAULT 1 COMMENT '1正常 0冻结',
            `create_time` datetime DEFAULT current_timestamp() COMMENT '注册时间',
            PRIMARY KEY (`id`), UNIQUE KEY `phone` (`phone`)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='用户表'""",
        """CREATE TABLE IF NOT EXISTS `address` (
            `id` int(11) NOT NULL AUTO_INCREMENT,
            `user_id` int(11) NOT NULL,
            `receiver_name` varchar(50) NOT NULL,
            `receiver_phone` varchar(20) NOT NULL,
            `address` varchar(255) NOT NULL,
            `is_default` tinyint NOT NULL DEFAULT 0,
            PRIMARY KEY (`id`), KEY `user_id` (`user_id`)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='收货地址表'""",
        """CREATE TABLE IF NOT EXISTS `cake_category` (
            `id` int(11) NOT NULL AUTO_INCREMENT,
            `category_name` varchar(50) NOT NULL,
            `sort` int(11) DEFAULT 0,
            PRIMARY KEY (`id`)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='蛋糕分类表'""",
        """CREATE TABLE IF NOT EXISTS `cake` (
            `id` int(11) NOT NULL AUTO_INCREMENT COMMENT '蛋糕ID',
            `cake_name` varchar(100) NOT NULL COMMENT '蛋糕名称',
            `price` decimal(10,2) NOT NULL COMMENT '售价',
            `stock` int(11) DEFAULT 0 COMMENT '库存数量',
            `category_id` int(11) NOT NULL COMMENT '所属分类ID',
            `image` varchar(255) DEFAULT NULL COMMENT '商品图片',
            `description` text DEFAULT NULL COMMENT '蛋糕描述',
            `spec` varchar(255) DEFAULT NULL COMMENT '可选规格',
            `on_shelf` tinyint NOT NULL DEFAULT 1 COMMENT '1上架 0下架',
            `create_time` datetime DEFAULT current_timestamp() COMMENT '上架时间',
            PRIMARY KEY (`id`), KEY `category_id` (`category_id`)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='蛋糕商品表'""",
        """CREATE TABLE IF NOT EXISTS `favorite` (
            `id` int(11) NOT NULL AUTO_INCREMENT,
            `user_id` int(11) NOT NULL,
            `cake_id` int(11) NOT NULL,
            `create_time` datetime DEFAULT current_timestamp(),
            PRIMARY KEY (`id`), UNIQUE KEY `uk_user_cake` (`user_id`,`cake_id`)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='收藏表'""",
        """CREATE TABLE IF NOT EXISTS `cart` (
            `id` int(11) NOT NULL AUTO_INCREMENT,
            `user_id` int(11) NOT NULL,
            `cake_id` int(11) NOT NULL,
            `buy_num` int(11) NOT NULL DEFAULT 1,
            PRIMARY KEY (`id`), UNIQUE KEY `uk_user_cake` (`user_id`,`cake_id`)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='购物车表'""",
        """CREATE TABLE IF NOT EXISTS `orders` (
            `id` int(11) NOT NULL AUTO_INCREMENT COMMENT '订单ID',
            `order_no` varchar(32) NOT NULL COMMENT '订单号',
            `user_id` int(11) NOT NULL COMMENT '下单用户ID',
            `total_amount` decimal(10,2) NOT NULL COMMENT '订单总金额',
            `order_status` tinyint DEFAULT 0 COMMENT '0待支付 1待配送 2已完成 3已取消',
            `receiver_name` varchar(50) DEFAULT NULL,
            `receiver_phone` varchar(20) DEFAULT NULL,
            `receiver_address` varchar(255) NOT NULL COMMENT '收货地址',
            `remark` varchar(255) DEFAULT NULL COMMENT '备注',
            `create_time` datetime DEFAULT current_timestamp(),
            PRIMARY KEY (`id`), UNIQUE KEY `order_no` (`order_no`), KEY `user_id` (`user_id`)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='订单表'""",
        """CREATE TABLE IF NOT EXISTS `order_item` (
            `id` int(11) NOT NULL AUTO_INCREMENT COMMENT '明细ID',
            `order_id` int(11) NOT NULL COMMENT '订单ID',
            `cake_id` int(11) NOT NULL COMMENT '蛋糕ID',
            `buy_num` int(11) NOT NULL COMMENT '购买数量',
            `buy_price` decimal(10,2) NOT NULL COMMENT '下单时单价',
            PRIMARY KEY (`id`), KEY `order_id` (`order_id`), KEY `cake_id` (`cake_id`)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='订单明细表'""",
        """CREATE TABLE IF NOT EXISTS `comment` (
            `id` int(11) NOT NULL AUTO_INCREMENT COMMENT '评论ID',
            `user_id` int(11) NOT NULL COMMENT '评论用户ID',
            `cake_id` int(11) NOT NULL COMMENT '评论的蛋糕ID',
            `content` text NOT NULL COMMENT '评论内容',
            `create_time` datetime DEFAULT current_timestamp(),
            PRIMARY KEY (`id`), KEY `user_id` (`user_id`), KEY `cake_id` (`cake_id`)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='商品评论表'""",
    ]
    with conn.cursor() as cur:
        for sql in tables:
            if sql.strip(): cur.execute(sql)
    conn.commit()

    # 3. 样例数据
    def pw(p): return md5(p.encode()).hexdigest()

    with conn.cursor() as cur:
        cur.execute("SELECT COUNT(*) AS c FROM user")
        if cur.fetchone()["c"] == 0:
            cur.executemany(
                "INSERT INTO user (username, nickname, phone, password, role) VALUES (%s,%s,%s,%s,%s)",
                [("admin", "店主小明", "13800000000", pw("123456"), 1),
                 ("lily", "莉莉", "13900000001", pw("123456"), 0),
                 ("tom", "汤姆", "13900000002", pw("123456"), 0)])
        cur.execute("SELECT COUNT(*) AS c FROM cake_category")
        if cur.fetchone()["c"] == 0:
            cur.executemany(
                "INSERT INTO cake_category (category_name, sort) VALUES (%s,%s)",
                [("生日蛋糕", 1), ("慕斯小蛋糕", 2), ("千层蛋糕", 3), ("芝士蛋糕", 4), ("甜品点心", 5)])
        cur.execute("SELECT COUNT(*) AS c FROM cake")
        if cur.fetchone()["c"] == 0:
            cur.executemany(
                "INSERT INTO cake (cake_name, price, stock, category_id, image, description, spec, on_shelf) VALUES (%s,%s,%s,%s,%s,%s,%s,%s)",
                [("草莓鲜奶生日蛋糕 8寸", 168.00, 50, 1, "/static/images/cake1.jpg", "新鲜草莓+进口动物奶油，香甜不腻。", "8寸/10寸/12寸", 1),
                 ("黑森林巧克力蛋糕", 198.00, 30, 1, "/static/images/cake2.jpg", "比利时黑巧+樱桃酒，经典德国风味。", "8寸/10寸", 1),
                 ("芒果慕斯小蛋糕", 38.00, 100, 2, "/static/images/cake3.jpg", "下午茶首选，轻盈口感。", "单只/6只装", 1),
                 ("提拉米苏千层", 228.00, 20, 3, "/static/images/cake4.jpg", "意式浓缩+马斯卡彭芝士。", "8寸", 1),
                 ("巴斯克芝士蛋糕", 158.00, 25, 4, "/static/images/cake5.jpg", "焦香表面+内心流心。", "6寸/8寸", 1),
                 ("手工曲奇礼盒装", 68.00, 200, 5, "/static/images/cake6.jpg", "黄油、抹茶、巧克力三种口味。", "250g/500g", 1)])
        conn.commit()
    conn.close()

    # 4. 下载/检查图片
    print("\n📷 检查蛋糕图片...")
    download_images()

    # 5. 把图片路径写进 DB（避免 init_db 跑第二次跳过样例数据时漏了 image 字段）
    conn = get_conn(DB_NAME)
    with conn.cursor() as cur:
        for cid in IMG_URLS:
            dst = os.path.join(IMG_DIR, f"cake{cid}.jpg")
            if os.path.exists(dst) and os.path.getsize(dst) > 3000:
                cur.execute("UPDATE cake SET image=%s WHERE id=%s AND image IS NULL", (f"/static/images/cake{cid}.jpg", cid))
        conn.commit()
    conn.close()

    print("\n✅ cakeshop 数据库初始化完成")


if __name__ == "__main__":
    init()

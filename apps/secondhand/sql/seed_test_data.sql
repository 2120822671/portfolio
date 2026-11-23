-- ============================================================
-- 校园二手交易平台 · 测试数据脚本（含真实商品图片）
-- 执行方式：
--   mysql --default-character-set=utf8mb4 -u root -p campus_secondhand < seed_test_data.sql
-- 说明：
--   1) 本脚本会先清空商品/图片/点赞/留言/用户/分类等业务表，重建自增ID，便于反复执行；
--   2) 商品图片存放于 static/uploads/，URL 以 /static/uploads/ 开头，与 upload 接口返回格式一致；
--   3) 图片均为 Pexels 免费授权真实照片（Pexels License，可免费用于商业用途）；
--   4) 用户密码统一为 test123（bcrypt 加密存储），可直接用于登录测试。
-- ============================================================

USE campus_secondhand;

-- ---------- 0. 清空旧数据（重置自增ID，保证脚本可重复执行） ----------
SET FOREIGN_KEY_CHECKS = 0;
TRUNCATE TABLE goods_message;
TRUNCATE TABLE goods_like;
TRUNCATE TABLE goods_image;
TRUNCATE TABLE goods;
TRUNCATE TABLE `user`;
TRUNCATE TABLE category;
SET FOREIGN_KEY_CHECKS = 1;

-- ---------- 1. 用户（卖家 / 买家） ----------
INSERT INTO `user` (id, username, password, nickname, phone, avatar, credit_score, status, created_at, updated_at) VALUES
(1, 'linxiaoyu', '$2b$12$21gbevvvO/MDfc1X6vOv9OdhjQwMTMGRrRlwexparQt0MOSut.2uK', '林小雨', '13800001111', NULL, 98,  1, '2026-09-02 09:15:00', '2026-09-02 09:15:00'),
(2, 'chenmo',    '$2b$12$9.reUP06gjI44HC7n6nr4O7PPjOzArZoQ3jTrbVfNXoRkFflnuvRC', '陈默',   '13800002222', NULL, 95,  1, '2026-09-05 14:30:00', '2026-09-05 14:30:00'),
(3, 'wangzhe',   '$2b$12$uWIl9LUmkQ3unVB8nVg7ZuLlkfNYyLTDqyPyiw3jw0F9HA1x9h0VK', '王喆',   '13800003333', NULL, 100, 1, '2026-09-11 20:05:00', '2026-09-11 20:05:00'),
(4, 'sujing',    '$2b$12$3VZEzMByO3owi/c26pYIoeeA9eAH.L2BGHUX8HQ44w7QAbH13LfRW', '苏静',   '13800004444', NULL, 92,  1, '2026-09-18 11:40:00', '2026-09-18 11:40:00'),
(5, 'zhouting',  '$2b$12$21gbevvvO/MDfc1X6vOv9OdhjQwMTMGRrRlwexparQt0MOSut.2uK', '周婷',   '13800005555', NULL, 100, 1, '2026-10-03 16:20:00', '2026-10-03 16:20:00'),
(6, 'hejun',     '$2b$12$9.reUP06gjI44HC7n6nr4O7PPjOzArZoQ3jTrbVfNXoRkFflnuvRC', '何俊',   '13800006666', NULL, 88,  1, '2026-10-21 08:50:00', '2026-10-21 08:50:00');

-- ---------- 2. 商品分类 ----------
INSERT INTO category (id, name, icon, sort_order, created_at) VALUES
(1, '数码电子', NULL, 1, '2026-09-01 10:00:00'),
(2, '教材书籍', NULL, 2, '2026-09-01 10:00:00'),
(3, '宿舍家居', NULL, 3, '2026-09-01 10:00:00'),
(4, '运动户外', NULL, 4, '2026-09-01 10:00:00'),
(5, '乐器文娱', NULL, 5, '2026-09-01 10:00:00'),
(6, '生活用品', NULL, 6, '2026-09-01 10:00:00');

-- ---------- 3. 商品 ----------
-- status: 1在售 2已售出 3已下架；favorite_count 与 goods_like 记录数保持一致
INSERT INTO goods
(id, title, description, price, original_price, cover_image, location, contact, status, stock,
 view_count, like_count, favorite_count, seller_id, category_id, created_at, updated_at) VALUES
(1, 'iPhone 13 128G 蓝色 国行 电池健康89%',
 '2023年入学时买的，一直贴膜带壳使用，机身无磕碰，只有边框轻微使用痕迹。电池健康度89%，功能全部正常，无维修无拆修。附原装数据线和非原装充电头，可当面验机。',
 2499.00, 5999.00, '/static/uploads/goods_iphone13_1.jpg', '三号宿舍楼下', '微信 lxy2024', 1, 1,
 328, 4, 4, 1, 1, '2026-11-10 19:22:00', '2026-11-10 19:22:00'),

(2, 'MacBook Air 13寸 2019款 i5/8G/256G',
 '自用办公本，日常写论文、做PPT完全够用。键盘无油光，屏幕无坏点，电池循环312次。附原装充电器和内胆包。毕业换代出，诚心要可小刀。',
 3200.00, 7999.00, '/static/uploads/goods_macbook_1.jpg', '图书馆一楼大厅', 'QQ 88223344', 1, 1,
 256, 3, 3, 2, 1, '2026-11-11 15:08:00', '2026-11-11 15:08:00'),

(3, '复古机械键盘 87键 灰白配色 茶轴',
 '自己组装的客制化键盘，灰白复古配色，茶轴手感清脆不吵，适合宿舍和图书馆使用。带键盘线和拔键器，键帽无打油。',
 189.00, 399.00, '/static/uploads/goods_keyboard_1.jpg', '二号宿舍楼下', '微信 wz_keyboard', 1, 2,
 142, 5, 5, 3, 1, '2026-11-12 10:35:00', '2026-11-12 10:35:00'),

(4, '捷安特山地自行车 27速 铝合金车架',
 '大二买的通勤车，平时上下课骑，保养得很好，变速顺畅刹车灵敏。车架有正常使用划痕不影响使用。送车锁和打气筒。',
 680.00, 1580.00, '/static/uploads/goods_bike_1.jpg', '西区车棚', '微信 cm_bike', 1, 1,
 198, 2, 2, 2, 4, '2026-11-08 16:45:00', '2026-11-08 16:45:00'),

(5, '民谣木吉他 41寸 云杉面单 带琴包',
 '大一开始学的，现在忙着实习没时间弹了。云杉面单音色明亮，琴颈平直无打品。附原装琴包、变调夹、备用琴弦和拨片。',
 350.00, 899.00, '/static/uploads/goods_guitar_1.jpg', '艺术楼门口', '微信 sj_guitar', 1, 1,
 87, 3, 3, 4, 5, '2026-11-13 21:10:00', '2026-11-13 21:10:00'),

(6, '护眼LED台灯 三档调光 可折叠',
 '宿舍用了一学期，三档亮度可调，光线柔和不刺眼，可折叠收纳不占地方。USB 供电，搬家出。',
 45.00, 129.00, '/static/uploads/goods_lamp_1.jpg', '三号宿舍楼下', '微信 lxy2024', 1, 3,
 65, 1, 1, 1, 3, '2026-11-14 08:30:00', '2026-11-14 08:30:00'),

(7, '考研数学全套教材（4本）九成新',
 '考研上岸了，教材用不上了。高数、线代、概率论加真题解析共4本，只有前两章有少量铅笔笔记，其余全新。',
 60.00, 210.00, '/static/uploads/goods_books_1.jpg', '图书馆三楼', '微信 sj_book', 2, 1,
 210, 6, 6, 4, 2, '2026-10-28 13:05:00', '2026-11-09 10:12:00'),

(8, 'SONY 便携蓝牙音箱 SRS-XB12',
 '音质在这个价位没得说，低音很足，防水可户外用。买来听歌用的，现在换了大音箱，闲置出。',
 199.00, 499.00, '/static/uploads/goods_speaker_1.jpg', '二号宿舍楼下', '微信 wz_audio', 3, 1,
 43, 2, 2, 3, 1, '2026-11-05 17:55:00', '2026-11-15 09:20:00');

-- ---------- 4. 商品图片（多图，与 goods_image 一对多） ----------
INSERT INTO goods_image (id, goods_id, url, created_at) VALUES
(1,  1, '/static/uploads/goods_iphone13_1.jpg', '2026-11-10 19:22:00'),
(2,  1, '/static/uploads/goods_iphone13_2.jpg', '2026-11-10 19:22:00'),
(3,  2, '/static/uploads/goods_macbook_1.jpg',  '2026-11-11 15:08:00'),
(4,  2, '/static/uploads/goods_macbook_2.jpg',  '2026-11-11 15:08:00'),
(5,  3, '/static/uploads/goods_keyboard_1.jpg', '2026-11-12 10:35:00'),
(6,  3, '/static/uploads/goods_keyboard_2.jpg', '2026-11-12 10:35:00'),
(7,  4, '/static/uploads/goods_bike_1.jpg',     '2026-11-08 16:45:00'),
(8,  5, '/static/uploads/goods_guitar_1.jpg',   '2026-11-13 21:10:00'),
(9,  6, '/static/uploads/goods_lamp_1.jpg',     '2026-11-14 08:30:00'),
(10, 7, '/static/uploads/goods_books_1.jpg',    '2026-10-28 13:05:00'),
(11, 7, '/static/uploads/goods_books_2.jpg',    '2026-10-28 13:05:00'),
(12, 8, '/static/uploads/goods_speaker_1.jpg',  '2026-11-05 17:55:00');

-- ---------- 5. 点赞/收藏记录（goods_like 是 favorite_count 的统计来源） ----------
INSERT INTO goods_like (goods_id, user_id, created_at) VALUES
-- 商品1：4 条
(1, 2, '2026-11-10 20:01:00'),
(1, 3, '2026-11-11 09:12:00'),
(1, 4, '2026-11-11 19:40:00'),
(1, 5, '2026-11-12 08:22:00'),
-- 商品2：3 条
(2, 1, '2026-11-11 16:30:00'),
(2, 3, '2026-11-12 11:05:00'),
(2, 6, '2026-11-13 14:48:00'),
-- 商品3：5 条
(3, 1, '2026-11-12 12:10:00'),
(3, 2, '2026-11-12 18:25:00'),
(3, 4, '2026-11-13 09:33:00'),
(3, 5, '2026-11-13 20:15:00'),
(3, 6, '2026-11-14 10:05:00'),
-- 商品4：2 条
(4, 3, '2026-11-09 08:40:00'),
(4, 6, '2026-11-10 17:12:00'),
-- 商品5：3 条
(5, 2, '2026-11-14 09:18:00'),
(5, 5, '2026-11-14 21:30:00'),
(5, 6, '2026-11-15 11:02:00'),
-- 商品6：1 条
(6, 3, '2026-11-14 12:45:00'),
-- 商品7：6 条
(7, 1, '2026-10-29 09:10:00'),
(7, 2, '2026-10-30 14:22:00'),
(7, 3, '2026-11-01 10:38:00'),
(7, 4, '2026-11-02 19:05:00'),
(7, 5, '2026-11-03 08:47:00'),
(7, 6, '2026-11-05 15:26:00'),
-- 商品8：2 条
(8, 4, '2026-11-06 10:14:00'),
(8, 5, '2026-11-07 16:52:00');

-- ---------- 6. 商品留言 ----------
INSERT INTO goods_message (goods_id, user_id, content, created_at) VALUES
(1, 3, '手机还在保修期内吗？发票还在不在？', '2026-11-11 09:15:00'),
(1, 5, '2400 能出吗？我今天就能去拿', '2026-11-12 08:25:00'),
(2, 1, '能拍个开机和键盘的视频看看吗？', '2026-11-11 16:35:00'),
(4, 6, '车架是多大尺寸的？我身高178合适吗', '2026-11-10 17:20:00'),
(7, 2, '书里有笔记吗？不影响看的话我要了', '2026-10-30 14:30:00');

-- ---------- 7. 数据校验 ----------
SELECT '用户' AS 表名, COUNT(*) AS 记录数 FROM `user`
UNION ALL SELECT '分类', COUNT(*) FROM category
UNION ALL SELECT '商品', COUNT(*) FROM goods
UNION ALL SELECT '商品图片', COUNT(*) FROM goods_image
UNION ALL SELECT '点赞', COUNT(*) FROM goods_like
UNION ALL SELECT '留言', COUNT(*) FROM goods_message;

-- 校验 favorite_count 与 goods_like 实际统计是否一致（应全部为 0 行）
SELECT g.id, g.title, g.favorite_count, COUNT(gl.id) AS 实际收藏数
FROM goods g LEFT JOIN goods_like gl ON gl.goods_id = g.id
GROUP BY g.id, g.title, g.favorite_count
HAVING g.favorite_count <> COUNT(gl.id);

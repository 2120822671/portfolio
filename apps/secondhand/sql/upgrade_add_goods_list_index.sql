-- 增量新增：商品列表查询复合索引（只加索引，不改表结构、不改任何 Python 业务代码）
-- 目标查询形态：where status = 在售 and school_id = ? order by created_at desc
--
-- 【与工程实际的偏差说明】
-- 1) 本工程 goods 表当前没有 school_id 列（现有列：见 SHOW COLUMNS FROM goods），
--    因此无法创建含 school_id 的复合索引，否则 DDL 会直接报 Unknown column。
-- 2) list_goods 的默认 newest 排序实际用 Goods.id.desc()，按 created_at 排序需显式传 sort=newest
--    之外的口径；但 status 过滤 + created_at 时间范围统计（/stats today_new）确实存在。
-- 3) 因此先落地 (status, created_at) 复合索引：覆盖 status 等值过滤 + created_at 范围/排序，
--    同时兼容现有 idx_goods_status / idx_goods_created 单列索引场景，无需删除旧索引。
--
-- 【若后续真的引入 school_id 字段】
-- 需先由业务侧新增列（本脚本不涉及），再补建：
--   CREATE INDEX idx_goods_school_status_created ON goods(school_id, status, created_at);

-- 复合索引：status 等值 + created_at 排序/范围，最左前缀可复用 status 单列查询
CREATE INDEX idx_goods_status_created ON goods(status, created_at);

-- ============================================================
-- 增量迁移：为 goods 表新增 favorite_count（收藏数）字段
-- 用途：商品收藏统计补偿接口 POST /api/v1/products/favorite-sync
-- 说明：本脚本为增量脚本，不修改原有 create_tables.sql
-- 执行：mysql -u root -p campus_secondhand < upgrade_add_favorite_count.sql
-- 幂等：若字段已存在会报 1060，可忽略
-- ============================================================

ALTER TABLE `goods`
    ADD COLUMN `favorite_count` INT NOT NULL DEFAULT 0 COMMENT '收藏数（补偿统计字段）'
    AFTER `like_count`;

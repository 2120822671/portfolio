-- step04 数据库升级脚本（在 step01 建表基础上执行）
USE campus_secondhand;

-- 1. 商品表扩展：库存/交易地点/联系方式/点赞数
ALTER TABLE goods
    ADD COLUMN stock      INT          NOT NULL DEFAULT 1  COMMENT '库存数量' AFTER status,
    ADD COLUMN location   VARCHAR(100) DEFAULT NULL        COMMENT '交易地点' AFTER cover_image,
    ADD COLUMN contact    VARCHAR(50)  DEFAULT NULL        COMMENT '联系方式' AFTER location,
    ADD COLUMN like_count INT          NOT NULL DEFAULT 0  COMMENT '点赞数'   AFTER view_count;

-- 2. 商品图片表（多图与商品分离）
CREATE TABLE IF NOT EXISTS goods_image (
    id         INT          NOT NULL AUTO_INCREMENT COMMENT '图片ID',
    goods_id   INT          NOT NULL COMMENT '商品ID',
    url        VARCHAR(255) NOT NULL COMMENT '图片URL',
    created_at DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '上传时间',
    PRIMARY KEY (id),
    KEY idx_image_goods (goods_id),
    CONSTRAINT fk_image_goods FOREIGN KEY (goods_id) REFERENCES goods (id)
) ENGINE = InnoDB COMMENT = '商品图片表';

-- 3. 点赞表（一人一商品仅一条，取消后删除可再点）
CREATE TABLE IF NOT EXISTS goods_like (
    id         INT      NOT NULL AUTO_INCREMENT COMMENT '点赞ID',
    goods_id   INT      NOT NULL COMMENT '商品ID',
    user_id    INT      NOT NULL COMMENT '用户ID',
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '点赞时间',
    PRIMARY KEY (id),
    UNIQUE KEY uk_like_goods_user (goods_id, user_id),
    CONSTRAINT fk_like_goods FOREIGN KEY (goods_id) REFERENCES goods (id),
    CONSTRAINT fk_like_user  FOREIGN KEY (user_id)  REFERENCES `user` (id)
) ENGINE = InnoDB COMMENT = '商品点赞表';

-- 4. 留言表
CREATE TABLE IF NOT EXISTS goods_message (
    id         INT          NOT NULL AUTO_INCREMENT COMMENT '留言ID',
    goods_id   INT          NOT NULL COMMENT '商品ID',
    user_id    INT          NOT NULL COMMENT '留言人ID',
    content    VARCHAR(500) NOT NULL COMMENT '留言内容',
    created_at DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '留言时间',
    PRIMARY KEY (id),
    KEY idx_msg_goods (goods_id),
    CONSTRAINT fk_msg_goods FOREIGN KEY (goods_id) REFERENCES goods (id),
    CONSTRAINT fk_msg_user  FOREIGN KEY (user_id)  REFERENCES `user` (id)
) ENGINE = InnoDB COMMENT = '商品留言表';

-- 5. 商品表查询索引
ALTER TABLE goods
    ADD INDEX idx_goods_title (title),
    ADD INDEX idx_goods_price (price),
    ADD INDEX idx_goods_status (status),
    ADD INDEX idx_goods_created (created_at);

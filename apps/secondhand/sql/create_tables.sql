-- 校园二手交易平台 建表 SQL
-- 执行方式：mysql -u root -p < create_tables.sql

CREATE DATABASE IF NOT EXISTS campus_secondhand
    DEFAULT CHARACTER SET utf8mb4
    DEFAULT COLLATE utf8mb4_unicode_ci;

USE campus_secondhand;

-- 1. 用户表
CREATE TABLE IF NOT EXISTS `user` (
    `id`           INT           NOT NULL AUTO_INCREMENT COMMENT '用户ID',
    `username`     VARCHAR(50)   NOT NULL COMMENT '登录用户名',
    `password`     VARCHAR(128)  NOT NULL COMMENT '密码（加密存储）',
    `nickname`     VARCHAR(50)   DEFAULT NULL COMMENT '昵称',
    `phone`        VARCHAR(20)   DEFAULT NULL COMMENT '手机号',
    `avatar`       VARCHAR(255)  DEFAULT NULL COMMENT '头像URL',
    `credit_score` INT           NOT NULL DEFAULT 100 COMMENT '信用分',
    `status`       TINYINT       NOT NULL DEFAULT 1 COMMENT '状态：1正常 0冻结',
    `created_at`   DATETIME      NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '注册时间',
    `updated_at`   DATETIME      NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    PRIMARY KEY (`id`),
    UNIQUE KEY `uk_username` (`username`)
) ENGINE = InnoDB COMMENT = '用户表';

-- 2. 商品分类表
CREATE TABLE IF NOT EXISTS `category` (
    `id`         INT          NOT NULL AUTO_INCREMENT COMMENT '分类ID',
    `name`       VARCHAR(50)  NOT NULL COMMENT '分类名称',
    `icon`       VARCHAR(255) DEFAULT NULL COMMENT '分类图标URL',
    `sort_order` INT          NOT NULL DEFAULT 0 COMMENT '排序权重，越小越靠前',
    `created_at` DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    PRIMARY KEY (`id`),
    UNIQUE KEY `uk_name` (`name`)
) ENGINE = InnoDB COMMENT = '商品分类表';

-- 3. 商品表
CREATE TABLE IF NOT EXISTS `goods` (
    `id`          INT           NOT NULL AUTO_INCREMENT COMMENT '商品ID',
    `title`       VARCHAR(100)  NOT NULL COMMENT '商品标题',
    `description` TEXT          DEFAULT NULL COMMENT '商品详细描述',
    `price`       DECIMAL(10,2) NOT NULL COMMENT '售价（元）',
    `original_price` DECIMAL(10,2) DEFAULT NULL COMMENT '原价（元）',
    `cover_image` VARCHAR(255)  DEFAULT NULL COMMENT '封面图URL',
    `status`      TINYINT       NOT NULL DEFAULT 1 COMMENT '状态：1在售 2已售出 3已下架',
    `view_count`  INT           NOT NULL DEFAULT 0 COMMENT '浏览量',
    `seller_id`   INT           NOT NULL COMMENT '卖家ID',
    `category_id` INT           NOT NULL COMMENT '分类ID',
    `created_at`  DATETIME      NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '发布时间',
    `updated_at`  DATETIME      NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    PRIMARY KEY (`id`),
    KEY `idx_seller` (`seller_id`),
    KEY `idx_category` (`category_id`),
    CONSTRAINT `fk_goods_seller`   FOREIGN KEY (`seller_id`)   REFERENCES `user` (`id`),
    CONSTRAINT `fk_goods_category` FOREIGN KEY (`category_id`) REFERENCES `category` (`id`)
) ENGINE = InnoDB COMMENT = '商品表';

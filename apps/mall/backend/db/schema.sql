-- ============================================================
-- 蛋糕线上商城 cakeshop · 完整数据库表结构
-- MySQL 8.0 · utf8mb4
-- 运行方式：mysql -u root -p < backend/db/schema.sql
-- 或直接执行：python backend/db/init_db.py（自动建库+表+样例数据）
-- ============================================================

CREATE DATABASE IF NOT EXISTS `cakeshop`
  DEFAULT CHARSET utf8mb4 COLLATE utf8mb4_general_ci;

USE `cakeshop`;

SET FOREIGN_KEY_CHECKS = 0;

-- 用户表
DROP TABLE IF EXISTS `user`;
CREATE TABLE `user` (
  `id`           INT(11)      NOT NULL AUTO_INCREMENT COMMENT '用户ID',
  `username`     VARCHAR(50)  NOT NULL                 COMMENT '用户名',
  `nickname`     VARCHAR(50)  DEFAULT NULL             COMMENT '昵称',
  `phone`        VARCHAR(20)  NOT NULL                 COMMENT '手机号',
  `password`     VARCHAR(100) NOT NULL                 COMMENT '密码(MD5)',
  `role`         TINYINT      NOT NULL DEFAULT 0       COMMENT '0=普通顾客 1=管理员',
  `status`       TINYINT      NOT NULL DEFAULT 1       COMMENT '1=正常 0=冻结',
  `create_time`  DATETIME     DEFAULT CURRENT_TIMESTAMP COMMENT '注册时间',
  PRIMARY KEY (`id`),
  UNIQUE KEY `phone` (`phone`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='用户表';

-- 收货地址表
DROP TABLE IF EXISTS `address`;
CREATE TABLE `address` (
  `id`              INT(11)      NOT NULL AUTO_INCREMENT,
  `user_id`         INT(11)      NOT NULL,
  `receiver_name`   VARCHAR(50)  NOT NULL,
  `receiver_phone`  VARCHAR(20)  NOT NULL,
  `address`         VARCHAR(255) NOT NULL,
  `is_default`      TINYINT      NOT NULL DEFAULT 0,
  PRIMARY KEY (`id`),
  KEY `user_id` (`user_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='收货地址表';

-- 蛋糕分类
DROP TABLE IF EXISTS `cake_category`;
CREATE TABLE `cake_category` (
  `id`             INT(11)      NOT NULL AUTO_INCREMENT,
  `category_name`  VARCHAR(50)  NOT NULL,
  `sort`           INT(11)      DEFAULT 0,
  PRIMARY KEY (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='蛋糕分类表';

-- 蛋糕商品
DROP TABLE IF EXISTS `cake`;
CREATE TABLE `cake` (
  `id`            INT(11)        NOT NULL AUTO_INCREMENT COMMENT '蛋糕ID',
  `cake_name`     VARCHAR(100)   NOT NULL                COMMENT '蛋糕名称',
  `price`         DECIMAL(10,2)  NOT NULL                COMMENT '售价',
  `stock`         INT(11)        DEFAULT 0               COMMENT '库存数量',
  `category_id`   INT(11)        NOT NULL                COMMENT '所属分类',
  `image`         VARCHAR(255)   DEFAULT NULL            COMMENT '商品图片URL',
  `description`   TEXT           DEFAULT NULL            COMMENT '蛋糕描述',
  `spec`          VARCHAR(255)   DEFAULT NULL            COMMENT '可选规格（/分隔）',
  `on_shelf`      TINYINT        NOT NULL DEFAULT 1      COMMENT '1=上架 0=下架',
  `create_time`   DATETIME       DEFAULT CURRENT_TIMESTAMP COMMENT '上架时间',
  PRIMARY KEY (`id`),
  KEY `category_id` (`category_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='蛋糕商品表';

-- 购物车
DROP TABLE IF EXISTS `cart`;
CREATE TABLE `cart` (
  `id`        INT(11) NOT NULL AUTO_INCREMENT,
  `user_id`   INT(11) NOT NULL,
  `cake_id`   INT(11) NOT NULL,
  `buy_num`   INT(11) NOT NULL DEFAULT 1,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_user_cake` (`user_id`, `cake_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='购物车表';

-- 收藏
DROP TABLE IF EXISTS `favorite`;
CREATE TABLE `favorite` (
  `id`          INT(11)   NOT NULL AUTO_INCREMENT,
  `user_id`     INT(11)   NOT NULL,
  `cake_id`     INT(11)   NOT NULL,
  `create_time` DATETIME  DEFAULT CURRENT_TIMESTAMP(),
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_user_cake` (`user_id`, `cake_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='收藏表';

-- 订单
DROP TABLE IF EXISTS `orders`;
CREATE TABLE `orders` (
  `id`                INT(11)        NOT NULL AUTO_INCREMENT COMMENT '订单ID',
  `order_no`          VARCHAR(32)    NOT NULL                COMMENT '订单号',
  `user_id`           INT(11)        NOT NULL                COMMENT '下单用户',
  `total_amount`      DECIMAL(10,2)  NOT NULL                COMMENT '订单总金额',
  `order_status`      TINYINT        DEFAULT 0               COMMENT '0=待支付 1=待配送 2=已完成 3=已取消',
  `receiver_name`     VARCHAR(50)    DEFAULT NULL,
  `receiver_phone`    VARCHAR(20)    DEFAULT NULL,
  `receiver_address`  VARCHAR(255)   NOT NULL,
  `remark`            VARCHAR(255)   DEFAULT NULL,
  `create_time`       DATETIME       DEFAULT CURRENT_TIMESTAMP(),
  PRIMARY KEY (`id`),
  UNIQUE KEY `order_no` (`order_no`),
  KEY `user_id` (`user_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='订单表';

-- 订单明细
DROP TABLE IF EXISTS `order_item`;
CREATE TABLE `order_item` (
  `id`         INT(11)        NOT NULL AUTO_INCREMENT,
  `order_id`   INT(11)        NOT NULL,
  `cake_id`    INT(11)        NOT NULL,
  `buy_num`    INT(11)        NOT NULL,
  `buy_price`  DECIMAL(10,2)  NOT NULL                COMMENT '下单时单价',
  PRIMARY KEY (`id`),
  KEY `order_id` (`order_id`),
  KEY `cake_id`  (`cake_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='订单明细表';

-- 商品评论
DROP TABLE IF EXISTS `comment`;
CREATE TABLE `comment` (
  `id`          INT(11)   NOT NULL AUTO_INCREMENT,
  `user_id`     INT(11)   NOT NULL,
  `cake_id`     INT(11)   NOT NULL,
  `content`     TEXT      NOT NULL,
  `create_time` DATETIME  DEFAULT CURRENT_TIMESTAMP(),
  PRIMARY KEY (`id`),
  KEY `user_id` (`user_id`),
  KEY `cake_id` (`cake_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='商品评论表';

SET FOREIGN_KEY_CHECKS = 1;

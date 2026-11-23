-- 增量脚本：购物车 + 聊天 + 订单支付方式（购物车/砍价换物需求）
-- 说明：仅新增两张表与 orders 一个字段，不修改任何已存在的表结构
-- 执行：mysql -uroot -p campus_secondhand < upgrade_add_cart_chat.sql

USE campus_secondhand;

-- 1. 订单新增支付方式（模拟支付：校园一卡通/微信/支付宝/线下当面交易）
ALTER TABLE `orders`
  ADD COLUMN `pay_method` VARCHAR(20) DEFAULT NULL COMMENT '支付方式：campus_card/wechat/alipay/cash' AFTER `amount`;

-- 2. 购物车表：同一用户同一商品只保留一行，数量累加
CREATE TABLE IF NOT EXISTS `cart_item` (
  `id`         INT      NOT NULL AUTO_INCREMENT COMMENT '购物车项ID',
  `user_id`    INT      NOT NULL COMMENT '用户ID',
  `goods_id`   INT      NOT NULL COMMENT '商品ID',
  `quantity`   INT      NOT NULL DEFAULT 1 COMMENT '数量',
  `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '加入时间',
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_cart_user_goods` (`user_id`, `goods_id`),
  KEY `idx_cart_goods` (`goods_id`),
  CONSTRAINT `fk_cart_user`  FOREIGN KEY (`user_id`)  REFERENCES `user` (`id`),
  CONSTRAINT `fk_cart_goods` FOREIGN KEY (`goods_id`) REFERENCES `goods` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='购物车表（增量新增）';

-- 3. 聊天消息表：按（商品, 买卖双方）组成会话，支持砍价/换物等消息类型
CREATE TABLE IF NOT EXISTS `chat_message` (
  `id`          INT          NOT NULL AUTO_INCREMENT COMMENT '消息ID',
  `goods_id`    INT          NOT NULL COMMENT '关联商品ID',
  `sender_id`   INT          NOT NULL COMMENT '发送者ID',
  `receiver_id` INT          NOT NULL COMMENT '接收者ID',
  `msg_type`    VARCHAR(20)  NOT NULL DEFAULT 'text'
                COMMENT 'text/bargain/bargain_accept/bargain_reject/swap/swap_accept/swap_reject',
  `content`     VARCHAR(500) NOT NULL COMMENT '消息内容',
  `extra`       TEXT         DEFAULT NULL COMMENT '扩展信息（JSON：出价/换物商品/回复引用）',
  `read_at`     DATETIME     DEFAULT NULL COMMENT '对方阅读时间',
  `created_at`  DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '发送时间',
  PRIMARY KEY (`id`),
  KEY `idx_chat_goods` (`goods_id`),
  KEY `idx_chat_sender` (`sender_id`),
  KEY `idx_chat_receiver_read` (`receiver_id`, `read_at`),
  CONSTRAINT `fk_chat_goods`    FOREIGN KEY (`goods_id`)    REFERENCES `goods` (`id`),
  CONSTRAINT `fk_chat_sender`   FOREIGN KEY (`sender_id`)   REFERENCES `user` (`id`),
  CONSTRAINT `fk_chat_receiver` FOREIGN KEY (`receiver_id`) REFERENCES `user` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='聊天消息表（增量新增）';

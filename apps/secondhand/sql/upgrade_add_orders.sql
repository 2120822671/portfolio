-- 增量脚本：订单模块（定时关单需求）
-- 说明：仅新增 orders / order_logs 两张表，不修改任何已存在的表结构
-- 执行：mysql -uroot -p campus_secondhand < upgrade_add_orders.sql   （或通过 pymysql 执行）

CREATE TABLE IF NOT EXISTS `orders` (
  `id`           INT           NOT NULL AUTO_INCREMENT COMMENT '订单ID',
  `order_no`     VARCHAR(32)   NOT NULL COMMENT '订单号（业务唯一）',
  `goods_id`     INT           NOT NULL COMMENT '商品ID',
  `buyer_id`     INT           NOT NULL COMMENT '买家ID',
  `seller_id`    INT           NOT NULL COMMENT '卖家ID',
  `amount`       DECIMAL(10,2) NOT NULL COMMENT '订单金额',
  `status`       TINYINT(4)    NOT NULL DEFAULT 10 COMMENT '状态：10待付款 20已支付 30已完成 40已关闭',
  `pay_deadline` DATETIME      NOT NULL COMMENT '付款截止时间（下单+30分钟）',
  `close_type`   VARCHAR(20)   DEFAULT NULL COMMENT '关闭方式：timeout超时 user用户取消',
  `closed_at`    DATETIME      DEFAULT NULL COMMENT '关闭时间',
  `created_at`   DATETIME      NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '下单时间',
  `updated_at`   DATETIME      NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_order_no` (`order_no`),
  KEY `idx_status_deadline` (`status`, `pay_deadline`),
  KEY `idx_buyer` (`buyer_id`),
  KEY `idx_goods` (`goods_id`),
  CONSTRAINT `fk_order_goods`  FOREIGN KEY (`goods_id`)  REFERENCES `goods` (`id`),
  CONSTRAINT `fk_order_buyer`  FOREIGN KEY (`buyer_id`)  REFERENCES `user` (`id`),
  CONSTRAINT `fk_order_seller` FOREIGN KEY (`seller_id`) REFERENCES `user` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='订单表（增量新增）';

CREATE TABLE IF NOT EXISTS `order_logs` (
  `id`          INT          NOT NULL AUTO_INCREMENT COMMENT '流水ID',
  `order_id`    INT          NOT NULL COMMENT '订单ID',
  `from_status` TINYINT(4)   NOT NULL COMMENT '变更前状态',
  `to_status`   TINYINT(4)   NOT NULL COMMENT '变更后状态',
  `action`      VARCHAR(32)  NOT NULL COMMENT '动作：create/pay/cancel/auto_close',
  `remark`      VARCHAR(255) DEFAULT NULL COMMENT '备注',
  `created_at`  DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '发生时间',
  PRIMARY KEY (`id`),
  KEY `idx_order` (`order_id`),
  CONSTRAINT `fk_log_order` FOREIGN KEY (`order_id`) REFERENCES `orders` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='订单状态流水表（增量新增）';

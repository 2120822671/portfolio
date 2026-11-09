-- =============================================
-- 个人记账小系统 · 建表 SQL
-- Lesson 02 · 任务 2
-- =============================================

-- 1. 创建数据库
CREATE DATABASE IF NOT EXISTS account_db
  DEFAULT CHARACTER SET utf8mb4
  DEFAULT COLLATE utf8mb4_unicode_ci;

USE account_db;

-- 2. 创建记账记录表
CREATE TABLE IF NOT EXISTS account_record (
  id          BIGINT        NOT NULL AUTO_INCREMENT COMMENT '唯一标识每一笔记账记录',
  type        TINYINT       NOT NULL                 COMMENT '收支类型：1=收入，2=支出',
  amount      DECIMAL(10,2) NOT NULL                 COMMENT '金额，精确到小数点后2位',
  category    VARCHAR(50)   NOT NULL                 COMMENT '分类名称：餐饮/交通/工资/购物等',
  remark      VARCHAR(255)  NULL                     COMMENT '备注信息，可选填写',
  record_time DATETIME      NOT NULL                 COMMENT '这笔账实际发生的时间',
  create_time DATETIME      NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '记录创建时间（系统自动填入）',
  PRIMARY KEY (id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='记账记录表';

-- 3. 插入 3 条测试数据（可选，方便接口测试）
INSERT INTO account_record (type, amount, category, remark, record_time) VALUES
  (1, 8000.00, '工资', '11月工资', '2026-11-01 10:00:00'),
  (2, 15.00,  '交通', '地铁',     '2026-11-04 08:30:00'),
  (2, 25.50,  '餐饮', '午餐牛肉面', '2026-11-04 12:30:00');

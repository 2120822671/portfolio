-- 增量新增：管理后台扩展表（任务10 用户/审核/举报/订单监管）
-- 只新建 2 张表，不改动任何已有表结构与数据
CREATE TABLE IF NOT EXISTS goods_audit_log (
  id INT AUTO_INCREMENT PRIMARY KEY COMMENT '流水ID',
  goods_id INT NOT NULL COMMENT '商品ID',
  goods_title VARCHAR(100) NOT NULL COMMENT '审核时商品标题快照',
  from_status INT NOT NULL COMMENT '变更前状态',
  to_status INT NOT NULL COMMENT '变更后状态',
  action VARCHAR(16) NOT NULL COMMENT '动作：submit/approve/reject',
  remark VARCHAR(255) DEFAULT NULL COMMENT '审核备注',
  operator_id INT NOT NULL COMMENT '操作管理员ID',
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '时间',
  KEY idx_goods_audit_goods (goods_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='商品审核流水表';

CREATE TABLE IF NOT EXISTS report_handle (
  id INT AUTO_INCREMENT PRIMARY KEY COMMENT '主键',
  report_id INT NOT NULL COMMENT '举报ID',
  action VARCHAR(16) NOT NULL COMMENT '处理：processed 已处理 / ignored 已忽略',
  remark VARCHAR(255) DEFAULT NULL COMMENT '处理备注',
  handler_id INT NOT NULL COMMENT '处理管理员ID',
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '处理时间',
  updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
  UNIQUE KEY uk_report_handle_report (report_id),
  KEY idx_report_handle_report (report_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='举报处理记录表';

-- 说明：goods.status 追加取值 5=待审核（1在售/2已售/3下架/4已预订 的原有语义与判定逻辑一律不改）

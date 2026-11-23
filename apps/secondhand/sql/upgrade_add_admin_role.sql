-- 增量新增：管理员角色表（任务8 管理后台看板）
-- 只新建 admin_role 表，不改动任何已有表结构与数据
CREATE TABLE IF NOT EXISTS admin_role (
  id INT AUTO_INCREMENT PRIMARY KEY COMMENT '主键',
  user_id INT NOT NULL COMMENT '用户ID',
  role VARCHAR(20) NOT NULL COMMENT '角色：admin 管理员 / super_admin 超级管理员',
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '授权时间',
  UNIQUE KEY uk_admin_role_user (user_id),
  CONSTRAINT fk_admin_role_user FOREIGN KEY (user_id) REFERENCES user(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='管理员角色表';

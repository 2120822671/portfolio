-- 增量新增：举报表（风控需求：24 小时同一用户对同一对象只能举报一次）
-- 注意：时间语义（24 小时解禁）由 Redis TTL 控制，本表只存流水，
--       因此不建 (user_id, target_type, target_id) 唯一约束，只建普通联合索引。
USE campus_secondhand;

CREATE TABLE IF NOT EXISTS `report` (
    `id`          INT          NOT NULL AUTO_INCREMENT COMMENT '举报ID',
    `user_id`     INT          NOT NULL COMMENT '举报人ID',
    `target_type` VARCHAR(16)  NOT NULL COMMENT '举报对象类型：goods/user/message',
    `target_id`   INT          NOT NULL COMMENT '举报对象ID',
    `reason`      VARCHAR(200) NOT NULL COMMENT '举报原因',
    `created_at`  DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '举报时间',
    PRIMARY KEY (`id`),
    KEY `idx_report_user` (`user_id`),
    KEY `idx_report_target` (`target_type`, `target_id`),
    CONSTRAINT `fk_report_user` FOREIGN KEY (`user_id`) REFERENCES `user` (`id`)
) ENGINE = InnoDB
  DEFAULT CHARSET = utf8mb4
  COLLATE = utf8mb4_unicode_ci COMMENT ='举报流水表（24小时去重由Redis控制）';

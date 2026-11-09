-- ============================================================
-- 星坞 StarDock —— 一键建库脚本
-- 引擎: InnoDB | 字符集: utf8mb4
-- ============================================================

DROP DATABASE IF EXISTS stardock;
CREATE DATABASE stardock DEFAULT CHARSET utf8mb4 COLLATE utf8mb4_general_ci;
USE stardock;

-- -----------------------------------------------------------
-- users 用户表（三角色）
-- role: 1 粉丝 / 2 管理员 / 3 明星
-- status: 0 禁用 / 1 正常
-- -----------------------------------------------------------
CREATE TABLE users (
  id INT AUTO_INCREMENT PRIMARY KEY,
  username VARCHAR(50) NOT NULL UNIQUE COMMENT '登录账号',
  password CHAR(32) NOT NULL COMMENT 'MD5 加密',
  nickname VARCHAR(50) NOT NULL COMMENT '昵称（显示用）',
  avatar VARCHAR(255) DEFAULT NULL COMMENT '头像 URL',
  role TINYINT NOT NULL DEFAULT 1 COMMENT '1粉丝/2管理员/3明星',
  score INT NOT NULL DEFAULT 1000 COMMENT '积分（注册送1000）',
  status TINYINT NOT NULL DEFAULT 1 COMMENT '0禁用/1正常',
  create_time DATETIME NOT NULL,
  CONSTRAINT chk_users_role CHECK (role IN (1, 2, 3)),
  CONSTRAINT chk_users_status CHECK (status IN (0, 1))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='用户表';

-- -----------------------------------------------------------
-- celebrities 明星档案表（只有 role=3 的用户有对应记录）
-- category: 歌手/演员/游戏主播/UP主/其他
-- status: 0 隐藏 / 1 显示
-- -----------------------------------------------------------
CREATE TABLE celebrities (
  id INT AUTO_INCREMENT PRIMARY KEY,
  user_id INT NOT NULL UNIQUE COMMENT '关联 users.id',
  stage_name VARCHAR(50) NOT NULL COMMENT '艺名/主播名',
  category VARCHAR(30) NOT NULL COMMENT '分类',
  bio TEXT COMMENT '个人简介',
  cover_image VARCHAR(255) DEFAULT NULL COMMENT '封面图',
  fan_count INT NOT NULL DEFAULT 0 COMMENT '粉丝数（冗余）',
  status TINYINT NOT NULL DEFAULT 1 COMMENT '0隐藏/1显示',
  create_time DATETIME NOT NULL,
  CONSTRAINT chk_celebrities_category CHECK (category IN ('歌手', '演员', '游戏主播', 'UP主', '其他')),
  CONSTRAINT chk_celebrities_status CHECK (status IN (0, 1))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='明星档案表';

-- -----------------------------------------------------------
-- fan_clubs 粉丝团表（一星一团）
-- -----------------------------------------------------------
CREATE TABLE fan_clubs (
  id INT AUTO_INCREMENT PRIMARY KEY,
  celebrity_id INT NOT NULL UNIQUE COMMENT '关联 celebrities.id',
  name VARCHAR(50) NOT NULL COMMENT '粉丝团名称',
  description TEXT COMMENT '粉丝团简介',
  member_count INT NOT NULL DEFAULT 0 COMMENT '成员数（冗余）',
  create_time DATETIME NOT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='粉丝团表';

-- -----------------------------------------------------------
-- fan_club_members 粉丝团成员表
-- -----------------------------------------------------------
CREATE TABLE fan_club_members (
  id INT AUTO_INCREMENT PRIMARY KEY,
  club_id INT NOT NULL COMMENT '粉丝团 ID',
  user_id INT NOT NULL COMMENT '用户 ID',
  nick_in_club VARCHAR(50) DEFAULT NULL COMMENT '团内昵称（可空）',
  join_time DATETIME NOT NULL,
  UNIQUE KEY uk_club_user (club_id, user_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='粉丝团成员表';

-- -----------------------------------------------------------
-- chat_messages 聊天消息表
-- msg_type: 1 文本 / 2 系统消息
-- -----------------------------------------------------------
CREATE TABLE chat_messages (
  id BIGINT AUTO_INCREMENT PRIMARY KEY,
  club_id INT NOT NULL COMMENT '所属粉丝团',
  user_id INT NOT NULL COMMENT '发送者',
  content VARCHAR(1000) NOT NULL COMMENT '消息内容',
  msg_type TINYINT NOT NULL DEFAULT 1 COMMENT '1文本/2系统消息',
  create_time DATETIME NOT NULL,
  CONSTRAINT chk_msgs_type CHECK (msg_type IN (1, 2)),
  INDEX idx_club_time (club_id, create_time)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='聊天消息表';

-- -----------------------------------------------------------
-- card_pools 卡池表
-- is_active: 0 关闭 / 1 开放
-- -----------------------------------------------------------
CREATE TABLE card_pools (
  id INT AUTO_INCREMENT PRIMARY KEY,
  name VARCHAR(50) NOT NULL COMMENT '卡池名称',
  celebrity_id INT DEFAULT NULL COMMENT '关联明星（NULL 为通用池）',
  description TEXT COMMENT '卡池介绍',
  cost_per_draw INT NOT NULL DEFAULT 100 COMMENT '单抽消耗积分',
  cost_per_ten INT NOT NULL DEFAULT 900 COMMENT '十连消耗积分（九折）',
  is_active TINYINT NOT NULL DEFAULT 1 COMMENT '0关闭/1开放',
  create_time DATETIME NOT NULL,
  CONSTRAINT chk_pools_active CHECK (is_active IN (0, 1))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='卡池表';

-- -----------------------------------------------------------
-- cards 卡片表
-- rarity: 1 N / 2 R / 3 SR / 4 SSR
-- -----------------------------------------------------------
CREATE TABLE cards (
  id INT AUTO_INCREMENT PRIMARY KEY,
  pool_id INT NOT NULL COMMENT '所属卡池',
  celebrity_id INT DEFAULT NULL COMMENT '关联明星',
  name VARCHAR(50) NOT NULL COMMENT '卡片名称',
  image_url VARCHAR(255) NOT NULL COMMENT '卡片图片',
  rarity TINYINT NOT NULL COMMENT '1N/2R/3SR/4SSR',
  weight INT NOT NULL DEFAULT 100 COMMENT '抽中权重',
  description VARCHAR(255) DEFAULT NULL COMMENT '卡片描述',
  create_time DATETIME NOT NULL,
  CONSTRAINT chk_cards_rarity CHECK (rarity IN (1, 2, 3, 4)),
  INDEX idx_pool (pool_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='卡片表';

-- -----------------------------------------------------------
-- user_cards 用户持卡表
-- -----------------------------------------------------------
CREATE TABLE user_cards (
  id INT AUTO_INCREMENT PRIMARY KEY,
  user_id INT NOT NULL COMMENT '用户',
  card_id INT NOT NULL COMMENT '卡片',
  count INT NOT NULL DEFAULT 1 COMMENT '持有数量',
  obtain_time DATETIME NOT NULL COMMENT '首次获得时间',
  UNIQUE KEY uk_user_card (user_id, card_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='用户持卡表';

-- -----------------------------------------------------------
-- gacha_records 抽卡记录表
-- draw_type: 1 单抽 / 2 十连
-- results_json 示例: [{"card_id":1,"rarity":3},{"card_id":5,"rarity":2}]
-- -----------------------------------------------------------
CREATE TABLE gacha_records (
  id BIGINT AUTO_INCREMENT PRIMARY KEY,
  user_id INT NOT NULL COMMENT '抽卡用户',
  pool_id INT NOT NULL COMMENT '卡池',
  draw_type TINYINT NOT NULL COMMENT '1单抽/2十连',
  total_cost INT NOT NULL COMMENT '总消耗积分',
  results_json JSON NOT NULL COMMENT '抽卡结果列表',
  create_time DATETIME NOT NULL,
  CONSTRAINT chk_records_type CHECK (draw_type IN (1, 2)),
  INDEX idx_user_time (user_id, create_time)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='抽卡记录表';


-- ============================================================
-- 初始化数据
-- ============================================================

-- 默认管理员账号：admin / 123456 (MD5 = e10adc3949ba59abbe56e057f20f883e)
INSERT INTO users (username, password, nickname, role, score, create_time) VALUES
('admin', 'e10adc3949ba59abbe56e057f20f883e', '超级管理员', 2, 99999, NOW()),
('star_luna', 'e10adc3949ba59abbe56e057f20f883e', 'Luna月影', 3, 99999, NOW()),
('star_ray',  'e10adc3949ba59abbe56e057f20f883e', 'Ray光翼',  3, 99999, NOW()),
('fan_test',  'e10adc3949ba59abbe56e057f20f883e', '测试粉丝', 1, 1000, NOW());

-- 明星档案
INSERT INTO celebrities (user_id, stage_name, category, bio, cover_image, status, create_time) VALUES
(2, 'Luna月影', '歌手', '治愈系女声，月光般温暖你的每个夜晚。', '/img/celeb/luna.jpg', 1, NOW()),
(3, 'Ray光翼',  '游戏主播', '硬核操作+搞笑解说，带你上分不孤单。', '/img/celeb/ray.jpg',  1, NOW());

-- 粉丝团
INSERT INTO fan_clubs (celebrity_id, name, description, create_time) VALUES
(1, '月光俱乐部', 'Luna月影的温暖港湾，欢迎每一颗小星星~', NOW()),
(2, '光之翼战队', 'Ray光翼的硬核粉丝团，一起冲上王者！', NOW());

-- 粉丝团成员（测试粉丝加入月光俱乐部）
INSERT INTO fan_club_members (club_id, user_id, join_time) VALUES
(1, 4, NOW()),
(2, 1, NOW());

-- 初始化卡池
INSERT INTO card_pools (name, celebrity_id, description, cost_per_draw, cost_per_ten, is_active, create_time) VALUES
('通用纪念池', NULL, '经典永不过时，收藏你的第一星卡！', 100, 900, 1, NOW()),
('Luna限定池', 1, 'Luna月影专属星卡，绝版收藏！', 150, 1350, 1, NOW());

-- 初始化卡片（通用池 N/R/SR/SSR）
INSERT INTO cards (pool_id, celebrity_id, name, image_url, rarity, weight, description, create_time) VALUES
-- 通用池
(1, NULL, '星光碎片', '/img/card/star_n1.jpg',  1, 500, '最常见的星尘碎片',   NOW()),
(1, NULL, '闪烁微光', '/img/card/star_n2.jpg',  1, 500, '微弱但坚定的光芒',   NOW()),
(1, NULL, '银色星芒', '/img/card/star_r1.jpg',  2, 250, '值得收藏的银色星芒', NOW()),
(1, NULL, '金色星雨', '/img/card/star_r2.jpg',  2, 250, '流星雨般的金色光辉', NOW()),
(1, NULL, '紫晶星核', '/img/card/star_sr1.jpg', 3, 80,  '稀有的紫晶核心',     NOW()),
(1, NULL, '永恒之光', '/img/card/star_ssr1.jpg',4, 20,  '传说中的永恒之星',   NOW()),
-- Luna 限定池
(2, 1, 'Luna·素颜',  '/img/card/luna_n1.jpg',   1, 500, '日常素颜的 Luna',    NOW()),
(2, 1, 'Luna·舞台',  '/img/card/luna_r1.jpg',   2, 300, '舞台上闪闪发光',     NOW()),
(2, 1, 'Luna·月光',  '/img/card/luna_sr1.jpg',  3, 80,  '月光下的 Luna',      NOW()),
(2, 1, 'Luna·传说',  '/img/card/luna_ssr1.jpg', 4, 20,  '传说级 Luna 限定',   NOW());

-- 初始聊天消息（系统欢迎语）
INSERT INTO chat_messages (club_id, user_id, content, msg_type, create_time) VALUES
(1, 1, '欢迎来到月光俱乐部！请文明聊天~', 2, NOW()),
(2, 1, '欢迎来到光之翼战队！一起开黑吧~', 2, NOW());


-- -----------------------------------------------------------
-- activities 活动 / 通知表
-- scope: 1 全体 / 2 指定明星粉丝团
-- activity_type: 1 通知 / 2 活动
-- target_club_id: scope=2 时生效
-- -----------------------------------------------------------
CREATE TABLE activities (
  id INT AUTO_INCREMENT PRIMARY KEY,
  title VARCHAR(100) NOT NULL COMMENT '标题',
  content TEXT NOT NULL COMMENT '正文（支持简单换行）',
  activity_type TINYINT NOT NULL DEFAULT 1 COMMENT '1通知/2活动',
  scope TINYINT NOT NULL DEFAULT 1 COMMENT '1全体/2指定粉丝团',
  target_club_id INT DEFAULT NULL COMMENT 'scope=2 时指定粉丝团',
  poster_id INT NOT NULL COMMENT '发布者 users.id',
  poster_name VARCHAR(50) NOT NULL COMMENT '发布者昵称（冗余）',
  status TINYINT NOT NULL DEFAULT 1 COMMENT '0已撤回/1发布中',
  create_time DATETIME NOT NULL,
  CONSTRAINT chk_act_type CHECK (activity_type IN (1, 2)),
  CONSTRAINT chk_act_scope CHECK (scope IN (1, 2)),
  CONSTRAINT chk_act_status CHECK (status IN (0, 1)),
  INDEX idx_time (create_time DESC)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='活动/通知表';

-- -----------------------------------------------------------
-- recharge_orders 模拟充值订单
-- pay_type: 1 微信 / 2 支付宝 / 3 积分兑换码
-- status: 0 待支付 / 1 已支付 / 2 已取消
-- -----------------------------------------------------------
CREATE TABLE recharge_orders (
  id INT AUTO_INCREMENT PRIMARY KEY,
  order_no VARCHAR(32) NOT NULL UNIQUE COMMENT '订单号',
  user_id INT NOT NULL COMMENT '用户',
  amount INT NOT NULL COMMENT '充值积分',
  pay_type TINYINT NOT NULL COMMENT '1微信/2支付宝/3兑换码',
  pay_code VARCHAR(20) DEFAULT NULL COMMENT '兑换码（pay_type=3 时填）',
  status TINYINT NOT NULL DEFAULT 0 COMMENT '0待支付/1已支付/2已取消',
  create_time DATETIME NOT NULL,
  pay_time DATETIME DEFAULT NULL,
  CONSTRAINT chk_ord_pay CHECK (pay_type IN (1, 2, 3)),
  CONSTRAINT chk_ord_status CHECK (status IN (0, 1, 2)),
  INDEX idx_user (user_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='充值订单表';

-- 预置一些兑换码（1000/5000/10000）
-- 真实项目应该存到单独表做核销，这里简化成常量列表即可
INSERT INTO activities (title, content, activity_type, scope, poster_id, poster_name, create_time) VALUES
('欢迎来到星坞 StarDock！', '这里是粉丝的港湾——\n⭐ 明星/主播入驻，打造专属粉丝团\n💬 粉丝团实时聊天，结交同好\n🎴 抽卡收集你的心头好\n💰 新用户注册即送 1000 积分，快去抽一发吧！', 1, 1, 1, '超级管理员', NOW()),
('月光俱乐部限时活动！', 'Luna月影粉丝团专属——\n本周六 20:00 直播唱歌，直播期间粉丝团聊天区有专属兑换码掉落～', 2, 2, 1, '超级管理员', NOW());

import os

# 数据库连接配置（请按本机 MySQL 实际情况修改密码）
DB_HOST = "localhost"
DB_PORT = 3306
DB_USER = "root"
DB_PASSWORD = "123456"
DB_NAME = "campus_secondhand"

DATABASE_URL = (
    f"mysql+pymysql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
    "?charset=utf8mb4"
)

# ---------- Redis 风控配置（增量新增：发布限流 / 举报去重） ----------
REDIS_HOST = "127.0.0.1"
REDIS_PORT = 6379
REDIS_DB = 0
# Redis 不可用时是否放行：True=放行（fail-open，风控不拖垮主业务）；False=拦截
RISK_FAIL_OPEN = True

# ---------- 登录令牌签名配置（增量新增：修复身份可伪造缺陷） ----------
# 生产环境请改为环境变量注入（CS_TOKEN_SECRET），不要使用代码里的默认值
TOKEN_SECRET = os.getenv("CS_TOKEN_SECRET", "campus-secondhand-dev-secret-2026")
TOKEN_TTL_SECONDS = 86400  # 令牌有效期 24 小时

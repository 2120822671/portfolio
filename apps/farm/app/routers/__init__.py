"""
路由包 —— 每个文件对应一个业务模块

每个 router 只负责:
    1. 路径 + HTTP 方法 + 参数/请求体类型声明
    2. 依赖注入（认证/数据库 session）
    3. 调用 service 层业务逻辑（待实现）
    4. 返回统一 ApiResponse 结构

业务逻辑统一放在 services/ 中实现。
"""

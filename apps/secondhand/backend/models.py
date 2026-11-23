from datetime import datetime

from sqlalchemy import (
    DECIMAL,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database import Base


class User(Base):
    """用户表"""
    __tablename__ = "user"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True, comment="用户ID")
    username: Mapped[str] = mapped_column(String(50), unique=True, nullable=False, comment="登录用户名")
    password: Mapped[str] = mapped_column(String(128), nullable=False, comment="密码（bcrypt哈希）")
    nickname: Mapped[str | None] = mapped_column(String(50), comment="昵称")
    phone: Mapped[str | None] = mapped_column(String(20), comment="手机号")
    avatar: Mapped[str | None] = mapped_column(String(255), comment="头像URL")
    credit_score: Mapped[int] = mapped_column(Integer, default=100, nullable=False, comment="信用分")
    status: Mapped[int] = mapped_column(Integer, default=1, nullable=False, comment="状态：1正常 0冻结")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, nullable=False, comment="注册时间")
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, onupdate=datetime.now, nullable=False, comment="更新时间")

    goods: Mapped[list["Goods"]] = relationship(back_populates="seller")

    def __repr__(self) -> str:
        return f"<User id={self.id} username={self.username}>"


class Category(Base):
    """商品分类表"""
    __tablename__ = "category"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True, comment="分类ID")
    name: Mapped[str] = mapped_column(String(50), unique=True, nullable=False, comment="分类名称")
    icon: Mapped[str | None] = mapped_column(String(255), comment="分类图标URL")
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False, comment="排序权重")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, nullable=False, comment="创建时间")

    goods: Mapped[list["Goods"]] = relationship(back_populates="category")

    def __repr__(self) -> str:
        return f"<Category id={self.id} name={self.name}>"


class Goods(Base):
    """商品表"""
    __tablename__ = "goods"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True, comment="商品ID")
    title: Mapped[str] = mapped_column(String(100), nullable=False, index=True, comment="商品标题")
    description: Mapped[str | None] = mapped_column(Text, comment="商品详细描述")
    price: Mapped[float] = mapped_column(DECIMAL(10, 2), nullable=False, index=True, comment="售价（元）")
    original_price: Mapped[float | None] = mapped_column(DECIMAL(10, 2), comment="原价（元）")
    cover_image: Mapped[str | None] = mapped_column(String(255), comment="封面图URL")
    location: Mapped[str | None] = mapped_column(String(100), comment="交易地点")
    contact: Mapped[str | None] = mapped_column(String(50), comment="联系方式")
    status: Mapped[int] = mapped_column(Integer, default=1, nullable=False, index=True, comment="状态：1在售 2已售出 3已下架")
    stock: Mapped[int] = mapped_column(Integer, default=1, nullable=False, comment="库存数量")
    view_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False, comment="浏览量")
    like_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False, comment="点赞数")
    # 增量新增：收藏数（由补偿接口 favorite-sync 重算回写，不影响 like_count）
    favorite_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False, comment="收藏数（补偿统计字段）")

    seller_id: Mapped[int] = mapped_column(ForeignKey("user.id"), nullable=False, comment="卖家ID")
    category_id: Mapped[int] = mapped_column(ForeignKey("category.id"), nullable=False, comment="分类ID")

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, nullable=False, index=True, comment="发布时间")
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, onupdate=datetime.now, nullable=False, comment="更新时间")

    seller: Mapped["User"] = relationship(back_populates="goods")
    category: Mapped["Category"] = relationship(back_populates="goods")
    images: Mapped[list["GoodsImage"]] = relationship(cascade="all, delete-orphan")
    likes: Mapped[list["GoodsLike"]] = relationship(cascade="all, delete-orphan")
    messages: Mapped[list["GoodsMessage"]] = relationship(cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return f"<Goods id={self.id} title={self.title}>"


class GoodsImage(Base):
    """商品图片表：多图与商品一对多分离存储"""
    __tablename__ = "goods_image"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True, comment="图片ID")
    goods_id: Mapped[int] = mapped_column(ForeignKey("goods.id"), nullable=False, index=True, comment="商品ID")
    url: Mapped[str] = mapped_column(String(255), nullable=False, comment="图片URL")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, nullable=False, comment="上传时间")


class GoodsLike(Base):
    """点赞表：同一用户对同一商品只能点赞一次（唯一约束），取消后删除记录"""
    __tablename__ = "goods_like"
    __table_args__ = (UniqueConstraint("goods_id", "user_id", name="uk_like_goods_user"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True, comment="点赞ID")
    goods_id: Mapped[int] = mapped_column(ForeignKey("goods.id"), nullable=False, comment="商品ID")
    user_id: Mapped[int] = mapped_column(ForeignKey("user.id"), nullable=False, comment="用户ID")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, nullable=False, comment="点赞时间")


class GoodsMessage(Base):
    """商品留言表"""
    __tablename__ = "goods_message"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True, comment="留言ID")
    goods_id: Mapped[int] = mapped_column(ForeignKey("goods.id"), nullable=False, index=True, comment="商品ID")
    user_id: Mapped[int] = mapped_column(ForeignKey("user.id"), nullable=False, comment="留言人ID")
    content: Mapped[str] = mapped_column(String(500), nullable=False, comment="留言内容")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, nullable=False, comment="留言时间")


# ---------- 订单（增量新增：定时关单需求） ----------
class Order(Base):
    """订单表：status 10待付款 20已支付 30已完成 40已关闭"""
    __tablename__ = "orders"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True, comment="订单ID")
    order_no: Mapped[str] = mapped_column(String(32), unique=True, nullable=False, comment="订单号")
    goods_id: Mapped[int] = mapped_column(ForeignKey("goods.id"), nullable=False, index=True, comment="商品ID")
    buyer_id: Mapped[int] = mapped_column(ForeignKey("user.id"), nullable=False, index=True, comment="买家ID")
    seller_id: Mapped[int] = mapped_column(ForeignKey("user.id"), nullable=False, comment="卖家ID")
    amount: Mapped[float] = mapped_column(DECIMAL(10, 2), nullable=False, comment="订单金额")
    pay_method: Mapped[str | None] = mapped_column(String(20), comment="支付方式：campus_card/wechat/alipay/cash")
    status: Mapped[int] = mapped_column(Integer, default=10, nullable=False, index=True,
                                        comment="状态：10待付款 20已支付 30已完成 40已关闭")
    pay_deadline: Mapped[datetime] = mapped_column(DateTime, nullable=False, comment="付款截止时间（下单+30分钟）")
    close_type: Mapped[str | None] = mapped_column(String(20), comment="关闭方式：timeout超时 user用户取消")
    closed_at: Mapped[datetime | None] = mapped_column(DateTime, comment="关闭时间")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, nullable=False, comment="下单时间")
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, onupdate=datetime.now, nullable=False, comment="更新时间")

    def __repr__(self) -> str:
        return f"<Order id={self.id} no={self.order_no} status={self.status}>"


class OrderLog(Base):
    """订单状态流水表"""
    __tablename__ = "order_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True, comment="流水ID")
    order_id: Mapped[int] = mapped_column(ForeignKey("orders.id"), nullable=False, index=True, comment="订单ID")
    from_status: Mapped[int] = mapped_column(Integer, nullable=False, comment="变更前状态")
    to_status: Mapped[int] = mapped_column(Integer, nullable=False, comment="变更后状态")
    action: Mapped[str] = mapped_column(String(32), nullable=False, comment="动作：create/pay/cancel/auto_close")
    remark: Mapped[str | None] = mapped_column(String(255), comment="备注")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, nullable=False, comment="发生时间")

    def __repr__(self) -> str:
        return f"<OrderLog order_id={self.order_id} {self.from_status}->{self.to_status} {self.action}>"


# ---------- 举报（增量新增：风控需求） ----------
# ---------- 购物车（增量新增：购物车结算需求） ----------
class CartItem(Base):
    """购物车表：同一用户对同一商品只保留一行，重复加入时数量累加"""
    __tablename__ = "cart_item"
    __table_args__ = (UniqueConstraint("user_id", "goods_id", name="uk_cart_user_goods"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True, comment="购物车项ID")
    user_id: Mapped[int] = mapped_column(ForeignKey("user.id"), nullable=False, index=True, comment="用户ID")
    goods_id: Mapped[int] = mapped_column(ForeignKey("goods.id"), nullable=False, index=True, comment="商品ID")
    quantity: Mapped[int] = mapped_column(Integer, default=1, nullable=False, comment="数量")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, nullable=False, comment="加入时间")

    def __repr__(self) -> str:
        return f"<CartItem id={self.id} user={self.user_id} goods={self.goods_id} x{self.quantity}>"


# ---------- 聊天（增量新增：砍价 / 换物互动需求） ----------
class ChatMessage(Base):
    """聊天消息表：按 (商品, 买卖双方) 组成会话。

    msg_type：
    - text 普通文字
    - bargain 买家出价（extra: {"price": "199.00"}）
    - bargain_accept / bargain_reject 卖家回应（extra: {"ref": 原消息ID, "price": ...}）
    - swap 发起以物换物（extra: {"my_goods_id": 12, "my_goods_title": "..."}）
    - swap_accept / swap_reject 对方回应（extra: {"ref": 原消息ID}）
    """
    __tablename__ = "chat_message"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True, comment="消息ID")
    goods_id: Mapped[int] = mapped_column(ForeignKey("goods.id"), nullable=False, index=True, comment="关联商品ID")
    sender_id: Mapped[int] = mapped_column(ForeignKey("user.id"), nullable=False, index=True, comment="发送者ID")
    receiver_id: Mapped[int] = mapped_column(ForeignKey("user.id"), nullable=False, index=True, comment="接收者ID")
    msg_type: Mapped[str] = mapped_column(String(20), default="text", nullable=False,
                                          comment="text/bargain/bargain_accept/bargain_reject/swap/swap_accept/swap_reject")
    content: Mapped[str] = mapped_column(String(500), nullable=False, comment="消息内容")
    extra: Mapped[str | None] = mapped_column(Text, comment="扩展信息（JSON：出价/换物商品/回复引用）")
    read_at: Mapped[datetime | None] = mapped_column(DateTime, comment="对方阅读时间")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, nullable=False, comment="发送时间")

    def __repr__(self) -> str:
        return f"<ChatMessage id={self.id} goods={self.goods_id} {self.sender_id}->{self.receiver_id}>"


class Report(Base):
    """举报表：24 小时去重语义由 Redis TTL 控制，本表只存举报流水。

    注意：不能对 (user_id, target_type, target_id) 建唯一约束，
    否则 24 小时后无法再次举报，与业务规则冲突；这里只建普通联合索引用于查询。
    """
    __tablename__ = "report"
    __table_args__ = (Index("idx_report_target", "target_type", "target_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True, comment="举报ID")
    user_id: Mapped[int] = mapped_column(ForeignKey("user.id"), nullable=False, index=True, comment="举报人ID")
    target_type: Mapped[str] = mapped_column(String(16), nullable=False, comment="举报对象类型：goods/user/message")
    target_id: Mapped[int] = mapped_column(Integer, nullable=False, comment="举报对象ID")
    reason: Mapped[str] = mapped_column(String(200), nullable=False, comment="举报原因")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, nullable=False, comment="举报时间")

    def __repr__(self) -> str:
        return f"<Report id={self.id} {self.target_type}:{self.target_id} by={self.user_id}>"


# ---------- 管理员角色（增量新增：任务8 管理后台看板） ----------
class AdminRole(Base):
    """管理员角色表：一个用户对应一条角色记录，合法值 admin / super_admin。

    新表，不改动 User 模型与 auth.py 的任何既有逻辑。
    """
    __tablename__ = "admin_role"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True, comment="主键")
    user_id: Mapped[int] = mapped_column(ForeignKey("user.id"), nullable=False, unique=True,
                                        index=True, comment="用户ID")
    role: Mapped[str] = mapped_column(String(20), nullable=False,
                                      comment="角色：admin 管理员 / super_admin 超级管理员")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, nullable=False, comment="授权时间")

    def __repr__(self) -> str:
        return f"<AdminRole user_id={self.user_id} role={self.role}>"


# ---------- 管理后台扩展（增量新增：任务10 用户/审核/举报/订单监管） ----------
class GoodsAuditLog(Base):
    """商品审核流水：每次提交审核/通过/驳回各记一条，便于追溯。"""
    __tablename__ = "goods_audit_log"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True, comment="流水ID")
    goods_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True, comment="商品ID")
    goods_title: Mapped[str] = mapped_column(String(100), nullable=False, comment="审核时商品标题快照")
    from_status: Mapped[int] = mapped_column(Integer, nullable=False, comment="变更前状态")
    to_status: Mapped[int] = mapped_column(Integer, nullable=False, comment="变更后状态")
    action: Mapped[str] = mapped_column(String(16), nullable=False, comment="动作：submit/approve/reject")
    remark: Mapped[str | None] = mapped_column(String(255), comment="审核备注")
    operator_id: Mapped[int] = mapped_column(Integer, nullable=False, comment="操作管理员ID")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, nullable=False, comment="时间")

    def __repr__(self) -> str:
        return f"<GoodsAuditLog goods={self.goods_id} {self.from_status}->{self.to_status} {self.action}>"


class ReportHandle(Base):
    """举报处理记录：一条举报对应一条处理记录（无待处理行即代表待处理）。"""
    __tablename__ = "report_handle"
    __table_args__ = (UniqueConstraint("report_id", name="uk_report_handle_report"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True, comment="主键")
    report_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True, comment="举报ID")
    action: Mapped[str] = mapped_column(String(16), nullable=False, comment="处理：processed 已处理 / ignored 已忽略")
    remark: Mapped[str | None] = mapped_column(String(255), comment="处理备注")
    handler_id: Mapped[int] = mapped_column(Integer, nullable=False, comment="处理管理员ID")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, nullable=False, comment="处理时间")
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, onupdate=datetime.now, nullable=False, comment="更新时间")

    def __repr__(self) -> str:
        return f"<ReportHandle report={self.report_id} {self.action}>"

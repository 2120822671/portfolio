from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field


# ---------- 用户 ----------
class UserRegister(BaseModel):
    username: str = Field(min_length=3, max_length=50, description="登录用户名")
    password: str = Field(min_length=6, max_length=64, description="登录密码（至少6位）")
    nickname: str | None = Field(default=None, max_length=50, description="昵称")
    phone: str | None = Field(default=None, max_length=20, description="手机号")


class UserLogin(BaseModel):
    username: str
    password: str


# ---------- 商品 ----------
class GoodsCreate(BaseModel):
    """发布商品：名称/价格/分类/库存/描述必填，价格>0，库存非负整数"""
    title: str = Field(min_length=1, max_length=100, description="商品标题")
    price: Decimal = Field(gt=0, description="售价（元），必须大于0")
    category_id: int = Field(description="分类ID（必传）")
    seller_id: int = Field(description="发布人ID（必传）")
    description: str = Field(min_length=1, max_length=2000, description="详细描述（必填）")
    stock: int = Field(default=1, ge=0, description="库存数量（非负整数）")
    original_price: Decimal | None = Field(default=None, gt=0, description="原价（元）")
    location: str | None = Field(default=None, max_length=100, description="交易地点")
    contact: str | None = Field(default=None, max_length=50, description="联系方式")
    images: list[str] = Field(default_factory=list, description="图片URL列表（先经 /upload 上传）")


class StatusUpdate(BaseModel):
    action: Literal["off", "on", "sold"] = Field(description="off下架 on重新上架 sold标记已售")


class MessageCreate(BaseModel):
    content: str = Field(min_length=1, max_length=500, description="留言内容")


# ---------- 收藏统计补偿（增量新增） ----------
class FavoriteSyncIn(BaseModel):
    """收藏统计补偿入参：goods_id 可选，不传则全量补偿"""
    goods_id: int | None = Field(default=None, description="商品ID；不传=全量同步，传入=仅同步该商品")


# ---------- 订单（增量新增：定时关单需求） ----------
class OrderCreate(BaseModel):
    """下单入参：商品ID + 买家ID"""
    goods_id: int = Field(description="商品ID（必须是「在售」状态）")
    buyer_id: int = Field(description="买家ID（不能是商品发布人本人）")


# ---------- 购物车（增量新增：购物车结算需求） ----------
class CartAdd(BaseModel):
    """加入购物车：商品ID + 数量"""
    goods_id: int = Field(description="商品ID")
    quantity: int = Field(default=1, ge=1, le=99, description="数量（1~99）")


class CartUpdate(BaseModel):
    """修改购物车数量"""
    quantity: int = Field(ge=1, le=99, description="数量（1~99）")


class OrderBatchCreate(BaseModel):
    """购物车批量结算：一次为多件商品生成订单并模拟支付"""
    buyer_id: int = Field(description="买家ID（必须是登录本人）")
    goods_ids: list[int] = Field(min_length=1, max_length=20, description="要结算的商品ID列表")
    pay_method: str = Field(default="campus_card", max_length=20,
                            description="支付方式：campus_card/wechat/alipay/cash")


class OrderPayIn(BaseModel):
    """支付订单时选择支付方式（可选）"""
    pay_method: str | None = Field(default=None, max_length=20, description="支付方式")


# ---------- 聊天（增量新增：砍价 / 换物互动） ----------
class ChatSend(BaseModel):
    goods_id: int = Field(description="关联商品ID")
    to_user_id: int = Field(description="接收者ID（商品卖家或买家）")
    content: str = Field(min_length=1, max_length=500, description="消息内容")
    msg_type: Literal["text", "bargain", "bargain_accept", "bargain_reject",
                      "swap", "swap_accept", "swap_reject"] = Field(default="text", description="消息类型")
    extra: dict | None = Field(default=None, description="扩展信息：出价金额 / 换物商品 / 回复引用")


# ---------- 举报（增量新增：风控需求） ----------
class ReportCreate(BaseModel):
    """举报入参：类型用 str 而非 Literal，便于在路由内返回 400 而非 422"""
    target_type: str = Field(min_length=1, max_length=16, description="举报对象类型：goods/user/message")
    target_id: int = Field(gt=0, description="举报对象ID")
    reason: str = Field(min_length=1, max_length=200, description="举报原因")


# ---------- 管理后台看板（增量新增：任务8） ----------
class AdminDashboardData(BaseModel):
    """管理员看板统计指标：四项均为整数计数"""
    today_new_users: int = Field(description="今日新增注册用户数")
    today_new_goods: int = Field(description="今日新增发布商品数")
    today_orders: int = Field(description="今日产生订单总数")
    pending_goods: int = Field(description="待审核商品总数（status=1）")


# ---------- 管理后台扩展（增量新增：任务10） ----------
class AdminUserStatusIn(BaseModel):
    """用户状态变更：1正常 0冻结（复用 user.status 字段）"""
    status: int = Field(ge=0, le=1, description="状态：1正常 0冻结")


class AdminAuditIn(BaseModel):
    """商品审核入参"""
    action: str = Field(min_length=1, max_length=16, description="审核动作：approve 通过 / reject 驳回")
    remark: str | None = Field(default=None, max_length=255, description="审核备注")


class AdminReportHandleIn(BaseModel):
    """举报处理入参"""
    action: str = Field(min_length=1, max_length=16, description="处理动作：processed 已处理 / ignored 已忽略")
    remark: str | None = Field(default=None, max_length=255, description="处理备注")

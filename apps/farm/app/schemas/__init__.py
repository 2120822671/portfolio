"""
Pydantic DTO 包 —— 接口契约层

⚠️ 设计原则:
    - schemas 只负责接口数据结构定义，绝不混入数据库操作
    - ORM model 和 Pydantic schema 分离：model 是表结构，schema 是 API 契约
    - 每个 schema 文件按业务模块划分，与 routers/ 一一对应
"""
from app.schemas.common import ApiResponse, MessageResponse
from app.schemas.user import (
    UserRegister,
    UserLogin,
    UserLoginResponse,
    UserInfoResponse,
    PasswordChange,
)
from app.schemas.farm import (
    FarmCellResponse,
    FarmStatusResponse,
    FarmPlantRequest,
    FarmHarvestRequest,
    FarmExpandResponse,
)
from app.schemas.shop import (
    ShopItemResponse,
    ShopBuyRequest,
    ShopSellRequest,
)
from app.schemas.inventory import (
    InventoryItemResponse,
    InventoryListResponse,
)
from app.schemas.task import (
    DailyTaskResponse,
    DailyTaskListResponse,
    DailyTaskClaimResponse,
)
from app.schemas.admin import (
    AdminUserListResponse,
    AdminCropTemplateRequest,
    AdminAnimalTemplateRequest,
    AdminShopItemRequest,
    AdminStatsResponse,
)

__all__ = [
    # common
    "ApiResponse", "MessageResponse",
    # user
    "UserRegister", "UserLogin", "UserLoginResponse", "UserInfoResponse", "PasswordChange",
    # farm
    "FarmCellResponse", "FarmStatusResponse", "FarmPlantRequest",
    "FarmHarvestRequest", "FarmExpandResponse",
    # shop
    "ShopItemResponse", "ShopBuyRequest", "ShopSellRequest",
    # inventory
    "InventoryItemResponse", "InventoryListResponse",
    # task
    "DailyTaskResponse", "DailyTaskListResponse", "DailyTaskClaimResponse",
    # admin
    "AdminUserListResponse", "AdminCropTemplateRequest",
    "AdminAnimalTemplateRequest", "AdminShopItemRequest", "AdminStatsResponse",
]

"""
ORM 模型包

⚠️ 关键规则（来自多次踩坑经验）:
    1. 此文件必须集中 import 所有 models —— 否则 Base.metadata.create_all() 看不到新表！
    2. 如果新增了一个 ORM 模型文件，必须在这里 import 它
    3. 新增模型后，需要重新运行程序让 create_all 执行
"""
from __future__ import annotations


def _ensure_all_models_imported() -> None:
    """
    空函数 —— 但本文件顶部的 import 语句会在此函数被引用时
    触发 SQLAlchemy 的元数据注册。

    database.init_db() 中调用此函数，确保所有模型都已被加载。
    """
    pass


# ============================================================
# 所有模型必须集中 import 在这里！
# ============================================================
from app.models.user import User  # noqa: E402
from app.models.crop import CropTemplate  # noqa: E402
from app.models.animal import AnimalTemplate, PlayerAnimal  # noqa: E402
from app.models.farm import FarmCell  # noqa: E402
from app.models.inventory import Inventory  # noqa: E402
from app.models.shop import ShopItem  # noqa: E402
from app.models.task import DailyTaskProgress  # noqa: E402

__all__ = [
    "User",
    "CropTemplate",
    "AnimalTemplate",
    "PlayerAnimal",
    "FarmCell",
    "Inventory",
    "ShopItem",
    "DailyTaskProgress",
]

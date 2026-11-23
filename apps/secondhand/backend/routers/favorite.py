"""收藏统计补偿模块（增量新增）

功能：重新统计每件商品的真实收藏数量，同步更新 goods.favorite_count。
说明：仅新增本文件，不改动原有用户 / 商品 / 点赞 / 留言 / 上传 / 统计等任何业务。
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select

from database import get_db
from models import Goods, GoodsLike
from resp import ok
from schemas import FavoriteSyncIn

# 独立前缀，避免与既有 /goods 路由冲突；完整路径 = /api/v1/products/favorite-sync
router = APIRouter(prefix="/api/v1/products", tags=["收藏补偿"])


@router.post("/favorite-sync", summary="商品收藏统计补偿（重算并回写 favorite_count）")
def favorite_sync(payload: FavoriteSyncIn | None = None, db=Depends(get_db)):
    """重新统计商品收藏数量并回写 goods.favorite_count。

    逻辑：
    - 数据来源为 goods_like（收藏/点赞明细），按 goods_id 分组 COUNT(*) 得真实收藏数；
      统计时 INNER JOIN goods，只统计商品表中真实存在的商品，孤儿记录不计入；
    - 不传 goods_id：全量补偿——先把所有商品 favorite_count 归零，再按统计结果回写，保证无残留脏值；
    - 传 goods_id：仅补偿该商品，商品不存在返回 404；
    - 无收藏记录的商品回写 0；不修改 like_count 及任何其它字段；
    - 返回 scope 标注统计范围；total_favorites = 本次范围内有效收藏合计；
      orphan_favorites = 未匹配到有效商品的脏记录数（仅提示，不删除）。
    """
    target_id = payload.goods_id if payload else None

    # 校验单商品存在性
    if target_id is not None:
        if db.get(Goods, target_id) is None:
            raise HTTPException(status_code=404, detail="商品不存在")

    # 统计每个商品的真实收藏数：goods_id -> count
    # 修复：INNER JOIN goods，统计口径与商品表对齐；goods_id 指向不存在商品的脏记录
    #       （历史导入 / 关闭外键检查遗留）不再被计入合计
    stmt = (
        select(GoodsLike.goods_id, func.count(GoodsLike.id))
        .join(Goods, Goods.id == GoodsLike.goods_id)
        .group_by(GoodsLike.goods_id)
    )
    if target_id is not None:
        stmt = stmt.where(GoodsLike.goods_id == target_id)
    counted = {gid: cnt for gid, cnt in db.execute(stmt).all()}

    # 孤儿收藏：goods_id 在 goods 表中不存在，仅统计提示，不计入合计、不自动删除
    orphan_favorites = db.scalar(
        select(func.count(GoodsLike.id))
        .outerjoin(Goods, Goods.id == GoodsLike.goods_id)
        .where(Goods.id.is_(None))
    ) or 0

    # 目标商品集合
    goods_stmt = select(Goods)
    if target_id is not None:
        goods_stmt = goods_stmt.where(Goods.id == target_id)
    goods_list = db.scalars(goods_stmt).all()

    updated = 0
    for g in goods_list:
        real = counted.get(g.id, 0)
        if g.favorite_count != real:      # 仅在实际变化时写，幂等
            g.favorite_count = real
            updated += 1
    db.commit()

    return ok(
        {
            # 显式标注本次统计范围，避免 total_favorites 语义随入参漂移
            "scope": "single" if target_id is not None else "all",
            "scanned_products": len(goods_list),
            "updated_products": updated,
            # 语义固定：本次同步范围内的有效收藏合计（不含孤儿记录）
            "total_favorites": sum(counted.values()),
            # 未匹配到有效商品的脏记录数，不计入合计，供运维排查
            "orphan_favorites": orphan_favorites,
        },
        "收藏统计同步完成",
    )

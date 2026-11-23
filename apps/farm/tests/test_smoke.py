"""
核心玩法冒烟测试

覆盖本次优化的关键回归点:
    1. 作物 购买 → 播种 → 成熟 → 收获 → 出售 全链路
    2. 动物 购买 → 生产 → 采集 → 喂养 闭环
    3. 动物产物按自身单价出售（不再被当成作物）
    4. 成熟超时枯萎与清理
    5. 参数校验错误结构、扩建数量限制
"""
from __future__ import annotations

import uuid
from datetime import timedelta

import pytest
from sqlalchemy import select

from app.database import AsyncSessionLocal
from app.models.animal import PlayerAnimal
from app.models.farm import FarmCell
from app.models.user import User
from app.utils.time_utils import now_utc


API = "/api/v1"


async def register_and_login(client, prefix: str) -> tuple[str, dict]:
    username = f"{prefix}_{uuid.uuid4().hex[:8]}"
    password = "secret123"

    r = await client.post(f"{API}/auth/register", json={
        "username": username, "password": password,
    })
    assert r.status_code == 201, r.text

    r = await client.post(f"{API}/auth/login", json={
        "username": username, "password": password,
    })
    assert r.status_code == 200, r.text
    token = r.json()["access_token"]

    return username, {"Authorization": f"Bearer {token}"}


async def get_user_id(username: str) -> int:
    async with AsyncSessionLocal() as db:
        user = (await db.execute(
            select(User).where(User.username == username)
        )).scalar_one()
        return user.id


async def set_user_gold(username: str, gold: int) -> None:
    async with AsyncSessionLocal() as db:
        user = (await db.execute(
            select(User).where(User.username == username)
        )).scalar_one()
        user.gold = gold
        await db.commit()


async def force_cell_ready(username: str, cell_index: int, seconds_ago: int) -> None:
    user_id = await get_user_id(username)
    async with AsyncSessionLocal() as db:
        cell = (await db.execute(
            select(FarmCell).where(
                FarmCell.user_id == user_id,
                FarmCell.cell_index == cell_index,
            )
        )).scalar_one()
        cell.ready_at = now_utc() - timedelta(seconds=seconds_ago)
        await db.commit()


async def force_animal_ready(username: str, seconds_ago: int) -> None:
    user_id = await get_user_id(username)
    async with AsyncSessionLocal() as db:
        animal = (await db.execute(
            select(PlayerAnimal).where(PlayerAnimal.user_id == user_id)
        )).scalars().first()
        assert animal is not None
        animal.last_produce_at = now_utc() - timedelta(seconds=seconds_ago)
        await db.commit()


def find_item(items: list[dict], **conditions) -> dict:
    for item in items:
        if all(item.get(k) == v for k, v in conditions.items()):
            return item
    raise AssertionError(f"未找到商品: {conditions}")


@pytest.mark.asyncio
async def test_crop_flow_wither_and_wealth(client):
    username, headers = await register_and_login(client, "crop")

    # 初始农场
    farm = (await client.get(f"{API}/farm/", headers=headers)).json()
    assert farm["cell_count"] == 3
    assert len(farm["cells"]) == 3

    # 购买 2 份小麦种子
    shop = (await client.get(f"{API}/shop/items")).json()["items"]
    wheat_seed = find_item(shop, item_type="seed", template_id=1)
    r = await client.post(f"{API}/shop/buy", headers=headers, json={
        "item_id": wheat_seed["id"], "quantity": 2,
    })
    assert r.status_code == 200, r.text
    assert r.json()["gold_remaining"] == 80

    # 播种
    r = await client.post(f"{API}/farm/plant", headers=headers, json={
        "cell_index": 0, "template_id": 1,
    })
    assert r.status_code == 200, r.text

    # 强制成熟（仍在 24h 枯萎宽限期内）
    await force_cell_ready(username, 0, seconds_ago=10)
    farm = (await client.get(f"{API}/farm/", headers=headers)).json()
    cell0 = next(c for c in farm["cells"] if c["cell_index"] == 0)
    assert cell0["status"] == "ready"
    assert cell0["seconds_until_wither"] > 0

    # 收获 → 背包产物
    r = await client.post(f"{API}/farm/harvest", headers=headers, json={"cell_index": 0})
    assert r.status_code == 200, r.text

    inv = (await client.get(f"{API}/inventory/", headers=headers)).json()
    produce = next(i for i in inv["items"] if i["item_type"] == "produce")
    assert produce["item_name"] == "小麦颗粒"
    assert produce["quantity"] == 3
    assert produce["sell_price_per_unit"] == 5

    # 出售产物
    r = await client.post(f"{API}/shop/sell", headers=headers, json={
        "inventory_id": produce["id"], "quantity": 3,
    })
    assert r.status_code == 200, r.text
    assert r.json()["gold_earned"] == 15
    assert r.json()["gold_remaining"] == 95

    # 任务进度按实际产出数量累计
    tasks = (await client.get(f"{API}/tasks/daily", headers=headers)).json()["tasks"]
    harvest_task = next(t for t in tasks if t["task_type"] == "harvest")
    assert harvest_task["progress"] == 3

    # 财富榜 = 金币 + 仓库价值（剩余 1 份种子）
    rank = (await client.get(f"{API}/rank/wealth")).json()["list"]
    me = next(row for row in rank if row["username"] == username)
    assert me["gold"] == 95
    assert me["inventory_value"] >= 10
    assert me["wealth"] == me["gold"] + me["inventory_value"]

    # 再种一格并模拟超时，验证枯萎 + 清理
    r = await client.post(f"{API}/farm/plant", headers=headers, json={
        "cell_index": 1, "template_id": 1,
    })
    assert r.status_code == 200, r.text

    await force_cell_ready(username, 1, seconds_ago=25 * 3600)
    farm = (await client.get(f"{API}/farm/", headers=headers)).json()
    cell1 = next(c for c in farm["cells"] if c["cell_index"] == 1)
    assert cell1["status"] == "withered"

    r = await client.post(f"{API}/farm/harvest", headers=headers, json={"cell_index": 1})
    assert r.status_code == 400
    assert "枯萎" in r.json()["message"]

    r = await client.post(f"{API}/farm/clear/1", headers=headers)
    assert r.status_code == 200, r.text


@pytest.mark.asyncio
async def test_animal_flow_and_produce_price(client):
    username, headers = await register_and_login(client, "animal")
    await set_user_gold(username, 1000)

    shop = (await client.get(f"{API}/shop/items")).json()["items"]
    chicken = find_item(shop, item_type="animal", template_id=1)
    feed = find_item(shop, item_type="feed")

    # 买 1 只鸡 + 2 份饲料
    r = await client.post(f"{API}/shop/buy", headers=headers, json={
        "item_id": chicken["id"], "quantity": 1,
    })
    assert r.status_code == 200, r.text
    r = await client.post(f"{API}/shop/buy", headers=headers, json={
        "item_id": feed["id"], "quantity": 2,
    })
    assert r.status_code == 200, r.text

    # 购买后自动进入生产
    animals = (await client.get(f"{API}/animals/", headers=headers)).json()
    assert animals["total"] == 1
    assert animals["animals"][0]["state"] == "producing"

    # 生产中的动物不应被“喂养”重置
    r = await client.post(f"{API}/animals/feed", headers=headers)
    assert r.status_code == 200
    assert "不需要喂养" in r.json()["message"] or "都在生产中" in r.json()["message"]

    # 强制完成本轮生产并采集
    await force_animal_ready(username, seconds_ago=4000)
    animals = (await client.get(f"{API}/animals/", headers=headers)).json()
    assert animals["animals"][0]["state"] == "ready"

    animal_id = animals["animals"][0]["id"]
    r = await client.post(f"{API}/animals/collect/{animal_id}", headers=headers)
    assert r.status_code == 200, r.text

    # 采集后待喂养
    animals = (await client.get(f"{API}/animals/", headers=headers)).json()
    assert animals["animals"][0]["state"] == "hungry"

    # 喂养消耗 1 份饲料并开始下一轮
    r = await client.post(f"{API}/animals/feed", headers=headers)
    assert r.status_code == 200, r.text
    assert "已喂养" in r.json()["message"]

    inv = (await client.get(f"{API}/inventory/", headers=headers)).json()
    feed_item = next(i for i in inv["items"] if i["item_type"] == "feed")
    assert feed_item["quantity"] == 1

    # 第二轮采集，得到 2 个鸡蛋
    await force_animal_ready(username, seconds_ago=4000)
    r = await client.post(f"{API}/animals/collect/{animal_id}", headers=headers)
    assert r.status_code == 200, r.text

    inv = (await client.get(f"{API}/inventory/", headers=headers)).json()
    egg = next(i for i in inv["items"] if i["item_name"] == "鸡蛋")
    assert egg["quantity"] == 2
    assert egg["template_id"] < 0, "动物产物应使用负模板 id，避免与作物撞号"
    assert egg["sell_price_per_unit"] == 30, "鸡蛋必须按自身单价出售"
    assert egg["emoji"] == "🥚"

    # 按 30 金币 / 个出售，而不是小麦的 5
    r = await client.post(f"{API}/shop/sell", headers=headers, json={
        "inventory_id": egg["id"], "quantity": 1,
    })
    assert r.status_code == 200, r.text
    assert r.json()["gold_earned"] == 30


@pytest.mark.asyncio
async def test_validation_shape_and_expand_guard(client):
    # 非法用户名 → 422，返回统一 message
    r = await client.post(f"{API}/auth/register", json={
        "username": "ab", "password": "secret123",
    })
    assert r.status_code == 422
    body = r.json()
    assert body["code"] == 422
    assert body["message"]

    _, headers = await register_and_login(client, "guard")
    shop = (await client.get(f"{API}/shop/items")).json()["items"]
    expansion = find_item(shop, item_type="expansion")

    # 扩建一次只能买 1 块
    r = await client.post(f"{API}/shop/buy", headers=headers, json={
        "item_id": expansion["id"], "quantity": 2,
    })
    assert r.status_code == 400
    assert "1 块" in r.json()["message"]

    # 新玩家金币不足 → 扣费前就拦截
    r = await client.post(f"{API}/shop/buy", headers=headers, json={
        "item_id": expansion["id"], "quantity": 1,
    })
    assert r.status_code == 400
    assert "金币不足" in r.json()["message"]

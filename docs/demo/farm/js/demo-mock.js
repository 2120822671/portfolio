/* 像素农场 · 静态演示版 mock 层
   接管 /api/v1 请求，用内存数据模拟完整后端；刷新页面即还原。 */
(function () {
  "use strict";

  const CROPS = {
    1: { name: "胡萝卜", emoji: "🥕", sell: 18 },
    2: { name: "小麦", emoji: "🌾", sell: 12 },
    3: { name: "番茄", emoji: "🍅", sell: 25 },
    4: { name: "玉米", emoji: "🌽", sell: 32 },
    5: { name: "南瓜", emoji: "🎃", sell: 45 },
  };

  const now = () => Date.now();
  const user = { username: "demo", level: 5, gold: 2680, cell_count: 8 };
  const MAX_CELLS = 25;
  const EXPAND_PRICE = 500;

  const cells = [
    { cell_index: 0, status: "ready", crop_id: 2 },
    { cell_index: 1, status: "ready", crop_id: 1 },
    { cell_index: 2, status: "growing", crop_id: 3, ready_at: now() + 46000 },
    { cell_index: 3, status: "growing", crop_id: 4, ready_at: now() + 125000 },
    { cell_index: 4, status: "growing", crop_id: 5, ready_at: now() + 305000 },
    { cell_index: 5, status: "empty" },
    { cell_index: 6, status: "empty" },
    { cell_index: 7, status: "withered" },
  ];

  const shopItems = [
    { id: 1, name: "胡萝卜种子", emoji: "🥕", price: 20, stock: -1, item_type: "seed", description: "生长快，18 金币/个" },
    { id: 2, name: "小麦种子", emoji: "🌾", price: 15, stock: -1, item_type: "seed", description: "基础作物，稳定收益" },
    { id: 3, name: "番茄种子", emoji: "🍅", price: 30, stock: -1, item_type: "seed", description: "中周期，25 金币/个" },
    { id: 4, name: "玉米种子", emoji: "🌽", price: 40, stock: -1, item_type: "seed", description: "高收益作物" },
    { id: 5, name: "南瓜种子", emoji: "🎃", price: 60, stock: -1, item_type: "seed", description: "慢熟，单价最高" },
    { id: 6, name: "小鸡", emoji: "🐔", price: 300, stock: 5, item_type: "animal", description: "产鸡蛋，需喂养" },
    { id: 7, name: "奶牛", emoji: "🐄", price: 800, stock: 3, item_type: "animal", description: "产牛奶，收益更高" },
    { id: 8, name: "饲料", emoji: "🍚", price: 5, stock: -1, item_type: "feed", description: "喂养动物消耗" },
    { id: 9, name: "扩建令", emoji: "🟩", price: EXPAND_PRICE, stock: -1, item_type: "expansion", description: "增加一块土地" },
  ];

  let invId = 100;
  const inventory = [
    { id: invId++, template_id: 1, item_type: "seed", item_name: "胡萝卜种子", emoji: "🥕", quantity: 5 },
    { id: invId++, template_id: 2, item_type: "seed", item_name: "小麦种子", emoji: "🌾", quantity: 8 },
    { id: invId++, template_id: 3, item_type: "seed", item_name: "番茄种子", emoji: "🍅", quantity: 3 },
    { id: invId++, template_id: 8, item_type: "feed", item_name: "饲料", emoji: "🍚", quantity: 10 },
    { id: invId++, item_type: "produce", item_name: "小麦", emoji: "🌾", quantity: 12, sell_price_per_unit: 12 },
    { id: invId++, item_type: "produce", item_name: "胡萝卜", emoji: "🥕", quantity: 6, sell_price_per_unit: 18 },
  ];

  const tasks = [
    { task_type: "login", task_name: "每日登录", progress: 1, target: 1, reward_gold: 50, is_completed: true, is_claimed: false },
    { task_type: "plant", task_name: "播种 5 次", progress: 2, target: 5, reward_gold: 60, is_completed: false, is_claimed: false },
    { task_type: "harvest", task_name: "收获 3 次", progress: 1, target: 3, reward_gold: 80, is_completed: false, is_claimed: false },
    { task_type: "buy", task_name: "商店购买 2 次", progress: 1, target: 2, reward_gold: 40, is_completed: false, is_claimed: false },
    { task_type: "feed", task_name: "喂养动物 1 次", progress: 0, target: 1, reward_gold: 30, is_completed: false, is_claimed: false },
  ];

  let animalId = 1;
  const animals = [
    { id: animalId++, name: "小鸡", emoji: "🐔", state: "producing", produce_name: "鸡蛋", produce_emoji: "🥚", produce_sell_price: 15, feed_consumption: 2, ready_at: now() + 40000 },
    { id: animalId++, name: "奶牛", emoji: "🐄", state: "ready", produce_name: "牛奶", produce_emoji: "🥛", produce_sell_price: 40, feed_consumption: 3, ready_at: 0 },
  ];

  const ranks = [
    { username: "farmer_wang", gold: 12800, inventory_value: 3200 },
    { username: "农夫老李", gold: 9600, inventory_value: 2100 },
    { username: "demo", gold: user.gold, inventory_value: 520 },
    { username: "种田小能手", gold: 2100, inventory_value: 1500 },
    { username: "pixel_cat", gold: 1800, inventory_value: 900 },
    { username: "凌晨四点", gold: 1200, inventory_value: 400 },
    { username: "麦田守望者", gold: 980, inventory_value: 600 },
    { username: "玉米大王", gold: 750, inventory_value: 300 },
  ];

  const json = (data, status) =>
    new Response(JSON.stringify(data), {
      status: status || 200,
      headers: { "Content-Type": "application/json" },
    });

  const findInv = (predicate) => inventory.find(predicate);
  const cropOf = (c) => CROPS[c.crop_id] || { name: "作物", emoji: "🌱", sell: 10 };

  function addProduce(name, emoji, qty, sell) {
    const item = findInv((i) => i.item_type === "produce" && i.item_name === name);
    if (item) item.quantity += qty;
    else inventory.push({ id: invId++, item_type: "produce", item_name: name, emoji, quantity: qty, sell_price_per_unit: sell });
  }

  function farmSnapshot() {
    const ts = now();
    return {
      cell_count: user.cell_count,
      max_cell_count: MAX_CELLS,
      cells: cells.map((c) => {
        if (c.status === "growing") {
          const remain = Math.max(0, Math.ceil((c.ready_at - ts) / 1000));
          if (remain === 0) {
            c.status = "ready";
            c.wither_at = ts + 86400000;
          }
          return {
            cell_index: c.cell_index,
            status: c.status,
            crop_emoji: cropOf(c).emoji,
            seconds_until_ready: remain,
          };
        }
        return {
          cell_index: c.cell_index,
          status: c.status,
          crop_emoji: c.status === "ready" ? cropOf(c).emoji : null,
          seconds_until_ready: 0,
          seconds_until_wither: c.status === "ready" ? 86400 : 0,
        };
      }),
    };
  }

  function animalSnapshot() {
    const ts = now();
    return animals.map((a) => {
      let state = a.state;
      if (state === "producing") {
        const remain = Math.max(0, Math.ceil((a.ready_at - ts) / 1000));
        if (remain === 0) {
          state = "ready";
          a.state = "ready";
        }
        return { ...a, state, ready_in_seconds: remain };
      }
      return { ...a, ready_in_seconds: 0 };
    });
  }

  const realFetch = window.fetch.bind(window);

  window.fetch = function (input, init) {
    const url = typeof input === "string" ? input : (input && input.url) || "";
    if (!url.includes("/api/v1/")) return realFetch(input, init);

    const method = ((init && init.method) || "GET").toUpperCase();
    const headers = (init && init.headers) || {};
    const auth = headers.Authorization || headers.authorization || "";
    const body = init && init.body ? JSON.parse(init.body) : {};
    const path = url.split("/api/v1")[1].split("?")[0].replace(/\/+$/, "") || "/";

    if (!auth && path !== "/auth/login" && path !== "/auth/register") {
      return Promise.resolve(json({ message: "未登录" }, 401));
    }

    // ---- 账号 ----
    if (path === "/auth/register" && method === "POST") {
      return Promise.resolve(json({ message: "注册成功" }));
    }
    if (path === "/auth/login" && method === "POST") {
      user.username = body.username || "demo";
      user.gold = 2680;
      return Promise.resolve(json({ access_token: "demo-token" }));
    }
    if (path === "/auth/me") {
      return Promise.resolve(json({ ...user }));
    }

    // ---- 农场 ----
    if (path === "/farm" && method === "GET") {
      return Promise.resolve(json(farmSnapshot()));
    }
    if (path === "/farm/plant" && method === "POST") {
      const cell = cells.find((c) => c.cell_index === body.cell_index);
      const seed = findInv((i) => i.template_id === body.template_id && i.item_type === "seed" && i.quantity > 0);
      if (!cell || !seed) return Promise.resolve(json({ message: "种子不足" }, 400));
      seed.quantity -= 1;
      cell.status = "growing";
      cell.crop_id = body.template_id;
      cell.ready_at = now() + 60000;
      const task = tasks.find((t) => t.task_type === "plant");
      if (task) { task.progress = Math.min(task.target, task.progress + 1); task.is_completed = task.progress >= task.target; }
      return Promise.resolve(json({ message: "播种成功" }));
    }
    if (path === "/farm/harvest" && method === "POST") {
      const cell = cells.find((c) => c.cell_index === body.cell_index);
      if (!cell || cell.status !== "ready") return Promise.resolve(json({ message: "该地块不可收获" }, 400));
      const crop = cropOf(cell);
      addProduce(crop.name, crop.emoji, 3, crop.sell);
      cell.status = "empty";
      const task = tasks.find((t) => t.task_type === "harvest");
      if (task) { task.progress = Math.min(task.target, task.progress + 1); task.is_completed = task.progress >= task.target; }
      return Promise.resolve(json({ message: `收获 ${crop.name} ×3` }));
    }
    if (path.startsWith("/farm/clear/") && method === "POST") {
      const idx = Number(path.split("/").pop());
      const cell = cells.find((c) => c.cell_index === idx);
      if (cell) cell.status = "empty";
      return Promise.resolve(json({ message: "已清理" }));
    }
    if (path === "/farm/expand" && method === "POST") {
      if (user.gold < EXPAND_PRICE) return Promise.resolve(json({ message: "金币不足" }, 400));
      if (user.cell_count >= MAX_CELLS) return Promise.resolve(json({ message: "已达上限" }, 400));
      user.gold -= EXPAND_PRICE;
      user.cell_count += 1;
      cells.push({ cell_index: user.cell_count - 1, status: "empty" });
      return Promise.resolve(json({ cell_count_before: user.cell_count - 1, cell_count_after: user.cell_count }));
    }

    // ---- 商店 ----
    if (path === "/shop/items") {
      return Promise.resolve(json({ items: shopItems }));
    }
    if (path === "/shop/buy" && method === "POST") {
      const item = shopItems.find((i) => i.id === body.item_id);
      const qty = Math.max(1, Number(body.quantity) || 1);
      if (!item) return Promise.resolve(json({ message: "商品不存在" }, 400));
      const total = item.price * qty;
      if (total > user.gold) return Promise.resolve(json({ message: "金币不足" }, 400));
      user.gold -= total;
      if (item.item_type === "seed" || item.item_type === "feed") {
        const inv = findInv((i) => i.template_id === item.id && i.item_type === item.item_type);
        if (inv) inv.quantity += qty;
        else inventory.push({ id: invId++, template_id: item.id, item_type: item.item_type, item_name: item.name, emoji: item.emoji, quantity: qty });
      } else if (item.item_type === "animal") {
        animals.push({
          id: animalId++, name: item.name, emoji: item.emoji, state: "hungry",
          produce_name: item.name === "奶牛" ? "牛奶" : "鸡蛋",
          produce_emoji: item.name === "奶牛" ? "🥛" : "🥚",
          produce_sell_price: item.name === "奶牛" ? 40 : 15,
          feed_consumption: item.name === "奶牛" ? 3 : 2,
          ready_at: 0,
        });
      } else if (item.item_type === "expansion") {
        if (user.cell_count < MAX_CELLS) {
          user.cell_count += 1;
          cells.push({ cell_index: user.cell_count - 1, status: "empty" });
        }
      }
      const task = tasks.find((t) => t.task_type === "buy");
      if (task) { task.progress = Math.min(task.target, task.progress + 1); task.is_completed = task.progress >= task.target; }
      return Promise.resolve(json({ gold_spent: total }));
    }
    if (path === "/shop/sell" && method === "POST") {
      const item = findInv((i) => i.id === body.inventory_id);
      const qty = Math.min(item ? item.quantity : 0, Number(body.quantity) || 1);
      if (!item || qty <= 0) return Promise.resolve(json({ message: "物品不足" }, 400));
      item.quantity -= qty;
      const earned = qty * (item.sell_price_per_unit || 0);
      user.gold += earned;
      if (item.quantity <= 0) inventory.splice(inventory.indexOf(item), 1);
      return Promise.resolve(json({ item_name: item.item_name, quantity: qty, gold_earned: earned }));
    }
    if (path === "/inventory") {
      return Promise.resolve(json({ items: inventory.filter((i) => i.quantity > 0) }));
    }

    // ---- 任务 ----
    if (path === "/tasks/daily") {
      return Promise.resolve(json({ tasks }));
    }
    if (path.startsWith("/tasks/claim/") && method === "POST") {
      const type = path.split("/").pop();
      const task = tasks.find((t) => t.task_type === type);
      if (!task || !task.is_completed || task.is_claimed) return Promise.resolve(json({ message: "不可领取" }, 400));
      task.is_claimed = true;
      user.gold += task.reward_gold;
      return Promise.resolve(json({ reward_gold: task.reward_gold }));
    }

    // ---- 排行 ----
    if (path === "/rank/wealth") {
      const list = ranks.map((r) => ({
        ...r,
        gold: r.username === user.username ? user.gold : r.gold,
        wealth: (r.username === user.username ? user.gold : r.gold) + r.inventory_value,
      }));
      list.sort((a, b) => b.wealth - a.wealth);
      return Promise.resolve(json({ list: list.map((r, i) => ({ ...r, rank: i + 1 })) }));
    }

    // ---- 动物 ----
    if (path === "/animals" && method === "GET") {
      return Promise.resolve(json({ animals: animalSnapshot() }));
    }
    if (path === "/animals/feed" && method === "POST") {
      const feed = findInv((i) => i.item_type === "feed" && i.quantity > 0);
      const hungry = animals.filter((a) => a.state === "hungry");
      if (!hungry.length) return Promise.resolve(json({ message: "没有待喂养的动物" }));
      if (!feed) return Promise.resolve(json({ message: "饲料不足，先去商店购买" }, 400));
      hungry.forEach((a) => { a.state = "producing"; a.ready_at = now() + 60000; });
      feed.quantity = Math.max(0, feed.quantity - hungry.length * 2);
      const task = tasks.find((t) => t.task_type === "feed");
      if (task) { task.progress = task.target; task.is_completed = true; }
      return Promise.resolve(json({ message: `已喂养 ${hungry.length} 只动物` }));
    }
    if (path.startsWith("/animals/collect/") && method === "POST") {
      const id = Number(path.split("/").pop());
      const a = animals.find((x) => x.id === id);
      if (!a || a.state !== "ready") return Promise.resolve(json({ message: "暂不可采集" }, 400));
      addProduce(a.produce_name, a.produce_emoji, 3, a.produce_sell_price);
      a.state = "producing";
      a.ready_at = now() + 60000;
      return Promise.resolve(json({ message: `采集 ${a.produce_name} ×3` }));
    }

    return Promise.resolve(json({ message: "演示环境未实现该接口" }, 404));
  };
})();

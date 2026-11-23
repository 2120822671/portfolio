/* ============================================================
   🌾 像素农场 Online — 前端主逻辑

   性能约定:
   - 农场倒计时在前端本地递减，只有归零/操作/定时(30s)/页面重新可见时才请求后端
   - 网格按“状态签名”判断是否需要重建 DOM，否则只更新计时文本
   - 侧栏数据按 Tab 懒加载，首屏不再并行拉取排行榜与背包
   ============================================================ */

// ---------- 全局状态 ----------
const API_BASE = "/farm/api/v1";
const FARM_SYNC_MS = 30000;

let TOKEN = localStorage.getItem("pf_token") || "";
let ME = null;                 // 当前玩家信息
let FARM = null;               // 农场快照
let SHOP_ITEMS = [];           // 商店商品缓存
let ANIMALS = [];              // 动物列表缓存
let TASKS = null;              // 每日任务缓存
let EXPAND_PRICE = 500;        // 扩建价格（从商店读取）
let CURRENT_TAB = "shop";
let SELECTED_CELL = null;      // { index, status }

let farmSignature = "";
let farmInFlight = false;
let syncTimer = null;          // 农场防抖同步
let tickTimer = null;
let pollTimer = null;
let loginRewardTried = false;

let BUYING = false;
let BUY_STATE = { item: null, qty: 1, max: 1, affordable: 0 };

// ---------- 工具函数 ----------
const $  = (sel, parent = document) => parent.querySelector(sel);
const $$ = (sel, parent = document) => [...parent.querySelectorAll(sel)];

function esc(value) {
  return String(value ?? "").replace(/[&<>"']/g, ch => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
  }[ch]));
}

function toast(msg, type = "success") {
  const c = $("#toast-container");
  if (!c) return;
  const el = document.createElement("div");
  el.className = `toast ${type}`;
  el.textContent = msg;
  c.appendChild(el);
  setTimeout(() => { el.style.opacity = "0"; el.style.transform = "translateX(120%)"; }, 2400);
  setTimeout(() => el.remove(), 2800);
}

async function api(path, opts = {}) {
  const headers = { "Content-Type": "application/json", ...(opts.headers || {}) };
  if (TOKEN) headers["Authorization"] = `Bearer ${TOKEN}`;
  const res = await fetch(API_BASE + path, { ...opts, headers });
  let data = null;
  try { data = await res.json(); } catch { /* 非 JSON 响应 */ }
  if (res.status === 401) { logout(); throw new Error("登录已过期，请重新登录"); }
  if (!res.ok) {
    const msg = (data && (data.message || data.detail)) || `请求失败 (${res.status})`;
    throw new Error(msg);
  }
  return data;
}

/** 秒数 → mm:ss / h:mm:ss */
function fmtClock(seconds) {
  const total = Math.max(0, Math.floor(seconds || 0));
  const h = Math.floor(total / 3600);
  const m = Math.floor((total % 3600) / 60);
  const s = total % 60;
  if (h > 0) return `${h}:${String(m).padStart(2, "0")}:${String(s).padStart(2, "0")}`;
  return `${String(m).padStart(2, "0")}:${String(s).padStart(2, "0")}`;
}

function openModal(id) { $(`#${id}`)?.classList.remove("hidden"); }
function closeModal(id) { $(`#${id}`)?.classList.add("hidden"); }

document.addEventListener("click", (e) => {
  const closer = e.target.closest("[data-close-modal]");
  if (closer) closeModal(closer.dataset.closeModal);
  if (e.target.classList.contains("modal-backdrop") && e.target.closest(".modal")) {
    closeModal(e.target.closest(".modal").id);
  }
});

// ============================================================
// 登录 / 注册
// ============================================================
const authScreen = $("#auth-screen");
const gameScreen = $("#game-screen");

function showAuth() { authScreen.classList.remove("hidden"); gameScreen.classList.add("hidden"); }
function showGame() { authScreen.classList.add("hidden"); gameScreen.classList.remove("hidden"); }

function stopTimers() {
  if (tickTimer) clearInterval(tickTimer);
  if (pollTimer) clearInterval(pollTimer);
  if (syncTimer) clearTimeout(syncTimer);
  tickTimer = pollTimer = syncTimer = null;
}

function logout() {
  stopTimers();
  TOKEN = "";
  localStorage.removeItem("pf_token");
  ME = null; FARM = null; ANIMALS = []; TASKS = null; SELECTED_CELL = null;
  loginRewardTried = false;
  farmSignature = "";
  closeModal("buy-modal");
  closeModal("seed-modal");
  showAuth();
}

$$(".tab-btn").forEach(btn => {
  btn.addEventListener("click", () => {
    $$(".tab-btn").forEach(b => b.classList.remove("active"));
    btn.classList.add("active");
    $$(".auth-form").forEach(f => f.classList.add("hidden"));
    $(btn.dataset.tab === "login" ? "#login-form" : "#register-form").classList.remove("hidden");
    $("#auth-message").textContent = "";
  });
});

$("#login-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const fd = new FormData(e.target);
  try {
    const r = await api("/auth/login", { method: "POST", body: JSON.stringify({
      username: fd.get("username"), password: fd.get("password"),
    })});
    TOKEN = r.access_token;
    localStorage.setItem("pf_token", TOKEN);
    loginRewardTried = false;
    toast("欢迎回来，农夫！🌾");
    await initGame();
  } catch (err) {
    $("#auth-message").textContent = "❌ " + err.message;
  }
});

$("#register-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const fd = new FormData(e.target);
  try {
    await api("/auth/register", { method: "POST", body: JSON.stringify({
      username: fd.get("username"), password: fd.get("password"),
    })});
    toast("🎉 农场创建成功！请登录", "success");
    $("#tab-register").classList.remove("active");
    $("#tab-login").classList.add("active");
    $("#register-form").classList.add("hidden");
    $("#login-form").classList.remove("hidden");
    $("#login-form input[name=username]").value = fd.get("username");
    $("#auth-message").textContent = "";
  } catch (err) {
    $("#auth-message").textContent = "❌ " + err.message;
  }
});

$("#btn-logout").addEventListener("click", logout);

// ============================================================
// 游戏初始化
// ============================================================
async function initGame() {
  showGame();
  try {
    const me = await api("/auth/me");
    applyMe(me);
    if (!TOKEN) return;

    // 首屏只加载必要数据；背包/排行榜在切 Tab 时再拉
    await Promise.allSettled([
      loadFarm(true),
      loadShop(),
      loadTasks(),
      loadAnimals(),
    ]);
    if (!TOKEN) return;
    updateExpandLabel();
    startTimers();
    await maybeAutoClaimLogin();
  } catch (err) {
    if (TOKEN) toast(err.message, "error");
  }
}

function startTimers() {
  stopTimers();
  tickTimer = setInterval(tick, 1000);
  pollTimer = setInterval(() => loadFarm(true), FARM_SYNC_MS);
}

function applyMe(me) {
  ME = me;
  $("#player-name").textContent = me.username;
  $("#player-level").textContent = `Lv.${me.level}`;
  setGold(me.gold);
  updateExpandLabel();
}

function setGold(gold) {
  const el = $("#gold-text");
  if (!el) return;
  const prev = Number(el.dataset.value || "NaN");
  if (!Number.isNaN(prev) && prev !== gold) {
    el.classList.remove("gold-bump");
    void el.offsetWidth; // 强制重排以重播动画
    el.classList.add("gold-bump");
  }
  el.dataset.value = String(gold);
  el.textContent = Number(gold || 0).toLocaleString();
}

async function refreshUser() {
  const me = await api("/auth/me");
  applyMe(me);
}

async function maybeAutoClaimLogin() {
  if (loginRewardTried || !TASKS) return;
  loginRewardTried = true;
  const loginTask = TASKS.tasks.find(t => t.task_type === "login");
  if (!loginTask || !loginTask.is_completed || loginTask.is_claimed) return;
  try {
    const r = await api("/tasks/claim/login", { method: "POST" });
    toast(`📅 每日签到奖励 +${r.reward_gold} 金币`);
    await Promise.allSettled([refreshUser(), loadTasks()]);
  } catch { /* 已领取或网络问题，忽略 */ }
}

// ============================================================
// 农场
// ============================================================
async function loadFarm(silent = false) {
  if (farmInFlight) return;
  farmInFlight = true;
  try {
    const data = await api("/farm/");
    FARM = data;
    (data.cells || []).forEach(c => {
      c._remaining = c.status === "growing" ? (c.seconds_until_ready || 0) : 0;
    });

    if (SELECTED_CELL) {
      const c = data.cells.find(x => x.cell_index === SELECTED_CELL.index);
      SELECTED_CELL = c ? { index: c.cell_index, status: c.status } : null;
    }

    updateFarmStats();
    renderFarmGrid();
    renderActionBar();
  } catch (err) {
    if (!silent && TOKEN) toast(err.message, "error");
  } finally {
    farmInFlight = false;
  }
}

function scheduleFarmSync() {
  if (syncTimer) clearTimeout(syncTimer);
  syncTimer = setTimeout(() => loadFarm(true), 1200);
}

function updateFarmStats() {
  if (!FARM) return;
  let ready = 0, growing = 0, withered = 0;
  for (const c of FARM.cells) {
    if (c.status === "ready") ready++;
    else if (c.status === "growing") growing++;
    else if (c.status === "withered") withered++;
  }
  $("#stat-ready").textContent = ready;
  $("#stat-growing").textContent = growing;
  $("#stat-withered").textContent = withered;
}

function renderFarmGrid() {
  if (!FARM) return;
  const signature = FARM.cells.map(c => `${c.cell_index}:${c.status}`).join(",")
    + `|${FARM.cell_count}|${SELECTED_CELL ? SELECTED_CELL.index : "-"}`;

  // 状态与选中项都没变时只刷新计时文本，避免无意义地重建 25 个格子
  if (signature === farmSignature) {
    updateFarmTimers();
    return;
  }
  farmSignature = signature;

  const parts = [];
  for (const c of FARM.cells) {
    let inner = "";
    if (c.status === "empty") {
      inner = `<span class="cell-emoji">🕳️</span><span class="cell-label">空地</span>`;
    } else if (c.status === "growing") {
      inner = `<span class="cell-emoji">${c.crop_emoji || "🌱"}</span>
               <div class="cell-timer">${fmtClock(c._remaining)}</div>`;
    } else if (c.status === "ready") {
      inner = `<span class="cell-emoji">${c.crop_emoji || "🌾"}</span>
               <div class="cell-badge">可收获</div>`;
    } else if (c.status === "withered") {
      inner = `<span class="cell-emoji">🍂</span><span class="cell-label">枯萎</span>`;
    }
    const selected = SELECTED_CELL && SELECTED_CELL.index === c.cell_index ? " selected" : "";
    parts.push(`
      <div class="farm-cell cell-status-${c.status}${selected}" data-idx="${c.cell_index}">
        <span class="cell-idx">#${c.cell_index}</span>
        ${inner}
      </div>`);
  }

  // 预展示下一块可扩建土地，让扩建入口可见
  const max = FARM.max_cell_count || 25;
  const lockedCount = Math.min(2, Math.max(0, max - FARM.cell_count));
  for (let i = 0; i < lockedCount; i++) {
    parts.push(`
      <div class="farm-cell locked" data-locked="1" title="点击扩建一块土地">
        <span class="cell-emoji">🔒</span>
        <span class="cell-label">扩建 +1</span>
      </div>`);
  }

  $("#farm-grid").innerHTML = parts.join("");
}

function updateFarmTimers() {
  if (!FARM) return;
  for (const c of FARM.cells) {
    if (c.status !== "growing") continue;
    const el = $(`#farm-grid [data-idx="${c.cell_index}"] .cell-timer`);
    if (el) el.textContent = fmtClock(c._remaining);
  }
}

function tick() {
  if (document.hidden) return;

  let farmChanged = false;
  if (FARM) {
    for (const c of FARM.cells) {
      if (c.status !== "growing") continue;
      if (c._remaining > 0) c._remaining--;
      if (c._remaining <= 0) {
        c.status = "ready";
        c._remaining = 0;
        farmChanged = true;
        scheduleFarmSync();
      }
    }
    if (farmChanged) {
      updateFarmStats();
      renderFarmGrid();
      if (SELECTED_CELL) {
        const c = FARM.cells.find(x => x.cell_index === SELECTED_CELL.index);
        if (c) SELECTED_CELL.status = c.status;
        renderActionBar();
      }
    } else {
      updateFarmTimers();
      updateActionHint();
    }
  }

  let animalChanged = false;
  for (const a of ANIMALS) {
    if (a.state !== "producing") continue;
    if (a._remaining > 0) a._remaining--;
    if (a._remaining <= 0) {
      a.state = "ready";
      a._remaining = 0;
      animalChanged = true;
    }
  }
  if (ANIMALS.length) {
    if (animalChanged) renderAnimals();
    else updateAnimalTimers();
  }
}

function selectCell(idx) {
  const c = FARM?.cells.find(x => x.cell_index === idx);
  if (!c) return;
  SELECTED_CELL = { index: idx, status: c.status };
  $$("#farm-grid .farm-cell").forEach(el => {
    el.classList.toggle("selected", Number(el.dataset.idx) === idx);
  });
  renderActionBar();
}

function renderActionBar() {
  const bar = $("#cell-action-bar");
  if (!SELECTED_CELL) { bar.classList.add("hidden"); return; }
  const c = FARM?.cells.find(x => x.cell_index === SELECTED_CELL.index);
  if (!c) { SELECTED_CELL = null; bar.classList.add("hidden"); return; }

  bar.classList.remove("hidden");
  $("#action-cell-idx").textContent = c.cell_index;
  const statusText = {
    empty: "🕳️ 空地", growing: "🌱 生长中", ready: "✨ 可收获", withered: "🍂 已枯萎",
  };
  $("#action-cell-status").textContent = statusText[c.status] || "";

  const hint = $("#action-cell-hint");
  if (c.status === "growing") hint.textContent = `约 ${fmtClock(c._remaining)} 后成熟`;
  else if (c.status === "ready") {
    hint.textContent = c.seconds_until_wither
      ? `剩余 ${fmtClock(c.seconds_until_wither)} 会枯萎`
      : "尽快收获";
  } else if (c.status === "withered") hint.textContent = "清理后可重新种植";
  else hint.textContent = "选择种子开始种植";

  $("#btn-plant").disabled = !(c.status === "empty" || c.status === "withered");
  $("#btn-harvest").disabled = c.status !== "ready";
  $("#btn-clear").disabled = c.status !== "withered";
}

function updateActionHint() {
  if (!SELECTED_CELL || !FARM) return;
  const c = FARM.cells.find(x => x.cell_index === SELECTED_CELL.index);
  if (!c) return;
  const hint = $("#action-cell-hint");
  if (c.status === "growing") hint.textContent = `约 ${fmtClock(c._remaining)} 后成熟`;
}

$("#farm-grid").addEventListener("click", (e) => {
  const cell = e.target.closest(".farm-cell");
  if (!cell) return;
  if (cell.classList.contains("locked")) {
    const cost = EXPAND_PRICE;
    if (window.confirm(`花费 ${cost} 金币扩建一块土地？`)) doExpand();
    return;
  }
  selectCell(Number(cell.dataset.idx));
});

async function openSeedModal() {
  try {
    const inv = await api("/inventory/");
    const seeds = inv.items.filter(x => x.item_type === "seed" && x.quantity > 0);
    if (!seeds.length) { toast("背包里没有种子，先去商店买吧！🌰", "warn"); return; }

    $("#seed-choices").innerHTML = seeds.map(s => `
      <div class="shop-item">
        <span class="emoji">${s.emoji || "🌰"}</span>
        <div class="info">
          <div class="name">${esc(s.item_name)}</div>
          <div class="desc">库存 ×${s.quantity}</div>
        </div>
        <button class="pixel-btn small primary" data-pick="${s.template_id}">播种</button>
      </div>`).join("");
    openModal("seed-modal");
  } catch (err) {
    toast(err.message, "error");
  }
}

async function doPlant(templateId) {
  if (!SELECTED_CELL) return;
  try {
    await api("/farm/plant", { method: "POST", body: JSON.stringify({
      cell_index: SELECTED_CELL.index, template_id: templateId,
    })});
    toast("🌱 播种成功！");
    await loadFarm(false);
    if (CURRENT_TAB === "inventory") await loadInventory();
  } catch (err) { toast(err.message, "error"); }
}

async function doHarvest() {
  if (!SELECTED_CELL) return;
  try {
    const r = await api("/farm/harvest", { method: "POST", body: JSON.stringify({
      cell_index: SELECTED_CELL.index,
    })});
    toast(r.message || "🧺 收获成功！");
    SELECTED_CELL = null;
    await Promise.allSettled([
      loadFarm(false),
      loadTasks(),
      CURRENT_TAB === "inventory" ? loadInventory() : Promise.resolve(),
    ]);
  } catch (err) { toast(err.message, "error"); }
}

async function doClear() {
  if (!SELECTED_CELL) return;
  try {
    await api(`/farm/clear/${SELECTED_CELL.index}`, { method: "POST" });
    toast("🧹 已清理枯萎作物");
    SELECTED_CELL = null;
    await loadFarm(false);
  } catch (err) { toast(err.message, "error"); }
}

async function doExpand() {
  try {
    const r = await api("/farm/expand", { method: "POST" });
    toast(`🟩 扩建成功！格子 ${r.cell_count_before} → ${r.cell_count_after}`);
    await Promise.allSettled([refreshUser(), loadFarm(false), loadShop()]);
    updateExpandLabel();
  } catch (err) { toast(err.message, "error"); }
}

$("#btn-plant").addEventListener("click", openSeedModal);
$("#btn-harvest").addEventListener("click", doHarvest);
$("#btn-clear").addEventListener("click", doClear);

// 种子选择弹窗使用委托，避免每次重建都绑定事件
$("#seed-choices").addEventListener("click", (e) => {
  const btn = e.target.closest("[data-pick]");
  if (!btn) return;
  closeModal("seed-modal");
  doPlant(Number(btn.dataset.pick));
});

// ============================================================
// 商店
// ============================================================
async function loadShop() {
  const { items } = await api("/shop/items");
  SHOP_ITEMS = items;
  const expand = items.find(i => i.item_type === "expansion");
  if (expand) EXPAND_PRICE = expand.price;
  updateExpandLabel();

  renderShopGroup("#shop-seed", items.filter(i => i.item_type === "seed"));
  renderShopGroup("#shop-animal", items.filter(i => i.item_type === "animal"));
  renderShopGroup("#shop-tool", items.filter(i => i.item_type !== "seed" && i.item_type !== "animal"));
}

function renderShopGroup(selector, items) {
  const el = $(selector);
  if (!el) return;
  if (!items.length) {
    el.innerHTML = `<div class="empty-hint">暂无商品</div>`;
    return;
  }
  el.innerHTML = items.map(i => `
    <div class="shop-item" data-buy="${i.id}" title="点击购买">
      <span class="emoji">${i.emoji || "📦"}</span>
      <div class="info">
        <div class="name">${esc(i.name)}</div>
        <div class="desc">${esc(i.description || "")}</div>
      </div>
      <div class="price">💰 ${i.price}</div>
    </div>`).join("");
}

$("#panel-shop").addEventListener("click", (e) => {
  const item = e.target.closest("[data-buy]");
  if (item) openBuyModal(Number(item.dataset.buy));
});

function openBuyModal(itemId) {
  const item = SHOP_ITEMS.find(i => i.id === itemId);
  if (!item) return;

  const stockLimit = item.stock === -1 ? 99 : item.stock;
  const max = Math.max(1, Math.min(stockLimit, item.item_type === "expansion" ? 1 : 99));
  const affordable = Math.floor((ME?.gold || 0) / item.price);

  BUY_STATE = { item, qty: 1, max, affordable };
  $("#buy-emoji").textContent = item.emoji || "📦";
  $("#buy-name").textContent = item.name;
  $("#buy-desc").textContent = item.description || "";
  updateBuyModal();
  openModal("buy-modal");
}

function updateBuyModal() {
  const { item, qty, max, affordable } = BUY_STATE;
  if (!item) return;
  const total = item.price * qty;
  const gold = ME?.gold || 0;

  $("#buy-qty").textContent = qty;
  $("#buy-total").textContent = `合计 ${total} 💰`;
  $("#buy-balance").textContent = `余额 ${gold.toLocaleString()} 💰`;
  $("#buy-minus").disabled = qty <= 1;
  $("#buy-plus").disabled = qty >= max;

  const canBuy = total <= gold && affordable >= qty && !BUYING;
  $("#buy-confirm").disabled = !canBuy;

  let hint = "";
  if (total > gold) hint = `金币不足，还差 ${total - gold} 💰`;
  else if (item.item_type === "expansion") hint = "每次只能扩建 1 块";
  else if (item.stock !== -1) hint = `库存 ${item.stock}`;
  $("#buy-hint").textContent = hint;
}

$("#buy-minus").addEventListener("click", () => {
  BUY_STATE.qty = Math.max(1, BUY_STATE.qty - 1);
  updateBuyModal();
});
$("#buy-plus").addEventListener("click", () => {
  BUY_STATE.qty = Math.min(BUY_STATE.max, BUY_STATE.qty + 1);
  updateBuyModal();
});
$("#buy-confirm").addEventListener("click", confirmBuy);

async function confirmBuy() {
  if (BUYING) return;
  const { item, qty } = BUY_STATE;
  if (!item) return;

  BUYING = true;
  updateBuyModal();
  try {
    const r = await api("/shop/buy", { method: "POST", body: JSON.stringify({
      item_id: item.id, quantity: qty,
    })});
    toast(`✅ 购买成功：${item.name} ×${qty}，花费 ${r.gold_spent} 💰`);
    closeModal("buy-modal");

    const jobs = [refreshUser(), loadShop()];
    if (item.item_type === "expansion") jobs.push(loadFarm(false));
    if (item.item_type === "animal") jobs.push(loadAnimals());
    if ((item.item_type === "seed" || item.item_type === "feed") && CURRENT_TAB === "inventory") {
      jobs.push(loadInventory());
    }
    await Promise.allSettled(jobs);
    updateExpandLabel();
  } catch (err) {
    toast(err.message, "error");
  } finally {
    BUYING = false;
    updateBuyModal();
  }
}

// ============================================================
// 背包
// ============================================================
async function loadInventory() {
  const data = await api("/inventory/");
  const el = $("#inv-list");
  if (!data.items.length) {
    el.innerHTML = `<div class="empty-hint">🎒 背包空空如也，快去商店看看吧</div>`;
  } else {
    el.innerHTML = data.items.map(i => {
      const sellable = i.item_type === "produce" && i.sell_price_per_unit != null;
      return `
        <div class="inv-item" data-type="${i.item_type}">
          <span class="emoji">${i.emoji || "📦"}</span>
          <div class="info">
            <div class="name">${esc(i.item_name)}</div>
            ${sellable ? `<div class="desc">单价 ${i.sell_price_per_unit} 💰</div>` : ""}
          </div>
          <span class="qty">×${i.quantity}</span>
          ${sellable ? `
            <div class="inv-actions">
              <button class="pixel-btn small" data-sell="${i.id}" data-qty="1">卖1</button>
              <button class="pixel-btn small ghost" data-sell="${i.id}" data-qty="${i.quantity}">全卖</button>
            </div>` : ""}
        </div>`;
    }).join("");
  }
  updateExpandLabel();
}

$("#inv-list").addEventListener("click", (e) => {
  const btn = e.target.closest("[data-sell]");
  if (!btn) return;
  doSell(Number(btn.dataset.sell), Number(btn.dataset.qty));
});

async function doSell(invId, qty) {
  try {
    const r = await api("/shop/sell", { method: "POST", body: JSON.stringify({
      inventory_id: invId, quantity: qty,
    })});
    toast(`💰 出售 ${r.item_name} ×${r.quantity}，获得 ${r.gold_earned} 金币`);
    await Promise.allSettled([refreshUser(), loadInventory(), loadTasks()]);
  } catch (err) { toast(err.message, "error"); }
}

function updateExpandLabel() {
  const btn = $("#btn-expand");
  if (!btn) return;
  const costEl = btn.querySelector(".cost");
  const current = ME?.cell_count ?? 3;
  const max = FARM?.max_cell_count ?? 25;
  if (costEl) costEl.textContent = `花费 ${EXPAND_PRICE} 💰（${current}/${max}）`;
  btn.disabled = current >= max;
}

$("#btn-expand").addEventListener("click", doExpand);

// ============================================================
// 每日任务
// ============================================================
async function loadTasks() {
  const data = await api("/tasks/daily");
  TASKS = data;
  const el = $("#task-list");
  el.innerHTML = data.tasks.map(t => {
    const pct = Math.min(100, Math.round(t.progress / t.target * 100));
    const doneClass = t.is_completed ? "done" : "";
    return `
      <div class="task-item ${doneClass}">
        <div class="task-row-top">
          <span class="task-name">${esc(t.task_name)}</span>
          <span class="task-reward">💰 +${t.reward_gold}</span>
        </div>
        <div class="task-progress"><div class="task-progress-fill" style="width:${pct}%"></div></div>
        <div class="task-row-bot">
          <span class="task-text">${t.progress}/${t.target}</span>
          ${t.is_completed && !t.is_claimed
            ? `<button class="pixel-btn small primary" data-claim="${t.task_type}">领取</button>`
            : t.is_claimed ? `<span class="task-claimed">✅ 已领取</span>` : ""}
        </div>
      </div>`;
  }).join("");
  updateBadges();
}

$("#task-list").addEventListener("click", (e) => {
  const btn = e.target.closest("[data-claim]");
  if (!btn) return;
  claimTask(btn.dataset.claim);
});

async function claimTask(type) {
  try {
    const r = await api(`/tasks/claim/${type}`, { method: "POST" });
    toast(`🎉 领取成功！+${r.reward_gold} 金币`);
    await Promise.allSettled([refreshUser(), loadTasks()]);
  } catch (err) { toast(err.message, "error"); }
}

// ============================================================
// 排行榜
// ============================================================
async function loadRank() {
  const data = await api("/rank/wealth");
  const el = $("#rank-list");
  if (!data.list.length) {
    el.innerHTML = `<div class="empty-hint">还没有玩家上榜</div>`;
    return;
  }
  el.innerHTML = data.list.map(r => {
    const cls = r.rank === 1 ? "top1" : r.rank === 2 ? "top2" : r.rank === 3 ? "top3" : "";
    const wealth = r.wealth ?? r.gold ?? 0;
    const isMe = r.username === ME?.username ? " (我)" : "";
    return `
      <div class="rank-item">
        <span class="rank-no ${cls}">#${r.rank}</span>
        <div class="rank-main">
          <span class="rank-name">${esc(r.username)}${isMe}</span>
          <span class="rank-sub">金币 ${Number(r.gold || 0).toLocaleString()} · 仓库 ${Number(r.inventory_value || 0).toLocaleString()}</span>
        </div>
        <span class="rank-gold">💰 ${Number(wealth).toLocaleString()}</span>
      </div>`;
  }).join("");
}

// ============================================================
// 动物
// ============================================================
async function loadAnimals() {
  const data = await api("/animals/");
  ANIMALS = data.animals || [];
  ANIMALS.forEach(a => { a._remaining = a.ready_in_seconds || 0; });
  renderAnimals();
}

function renderAnimals() {
  const el = $("#animal-list");
  const feedBtn = $("#btn-feed-all");

  if (!ANIMALS.length) {
    el.innerHTML = `<div class="empty-hint">🐾 还没有动物，去商店买一只吧</div>`;
    feedBtn.disabled = true;
    feedBtn.textContent = "🍚 喂养全部";
    updateBadges();
    return;
  }

  const hungryCount = ANIMALS.filter(a => a.state === "hungry").length;
  el.innerHTML = ANIMALS.map(a => {
    let status = "";
    if (a.state === "ready") {
      status = `✨ 可采集 · ${a.produce_sell_price} 💰/个`;
    } else if (a.state === "hungry") {
      status = `🍚 待喂养 · 每轮 ${a.feed_consumption} 饲料`;
    } else if (a.state === "producing") {
      status = `<span data-timer="${a.id}">⏱ ${fmtClock(a._remaining)}</span>`;
    } else {
      status = "💀 已停养";
    }
    return `
      <div class="animal-item ${a.state}">
        <span class="emoji">${a.emoji || "🐾"}</span>
        <div class="info">
          <div class="name">${esc(a.name)} · ${a.produce_emoji || ""} ${esc(a.produce_name)}</div>
          <div class="timer">${status}</div>
        </div>
        ${a.state === "ready" ? `<button class="pixel-btn small primary" data-collect="${a.id}">采集</button>` : ""}
      </div>`;
  }).join("");

  feedBtn.disabled = hungryCount === 0;
  feedBtn.textContent = hungryCount > 0
    ? `🍚 喂养待产动物（${hungryCount} 只）`
    : "🍚 动物都在生产中";
  updateBadges();
}

function updateAnimalTimers() {
  $$("#animal-list [data-timer]").forEach(el => {
    const animal = ANIMALS.find(a => a.id === Number(el.dataset.timer));
    if (animal && animal.state === "producing") {
      el.textContent = `⏱ ${fmtClock(animal._remaining)}`;
    }
  });
}

$("#animal-list").addEventListener("click", (e) => {
  const btn = e.target.closest("[data-collect]");
  if (btn) collectAnimal(Number(btn.dataset.collect));
});

$("#btn-feed-all").addEventListener("click", async () => {
  try {
    const r = await api("/animals/feed", { method: "POST" });
    toast(r.message || "🍚 喂养成功");
    await Promise.allSettled([
      loadAnimals(),
      CURRENT_TAB === "inventory" ? loadInventory() : Promise.resolve(),
    ]);
  } catch (err) { toast(err.message, "error"); }
});

async function collectAnimal(id) {
  try {
    const r = await api(`/animals/collect/${id}`, { method: "POST" });
    toast(r.message || "✨ 采集成功！");
    await Promise.allSettled([
      loadAnimals(),
      CURRENT_TAB === "inventory" ? loadInventory() : Promise.resolve(),
    ]);
  } catch (err) { toast(err.message, "error"); }
}

// ============================================================
// 徽标
// ============================================================
function setBadge(selector, count) {
  const el = $(selector);
  if (!el) return;
  el.textContent = count > 99 ? "99+" : String(count);
  el.classList.toggle("hidden", count <= 0);
}

function updateBadges() {
  const claimable = TASKS
    ? TASKS.tasks.filter(t => t.is_completed && !t.is_claimed).length
    : 0;
  const readyAnimals = ANIMALS.filter(a => a.state === "ready").length;
  setBadge("#badge-tasks", claimable);
  setBadge("#badge-animals", readyAnimals);
}

// ============================================================
// 侧栏 Tab 切换（按需加载）
// ============================================================
const TAB_LOADERS = {
  shop: loadShop,
  inventory: loadInventory,
  tasks: loadTasks,
  rank: loadRank,
  animals: loadAnimals,
};

$$(".panel-tab").forEach(tab => {
  tab.addEventListener("click", () => {
    CURRENT_TAB = tab.dataset.tab;
    $$(".panel-tab").forEach(t => t.classList.remove("active"));
    tab.classList.add("active");
    $$(".panel-content").forEach(c => c.classList.add("hidden"));
    $(`#panel-${CURRENT_TAB}`)?.classList.remove("hidden");

    const loader = TAB_LOADERS[CURRENT_TAB];
    if (loader) {
      Promise.resolve(loader()).catch(err => {
        if (TOKEN) toast(err.message, "error");
      });
    }
  });
});

// 页面重新可见时同步一次，避免后台标签页计时漂移
document.addEventListener("visibilitychange", () => {
  if (document.hidden || !TOKEN) return;
  if (FARM) loadFarm(true);
  if (ANIMALS.length) loadAnimals().catch(() => {});
});

// ============================================================
// 启动入口
// ============================================================
if (TOKEN) {
  initGame().catch(() => { if (TOKEN) showGame(); });
} else {
  showAuth();
}

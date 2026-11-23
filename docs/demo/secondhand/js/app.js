/* 公共逻辑：API封装、登录态、导航栏、Toast、确认弹窗、工具函数 */
const API = "";   // 静态演示版：接口改走同目录相对路径（由 demo-mock.js 拦截），图片亦为相对路径
/* 与数据库 category 表保持一致：1数码电子 2教材书籍 3宿舍家居 4运动户外 5乐器文娱 6生活用品
   （实际选项以 GET /categories 动态渲染为准，这里仅作接口失败时的兜底） */
const CATEGORIES = { 1: "数码电子", 2: "教材书籍", 3: "宿舍家居", 4: "运动户外", 5: "乐器文娱", 6: "生活用品" };

/* ---------- 统一返回解包：{code,msg,data}，自动携带 X-User-Id ---------- */
async function request(path, { method = "GET", body, formData } = {}) {
  const headers = {};
  const user = getUser();
  if (user) {
    headers["X-User-Id"] = user.id;
    // 增量修复：携带服务端签名令牌，后端以令牌解析出的身份为准（防止改 id 冒名）
    if (user.token) headers["Authorization"] = "Bearer " + user.token;
  }
  const opt = { method, headers };
  if (formData) {
    opt.body = formData;
  } else if (body !== undefined) {
    headers["Content-Type"] = "application/json";
    opt.body = JSON.stringify(body);
  }
  let res, json;
  try {
    // 静态演示版：去掉开头的 "/"，避免部署到子路径时请求逃到站点根目录
    res = await fetch((API + path).replace(/^\//, ""), opt);
    json = await res.json();
  } catch (e) {
    throw new Error("网络请求失败，请确认后端服务已启动");
  }
  if (json.code !== 0) {
    if (handleAuthExpired(res.status)) throw new Error("登录已失效，请重新登录");
    const message = json.message || json.msg || `HTTP ${res.status}`;
    notifyBizError(json.code, message);   // 增量：业务异常全局弹窗（带去重，避免与页面 toast 重复）
    const err = new Error(message);
    err.code = json.code;                 // 增量：错误码挂到异常对象，调用方可按需细分处理
    err.traceId = json.trace_id;
    throw err;
  }
  return json.data;
}

/* 增量新增：业务异常全局提示（等价 ElementPlus ElMessage.error）
   - 按 code 识别错误码，统一弹窗；
   - 同一文案 800ms 内去重，避免与页面 catch 中已有的 toast 重复弹出。 */
const BIZ_ERROR_TEXT = {
  400: "请求参数有误", 401: "请先登录", 403: "无权限访问", 404: "资源不存在",
  409: "操作冲突，请刷新后重试", 422: "参数校验失败", 429: "操作太频繁，请稍后再试",
  500: "服务器开小差了，请稍后重试",
};
let _lastBizToast = { msg: "", at: 0 };
function notifyBizError(code, message) {
  const text = (code >= 1000 && message) ? message
             : (BIZ_ERROR_TEXT[code] || message || "操作失败");
  const now = Date.now();
  if (_lastBizToast.msg === text && now - _lastBizToast.at < 800) return;
  _lastBizToast = { msg: text, at: now };
  if (typeof toast === "function") toast(text, "err");
}

/* 令牌缺失/过期（401）：清理本地登录态并引导重新登录，避免"已登录却一直被拦" */
let authPrompting = false;
function handleAuthExpired(status) {
  if (status !== 401) return false;
  localStorage.removeItem("cs_user");
  renderNav();
  if (!authPrompting) {
    authPrompting = true;
    openLoginModal();
    setTimeout(() => { authPrompting = false; }, 2000);
  }
  return true;
}

/* ---------- 登录态（localStorage） ---------- */
function getUser() {
  try {
    const u = JSON.parse(localStorage.getItem("cs_user"));
    // 没有签名令牌的登录态（旧版本写入）后端一律 401，这里直接视为未登录
    return u && u.token ? u : null;
  } catch { return null; }
}
function setUser(u) {
  if (u) localStorage.setItem("cs_user", JSON.stringify(u));
  else localStorage.removeItem("cs_user");
  renderNav();
}
function requireLogin() {
  if (getUser()) return true;
  openLoginModal();
  return false;
}

/* ---------- 顶部导航栏 + 登录弹窗 ---------- */
function renderNav(active = "") {
  const u = getUser();
  const links = [
    ["index.html", "首页", "home"],
    ["publish.html", "发布商品", "publish"],
    ["cart.html", "购物车", "cart"],
    ["orders.html", "我的交易", "order"],
    ["messages.html", "消息通知", "msg"],
    ["admin.html", "管理看板", "admin"],  // 增量新增：管理员看板入口
  ];
  document.getElementById("navbar").className = "navbar";
  document.getElementById("navbar").innerHTML = `
    <span class="brand" id="brand-logo" title="点我三下有惊喜">🎓 校淘集市<span class="sub">CAMPUS TREASURE</span></span>
    ${links.map(([href, text, key, cls]) =>
      `<a class="nav-link ${cls || ""} ${key === active ? "active" : ""}" href="${href}">${text}</a>`).join("")}
    <span class="spacer"></span>
    ${u ? `<span class="avatar-btn" onclick="logout()"><span class="avatar-circle">${esc((u.nickname || u.username).slice(0, 1))}</span>${esc(u.nickname || u.username)}（退出）</span>`
        : `<span class="avatar-btn" onclick="openLoginModal()"><span class="avatar-circle">?</span>登录</span>`}
  `;
  refreshMsgBadge();
}

/* 未读聊天角标：挂在「消息通知」入口上，失败静默（不影响页面主流程） */
async function refreshMsgBadge() {
  const u = getUser();
  if (!u) return;
  try {
    const d = await request("/chat/unread");
    const link = document.querySelector('#navbar a[href="messages.html"]');
    if (!link) return;
    let badge = link.querySelector(".nav-badge");
    if (!d.unread) { if (badge) badge.remove(); return; }
    if (!badge) {
      badge = document.createElement("span");
      badge.className = "nav-badge";
      link.appendChild(badge);
    }
    badge.textContent = d.unread > 99 ? "99+" : d.unread;
  } catch { /* 未登录/网络异常时不打扰用户 */ }
}
function tip() { toast("该功能开发中，敬请期待", "info"); }
function logout() { setUser(null); toast("已退出登录", "info"); }

function openLoginModal() {
  ensureAuthModal();    // 页面脚本可能早于 DOMContentLoaded 调用，这里保证弹窗已挂载
  const modal = document.getElementById("login-modal");
  if (!modal) return;
  modal.classList.add("show");
  const regVisible = document.getElementById("pane-register").style.display !== "none";
  (regVisible ? document.getElementById("reg-user") : document.getElementById("login-user")).focus();
}
function closeAuthModal() {
  document.getElementById("login-modal").classList.remove("show");
}
/* 登录 / 注册 面板切换 */
function switchAuthTab(mode) {
  const isReg = mode === "register";
  document.getElementById("tab-login").classList.toggle("active", !isReg);
  document.getElementById("tab-register").classList.toggle("active", isReg);
  document.getElementById("pane-login").style.display = isReg ? "none" : "block";
  document.getElementById("pane-register").style.display = isReg ? "block" : "none";
  document.getElementById("auth-title").textContent = isReg ? "📝 校淘集市 · 注册" : "🔐 校淘集市 · 登录";
  const el = document.getElementById(isReg ? "reg-user" : "login-user");
  if (el) el.focus();
}

/* 增量新增：一键填入演示账号（确保在登录面板并聚焦密码框） */
function fillDemo(username, password) {
  if (document.getElementById("pane-register").style.display !== "none") switchAuthTab("login");
  document.getElementById("login-user").value = username;
  document.getElementById("login-pwd").value = password;
  document.getElementById("login-pwd").focus();
}
async function doLogin() {
  const btn = document.getElementById("login-btn");
  const username = document.getElementById("login-user").value.trim();
  const password = document.getElementById("login-pwd").value;
  if (!username || !password) { toast("请填写用户名和密码", "err"); return; }
  btn.disabled = true;
  try {
    const data = await request("/auth/login", { method: "POST", body: { username, password } });
    setUser({ ...data.user, token: data.token });
    closeAuthModal();
    toast(`欢迎回来，${data.user.nickname}`, "ok");
    document.dispatchEvent(new CustomEvent("cs:login"));
  } catch (e) {
    toast(e.message, "err");
  } finally {
    btn.disabled = false;
  }
}
/* 注册：校验通过后调用 /auth/register，成功后自动登录，省去再输一次密码 */
async function doRegister() {
  const btn = document.getElementById("reg-btn");
  const username = document.getElementById("reg-user").value.trim();
  const password = document.getElementById("reg-pwd").value;
  const confirm = document.getElementById("reg-pwd2").value;
  const nickname = document.getElementById("reg-nick").value.trim();
  const phone = document.getElementById("reg-phone").value.trim();

  if (username.length < 3 || username.length > 50) { toast("用户名需 3~50 个字符", "err"); return; }
  if (password.length < 6 || password.length > 64) { toast("密码需 6~64 位", "err"); return; }
  if (password !== confirm) { toast("两次输入的密码不一致", "err"); return; }

  btn.disabled = true;
  try {
    const payload = { username, password };
    if (nickname) payload.nickname = nickname;
    if (phone) payload.phone = phone;
    await request("/auth/register", { method: "POST", body: payload });
    const data = await request("/auth/login", { method: "POST", body: { username, password } });
    setUser({ ...data.user, token: data.token });
    ["reg-user", "reg-pwd", "reg-pwd2", "reg-nick", "reg-phone"].forEach(id => { document.getElementById(id).value = ""; });
    switchAuthTab("login");
    closeAuthModal();
    toast(`注册成功，欢迎你，${data.user.nickname}`, "ok");
    document.dispatchEvent(new CustomEvent("cs:login"));
  } catch (e) {
    toast(e.message, "err");
  } finally {
    btn.disabled = false;
  }
}

/* ---------- Toast 全局消息 ---------- */
function toast(msg, type = "ok") {
  let box = document.getElementById("toast-box");
  if (!box) { box = document.createElement("div"); box.id = "toast-box"; document.body.appendChild(box); }
  const t = document.createElement("div");
  t.className = `toast ${type}`;
  t.textContent = msg;
  box.appendChild(t);
  setTimeout(() => t.remove(), 2600);
}

/* ---------- 确认弹窗（删除/下架/成交等危险操作） ---------- */
function confirmDialog(title, text, danger = false) {
  return new Promise(resolve => {
    const mask = document.createElement("div");
    mask.className = "modal-mask show";
    mask.innerHTML = `<div class="modal">
      <h3>${title}</h3><p style="color:#566573;font-size:14px;">${text}</p>
      <div class="actions"><button class="cancel">取消</button>
      <button class="${danger ? "danger" : "ok"}">确定</button></div></div>`;
    document.body.appendChild(mask);
    mask.querySelector(".cancel").onclick = () => { mask.remove(); resolve(false); };
    mask.querySelector(".actions button:last-child").onclick = () => { mask.remove(); resolve(true); };
  });
}

/* ---------- 工具 ---------- */
function esc(s) { return String(s ?? "").replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c])); }
function fmtTime(iso) {
  const d = new Date(iso), now = new Date(), diff = (now - d) / 1000;
  if (diff < 60) return "刚刚";
  if (diff < 3600) return `${Math.floor(diff / 60)}分钟前`;
  if (diff < 86400) return `${Math.floor(diff / 3600)}小时前`;
  if (diff < 86400 * 7) return `${Math.floor(diff / 86400)}天前`;
  return iso.slice(0, 10);
}
function debounce(fn, ms = 350) {
  let timer; return (...args) => { clearTimeout(timer); timer = setTimeout(() => fn(...args), ms); };
}
/* 防重复提交：按钮置灰直到请求结束 */
async function withLoading(btn, fn) {
  if (btn.disabled) return;
  btn.disabled = true;
  try { await fn(); } finally { btn.disabled = false; }
}

/* ---------- 趣味模块 ---------- */
/* 手账贴纸常量：砍价贴纸 + logo彩蛋掉落 */
const BARGAIN_STICKERS = ["🍋 酸了，能便宜点吗", "🔪 砍一刀！", "😭 求包邮", "🔥 秒了，还在吗", "🤝 诚心要，给个友情价"];
const CONFETTI_STICKERS = ["📎", "🧷", "✏️", "📌", "🎀", "🍅", "📼", "🧸", "🎐", "🖍️", "📛", "🍥"];
let _brandClicks = 0, _brandTimer = null;
document.addEventListener("click", e => {
  const logo = e.target.closest("#brand-logo");
  if (!logo) return;
  _brandClicks++;
  clearTimeout(_brandTimer);
  _brandTimer = setTimeout(() => { _brandClicks = 0; }, 1500);
  if (_brandClicks >= 3) { _brandClicks = 0; dropStickers(); }
});
function dropStickers() {
  toast("✨ 哇，掉了一手账贴纸！", "ok");
  const layer = document.createElement("div");
  layer.className = "sticker-confetti";
  for (let i = 0; i < 26; i++) {
    const s = document.createElement("span");
    s.textContent = CONFETTI_STICKERS[Math.floor(Math.random() * CONFETTI_STICKERS.length)];
    s.style.left = Math.random() * 100 + "vw";
    s.style.animationDelay = Math.random() * .5 + "s";
    s.style.animationDuration = 1.6 + Math.random() * 1.4 + "s";
    s.style.fontSize = 16 + Math.random() * 18 + "px";
    layer.appendChild(s);
  }
  document.body.appendChild(layer);
  setTimeout(() => layer.remove(), 3400);
}
/* 深夜emo：23点~5点切换 hero 氛围 */
function isNightOwl() { const h = new Date().getHours(); return h >= 23 || h < 5; }
/* 集章卡：已售出商品数=章数，3/5/10 解锁称号 */
const STAMP_TIERS = [[10, "👑 校园倒爷"], [5, "💼 收藏家"], [3, "🏷️ 砍价王"], [1, "🌱 初出茅庐"]];
function stampTitle(n) { for (const [min, t] of STAMP_TIERS) if (n >= min) return t; return "🐣 还没开张"; }
async function getMyStamps() {
  const u = getUser();
  if (!u) return { stamps: 0, title: "🐣 还没开张" };
  const d = await request(`/goods?seller_id=${u.id}&status=2&page_size=50`);
  const n = d.total || 0;
  return { stamps: n, title: stampTitle(n) };
}

/* 公共弹窗容器：脚本位于 body 末尾时立即创建，页面脚本可同步调用 openLoginModal */
function ensureAuthModal() {
  if (document.getElementById("login-modal") || !document.body) return;
  const m = document.createElement("div");
  m.id = "login-modal"; m.className = "modal-mask";
  m.innerHTML = `<div class="modal"><h3 id="auth-title">🔐 校淘集市 · 登录</h3>
    <div class="modal-tabs">
      <button id="tab-login" class="active" onclick="switchAuthTab('login')">登录</button>
      <button id="tab-register" onclick="switchAuthTab('register')">注册</button>
    </div>
    <div id="pane-login">
      <div class="form-item"><label>用户名</label><input id="login-user" value="demo" placeholder="例如 xiaoming"></div>
      <div class="form-item"><label>密码</label><input id="login-pwd" type="password" value="demo123" placeholder="请输入登录密码"></div>
      <div class="auth-tip">第一次来？点上方「注册」创建账号，注册成功后会自动登录。</div>
      <div class="demo-accounts">
        <div class="demo-title">🔑 演示账号（已预填，任意账号密码均可登录）</div>
        <div class="demo-row"><span>账号：<code>demo / demo123</code></span><button onclick="fillDemo('demo','demo123')">填入</button></div>
      </div>
      <div class="actions"><button onclick="closeAuthModal()">取消</button>
      <button class="ok" id="login-btn" onclick="doLogin()">登录</button></div>
    </div>
    <div id="pane-register" style="display:none">
      <div class="form-item"><label>用户名 <span class="req">*</span></label><input id="reg-user" placeholder="3~50 位，登录时使用"></div>
      <div class="form-item"><label>密码 <span class="req">*</span></label><input id="reg-pwd" type="password" placeholder="至少 6 位"></div>
      <div class="form-item"><label>确认密码 <span class="req">*</span></label><input id="reg-pwd2" type="password" placeholder="再输入一次密码"></div>
      <div class="form-row">
        <div class="form-item"><label>昵称</label><input id="reg-nick" maxlength="50" placeholder="选填"></div>
        <div class="form-item"><label>手机号</label><input id="reg-phone" maxlength="20" placeholder="选填"></div>
      </div>
      <div class="auth-tip">昵称留空时默认与用户名相同；注册即同意校园二手交易规范。</div>
      <div class="actions"><button onclick="closeAuthModal()">取消</button>
      <button class="ok" id="reg-btn" onclick="doRegister()">注册并登录</button></div>
    </div></div>`;
  m.addEventListener("click", e => { if (e.target === m) m.classList.remove("show"); });
  m.addEventListener("keydown", e => {
    if (e.key !== "Enter") return;
    const onRegister = document.getElementById("pane-register").style.display !== "none";
    (onRegister ? doRegister : doLogin)();
  });
  document.body.appendChild(m);
}
ensureAuthModal();                                        // body 末尾直接创建
document.addEventListener("DOMContentLoaded", ensureAuthModal);  // 兜底

/* ---------- 模拟支付方式（购物车 / 立即购买共用） ---------- */
const PAY_METHODS = [
  { id: "campus_card", name: "校园一卡通", icon: "💳", desc: "校园卡余额，即时到账" },
  { id: "wechat", name: "微信支付", icon: "💚", desc: "扫码模拟支付" },
  { id: "alipay", name: "支付宝", icon: "💙", desc: "扫码模拟支付" },
  { id: "cash", name: "线下当面交易", icon: "🤝", desc: "见面验货后付款" },
];
function payMethodText(id) {
  const m = PAY_METHODS.find(x => x.id === id);
  return m ? m.name : "在线支付";
}

/* 拉起支付方式选择弹窗，resolve 选中的方式 id；取消返回 null */
function choosePayMethod(amount, title = "") {
  return new Promise(resolve => {
    const mask = document.createElement("div");
    mask.className = "modal-mask show";
    mask.innerHTML = `<div class="modal pay-modal">
      <h3>💰 选择支付方式</h3>
      ${title ? `<p class="pay-title">${esc(title)}</p>` : ""}
      <div class="pay-amount">应付金额 <b>￥${amount}</b></div>
      <div class="pay-methods">
        ${PAY_METHODS.map((m, i) => `<label class="pay-method ${i === 0 ? "cur" : ""}" data-id="${m.id}">
          <span class="pay-ic">${m.icon}</span>
          <span class="pay-info"><b>${m.name}</b><small>${m.desc}</small></span>
          <input type="radio" name="pay-method-pick" value="${m.id}" ${i === 0 ? "checked" : ""}>
        </label>`).join("")}
      </div>
      <p class="pay-tip">校园模拟支付演示，不会产生真实扣款</p>
      <div class="actions"><button class="pay-cancel">取消</button>
        <button class="ok pay-confirm">确认支付</button></div>
    </div>`;
    document.body.appendChild(mask);          // 必须挂载到页面，否则弹窗永远不可见
    const close = val => { mask.remove(); resolve(val); };
    mask.addEventListener("click", e => {
      const card = e.target.closest(".pay-method");
      if (card) {
        mask.querySelectorAll(".pay-method").forEach(c => c.classList.toggle("cur", c === card));
        card.querySelector("input").checked = true;
        return;
      }
      if (e.target === mask) close(null);
    });
    mask.querySelector(".pay-cancel").onclick = () => close(null);
    mask.querySelector(".pay-confirm").onclick = () => {
      const picked = mask.querySelector("input[name=pay-method-pick]:checked");
      close(picked ? picked.value : PAY_METHODS[0].id);
    };
  });
}

/* 分类选项：优先取后端 /categories，失败时回落到本地映射 */
async function fetchCategories() {
  try {
    const d = await request("/categories");
    if (d && d.items && d.items.length) return d.items;
  } catch { /* 忽略，走兜底 */ }
  return Object.entries(CATEGORIES).map(([id, name]) => ({ id: Number(id), name }));
}

/* 打开与卖家的聊天页；action=swap 时直接进入换物模式 */
function openChat(goodsId, toId, action = "") {
  if (!requireLogin()) return;
  const q = new URLSearchParams({ goods: goodsId, to: toId });
  if (action) q.set("action", action);
  location.href = `messages.html?${q}`;
}

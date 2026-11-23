/* ============================================================
   common.js —— 公共脚本 v3
   统一封装：fetchJSON / loadNavbar / logout / requireRole
   增强：btnLoading / debounce / toast / throttle
   安全：loadNavbar 全面改用 textContent，消灭 innerHTML 拼接用户数据
   ============================================================ */

/** 当前登录用户（缓存）—— 跨页面存 sessionStorage，导航栏可以瞬间渲染不弹跳 */
let _currentUser = null;
try {
  _currentUser = JSON.parse(sessionStorage.getItem("stardock_user") || "null");
} catch (e) { /* ignore */ }

function _saveUser(u) {
  _currentUser = u;
  try { sessionStorage.setItem("stardock_user", JSON.stringify(u)); } catch (e) { /* ignore */ }
}

/** 导航栏是否已渲染过（防止每次 innerHTML 全重写） */
let _navbarRendered = false;

/** 基础 API 地址（同域为空） */
const API_BASE = "/stardock";

/* ============================================================
   fetchJSON —— 统一 fetch 封装
   ============================================================ */
async function fetchJSON(url, options = {}) {
  const opts = Object.assign({
    credentials: "include",
    headers: { "Content-Type": "application/json" },
  }, options);

  if (opts.body !== undefined && typeof opts.body !== "string") {
    opts.body = JSON.stringify(opts.body);
  }

  let resp;
  try {
    resp = await fetch(API_BASE + url, opts);
  } catch (e) {
    toast("网络错误，请检查连接", "error");
    throw e;
  }

  const data = await resp.json();

  if (data.code === 401) {
    toast("登录已过期，请重新登录", "error");
    window.location.href = "/stardock/login.html";
    throw new Error("Unauthorized");
  }

  if (data.code !== 0) {
    toast(data.msg || "请求失败", "error");
    throw new Error(data.msg || "Request failed");
  }

  return data;
}

/* ============================================================
   loadNavbar —— 渲染导航栏（全面安全版：textContent）
   ============================================================ */
async function loadNavbar(containerId = "navbar", force = false) {
  const el = document.getElementById(containerId);
  if (!el) return;

  let u = _currentUser;
  if (!u) {
    try {
      const res = await fetchJSON("/api/auth/me");
      _saveUser(res.data);
      u = _currentUser;
    } catch (e) {
      el.innerHTML = `
        <a href="/stardock/login.html">登录</a>
        <a href="/stardock/register.html">注册</a>
      `;
      _navbarRendered = false;
      return;
    }
  }

  if (_navbarRendered && !force) {
    const scoreEl = el.querySelector(".user-info .score");
    if (scoreEl && u) {
      scoreEl.textContent = `💎 ${(u.score ?? 0).toLocaleString()}`;
    }
    return;
  }

  // 安全构建：模板 + textContent 注入
  const roleMap = { 1: "粉丝", 2: "管理员", 3: "明星" };

  const nav = document.createElement("nav");
  nav.className = "stardock-nav";

  // 首页
  nav.appendChild(_navLink("🏠 首页", "/stardock/home.html"));
  nav.appendChild(_navLink("🎴 抽卡", "/stardock/gacha.html"));
  nav.appendChild(_navLink("📖 图鉴", "/stardock/my-cards.html"));
  nav.appendChild(_navLink("💰 充值", "/stardock/recharge.html"));

  // 管理链接（根据角色）
  if (u.role === 2) {
    nav.appendChild(_navLink("🛡️ 用户管理", "/stardock/admin/users.html"));
    nav.appendChild(_navLink("🎴 卡池配置", "/stardock/admin/gacha.html"));
    nav.appendChild(_navLink("📢 活动管理", "/stardock/admin/activities.html"));
  }
  if (u.role === 3) {
    nav.appendChild(_navLink("📢 发布活动", "/stardock/admin/activities.html"));
  }

  // 右侧用户区
  const userArea = document.createElement("div");
  userArea.className = "nav-user-area";

  const roleTag = document.createElement("span");
  roleTag.className = `role-tag role-${u.role}`;
  roleTag.textContent = roleMap[u.role] || "未知";

  const nick = document.createElement("span");
  nick.className = "nav-nick";
  nick.textContent = u.nickname || "";

  const score = document.createElement("span");
  score.className = "score";
  score.textContent = `💎 ${(u.score ?? 0).toLocaleString()}`;

  const profileLink = document.createElement("a");
  profileLink.href = "/stardock/profile.html";
  profileLink.className = "nav-link nav-link-sm";
  profileLink.textContent = "个人中心";

  const logoutBtn = document.createElement("button");
  logoutBtn.type = "button";
  logoutBtn.className = "nav-btn-logout";
  logoutBtn.textContent = "退出";
  logoutBtn.addEventListener("click", logout);

  userArea.appendChild(roleTag);
  userArea.appendChild(nick);
  userArea.appendChild(score);
  userArea.appendChild(profileLink);
  userArea.appendChild(logoutBtn);

  nav.appendChild(userArea);

  el.innerHTML = "";
  el.appendChild(nav);

  _navbarRendered = true;
}

function _navLink(text, href) {
  const a = document.createElement("a");
  a.href = href;
  a.className = "nav-link";
  a.textContent = text;
  return a;
}

/* ============================================================
   updateUserScore —— 只更新当前缓存的积分值（本地用）
   ============================================================ */
function updateUserScore(newScore) {
  if (_currentUser) _currentUser.score = newScore;
  _saveUser(_currentUser);
  const scoreEl = document.querySelector("#navbar .user-info .score, #navbar .nav-user-area .score");
  if (scoreEl) scoreEl.textContent = `💎 ${newScore.toLocaleString()}`;
}

/* ============================================================
   logout —— 退出
   ============================================================ */
async function logout() {
  try { await fetchJSON("/api/auth/logout", { method: "POST" }); } catch (e) {}
  _currentUser = null;
  try { sessionStorage.removeItem("stardock_user"); } catch (e) {}
  _navbarRendered = false;
  window.location.href = "/stardock/login.html";
}

/* ============================================================
   requireRole —— 鉴权 + 角色检查
   ============================================================ */
async function requireRole(allowRoles) {
  const res = await fetchJSON("/api/auth/me");
  _saveUser(res.data);
  _navbarRendered = false;
  const u = _currentUser;

  if (allowRoles !== undefined) {
    const allowed = Array.isArray(allowRoles) ? allowRoles : [allowRoles];
    if (!allowed.includes(u.role)) {
      toast("权限不足", "error");
      window.location.href = "/stardock/home.html";
      throw new Error("Forbidden");
    }
  }
  return u;
}

/* ============================================================
   按钮交互优化
   ============================================================ */

function btnLoading(btnOrId, loading, loadingText = "处理中...") {
  const btn = typeof btnOrId === "string" ? document.getElementById(btnOrId) : btnOrId;
  if (!btn) return;

  if (loading) {
    btn.dataset.origText = btn.textContent;
    btn.dataset.origClass = btn.className;
    btn.textContent = loadingText;
    btn.disabled = true;
    btn.style.opacity = "0.7";
    btn.style.cursor = "not-allowed";
  } else {
    btn.textContent = btn.dataset.origText || btn.textContent;
    btn.disabled = false;
    btn.style.opacity = "";
    btn.style.cursor = "";
  }
}

/** 防抖 */
function debounce(fn, wait = 300) {
  let t;
  return function (...args) {
    clearTimeout(t);
    t = setTimeout(() => fn.apply(this, args), wait);
  };
}

/** 节流 */
function throttle(fn, wait = 300) {
  let last = 0;
  return function (...args) {
    const now = Date.now();
    if (now - last >= wait) {
      last = now;
      fn.apply(this, args);
    }
  };
}

/* ============================================================
   toast —— 更好看的消息提示
   ============================================================ */
(function initToast() {
  if (document.getElementById("__toast_container")) return;
  const box = document.createElement("div");
  box.id = "__toast_container";
  Object.assign(box.style, {
    position: "fixed", top: "20px", right: "20px",
    zIndex: "99999", display: "flex", flexDirection: "column", gap: "10px",
    maxWidth: "360px", pointerEvents: "none"
  });
  document.body.appendChild(box);
})();

function toast(msg, type = "info", duration = 2800) {
  const box = document.getElementById("__toast_container");
  if (!box) return alert(msg);

  const el = document.createElement("div");
  const colors = {
    info:   { bg: "linear-gradient(135deg, #2196f3, #1976d2)", icon: "ℹ️" },
    success:{ bg: "linear-gradient(135deg, #4caf50, #2e7d32)", icon: "✅" },
    error:  { bg: "linear-gradient(135deg, #f44336, #c62828)", icon: "❌" },
    warn:   { bg: "linear-gradient(135deg, #ff9800, #e65100)", icon: "⚠️" },
  };
  const c = colors[type] || colors.info;

  Object.assign(el.style, {
    background: c.bg, color: "#fff", padding: "14px 20px",
    borderRadius: "12px", boxShadow: "0 8px 24px rgba(0,0,0,0.4)",
    fontSize: "14px", display: "flex", alignItems: "center", gap: "12px",
    animation: "toastIn 0.3s cubic-bezier(0.34, 1.56, 0.64, 1)", pointerEvents: "auto",
    backdropFilter: "blur(8px)"
  });
  const iconSpan = document.createElement("span");
  iconSpan.style.fontSize = "18px";
  iconSpan.textContent = c.icon;
  const msgSpan = document.createElement("span");
  msgSpan.textContent = msg;
  el.appendChild(iconSpan);
  el.appendChild(msgSpan);
  box.appendChild(el);

  setTimeout(() => {
    el.style.animation = "toastOut 0.3s ease forwards";
    setTimeout(() => el.remove(), 300);
  }, duration);
}

if (!document.getElementById("__toast_style")) {
  const st = document.createElement("style");
  st.id = "__toast_style";
  st.textContent = `
    @keyframes toastIn  { from { transform: translateX(120%) scale(0.9); opacity: 0 } to { transform: translateX(0) scale(1); opacity: 1 } }
    @keyframes toastOut { from { transform: translateX(0) scale(1); opacity: 1 } to { transform: translateX(120%) scale(0.9); opacity: 0 } }
  `;
  document.head.appendChild(st);
}

/* ============================================================
   小工具
   ============================================================ */
function setText(elId, text) {
  const el = document.getElementById(elId);
  if (el) el.textContent = text ?? "";
}

function fmt(dt) {
  if (!dt) return "";
  const d = new Date(dt.replace(" ", "T"));
  const m = String(d.getMonth() + 1).padStart(2, "0");
  const day = String(d.getDate()).padStart(2, "0");
  const hh = String(d.getHours()).padStart(2, "0");
  const mm = String(d.getMinutes()).padStart(2, "0");
  return `${m}-${day} ${hh}:${mm}`;
}

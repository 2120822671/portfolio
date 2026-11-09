/* ============================================================
   common.js —— 公共脚本
   统一封装：fetchJSON / loadNavbar / logout / requireRole
   增强：btnLoading / debounce / toast / throttle
   v2 —— loadNavbar 改为增量更新，不再每次 innerHTML 全重写
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

/** 基础 API 地址（作品集整合：统一挂载在 /stardock 前缀下） */
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
   loadNavbar —— 渲染导航栏
   优化：首次 innerHTML 全渲染，后续只更新积分数字
   参数 force: true 强制全量重绘（登录/登出/角色变化时用）
   ============================================================ */
async function loadNavbar(containerId = "navbar", force = false) {
  const el = document.getElementById(containerId);
  if (!el) return;

  // 拿用户信息（sessionStorage 缓存命中就同步渲染，不等接口 → 导航栏不弹跳）
  let u = _currentUser;
  if (!u) {
    try {
      const res = await fetchJSON("/api/auth/me");
      _saveUser(res.data);
      u = _currentUser;
    } catch (e) {
      el.innerHTML = `
        <a href="/">🏠 作品集</a>
        <a href="/stardock/login.html">登录</a>
        <a href="/stardock/register.html">注册</a>
      `;
      _navbarRendered = false;
      return;
    }
  }

  // 导航栏已存在 + 没强制重绘 → 只更积分
  if (_navbarRendered && !force) {
    const scoreEl = el.querySelector(".user-info .score");
    if (scoreEl) {
      scoreEl.textContent = `💎 ${u.score.toLocaleString()}`;
    }
    return;
  }

  // 首次渲染 / 强制重绘
  const roleMap = { 1: "粉丝", 2: "管理员", 3: "明星" };
  const roleName = roleMap[u.role] || "未知";

  let adminHtml = "";
  if (u.role === 2) {
    adminHtml = `
      <a href="/stardock/admin/users.html">用户管理</a>
      <a href="/stardock/admin/gacha.html">卡池配置</a>
      <a href="/stardock/admin/activities.html">活动管理</a>
    `;
  }
  if (u.role === 3) {
    adminHtml = `<a href="/stardock/admin/activities.html">发布活动</a>`;
  }

  el.innerHTML = `
    <a href="/">🏠 作品集</a>
    <a href="/stardock/home.html">🏠 首页</a>
    <a href="/stardock/gacha.html">🎴 抽卡</a>
    <a href="/stardock/my-cards.html">📖 图鉴</a>
    <a href="/stardock/recharge.html">💰 充值</a>
    ${adminHtml}
    <span class="user-info">
      <span class="role-tag role-${u.role}">${roleName}</span>
      <span class="nick">${u.nickname}</span>
      <span class="score">💎 ${u.score.toLocaleString()}</span>
      <a href="/stardock/profile.html" class="btn btn-sm btn-secondary">个人中心</a>
      <button onclick="logout()">退出</button>
    </span>
  `;
  _navbarRendered = true;
}

/* ============================================================
   updateUserScore —— 只更新当前缓存的积分值（本地用）
   调完后 loadNavbar() 就只改积分数字不重绘
   ============================================================ */
function updateUserScore(newScore) {
  if (_currentUser) _currentUser.score = newScore;
  _saveUser(_currentUser);   // 同步进 sessionStorage，切页面后积分也是新的
  const scoreEl = document.querySelector("#navbar .user-info .score");
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
  _navbarRendered = false; // 换页面了，重新渲染导航栏
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

/**
 * 给按钮加 loading 状态（文案替换 + 禁点）
 */
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

/** 节流（注意：async 函数别用这个，用 btnLoading 禁点更靠谱） */
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

function toast(msg, type = "info", duration = 2500) {
  const box = document.getElementById("__toast_container");
  if (!box) return alert(msg);

  const el = document.createElement("div");
  const colors = {
    info:   { bg: "#2196f3", icon: "ℹ️" },
    success:{ bg: "#4caf50", icon: "✅" },
    error:  { bg: "#f44336", icon: "❌" },
    warn:   { bg: "#ff9800", icon: "⚠️" },
  };
  const c = colors[type] || colors.info;

  Object.assign(el.style, {
    background: c.bg, color: "#fff", padding: "12px 18px",
    borderRadius: "8px", boxShadow: "0 4px 12px rgba(0,0,0,0.3)",
    fontSize: "14px", display: "flex", alignItems: "center", gap: "10px",
    animation: "toastIn 0.25s ease", pointerEvents: "auto"
  });
  el.innerHTML = `<span style="font-size:18px">${c.icon}</span><span>${msg}</span>`;
  box.appendChild(el);

  setTimeout(() => {
    el.style.animation = "toastOut 0.25s ease";
    setTimeout(() => el.remove(), 250);
  }, duration);
}

if (!document.getElementById("__toast_style")) {
  const st = document.createElement("style");
  st.id = "__toast_style";
  st.textContent = `
    @keyframes toastIn  { from { transform: translateX(120%); opacity: 0 } to { transform: translateX(0); opacity: 1 } }
    @keyframes toastOut { from { transform: translateX(0);     opacity: 1 } to { transform: translateX(120%); opacity: 0 } }
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

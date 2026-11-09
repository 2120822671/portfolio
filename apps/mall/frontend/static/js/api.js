// ============== 公共 API 封装 ==============
const API_BASE = "/mall";

async function api(path, options = {}) {
  const headers = { "Content-Type": "application/json", ...(options.headers || {}) };
  const res = await fetch(API_BASE + path, {
    credentials: "include",
    ...options,
    headers,
    body: options.body && typeof options.body === "object" ? JSON.stringify(options.body) : options.body,
  });
  // 非 JSON（如 401 重定向等）
  const ct = res.headers.get("content-type") || "";
  let data;
  if (ct.includes("application/json")) {
    data = await res.json();
  } else {
    data = { code: res.status, msg: await res.text() };
  }
  if (!res.ok && data.code === 401) {
    location.href = "/static/index.html?needLogin=1";
    throw new Error(data.msg || "未登录");
  }
  if (data.code !== 0) throw new Error(data.msg || "请求失败");
  return data;
}

const $ = (sel, root = document) => root.querySelector(sel);
const $$ = (sel, root = document) => Array.from(root.querySelectorAll(sel));

function toast(msg, type = "info") {
  const box = document.getElementById("__toast_box") || (() => {
    const d = document.createElement("div");
    d.id = "__toast_box";
    d.style.cssText = "position:fixed;top:20px;left:50%;transform:translateX(-50%);z-index:9999;display:flex;flex-direction:column;gap:8px;pointer-events:none;";
    document.body.appendChild(d);
    return d;
  })();
  const div = document.createElement("div");
  div.textContent = msg;
  div.style.cssText = `padding:10px 18px;background:${type === "error" ? "#f56c6c" : type === "success" ? "#67c23a" : "#409eff"};color:#fff;border-radius:6px;box-shadow:0 4px 12px rgba(0,0,0,.15);font-size:14px;`;
  box.appendChild(div);
  setTimeout(() => { div.style.opacity = 0; div.style.transition = "opacity .3s"; setTimeout(() => div.remove(), 300); }, 2200);
}

function confirm2(msg) {
  return new Promise(res => {
    const ok = confirm(msg);
    res(ok);
  });
}

async function getMe() {
  try { return (await api("/api/auth/me")).user; } catch { return null; }
}

// ============== 公共头部组件 ==============
async function renderNav(containerSel = "#nav-wrap") {
  const me = await getMe();
  const navHtml = `
    <nav class="nav">
      <div class="nav-inner">
        <a class="nav-link" href="/">🏠 作品集</a>
        <a class="logo" href="/static/index.html">🍰 蛋糕商城</a>
        <a class="nav-link" href="/static/index.html">首页</a>
        <a class="nav-link" href="/static/cart.html">购物车</a>
        <a class="nav-link" href="/static/order.html">我的订单</a>
        <a class="nav-link" href="/static/address.html">收货地址</a>
        <a class="nav-link" href="/static/profile.html">个人中心</a>
        <span style="flex:1"></span>
        ${me
          ? `<span class="hi">你好，${me.nickname || me.username}${me.role === 1 ? ' <a href="/static/admin.html" class="nav-link">[后台]</a>' : ''}</span>
             <button class="btn-link" id="btnLogout">退出</button>`
          : `<button class="btn-primary" id="btnLogin">登录/注册</button>`}
      </div>
    </nav>`;
  document.getElementById(containerSel.replace("#","")) || Object.defineProperty(document, 'head', {configurable:true});
  const host = document.getElementById("nav-wrap");
  if (host) {
    host.innerHTML = navHtml;
    $("#btnLogin", host)?.addEventListener("click", openLogin);
    $("#btnLogout", host)?.addEventListener("click", async () => {
      await api("/api/auth/logout", { method: "POST" });
      toast("已退出", "success"); location.reload();
    });
  }
}

// 登录弹窗
function openLogin() {
  let m = document.getElementById("__login_modal");
  if (m) { m.style.display = "flex"; return; }
  m = document.createElement("div");
  m.id = "__login_modal";
  m.innerHTML = `
    <div class="modal-mask">
      <div class="modal-box">
        <div class="modal-tabs">
          <button class="tab active" data-tab="login">登录</button>
          <button class="tab" data-tab="register">注册</button>
        </div>
        <form class="modal-body" id="login-form">
          <input name="account" placeholder="用户名或手机号" autocomplete="username"><br>
          <input type="password" name="password" placeholder="密码" autocomplete="current-password"><br>
          <button type="submit" class="btn-primary btn-block">登录</button>
          <div class="tip">管理员账号：admin / 123456</div>
        </form>
        <form class="modal-body" id="register-form" style="display:none">
          <input name="username" placeholder="用户名"><br>
          <input name="phone" placeholder="11位手机号"><br>
          <input type="password" name="password" placeholder="密码 (≥6位)"><br>
          <button type="submit" class="btn-primary btn-block">注册</button>
        </form>
        <div class="modal-close" id="loginClose">×</div>
      </div>
    </div>`;
  document.body.appendChild(m);
  m.style.cssText = "position:fixed;inset:0;background:rgba(0,0,0,.4);display:flex;align-items:center;justify-content:center;z-index:9998;";
  const box = $(".modal-box", m);
  box.style.cssText = "background:#fff;border-radius:12px;padding:24px;width:360px;position:relative;";
  $("#loginClose", m).onclick = () => m.remove();
  m.onclick = (e) => { if (e.target === m) m.remove(); };
  // tab 切换
  $$(".tab", m).forEach(t => t.onclick = () => {
    $$(".tab", m).forEach(x => x.classList.remove("active"));
    t.classList.add("active");
    const isLogin = t.dataset.tab === "login";
    $("#login-form", m).style.display = isLogin ? "" : "none";
    $("#register-form", m).style.display = isLogin ? "none" : "";
  });
  // 登录提交
  $("#login-form", m).addEventListener("submit", async (e) => {
    e.preventDefault();
    const fd = new FormData(e.target);
    try {
      await api("/api/auth/login", { method: "POST", body: { account: fd.get("account"), password: fd.get("password") } });
      toast("登录成功", "success"); m.remove(); location.reload();
    } catch (err) { toast(err.message, "error"); }
  });
  $("#register-form", m).addEventListener("submit", async (e) => {
    e.preventDefault();
    const fd = new FormData(e.target);
    try {
      await api("/api/auth/register", { method: "POST", body: {
        username: fd.get("username"), phone: fd.get("phone"), password: fd.get("password") }});
      toast("注册成功，请登录", "success");
      $$(".tab", m).forEach(x => x.classList.remove("active"));
      $(".tab[data-tab=login]", m).classList.add("active");
      $("#login-form", m).style.display = "";
      $("#register-form", m).style.display = "none";
    } catch (err) { toast(err.message, "error"); }
  });
}

function needLogin() { openLogin(); return false; }

// ============== 通用样式注入 ==============
function injectCommonCss() {
  if (document.getElementById("__common_css")) return;
  const css = document.createElement("style");
  css.id = "__common_css";
  css.textContent = `
    * { box-sizing: border-box; }
    body { margin: 0; font-family: -apple-system, "Segoe UI", "PingFang SC", "Microsoft Yahei", sans-serif; background: #fff8f0; color: #333; }
    a { color: inherit; text-decoration: none; }
    .nav { background: linear-gradient(90deg, #ff9a9e, #fad0c4); box-shadow: 0 2px 8px rgba(0,0,0,.08); position: sticky; top: 0; z-index: 100; }
    .nav-inner { max-width: 1200px; margin: 0 auto; padding: 0 20px; height: 60px; display: flex; align-items: center; gap: 20px; color: #fff; font-weight: 500; }
    .logo { font-size: 22px; font-weight: 700; color: #fff; }
    .nav-link { color: rgba(255,255,255,.9); padding: 6px 10px; border-radius: 6px; }
    .nav-link:hover { background: rgba(255,255,255,.2); }
    .btn-primary { background: #ff6b6b; color: #fff; border: none; border-radius: 6px; padding: 8px 16px; cursor: pointer; font-size: 14px; }
    .btn-primary:hover { background: #ff5252; }
    .btn-link { background: transparent; border: 1px solid rgba(255,255,255,.5); color: #fff; border-radius: 6px; padding: 6px 14px; cursor: pointer; }
    .btn-link:hover { background: rgba(255,255,255,.15); }
    .btn-block { width: 100%; padding: 12px; font-size: 15px; margin-top: 10px; }
    .container { max-width: 1200px; margin: 16px auto; padding: 0 20px; }
    .grid { display: grid; gap: 16px; }
    .grid-cols-4 { grid-template-columns: repeat(4, 1fr); }
    @media (max-width: 900px) { .grid-cols-4 { grid-template-columns: repeat(2, 1fr); } }
    .card { background: #fff; border-radius: 10px; padding: 12px; box-shadow: 0 2px 8px rgba(0,0,0,.06); }
    .card img { width: 100%; height: 200px; object-fit: cover; border-radius: 8px; background: #f4f4f4; }
    .card h3 { margin: 8px 0 4px; font-size: 15px; line-height: 1.4; }
    .price { color: #ff4757; font-size: 18px; font-weight: 700; }
    .muted { color: #999; font-size: 12px; }
    .tag { background: #ffecec; color: #ff6b6b; font-size: 12px; padding: 2px 8px; border-radius: 10px; margin-right: 6px; }
    input, textarea, select { width: 100%; padding: 10px; border: 1px solid #e3e3e3; border-radius: 6px; font-size: 14px; margin: 4px 0 8px; }
    input:focus, textarea:focus { outline: none; border-color: #ff9a9e; }
    .section-title { font-size: 18px; margin: 16px 0 10px; color: #333; display:flex;align-items:center;gap:8px; }
    .filter-bar { display:flex; gap:12px; align-items:center; margin-bottom: 14px; flex-wrap: wrap; }
    .badge { background: #ff6b6b; color: #fff; border-radius: 10px; font-size: 11px; padding: 1px 6px; vertical-align: middle; margin-left: 4px; }
    .empty { text-align: center; padding: 60px; color: #aaa; }
    .modal-tabs { display:flex; gap:12px; border-bottom: 1px solid #eee; margin-bottom: 16px; }
    .modal-tabs .tab { flex:1; background: transparent; border: none; padding: 10px; font-size: 15px; cursor: pointer; color: #888; }
    .modal-tabs .tab.active { color: #ff6b6b; border-bottom: 2px solid #ff6b6b; font-weight: 600; }
    .tip { color: #aaa; font-size: 12px; margin-top: 12px; text-align:center; }
    .modal-close { position: absolute; top: 10px; right: 14px; font-size: 24px; cursor: pointer; color: #aaa; }
    .row { display:flex; justify-content: space-between; align-items:center; gap: 12px; }
    .btn-sm { padding: 4px 10px; font-size: 12px; border-radius: 4px; border: 1px solid #ff6b6b; background: #fff; color: #ff6b6b; cursor: pointer; }
    .btn-sm:hover { background: #ff6b6b; color: #fff; }
    .btn-ghost { border: 1px solid #ddd; background: #fff; color: #555; padding: 4px 10px; font-size: 12px; border-radius: 4px; cursor: pointer; }
    .btn-ghost:hover { background: #f5f5f5; }
    .table { width: 100%; border-collapse: collapse; background: #fff; border-radius: 8px; overflow:hidden; box-shadow: 0 2px 8px rgba(0,0,0,.04); }
    .table th, .table td { padding: 12px 10px; border-bottom: 1px solid #f4f4f4; text-align: left; font-size: 13px; }
    .table th { background: #fff8f0; color: #666; font-weight: 600; }
    .table tr:last-child td { border-bottom: none; }
    .status-0 { color: #ff9800; } .status-1 { color: #2196f3; } .status-2 { color: #4caf50; } .status-3 { color: #999; }
    .stepper { display:flex; align-items:center; gap: 0; }
    .stepper button { width: 28px; height: 28px; border: 1px solid #ddd; background: #fff; cursor: pointer; font-size: 16px; }
    .stepper button:first-child { border-radius: 4px 0 0 4px; }
    .stepper button:last-child { border-radius: 0 4px 4px 0; }
    .stepper span { width: 36px; text-align: center; border-top: 1px solid #ddd; border-bottom: 1px solid #ddd; font-size: 14px; }
    .stats-grid { display:grid; grid-template-columns: repeat(4,1fr); gap:16px; margin-bottom: 20px; }
    .stat-card { background: #fff; border-radius: 8px; padding: 20px; box-shadow: 0 2px 8px rgba(0,0,0,.04); }
    .stat-card .label { color: #999; font-size: 13px; }
    .stat-card .value { font-size: 28px; font-weight: 700; color: #ff6b6b; margin-top: 6px; }
    textarea { resize: vertical; min-height: 80px; }
    /* 购物车：紧密度布局 */
    .cart-card { display:flex; gap: 16px; align-items:center; padding: 14px 18px !important; }
    .cart-card .chk { width: 20px; height: 20px; flex-shrink:0; }
    .cart-card img { width: 110px; height: 110px; flex-shrink:0; }
    .cart-info { flex:1; min-width:0; }
    .cart-info .title { font-size: 15px; font-weight: 500; margin-bottom: 4px; }
    .cart-info .sub { font-size: 12px; color: #999; }
    .cart-right { display:flex; flex-direction:column; align-items:flex-end; gap: 8px; min-width: 150px; }
    .cart-right .price { font-size: 16px; }
    #checkoutBar { position: sticky; bottom: 20px !important; margin-top: 16px; padding: 14px 20px; z-index: 10; }
  `;
  document.head.appendChild(css);
}

/* ==========================================================
   招财记账 · 看板 / 自动化 / 消息中心
   ------------------------------------------------------------
   图表全部用原生 Canvas 手绘，不依赖任何 CDN，断网也能用。
   ========================================================== */

const D = {
    books: [],
    currentBookId: 1,
    stats: null,
    budgets: [],
    recurring: [],
    reports: [],
    unread: 0,
    checkin: null,
    tab: "record",
};

/* ==========================================================
   通用
   ========================================================== */

function dq(id) { return document.getElementById(id); }

function dMoney(n) {
    const v = Number(n) || 0;
    return "¥" + v.toFixed(2);
}

function dEsc(str) {
    return String(str == null ? "" : str)
        .replace(/&/g, "&amp;").replace(/</g, "&lt;")
        .replace(/>/g, "&gt;").replace(/"/g, "&quot;");
}

async function dFetch(url, options) {
    let res;
    try {
        res = await fetch(url, options);
    } catch (e) {
        throw new Error(buildNetError(url));
    }
    let data = null;
    try { data = await res.json(); } catch (e) { data = null; }
    if (!res.ok) {
        let msg = (data && data.detail) || "请求失败（" + res.status + "）";
        if (Array.isArray(msg)) msg = (msg[0] && msg[0].msg) || "参数错误";
        throw new Error(typeof msg === "string" ? msg : "请求失败");
    }
    return data;
}

function dJson(method, body) {
    return {
        method: method,
        headers: { "Content-Type": "application/json" },
        body: body ? JSON.stringify(body) : undefined,
    };
}

/* ==========================================================
   Canvas 图表（手绘，无依赖）
   ========================================================== */

const CHART_COLORS = ["#C0392B", "#E6B422", "#00B894", "#8E44AD", "#3498DB",
    "#E67E22", "#16A085", "#D35400", "#7F8C8D", "#2C3E50", "#AF7AC5", "#48C9B0"];

/** 准备高分辨率画布，返回绘图上下文与 CSS 尺寸 */
function prepCanvas(canvas, height) {
    if (!canvas) return null;
    const dpr = window.devicePixelRatio || 1;
    const cssW = canvas.clientWidth || canvas.parentElement.clientWidth || 320;
    const cssH = height || canvas.clientHeight || 200;
    canvas.width = Math.round(cssW * dpr);
    canvas.height = Math.round(cssH * dpr);
    canvas.style.height = cssH + "px";
    const ctx = canvas.getContext("2d");
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    ctx.clearRect(0, 0, cssW, cssH);
    return { ctx: ctx, w: cssW, h: cssH };
}

/** 圆角矩形路径 */
function roundRect(ctx, x, y, w, h, r) {
    r = Math.min(r, w / 2, h / 2);
    ctx.beginPath();
    ctx.moveTo(x + r, y);
    ctx.arcTo(x + w, y, x + w, y + h, r);
    ctx.arcTo(x + w, y + h, x, y + h, r);
    ctx.arcTo(x, y + h, x, y, r);
    ctx.arcTo(x, y, x + w, y, r);
    ctx.closePath();
}

/** 分类占比饼图（带图例） */
function drawPie(canvas, data, emptyText) {
    const p = prepCanvas(canvas, 240);
    if (!p) return;
    const { ctx, w, h } = p;
    const list = (data || []).filter(d => Number(d.value) > 0);

    if (!list.length) {
        ctx.fillStyle = "#9AA0A6";
        ctx.font = '14px "Microsoft YaHei", sans-serif';
        ctx.textAlign = "center";
        ctx.fillText(emptyText || "本月还没有支出数据", w / 2, h / 2);
        return;
    }

    const total = list.reduce((s, d) => s + Number(d.value), 0);
    const cx = w / 2, cy = h / 2, R = Math.min(w, h) / 2 - 8;

    let start = -Math.PI / 2;
    list.forEach((d, i) => {
        const angle = (Number(d.value) / total) * Math.PI * 2;
        ctx.beginPath();
        ctx.moveTo(cx, cy);
        ctx.arc(cx, cy, R, start, start + angle);
        ctx.closePath();
        ctx.fillStyle = CHART_COLORS[i % CHART_COLORS.length];
        ctx.fill();
        ctx.strokeStyle = "#fff";
        ctx.lineWidth = 2;
        ctx.stroke();
        start += angle;
    });

    // 中心留白 + 总额
    ctx.beginPath();
    ctx.arc(cx, cy, R * 0.55, 0, Math.PI * 2);
    ctx.fillStyle = "#FDF6EC";
    ctx.fill();
    ctx.fillStyle = "#2f2b28";
    ctx.font = 'bold 15px "Microsoft YaHei", sans-serif';
    ctx.textAlign = "center";
    ctx.fillText("本月支出", cx, cy - 4);
    ctx.fillStyle = "#C0392B";
    ctx.font = 'bold 14px "Microsoft YaHei", sans-serif';
    ctx.fillText("¥" + total.toFixed(0), cx, cy + 14);
}

/** 月度趋势折线（收入 / 支出 双线） */
function drawLine(canvas, data, emptyText) {
    const p = prepCanvas(canvas, 240);
    if (!p) return;
    const { ctx, w, h } = p;
    const list = data || [];

    if (!list.length || list.every(d => !d.income && !d.expense)) {
        ctx.fillStyle = "#9AA0A6";
        ctx.font = '14px "Microsoft YaHei", sans-serif';
        ctx.textAlign = "center";
        ctx.fillText(emptyText || "暂无趋势数据", w / 2, h / 2);
        return;
    }

    const padL = 44, padR = 12, padT = 16, padB = 30;
    const cw = w - padL - padR, ch = h - padT - padB;

    const max = Math.max(1, ...list.map(d => Math.max(Number(d.income), Number(d.expense))));
    const niceMax = Math.ceil(max / 100) * 100 || max;

    // 网格 + Y 轴刻度
    ctx.strokeStyle = "#EDE3D4";
    ctx.lineWidth = 1;
    ctx.fillStyle = "#9A8F80";
    ctx.font = '11px "Microsoft YaHei", sans-serif';
    ctx.textAlign = "right";
    for (let i = 0; i <= 4; i++) {
        const y = padT + ch - (ch * i / 4);
        ctx.beginPath();
        ctx.moveTo(padL, y);
        ctx.lineTo(w - padR, y);
        ctx.stroke();
        ctx.fillText(Math.round(niceMax * i / 4), padL - 6, y + 4);
    }

    const stepX = list.length > 1 ? cw / (list.length - 1) : 0;
    const px = i => padL + stepX * i;
    const py = v => padT + ch - (Number(v) / niceMax) * ch;

    // 面积 + 折线
    const drawSeries = (key, color, fill) => {
        ctx.beginPath();
        list.forEach((d, i) => {
            const x = px(i), y = py(d[key]);
            i === 0 ? ctx.moveTo(x, y) : ctx.lineTo(x, y);
        });
        if (fill) {
            ctx.save();
            ctx.lineTo(px(list.length - 1), padT + ch);
            ctx.lineTo(px(0), padT + ch);
            ctx.closePath();
            const g = ctx.createLinearGradient(0, padT, 0, padT + ch);
            g.addColorStop(0, color.replace(")", ",0.28)").replace("rgb", "rgba"));
            g.addColorStop(1, color.replace(")", ",0.02)").replace("rgb", "rgba"));
            ctx.fillStyle = g;
            ctx.fill();
            ctx.restore();
            // 重画线
            ctx.beginPath();
            list.forEach((d, i) => {
                const x = px(i), y = py(d[key]);
                i === 0 ? ctx.moveTo(x, y) : ctx.lineTo(x, y);
            });
        }
        ctx.strokeStyle = color;
        ctx.lineWidth = 2.5;
        ctx.lineJoin = "round";
        ctx.stroke();

        list.forEach((d, i) => {
            const x = px(i), y = py(d[key]);
            ctx.beginPath();
            ctx.arc(x, y, 3.5, 0, Math.PI * 2);
            ctx.fillStyle = "#fff";
            ctx.fill();
            ctx.strokeStyle = color;
            ctx.lineWidth = 2;
            ctx.stroke();
        });
    };

    drawSeries("expense", "rgb(192,57,43)", true);
    drawSeries("income", "rgb(0,184,148)", true);

    // X 轴标签
    ctx.fillStyle = "#9A8F80";
    ctx.font = '11px "Microsoft YaHei", sans-serif';
    ctx.textAlign = "center";
    list.forEach((d, i) => {
        const label = String(d.month).slice(5) + "月";
        ctx.fillText(label, px(i), h - 10);
    });

    // 图例
    ctx.textAlign = "left";
    ctx.font = '12px "Microsoft YaHei", sans-serif';
    ctx.fillStyle = "#C0392B";
    ctx.fillText("● 支出", padL, 10);
    ctx.fillStyle = "#00B894";
    ctx.fillText("● 收入", padL + 56, 10);
}

/** 近 7 日支出柱状图 */
function drawBar(canvas, data, emptyText) {
    const p = prepCanvas(canvas, 240);
    if (!p) return;
    const { ctx, w, h } = p;
    const list = data || [];

    if (!list.length || list.every(d => !Number(d.amount))) {
        ctx.fillStyle = "#9AA0A6";
        ctx.font = '14px "Microsoft YaHei", sans-serif';
        ctx.textAlign = "center";
        ctx.fillText(emptyText || "最近 7 天还没有支出", w / 2, h / 2);
        return;
    }

    const padL = 44, padR = 12, padT = 18, padB = 30;
    const cw = w - padL - padR, ch = h - padT - padB;
    const max = Math.max(1, ...list.map(d => Number(d.amount)));
    const niceMax = Math.ceil(max / 50) * 50 || max;

    ctx.strokeStyle = "#EDE3D4";
    ctx.lineWidth = 1;
    ctx.fillStyle = "#9A8F80";
    ctx.font = '11px "Microsoft YaHei", sans-serif';
    ctx.textAlign = "right";
    for (let i = 0; i <= 4; i++) {
        const y = padT + ch - (ch * i / 4);
        ctx.beginPath();
        ctx.moveTo(padL, y);
        ctx.lineTo(w - padR, y);
        ctx.stroke();
        ctx.fillText(Math.round(niceMax * i / 4), padL - 6, y + 4);
    }

    const slot = cw / list.length;
    const bw = Math.min(30, slot * 0.55);

    list.forEach((d, i) => {
        const v = Number(d.amount);
        const bh = (v / niceMax) * ch;
        const x = padL + slot * i + (slot - bw) / 2;
        const y = padT + ch - bh;

        const g = ctx.createLinearGradient(0, y, 0, padT + ch);
        g.addColorStop(0, "#E8A33D");
        g.addColorStop(1, "#C0392B");
        ctx.fillStyle = g;
        roundRect(ctx, x, y, bw, Math.max(bh, 2), 5);
        ctx.fill();

        if (v > 0) {
            ctx.fillStyle = "#8A7B6B";
            ctx.font = 'bold 11px "Microsoft YaHei", sans-serif';
            ctx.textAlign = "center";
            ctx.fillText(Math.round(v), x + bw / 2, y - 5);
        }

        ctx.fillStyle = "#9A8F80";
        ctx.font = '11px "Microsoft YaHei", sans-serif';
        ctx.textAlign = "center";
        ctx.fillText(d.label, x + bw / 2, h - 10);
    });
}

/** 分类图例（HTML 形式，挂在饼图下方） */
function renderPieLegend(data) {
    const list = (data || []).filter(d => Number(d.value) > 0);
    const total = list.reduce((s, d) => s + Number(d.value), 0) || 1;
    if (!list.length) {
        return '<div class="legend-empty">本月还没有支出数据</div>';
    }
    return list.map((d, i) => {
        const pct = (Number(d.value) / total * 100).toFixed(1);
        return `<div class="legend-item">
            <span class="legend-dot" style="background:${CHART_COLORS[i % CHART_COLORS.length]}"></span>
            <span class="legend-name">${dEsc(d.name)}</span>
            <span class="legend-pct">${pct}%</span>
            <span class="legend-val">${dMoney(d.value)}</span>
        </div>`;
    }).join("");
}

/* ==========================================================
   账本（多账户）
   ========================================================== */

async function loadBooks() {
    try {
        const res = await dFetch(API_BASE + "/api/books");
        D.books = res.data || [];
        if (!D.books.find(b => b.id === D.currentBookId)) {
            D.currentBookId = D.books.length ? D.books[0].id : 1;
        }
        renderBookSwitcher();
        renderBookCards();
    } catch (err) {
        console.error("loadBooks 失败", err);
    }
}

function renderBookSwitcher() {
    const el = dq("bookSwitch");
    if (!el) return;
    const cur = D.books.find(b => b.id === D.currentBookId);
    const others = D.books.filter(b => b.id !== D.currentBookId);

    el.innerHTML = `
        <button class="book-current" id="bookCurrentBtn">
            <span class="book-icon">${cur ? cur.icon : "💰"}</span>
            <span class="book-name">${cur ? dEsc(cur.name) : "日常账本"}</span>
            <span class="book-caret">▾</span>
        </button>
        <div class="book-menu" id="bookMenu">
            ${D.books.map(b => `
                <div class="book-menu-item ${b.id === D.currentBookId ? "active" : ""}" data-book="${b.id}">
                    <span class="book-icon">${b.icon}</span>
                    <span class="book-name">${dEsc(b.name)}</span>
                    <span class="book-balance">${dMoney(b.balance)}</span>
                </div>`).join("")}
            <div class="book-menu-sep"></div>
            <div class="book-menu-item book-add" id="bookAddItem">➕ 新建账本</div>
        </div>`;

    const btn = dq("bookCurrentBtn");
    btn.addEventListener("click", e => {
        e.stopPropagation();
        el.classList.toggle("open");
    });

    el.querySelectorAll("[data-book]").forEach(item => {
        item.addEventListener("click", e => {
            e.stopPropagation();
            D.currentBookId = parseInt(item.dataset.book, 10);
            el.classList.remove("open");
            onBookChanged();
        });
    });

    const addItem = dq("bookAddItem");
    if (addItem) addItem.addEventListener("click", e => {
        e.stopPropagation();
        el.classList.remove("open");
        openBookDialog();
    });
}

function renderBookCards() {
    const el = dq("bookCards");
    if (!el) return;
    if (!D.books.length) {
        el.innerHTML = '<div class="empty-tip">还没有账本</div>';
        return;
    }
    el.innerHTML = D.books.map(b => `
        <div class="book-card ${b.id === D.currentBookId ? "active" : ""}" data-book="${b.id}">
            <div class="book-card-icon">${b.icon}</div>
            <div class="book-card-name">${dEsc(b.name)}</div>
            <div class="book-card-type">${dEsc(b.bookType)}</div>
            <div class="book-card-balance">${dMoney(b.balance)}</div>
            <div class="book-card-sub">收 ${dMoney(b.income)} · 支 ${dMoney(b.expense)} · ${b.count} 笔</div>
            ${b.isDefault ? "" : `<button class="book-card-del" data-del-book="${b.id}" title="删除账本">✕</button>`}
        </div>`).join("");

    el.querySelectorAll(".book-card").forEach(card => {
        card.addEventListener("click", e => {
            if (e.target.closest("[data-del-book]")) return;
            D.currentBookId = parseInt(card.dataset.book, 10);
            renderBookSwitcher();
            renderBookCards();
            onBookChanged();
        });
    });

    el.querySelectorAll("[data-del-book]").forEach(btn => {
        btn.addEventListener("click", async e => {
            e.stopPropagation();
            const id = parseInt(btn.dataset.delBook, 10);
            const book = D.books.find(b => b.id === id);
            if (!confirm(`确定删除账本「${book.name}」吗？\n该账本下的流水会转移到默认账本，不会丢失。`)) return;
            try {
                await dFetch(API_BASE + "/api/books/" + id, { method: "DELETE" });
                toast("账本已删除", "success");
                await loadBooks();
                onBookChanged();
            } catch (err) {
                toast("删除失败：" + err.message, "error");
            }
        });
    });
}

function openBookDialog() {
    const types = [
        { value: "现金", label: "💵 现金" },
        { value: "支付宝", label: "💙 支付宝" },
        { value: "微信", label: "💚 微信" },
        { value: "银行卡", label: "💳 银行卡" },
        { value: "信用卡", label: "🧧 信用卡" },
    ];
    const icons = { "现金": "💵", "支付宝": "💙", "微信": "💚", "银行卡": "💳", "信用卡": "🧧" };

    openFormModal({
        title: "新建账本",
        icon: "💳",
        desc: "给不同账户分开记账，余额自动算",
        submitText: "创建账本",
        fields: [
            { key: "name", label: "账本名称", required: true, placeholder: "如：支付宝、微信、现金" },
            { key: "bookType", label: "账本类型", type: "select", value: "现金", options: types },
            { key: "initBalance", label: "初始余额（元）", type: "number", value: 0, min: 0, step: "0.01", hint: "余额 = 初始余额 + 收入 − 支出" },
        ],
        onSubmit: async (v) => {
            const bookType = v.bookType || "现金";
            const res = await dFetch(API_BASE + "/api/books", dJson("POST", {
                name: v.name, bookType: bookType,
                initBalance: Number(v.initBalance) || 0,
                icon: icons[bookType] || "💰",
            }));
            toast("账本「" + res.data.name + "」创建成功 🎉", "success");
            await loadBooks();
        },
    });
}

async function onBookChanged() {
    // 同步全局账本状态（列表 / 汇总 / 统计都按账本过滤）
    if (typeof window.setGlobalBook === "function") {
        window.setGlobalBook(D.currentBookId);
    }
    renderBookSwitcher();
    renderBookCards();
    await Promise.all([
        loadDashboard(),
        loadBudgets(),
        typeof window.refreshRecords === "function" ? window.refreshRecords() : Promise.resolve(),
    ]);
}

/* ==========================================================
   看板
   ========================================================== */

async function loadDashboard() {
    try {
        const acc = D.currentBookId ? "?months=6&accountId=" + D.currentBookId : "?months=6";
        const res = await dFetch(API_BASE + "/api/stats/overview" + acc);
        D.stats = res.data;

        drawPie(dq("chartPie"), D.stats.category);
        dq("pieLegend").innerHTML = renderPieLegend(D.stats.category);
        drawLine(dq("chartTrend"), D.stats.trend);
        drawBar(dq("chartLast7"), D.stats.last7);

        await loadCheckin();
        loadQuote();
    } catch (err) {
        console.error("loadDashboard 失败", err);
    }
}

async function loadCheckin() {
    try {
        const res = await dFetch(API_BASE + "/api/checkin");
        D.checkin = res.data;
        const el = dq("checkinBox");
        if (!el) return;
        const c = D.checkin;
        el.innerHTML = `
            <div class="checkin-main">
                <div class="checkin-streak">🔥 ${c.streak}</div>
                <div class="checkin-label">连续记账天数</div>
            </div>
            <div class="checkin-side">
                <div class="checkin-stat"><b>${c.totalDays}</b><span>打卡天数</span></div>
                <div class="checkin-stat"><b>${c.totalRecords}</b><span>累计笔数</span></div>
            </div>
            <div class="badge-row">
                ${c.badges.map(b => `
                    <div class="badge ${b.got ? "got" : "locked"}" title="${dEsc(b.desc)}">
                        <span class="badge-icon">${b.got ? "🏅" : "🔒"}</span>
                        <span class="badge-name">${dEsc(b.name)}</span>
                    </div>`).join("")}
            </div>`;
    } catch (err) {
        console.error("loadCheckin 失败", err);
    }
}

async function loadQuote() {
    const el = dq("dailyQuote");
    if (!el) return;
    try {
        const res = await dFetch(API_BASE + "/api/quote");
        el.textContent = res.data.quote;
    } catch (e) { /* 忽略 */ }
}

/** 月度账单解读（大模型优先，失败回落规则） */
async function monthlyReview() {
    const btn = dq("btnMonthlyReview");
    if (btn) { btn.disabled = true; btn.textContent = "生成中…"; }
    const box = dq("monthlyReviewBox");
    if (box) box.innerHTML = '<div class="empty-tip">正在解读…</div>';

    try {
        const res = await dFetch(API_BASE + "/api/chat", dJson("POST", {
            text: "分析一下本月账单", accountId: D.currentBookId,
        }));
        const reply = (res.data && res.data.reply) || "暂时没有足够的数据来解读喵。";
        if (box) {
            box.innerHTML = `<div class="review-text">${dEsc(reply)}</div>
                <div class="review-meta">生成方式：${res.mode === "llm" ? "大模型" : "规则引擎"}</div>`;
        }
    } catch (err) {
        if (box) box.innerHTML = `<div class="empty-tip">生成失败：${dEsc(err.message)}</div>`;
    } finally {
        if (btn) { btn.disabled = false; btn.textContent = "📜 生成本月账单解读"; }
    }
}

/* ==========================================================
   预算
   ========================================================== */

async function loadBudgets() {
    try {
        const period = new Date().toISOString().slice(0, 7);
        const res = await dFetch(API_BASE + "/api/budgets?period=" + period);
        D.budgets = (res.data && res.data.budgets) || [];
        renderBudgets();
    } catch (err) {
        console.error("loadBudgets 失败", err);
    }
}

function renderBudgets() {
    const el = dq("budgetList");
    if (!el) return;
    if (!D.budgets.length) {
        el.innerHTML = '<div class="empty-tip">还没有设置预算，点右上角「设预算」开始</div>';
        return;
    }
    el.innerHTML = D.budgets.map(b => {
        const cls = b.over ? "over" : (b.rate >= 80 ? "warn" : "ok");
        const color = b.over ? "#D63031" : (b.rate >= 80 ? "#E6B422" : "#00B894");
        return `
        <div class="budget-item ${cls}">
            <div class="budget-head">
                <span class="budget-cat">${dEsc(b.category)}</span>
                <span class="budget-num">${dMoney(b.used)} / ${dMoney(b.amount)}</span>
            </div>
            <div class="budget-bar"><div class="budget-fill" style="width:${Math.min(100, b.rate)}%;background:${color}"></div></div>
            <div class="budget-foot">
                <span>${b.over ? "已超支 " + dMoney(-b.remain) : "剩余 " + dMoney(b.remain)}</span>
                <span>${b.rate}%</span>
                <button class="budget-del" data-del-budget="${b.id}" title="删除预算">✕</button>
            </div>
        </div>`;
    }).join("");

    el.querySelectorAll("[data-del-budget]").forEach(btn => {
        btn.addEventListener("click", async () => {
            try {
                await dFetch(API_BASE + "/api/budgets/" + btn.dataset.delBudget, { method: "DELETE" });
                toast("预算已删除", "success");
                loadBudgets();
            } catch (err) { toast("删除失败：" + err.message, "error"); }
        });
    });
}

function openBudgetDialog() {
    const period = new Date().toISOString().slice(0, 7);
    const commonCats = ["餐饮", "交通", "购物", "娱乐", "生活", "医疗"];

    openFormModal({
        title: "设置月度预算",
        icon: "🎯",
        desc: "给常用分类设个上限，超过 80% 提醒你",
        submitText: "保存预算",
        fields: [
            {
                key: "category", label: "预算分类", type: "select", value: "餐饮",
                options: commonCats.concat(["其他"]),
                hint: "选一个分类，下方填月度上限",
            },
            {
                key: "amount", label: "月度预算金额（元）", type: "number",
                required: true, min: 0, step: "0.01", placeholder: "如：800",
            },
            { key: "period", label: "预算月份", type: "month", value: period, hint: "默认本月" },
        ],
        onSubmit: async (v) => {
            const amount = Number(v.amount);
            if (!amount || amount <= 0) throw new Error("预算金额必须大于 0");
            await dFetch(API_BASE + "/api/budgets", dJson("POST", {
                category: v.category, period: v.period || period,
                amount: amount, enabled: 1,
            }));
            toast(`「${v.category}」本月预算 ${dMoney(amount)} 已设置 📌`, "success");
            await loadBudgets();
        },
    });
}

/* ==========================================================
   周期账单
   ========================================================== */

async function loadRecurring() {
    try {
        const res = await dFetch(API_BASE + "/api/recurring");
        D.recurring = (res.data && res.data.rules) || [];
        renderRecurring();
    } catch (err) {
        console.error("loadRecurring 失败", err);
    }
}

function renderRecurring() {
    const el = dq("recurringList");
    if (!el) return;
    if (!D.recurring.length) {
        el.innerHTML = '<div class="empty-tip">还没有周期账单，加一条房租/订阅试试～</div>';
        return;
    }
    const cycleText = { daily: "每天", weekly: "每周", monthly: "每月" };
    el.innerHTML = D.recurring.map(r => `
        <div class="rec-item ${r.enabled ? "" : "disabled"}">
            <div class="rec-icon">${r.type === 1 ? "💵" : "📆"}</div>
            <div class="rec-body">
                <div class="rec-title">${dEsc(r.name)}</div>
                <div class="rec-meta">
                    ${cycleText[r.cycleType] || r.cycleType}${r.cycleValue > 1 ? "×" + r.cycleValue : ""}
                    · ${dEsc(r.category)}
                    · ${r.autoPost ? "自动入账" : "仅提醒"}
                </div>
                <div class="rec-sub">起始 ${dEsc(r.startDate || "")}${r.endDate ? " · 截止 " + dEsc(r.endDate) : ""}</div>
            </div>
            <div class="rec-amount ${r.type === 1 ? "type-income" : "type-expense"}">
                ${r.type === 1 ? "+" : "-"}${Number(r.amount).toFixed(2)}
            </div>
            <div class="rec-actions">
                <button class="rec-btn" data-run-rule="${r.id}" title="立即执行一次">▶</button>
                <button class="rec-btn" data-del-rule="${r.id}" title="删除">✕</button>
            </div>
        </div>`).join("");

    el.querySelectorAll("[data-run-rule]").forEach(btn => {
        btn.addEventListener("click", async () => {
            try {
                const res = await dFetch(API_BASE + "/api/recurring/" + btn.dataset.runRule + "/run",
                    { method: "POST" });
                const d = res.data || {};
                if (d.ran === false) {
                    toast(d.reason || "今天不在执行周期内", "");
                } else {
                    toast(`执行完成：入账 ${d.posted} 条，跳过 ${d.skipped} 条`, "success");
                }
                loadRecurring();
                loadDashboard();
            } catch (err) { toast("执行失败：" + err.message, "error"); }
        });
    });

    el.querySelectorAll("[data-del-rule]").forEach(btn => {
        btn.addEventListener("click", async () => {
            if (!confirm("确定删除这条周期账单规则吗？")) return;
            try {
                await dFetch(API_BASE + "/api/recurring/" + btn.dataset.delRule, { method: "DELETE" });
                toast("规则已删除", "success");
                loadRecurring();
            } catch (err) { toast("删除失败：" + err.message, "error"); }
        });
    });
}

function openRecurringDialog() {
    const today = new Date();
    const p = n => String(n).padStart(2, "0");
    const todayStr = today.getFullYear() + "-" + p(today.getMonth() + 1) + "-" + p(today.getDate());

    openFormModal({
        title: "新建周期账单",
        icon: "🔁",
        desc: "房租、订阅、工资这类固定收支，设一次就够",
        submitText: "创建规则",
        fields: [
            { key: "name", label: "名称", required: true, placeholder: "如：房租、视频会员、工资" },
            {
                key: "type", label: "收支类型", type: "segment", value: "2",
                options: [{ value: "2", label: "支出" }, { value: "1", label: "收入" }],
            },
            { key: "amount", label: "金额（元）", type: "number", required: true, min: 0, step: "0.01", placeholder: "如：2800" },
            {
                key: "category", label: "分类", type: "select", value: "生活",
                options: ["生活", "餐饮", "交通", "购物", "娱乐", "医疗", "其他", "工资", "奖金", "其他收入"],
            },
            {
                key: "cycleType", label: "执行周期", type: "segment", value: "monthly",
                options: [
                    { value: "daily", label: "每天" },
                    { value: "weekly", label: "每周" },
                    { value: "monthly", label: "每月" },
                ],
                hint: "「每月」按起始日期的号数执行，例：起始 11-01 则每月 1 号入账",
            },
            {
                key: "cycleValue", label: "间隔（每 N 个周期）", type: "number",
                value: 1, min: 1, step: 1, hint: "填 2 表示每两天 / 每两周 / 每两个月",
            },
            { key: "startDate", label: "起始日期", type: "date", value: todayStr, required: true },
            {
                key: "autoPost", label: "执行方式", type: "segment", value: "1",
                options: [
                    { value: "1", label: "自动入账" },
                    { value: "0", label: "只提醒" },
                ],
                hint: "「只提醒」只生成待确认条目，不直接写账",
            },
        ],
        onSubmit: async (v) => {
            const amount = Number(v.amount);
            if (!amount || amount <= 0) throw new Error("金额必须大于 0");
            const cycleValue = Math.max(1, parseInt(v.cycleValue, 10) || 1);
            const type = parseInt(v.type, 10) === 1 ? 1 : 2;

            await dFetch(API_BASE + "/api/recurring", dJson("POST", {
                name: v.name,
                type: type,
                amount: amount,
                category: v.category,
                remark: v.name,
                accountId: D.currentBookId,
                cycleType: v.cycleType,
                cycleValue: cycleValue,
                startDate: v.startDate || todayStr,
                autoPost: parseInt(v.autoPost, 10) === 0 ? 0 : 1,
                enabled: 1,
            }));
            toast("周期账单「" + v.name + "」已创建 🔁", "success");
            await loadRecurring();
        },
    });
}

function cycleTypeVal(s) {
    if (s === "daily") return "daily";
    if (s === "weekly") return "weekly";
    return "monthly";
}

/* ==========================================================
   消息中心（日报 / 复盘 / 预警）
   ========================================================== */

async function loadReports() {
    try {
        const res = await dFetch(API_BASE + "/api/reports?limit=40");
        D.reports = (res.data && res.data.reports) || [];
        D.unread = (res.data && res.data.unread) || 0;
        renderReports();
        renderBell();
    } catch (err) {
        console.error("loadReports 失败", err);
    }
}

function renderBell() {
    const badge = dq("bellBadge");
    if (!badge) return;
    badge.textContent = D.unread > 99 ? "99+" : D.unread;
    badge.style.display = D.unread > 0 ? "flex" : "none";
}

function renderReports() {
    const html = buildReportsHtml();
    const el = dq("reportList");
    if (el) el.innerHTML = html;
    const side = dq("reportListSide");
    if (side) side.innerHTML = html;
}

function buildReportsHtml() {
    if (!D.reports.length) {
        return '<div class="empty-tip">还没有日报。系统每天 23:00 自动生成收支小结，23:10 生成消费复盘。</div>';
    }
    const typeIcon = { summary: "📊", review: "🐱", recurring: "🔁", warning: "⚠️" };
    return D.reports.map(r => `
        <div class="report-item ${r.isRead ? "" : "unread"} level-${dEsc(r.level)}">
            <div class="report-icon">${typeIcon[r.type] || "📄"}</div>
            <div class="report-body">
                <div class="report-title">${dEsc(r.title)}${r.isRead ? "" : '<span class="report-dot"></span>'}</div>
                <div class="report-content">${dEsc(r.content || "")}</div>
                <div class="report-time">${dEsc(r.createdAt || r.date || "")}</div>
            </div>
        </div>`).join("");
}

function openReportPanel() {
    const panel = dq("reportPanel");
    const mask = dq("reportMask");
    if (!panel) return;
    panel.classList.add("open");
    if (mask) mask.classList.add("open");
    loadReports();
}

function closeReportPanel() {
    const panel = dq("reportPanel");
    const mask = dq("reportMask");
    if (panel) panel.classList.remove("open");
    if (mask) mask.classList.remove("open");
}

/* ==========================================================
   标签页切换
   ========================================================== */

function bindTabs() {
    const tabs = dq("tabs");
    if (!tabs) return;

    tabs.addEventListener("click", e => {
        const btn = e.target.closest("button[data-tab]");
        if (!btn) return;
        switchTab(btn.dataset.tab);
    });
}

function switchTab(name) {
    D.tab = name;
    document.querySelectorAll("#tabs button[data-tab]").forEach(b => {
        b.classList.toggle("active", b.dataset.tab === name);
    });
    document.querySelectorAll("[data-panel]").forEach(p => {
        p.classList.toggle("active", p.dataset.panel === name);
    });

    // 切到看板时重绘（Canvas 尺寸依赖可见性）
    if (name === "board") {
        loadDashboard();
        loadBudgets();
    }
    if (name === "auto") {
        loadRecurring();
        loadReports();
        loadSchedulerStatus();
    }
}

async function loadSchedulerStatus() {
    const el = dq("schedulerStatus");
    if (!el) return;
    try {
        const res = await dFetch(API_BASE + "/api/scheduler/jobs");
        const d = res.data || {};
        el.innerHTML = `
            <div class="sched-row"><span>调度时区</span><b>${dEsc(d.timezone || "-")}</b></div>
            <div class="sched-row"><span>大模型</span><b>${d.llmEnabled ? "已启用 · " + dEsc(d.llmModel) : "未配置（走规则模式）"}</b></div>
            ${(d.jobs || []).map(j => `
                <div class="sched-row"><span>${dEsc(j.name)}</span><b>下次 ${dEsc(j.nextRun || "-")}</b></div>`).join("")}`;
    } catch (e) {
        el.innerHTML = '<div class="empty-tip">调度状态读取失败</div>';
    }
}

/* ==========================================================
   初始化
   ========================================================== */

/**
 * 初始化入口
 * 注意：本文件可能是「动态加载」的（脚本插入时 DOMContentLoaded 已经触发过），
 * 所以不能只依赖 DOMContentLoaded 事件，必须同时判断 document.readyState。
 */
function initDashboard() {
    if (initDashboard._done) return;
    initDashboard._done = true;

    bindTabs();
    loadBooks();
    loadDashboard();
    loadBudgets();
    loadRecurring();
    loadReports();

    const bell = dq("bellBtn");
    if (bell) bell.addEventListener("click", openReportPanel);

    const closeBtn = dq("reportClose");
    if (closeBtn) closeBtn.addEventListener("click", closeReportPanel);

    const mask = dq("reportMask");
    if (mask) mask.addEventListener("click", closeReportPanel);

    const readAll = dq("btnReadAll");
    if (readAll) {
        readAll.addEventListener("click", async () => {
            try {
                await dFetch(API_BASE + "/api/reports/read-all", { method: "POST" });
                loadReports();
            } catch (err) { toast("操作失败：" + err.message, "error"); }
        });
    }

    const btnBudget = dq("btnAddBudget");
    if (btnBudget) btnBudget.addEventListener("click", openBudgetDialog);

    const btnRec = dq("btnAddRecurring");
    if (btnRec) btnRec.addEventListener("click", openRecurringDialog);

    const btnRunRec = dq("btnRunRecurring");
    if (btnRunRec) {
        btnRunRec.addEventListener("click", async () => {
            try {
                const res = await dFetch(API_BASE + "/api/recurring/run", { method: "POST" });
                const d = res.data || {};
                toast(`已处理：入账 ${d.posted}，待确认 ${d.pending}，跳过 ${d.skipped}`, "success");
                loadRecurring();
            } catch (err) { toast("执行失败：" + err.message, "error"); }
        });
    }

    const btnSummary = dq("btnRunSummary");
    if (btnSummary) {
        btnSummary.addEventListener("click", async () => {
            try {
                await dFetch(API_BASE + "/api/automation/run-summary", { method: "POST" });
                toast("日终汇总已生成 📊", "success");
                loadReports();
            } catch (err) { toast("生成失败：" + err.message, "error"); }
        });
    }

    const btnReview = dq("btnRunReview");
    if (btnReview) {
        btnReview.addEventListener("click", async () => {
            try {
                await dFetch(API_BASE + "/api/automation/run-review", { method: "POST" });
                toast("消费复盘已生成 🐱", "success");
                loadReports();
            } catch (err) { toast("生成失败：" + err.message, "error"); }
        });
    }

    const btnMonthly = dq("btnMonthlyReview");
    if (btnMonthly) btnMonthly.addEventListener("click", monthlyReview);

    // 消息中心每 60 秒刷新一次未读数
    setInterval(loadReports, 60000);
}

/* 立即初始化：DOM 已就绪则直接跑，否则等 DOMContentLoaded */
if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", initDashboard);
} else {
    initDashboard();
}

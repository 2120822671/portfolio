/* ==========================================================
   个人记账小系统 · 前端逻辑
   ========================================================== */

/* API 基址：
   - 页面由后端托管（http://localhost:8005/）→ 用相对路径，同源，零跨域问题
   - 页面以 file:// 直接打开                → 用绝对地址，指向本机后端
   两种情况都做了兜底探测，避免出现 "Failed to fetch" */
const API_BASE = (location.protocol === "file:")
    ? "http://localhost:8005"
    : "/account";              // 作品集整合：子应用挂载前缀
const API = API_BASE + "/api/records";

// 招财猫解析模式：
//   auto = 调用后端 /api/chat（后端优先用大模型，失败自动回落规则，规则也失败再回落本地解析）
//   rule = 只用前端本地规则（完全离线）
//   llm  = 强制走后端大模型（未配置 Key 时后端会回落规则）
const PARSE_MODE = "auto";

const state = {
    pageNum: 1,
    pageSize: 10,
    total: 0,
    list: [],
    keyword: "",
    type: "",
    startDate: "",
    endDate: "",
    drawerRecord: null,
    lastCategory: null,
    summaryCache: null,
    accountId: 1,
};

/* ========================= 通用工具 ========================= */

function money(n) {
    const v = Number(n) || 0;
    return "¥" + v.toFixed(2);
}

function esc(str) {
    return String(str == null ? "" : str)
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;");
}

function toast(text, type = "") {
    const el = document.getElementById("toast");
    el.textContent = text;
    el.className = "toast show " + type;
    clearTimeout(el._timer);
    el._timer = setTimeout(() => { el.className = "toast " + type; }, 2600);
}

async function apiFetch(url, options) {
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
        if (Array.isArray(msg)) {
            msg = (msg[0] && msg[0].msg) || "参数错误";
        }
        throw new Error(typeof msg === "string" ? msg : "请求失败");
    }
    return data;
}

/**
 * fetch 抛异常时（连不上后端）生成可读提示，而不是干巴巴的 "Failed to fetch"
 */
function buildNetError(url) {
    const isFile = location.protocol === "file:";
    const target = isFile ? "http://localhost:8005" : (location.origin || "当前地址");
    return "连不上后端服务（" + target + "）——请先双击 start.bat 启动后端，或运行 python main.py，然后重试";
}

/* 服务端时间 "yyyy-MM-dd HH:mm:ss" → datetime-local 需要的 "yyyy-MM-ddTHH:mm" */
function toInputTime(s) {
    return s ? String(s).replace(" ", "T").slice(0, 16) : "";
}

/* datetime-local 值 → 服务端 "yyyy-MM-dd HH:mm:ss" */
function toApiTime(s) {
    if (!s) return "";
    const v = String(s).trim().replace("T", " ");
    return v.length === 16 ? v + ":00" : v.slice(0, 19);
}

function nowInputValue() {
    const d = new Date();
    const p = n => String(n).padStart(2, "0");
    return d.getFullYear() + "-" + p(d.getMonth() + 1) + "-" + p(d.getDate()) +
        "T" + p(d.getHours()) + ":" + p(d.getMinutes());
}

/* ========================= 概览卡 ========================= */

async function loadSummary() {
    try {
        const res = await apiFetch(API + "/summary?accountId=" + state.accountId);
        const d = res.data;
        state.summaryCache = d;
        document.getElementById("sumIncome").textContent = money(d.income);
        document.getElementById("sumExpense").textContent = money(d.expense);
        document.getElementById("sumBalance").textContent = money(d.balance);
        return d;
    } catch (err) {
        console.error("loadSummary 失败", err);
        return null;
    }
}

/* ========================= 列表 ========================= */

function buildListQuery() {
    const q = new URLSearchParams();
    q.set("pageNum", state.pageNum);
    q.set("pageSize", state.pageSize);
    if (state.type) q.set("type", state.type);
    if (state.keyword) q.set("keyword", state.keyword);
    if (state.startDate) q.set("startDate", state.startDate);
    if (state.endDate) q.set("endDate", state.endDate);
    if (state.accountId) q.set("accountId", state.accountId);
    return API + "?" + q.toString();
}

async function loadList() {
    const listEl = document.getElementById("recordList");
    try {
        const res = await apiFetch(buildListQuery());
        state.total = res.data.total;
        state.list = res.data.list || [];

        // 当前页被删空时自动回退一页
        if (state.list.length === 0 && state.pageNum > 1 && state.total > 0) {
            state.pageNum -= 1;
            return loadList();
        }
        renderList();
        renderPagination();
    } catch (err) {
        console.error("loadList 失败", err);
        listEl.innerHTML = '<div class="empty-tip">接口请求失败，请确认后端是否启动</div>';
    }
}

function renderList() {
    const listEl = document.getElementById("recordList");

    if (!state.list.length) {
        listEl.innerHTML = '<div class="empty-tip">暂无记录，快去记一笔，或跟招财猫说说吧～</div>';
        return;
    }

    let html = `
        <table>
            <thead>
                <tr>
                    <th>类型</th>
                    <th>分类</th>
                    <th class="amount-col">金额</th>
                    <th>备注</th>
                    <th>发生时间</th>
                    <th class="act-col">操作</th>
                </tr>
            </thead>
            <tbody>`;

    state.list.forEach(item => {
        const isIncome = item.type === 1;
        const cls = isIncome ? "type-income" : "type-expense";
        const sign = isIncome ? "+" : "-";
        html += `
            <tr data-id="${item.id}">
                <td class="${cls}">${isIncome ? "收入" : "支出"}</td>
                <td>${esc(item.category)}</td>
                <td class="amount-col ${cls}">${sign}${Number(item.amount).toFixed(2)}</td>
                <td class="remark-cell" title="${esc(item.remark)}">${esc(item.remark)}</td>
                <td>${esc(item.recordTime)}</td>
                <td class="act-col">
                    <button class="act-btn" data-act="edit" data-id="${item.id}" title="查看/编辑">✏️</button>
                    <button class="act-btn" data-act="del" data-id="${item.id}" title="删除">🗑️</button>
                </td>
            </tr>`;
    });

    html += "</tbody></table>";
    listEl.innerHTML = html;
}

function renderPagination() {
    const infoEl = document.getElementById("pageInfo");
    const btnsEl = document.getElementById("pageBtns");
    const totalPages = Math.max(1, Math.ceil(state.total / state.pageSize));

    infoEl.textContent = `共 ${state.total} 条 · 第 ${state.pageNum}/${totalPages} 页`;

    const pages = [];
    const start = Math.max(1, state.pageNum - 2);
    const end = Math.min(totalPages, start + 4);
    for (let i = start; i <= end; i++) pages.push(i);

    let html = `<button data-page="${state.pageNum - 1}" ${state.pageNum <= 1 ? "disabled" : ""}>上一页</button>`;
    pages.forEach(p => {
        html += `<button data-page="${p}" ${p === state.pageNum ? 'style="background:#e6b422;color:#fff;border-color:#e6b422"' : ""}>${p}</button>`;
    });
    html += `<button data-page="${state.pageNum + 1}" ${state.pageNum >= totalPages ? "disabled" : ""}>下一页</button>`;
    btnsEl.innerHTML = html;
}

/* ========================= 表单 ========================= */

/* 金额输入净化：全角转半角、只留数字和一个小数点（兼容中文输入法） */
function sanitizeAmountInput(el) {
    let v = el.value.replace(/[０-９．]/g, c => String.fromCharCode(c.charCodeAt(0) - 0xFEE0));
    v = v.replace(/[^\d.]/g, "");
    const parts = v.split(".");
    if (parts.length > 2) v = parts[0] + "." + parts.slice(1).join("");
    if (el.value !== v) el.value = v;
}

function bindForm() {
    document.getElementById("recordForm").addEventListener("submit", async (e) => {
        e.preventDefault();

        const body = {
            type: parseInt(document.getElementById("type").value, 10),
            amount: Math.round(parseFloat(document.getElementById("amount").value) * 100) / 100,
            category: document.getElementById("category").value.trim(),
            remark: document.getElementById("remark").value.trim() || null,
            recordTime: toApiTime(document.getElementById("recordTime").value),
            accountId: state.accountId,
        };

        if (!body.amount || body.amount <= 0 || !body.category || !body.recordTime) {
            toast("请填写完整的必填项（金额、分类、发生时间）", "error");
            return;
        }

        try {
            await apiFetch(API, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify(body),
            });
            toast("添加成功 🎉", "success");
            document.getElementById("recordForm").reset();
            document.getElementById("recordTime").value = nowInputValue();
            state.pageNum = 1;
            loadList();
            loadSummary();
            refreshDashboard();
        } catch (err) {
            toast("添加失败：" + err.message, "error");
        }
    });
}

/* 快捷金额 / 快捷分类按钮 */
function bindQuickButtons() {
    const amtWrap = document.getElementById("quickAmounts");
    if (amtWrap) {
        amtWrap.addEventListener("click", e => {
            const btn = e.target.closest("button[data-amt]");
            if (!btn) return;
            const v = btn.dataset.amt;
            const input = document.getElementById("amount");
            if (v === "clear") {
                input.value = "";
                input.focus();
                return;
            }
            input.value = v;
            sanitizeAmountInput(input);
            input.focus();
        });
    }

    const catWrap = document.getElementById("quickCategories");
    if (catWrap) {
        catWrap.addEventListener("click", e => {
            const btn = e.target.closest("button[data-cat]");
            if (!btn) return;
            const cat = btn.dataset.cat;
            const input = document.getElementById("category");
            input.value = cat;
            // 选「工资」自动切成收入，省一次点击
            if (cat === "工资") {
                document.getElementById("type").value = "1";
            } else if (document.getElementById("type").value === "1") {
                document.getElementById("type").value = "2";
            }
            input.focus();
        });
    }
}

/* ========================= 筛选 / 分页绑定 ========================= */

function bindFilter() {
    const search = () => {
        state.keyword = document.getElementById("fKeyword").value.trim();
        state.type = document.getElementById("fType").value;
        state.startDate = document.getElementById("fStart").value;
        state.endDate = document.getElementById("fEnd").value;
        state.pageNum = 1;
        loadList();
    };

    document.getElementById("btnSearch").addEventListener("click", search);
    document.getElementById("fKeyword").addEventListener("keydown", e => {
        if (e.key === "Enter") { e.preventDefault(); search(); }
    });

    document.getElementById("btnReset").addEventListener("click", () => {
        document.getElementById("fKeyword").value = "";
        document.getElementById("fType").value = "";
        document.getElementById("fStart").value = "";
        document.getElementById("fEnd").value = "";
        state.keyword = "";
        state.type = "";
        state.startDate = "";
        state.endDate = "";
        state.pageNum = 1;
        loadList();
    });

    document.getElementById("pageBtns").addEventListener("click", e => {
        const btn = e.target.closest("button[data-page]");
        if (!btn || btn.disabled) return;
        const page = parseInt(btn.dataset.page, 10);
        const totalPages = Math.max(1, Math.ceil(state.total / state.pageSize));
        if (page < 1 || page > totalPages) return;
        state.pageNum = page;
        loadList();
    });

    document.getElementById("recordList").addEventListener("click", e => {
        const actBtn = e.target.closest("button[data-act]");
        const row = e.target.closest("tr[data-id]");
        if (!row) return;
        const id = parseInt(row.dataset.id, 10);
        const record = state.list.find(r => r.id === id);

        if (actBtn && actBtn.dataset.act === "del") {
            e.stopPropagation();
            openDrawer(record, "delete");
            return;
        }
        openDrawer(record, actBtn && actBtn.dataset.act === "edit" ? "edit" : "view");
    });
}

/* ========================= 抽屉 ========================= */

function openDrawer(record, mode = "view") {
    if (!record) return;
    state.drawerRecord = record;
    const drawer = document.getElementById("drawer");
    const mask = document.getElementById("drawerMask");

    renderDrawer(mode);
    drawer.classList.add("open");
    mask.classList.add("open");
    drawer.setAttribute("aria-hidden", "false");
}

function closeDrawer() {
    document.getElementById("drawer").classList.remove("open");
    document.getElementById("drawerMask").classList.remove("open");
    document.getElementById("drawer").setAttribute("aria-hidden", "true");
    state.drawerRecord = null;
}

function renderDrawer(mode) {
    const r = state.drawerRecord;
    const title = document.getElementById("drawerTitle");
    const body = document.getElementById("drawerBody");
    if (!r) return;

    if (mode === "view") {
        title.textContent = "记录详情";
        const isIncome = r.type === 1;
        body.innerHTML = `
            <div class="detail-list">
                <div class="detail-item"><span>类型</span><span class="${isIncome ? 'type-income' : 'type-expense'}">${isIncome ? "收入" : "支出"}</span></div>
                <div class="detail-item"><span>金额</span><span class="${isIncome ? 'type-income' : 'type-expense'}">${isIncome ? "+" : "-"}${Number(r.amount).toFixed(2)} 元</span></div>
                <div class="detail-item"><span>分类</span><span>${esc(r.category)}</span></div>
                <div class="detail-item"><span>备注</span><span>${esc(r.remark) || "—"}</span></div>
                <div class="detail-item"><span>发生时间</span><span>${esc(r.recordTime)}</span></div>
                <div class="detail-item"><span>创建时间</span><span>${esc(r.createTime)}</span></div>
            </div>
            <div class="detail-actions">
                <button class="btn-ghost" data-drawer="edit">✏️ 编辑</button>
                <button class="btn-danger" data-drawer="delete">🗑️ 删除</button>
            </div>`;
        bindDrawerActions();
        return;
    }

    if (mode === "edit") {
        title.textContent = "编辑记录";
        body.innerHTML = `
            <form class="drawer-form" id="drawerForm">
                <div class="form-row">
                    <div class="form-group">
                        <label for="dType">类型</label>
                        <select id="dType">
                            <option value="1" ${r.type === 1 ? "selected" : ""}>收入</option>
                            <option value="2" ${r.type === 2 ? "selected" : ""}>支出</option>
                        </select>
                    </div>
                    <div class="form-group">
                        <label for="dAmount">金额（元）</label>
                        <input type="text" id="dAmount" inputmode="decimal" value="${Number(r.amount).toFixed(2)}" required>
                    </div>
                </div>
                <div class="form-group" style="margin-bottom:12px;">
                    <label for="dCategory">分类</label>
                    <input type="text" id="dCategory" value="${esc(r.category)}" required>
                </div>
                <div class="form-group" style="margin-bottom:12px;">
                    <label for="dRecordTime">发生时间</label>
                    <input type="datetime-local" id="dRecordTime" value="${toInputTime(r.recordTime)}" required>
                </div>
                <div class="form-group" style="margin-bottom:12px;">
                    <label for="dRemark">备注</label>
                    <input type="text" id="dRemark" value="${esc(r.remark)}">
                </div>
                <div class="drawer-actions">
                    <button type="submit" class="btn-primary">保存</button>
                    <button type="button" class="btn-ghost" data-drawer="view">取消</button>
                </div>
            </form>`;

        document.getElementById("drawerForm").addEventListener("submit", async (e) => {
            e.preventDefault();
            const payload = {
                type: parseInt(document.getElementById("dType").value, 10),
                amount: Math.round(parseFloat(document.getElementById("dAmount").value) * 100) / 100,
                category: document.getElementById("dCategory").value.trim(),
                remark: document.getElementById("dRemark").value.trim() || null,
                recordTime: toApiTime(document.getElementById("dRecordTime").value),
                accountId: state.accountId,
            };
            if (!payload.amount || payload.amount <= 0 || !payload.category || !payload.recordTime) {
                toast("请填写完整（金额、分类、发生时间）", "error");
                return;
            }
            try {
                const res = await apiFetch(API + "/" + r.id, {
                    method: "PUT",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify(payload),
                });
                state.drawerRecord = res.data;
                toast("修改成功 ✅", "success");
                renderDrawer("view");
                loadList();
                loadSummary();
            } catch (err) {
                toast("修改失败：" + err.message, "error");
            }
        });
        bindDrawerActions();
        return;
    }

    if (mode === "delete") {
        title.textContent = "删除记录";
        const isIncome = r.type === 1;
        body.innerHTML = `
            <div class="delete-warn">
                确定要删除这条记录吗？删除后无法恢复。<br>
                ${isIncome ? "收入" : "支出"} · ${esc(r.category)} · <strong>¥${Number(r.amount).toFixed(2)}</strong><br>
                ${esc(r.recordTime)}
            </div>
            <div class="detail-actions">
                <button class="btn-danger" data-drawer="confirm-delete">确认删除</button>
                <button class="btn-ghost" data-drawer="view">取消</button>
            </div>`;
        bindDrawerActions();
    }
}

function bindDrawerActions() {
    document.getElementById("drawerBody").querySelectorAll("[data-drawer]").forEach(btn => {
        btn.addEventListener("click", async () => {
            const action = btn.dataset.drawer;
            if (action === "edit") return renderDrawer("edit");
            if (action === "view") return renderDrawer("view");
            if (action === "delete") return renderDrawer("delete");

            if (action === "confirm-delete") {
                try {
                    await apiFetch(API + "/" + state.drawerRecord.id, { method: "DELETE" });
                    toast("已删除 🗑️", "success");
                    closeDrawer();
                    loadList();
                    loadSummary();
                    refreshDashboard();
                } catch (err) {
                    toast("删除失败：" + err.message, "error");
                }
            }
        });
    });
}

/* ========================= 招财猫对话 ========================= */

const CAT_RULES = [
    { keywords: ["午饭", "午餐", "晚饭", "晚餐", "早餐", "早饭", "吃饭", "火锅", "外卖", "餐饮", "奶茶", "咖啡", "零食", "面", "饭"], category: "餐饮" },
    { keywords: ["打车", "出租", "地铁", "公交", "车费", "加油", "停车", "交通", "高铁", "机票"], category: "交通" },
    { keywords: ["购物", "衣服", "鞋", "淘宝", "京东", "超市", "日用", "买"], category: "购物" },
    { keywords: ["电影", "游戏", "娱乐", "唱歌", "旅游", "KTV", "演唱会"], category: "娱乐" },
    { keywords: ["房租", "水电", "物业", "话费", "宽带", "生活"], category: "生活" },
    { keywords: ["医院", "药", "看病", "体检", "医疗"], category: "医疗" },
];

const INCOME_RULES = [
    { keywords: ["工资", "薪水"], category: "工资" },
    { keywords: ["奖金", "年终奖"], category: "奖金" },
    { keywords: ["报销"], category: "报销" },
    { keywords: ["红包", "转账", "收款", "到账", "兼职", "利息", "收入", "进账"], category: "其他收入" },
];

function parseRecord(text) {
    const raw = String(text || "").trim();
    if (!raw) return { intent: "unknown", text: raw };

    // 1. 问句意图
    if (/(今天|今日).*(花了|支出|流水|收支|消费|记账|账)/.test(raw) ||
        /(花了多少|支出多少|流水多少|今天怎么样)/.test(raw) ||
        /^(今日流水|今天流水|查一下今天)/.test(raw)) {
        return { intent: "query", text: raw };
    }

    // 2. 金额
    const amountMatch = raw.match(/(\d+(?:\.\d{1,2})?)/);
    if (!amountMatch) {
        if (raw.includes("再来一笔") || raw.includes("再记一笔")) {
            return { intent: "unknown", text: raw, hint: "再说一下金额喵，比如「再来一笔 20」" };
        }
        return { intent: "unknown", text: raw };
    }
    const amount = parseFloat(amountMatch[1]);
    if (!amount || amount <= 0) return { intent: "unknown", text: raw };

    // 3. 收支类型 + 分类
    let type = 2;
    let category = null;

    for (const rule of INCOME_RULES) {
        if (rule.keywords.some(k => raw.includes(k))) {
            type = 1;
            category = rule.category;
            break;
        }
    }

    if (type === 2) {
        for (const rule of CAT_RULES) {
            if (rule.keywords.some(k => raw.includes(k))) {
                category = rule.category;
                break;
            }
        }
    }

    // 4. 「再来一笔 20」沿用上一笔分类
    if (!category && (raw.includes("再来一笔") || raw.includes("再记一笔")) && state.lastCategory) {
        category = state.lastCategory;
    }

    if (!category) {
        category = type === 1 ? "其他收入" : "其他";
    }

    // 5. 时间
    let when = new Date();
    if (raw.includes("前天")) {
        when.setDate(when.getDate() - 2);
    } else if (raw.includes("昨天")) {
        when.setDate(when.getDate() - 1);
    }

    const p = n => String(n).padStart(2, "0");
    const recordTime = when.getFullYear() + "-" + p(when.getMonth() + 1) + "-" + p(when.getDate()) +
        " " + p(when.getHours()) + ":" + p(when.getMinutes()) + ":" + p(when.getSeconds());

    return {
        intent: "record",
        text: raw,
        type,
        amount: Math.round(amount * 100) / 100,
        category,
        remark: raw,
        recordTime,
    };
}

/* ---- 对话 UI ---- */

function openChat() {
    const chat = document.getElementById("catChat");
    chat.classList.add("open");
    chat.setAttribute("aria-hidden", "false");
    if (!chat.dataset.inited) {
        chat.dataset.inited = "1";
        addCatBubble("喵～我是招财猫，跟我说说今天花了什么吧！<br>比如「午饭 30」「工资 8000」，也可以问「今天花了多少」。");
    }
    setTimeout(() => document.getElementById("chatText").focus(), 220);
}

function closeChat() {
    const chat = document.getElementById("catChat");
    chat.classList.remove("open");
    chat.setAttribute("aria-hidden", "true");
}

function addUserBubble(text) {
    addBubble(text, "user");
}

function addCatBubble(html) {
    addBubble(html, "cat");
}

function addBubble(html, who) {
    const body = document.getElementById("chatBody");
    const div = document.createElement("div");
    div.className = "bubble " + who;
    div.innerHTML = html;
    body.appendChild(div);
    body.scrollTop = body.scrollHeight;
    return div;
}

function addConfirmCard(rec, index = 0, total = 1) {
    const body = document.getElementById("chatBody");
    const isIncome = rec.type === 1;
    const card = document.createElement("div");
    card.className = "confirm-card";
    const title = total > 1 ? `第 ${index + 1} 笔 / 共 ${total} 笔 · 请确认` : "请确认这笔账";
    card.innerHTML = `
        <div class="cf-title">${title}</div>
        <div class="cf-main">
            <span class="cf-amount" style="color:${isIncome ? '#00a884' : '#c0392b'}">
                ${isIncome ? "+" : "-"}¥${Number(rec.amount).toFixed(2)}
            </span>
            <span style="font-size:13px;color:#8a7a70">${isIncome ? "收入" : "支出"} · ${esc(rec.category)}</span>
        </div>
        <div class="cf-meta">
            发生时间：${esc(rec.recordTime)}<br>
            备注：${esc(rec.remark)}
        </div>
        <div class="cf-actions">
            <button class="cf-ok">确认记账</button>
            <button class="cf-cancel">改一下</button>
        </div>`;
    body.appendChild(card);
    body.scrollTop = body.scrollHeight;

    card.querySelector(".cf-ok").addEventListener("click", async () => {
        const btns = card.querySelectorAll("button");
        btns.forEach(b => b.disabled = true);
        try {
            await apiFetch(API, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    type: rec.type,
                    amount: rec.amount,
                    category: rec.category,
                    remark: rec.remark,
                    recordTime: rec.recordTime,
                    accountId: state.accountId,
                }),
            });
            state.lastCategory = rec.category;
            card.querySelector(".cf-actions").innerHTML =
                '<span style="color:#00a884;font-size:13px;">✅ 已记入账本</span>';
            catHappy();
            if (total === 1) {
                addCatBubble("记好啦！金币已经收进账本喵～ 💰");
            } else {
                addCatBubble(`第 ${index + 1} 笔记好啦喵～ 💰`);
            }
            toast("记账成功 🎉", "success");
            state.pageNum = 1;
            loadList();
            loadSummary();
            refreshDashboard();
        } catch (err) {
            btns.forEach(b => b.disabled = false);
            addCatBubble("喵…写入失败了：" + esc(err.message));
            toast("记账失败：" + err.message, "error");
        }
    });

    card.querySelector(".cf-cancel").addEventListener("click", () => {
        // 回填左侧表单，让用户手动改
        document.getElementById("type").value = String(rec.type);
        document.getElementById("amount").value = rec.amount;
        document.getElementById("category").value = rec.category;
        document.getElementById("remark").value = rec.remark;
        document.getElementById("recordTime").value = toInputTime(rec.recordTime);
        addCatBubble("已经帮你填到左边的表单啦，改完点提交就行～");
        toast("已回填表单", "success");
    });
}

function catAskUnknown() {
    addCatBubble("没听明白喵～ 你可以这样说：<br>「午饭 30」「打车 15 元」「工资 8000」「今天花了多少」");
}

function reportSummary() {
    const s = state.summaryCache;
    if (!s) {
        addCatBubble("喵…没拿到今天的账本数据，稍后再试试？");
        return;
    }
    const parts = [];
    parts.push("今天共记了 <b>" + s.count + "</b> 笔账。");
    parts.push("收入 <span class='mono' style='color:#00a884'>" + money(s.income) + "</span>，" +
        "支出 <span class='mono' style='color:#c0392b'>" + money(s.expense) + "</span>。");
    parts.push(s.balance >= 0
        ? "结余 <span class='mono'>" + money(s.balance) + "</span>，今天攒下钱啦喵～"
        : "结余 <span class='mono'>" + money(s.balance) + "</span>，今天超支了，明天省着点喵。");

    if (s.recent && s.recent.length) {
        parts.push("最近几笔：<br>" + s.recent.map(r =>
            "· " + (r.type === 1 ? "收入" : "支出") + " " + esc(r.category) + " " + money(r.amount)
        ).join("<br>"));
    }
    addCatBubble(parts.join("<br>"));
}

async function handleUserText(text) {
    const raw = String(text || "").trim();
    if (!raw) return;

    addUserBubble(esc(raw));
    document.getElementById("chatText").value = "";
    setCatState("thinking");

    let parsed = null;

    // 优先走后端智能体（大模型可用则大模型，不可用自动回落规则）
    if (PARSE_MODE === "auto" || PARSE_MODE === "llm") {
        try {
            const res = await apiFetch(API_BASE + "/api/chat", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ text: raw, accountId: state.accountId }),
            });
            if (res.data && res.data.intent) {
                parsed = res.data;
                if (res.data.mode) state.lastParseMode = res.data.mode;
            } else {
                parsed = parseRecord(raw);
            }
        } catch (err) {
            console.warn("后端解析失败，回落本地规则", err);
            parsed = parseRecord(raw);
        }
    } else {
        parsed = parseRecord(raw);
    }

    setCatState("");

    // 意图：查询
    if (parsed.intent === "query") {
        const reply = parsed.reply || "";
        if (reply) {
            addCatBubble(esc(reply).replace(/\n/g, "<br>"));
        } else {
            await loadSummary();
            reportSummary();
        }
        return;
    }

    // 意图：消费分析
    if (parsed.intent === "analysis") {
        const reply = parsed.reply || "";
        addCatBubble("🐱 " + esc(reply).replace(/\n/g, "<br>"));
        return;
    }

    // 意图：闲聊
    if (parsed.intent === "chat") {
        addCatBubble("🐱 " + esc(parsed.reply || "喵～我在呢，随时可以帮你记账。"));
        return;
    }

    // 意图：记账（可能多笔）
    if (parsed.intent === "record" && parsed.records && parsed.records.length) {
        if (parsed.records.length > 1) {
            addCatBubble("喵～听明白啦，这是 " + parsed.records.length + " 笔账，一笔笔确认喵：");
        } else {
            const t = parsed.records[0].type;
            addCatBubble("听明白啦～ 你这是要记一笔" + (t === 1 ? "收入" : "支出") + "，确认一下喵：");
        }
        parsed.records.forEach((rec, i) => addConfirmCard(rec, i, parsed.records.length));
        return;
    }

    if (parsed.hint) {
        addCatBubble(esc(parsed.hint));
        return;
    }
    catAskUnknown();
}

/* ---- 猫的动画状态 ---- */

function setCatState(cls) {
    const cat = document.querySelector(".cat-float");
    if (!cat) return;
    cat.classList.remove("thinking", "happy");
    if (cls) cat.classList.add(cls);
}

function catHappy() {
    const cat = document.querySelector(".cat-float");
    if (!cat) return;
    cat.classList.remove("thinking");
    cat.classList.add("happy");
    burstCoins();
    setTimeout(() => cat.classList.remove("happy"), 1900);
}

function burstCoins() {
    const stage = document.getElementById("catBtn");
    if (!stage) return;
    for (let i = 0; i < 7; i++) {
        const span = document.createElement("span");
        span.className = "coin-pop";
        span.textContent = "🪙";
        span.style.left = (30 + Math.random() * (stage.clientWidth - 60)) + "px";
        span.style.top = (stage.clientHeight * 0.35) + "px";
        span.style.setProperty("--dx", (Math.random() * 90 - 45) + "px");
        stage.appendChild(span);
        setTimeout(() => span.remove(), 950);
    }
}

/* ========================= 撸猫互动 ========================= */

const PET_WORDS = {
    head: ["喵～摸摸头，今天财运旺旺", "呼噜呼噜…最舒服了喵", "头毛梳得亮亮的，好运自然来"],
    belly: ["肚子圆圆，金币满满", "喵呜～别挠啦，好痒！", "摸肚子会招财哦，再摸一下"],
    bell: ["叮铃～招财铃响了！", "铃铛一响，黄金万两", "叮～财运 +1"],
    paw: ["击掌！一起发财喵", "握住小锤子，敲出好运来", "啪！击掌成交"],
    coin: ["招财进宝，钱钱快来", "金币擦得亮，钱包鼓起来", "财源滚滚喵～"],
    body: ["抱抱！今天也是圆滚滚的一天", "喵～整个人都软乎乎的", "蹭蹭你，沾点财气"],
    scarf: ["红围巾真暖和，财运也红彤彤", "围巾被我蹭得更有福气了喵", "红红火火，财气滚滚"],
    feet: ["踩踩肉垫，招财猫的印章喵", "肉垫软软的，踩一个脚印一枚金币", "咕叽咕叽～"],
};

function petTodayKey() {
    const d = new Date();
    const p = n => String(n).padStart(2, "0");
    return "pet_" + d.getFullYear() + p(d.getMonth() + 1) + p(d.getDate());
}

function loadPetCount() {
    const v = parseInt(localStorage.getItem(petTodayKey()) || "0", 10);
    document.getElementById("petCount").textContent = v;
}

function petCat(e) {
    const zoneEl = e.target.closest("[data-zone]");
    const zone = zoneEl ? zoneEl.dataset.zone : "head";
    const cat = document.querySelector(".cat-float");
    const btn = document.getElementById("catBtn");

    // 撸猫计数（当天，存 localStorage）
    const cur = parseInt(localStorage.getItem(petTodayKey()) || "0", 10) + 1;
    localStorage.setItem(petTodayKey(), String(cur));
    document.getElementById("petCount").textContent = cur;

    // 分部位反应
    if (zone === "paw") {
        // 敲小金锤：晃一下 + 金币
        const hand = document.querySelector(".cat-hand-right");
        if (hand) {
            hand.classList.remove("tap");
            void hand.getBoundingClientRect();
            hand.classList.add("tap");
            setTimeout(() => hand.classList.remove("tap"), 600);
        }
        burstCoins();
    } else if (zone === "coin") {
        // 摸钱袋：袋子晃一晃
        const hand = document.querySelector(".cat-hand-left");
        if (hand) {
            hand.classList.remove("shake");
            void hand.getBoundingClientRect();
            hand.classList.add("shake");
            setTimeout(() => hand.classList.remove("shake"), 600);
        }
        burstCoins();
    } else if (zone === "bell") {
        // 摸铃铛：铃铛晃一晃 + 铃声
        const bell = document.querySelector(".cat-bell");
        if (bell) {
            bell.classList.remove("swing");
            void bell.getBoundingClientRect();
            bell.classList.add("swing");
            setTimeout(() => bell.classList.remove("swing"), 600);
        }
        playBellSound();
    } else if (zone === "feet") {
        playBellSound();
    }

    if (cat) {
        cat.classList.remove("wiggle", "wobble");
        void cat.getBoundingClientRect();
        cat.classList.add(zone === "belly" ? "wobble" : "wiggle");
        setTimeout(() => cat.classList.remove("wiggle", "wobble"), 680);
    }

    floatHearts(btn, zone === "feet" ? 2 : 3);
    const words = PET_WORDS[zone] || PET_WORDS.head;
    catSay(btn, words[Math.floor(Math.random() * words.length)]);
}

function floatHearts(container, n) {
    for (let i = 0; i < n; i++) {
        const s = document.createElement("span");
        s.className = "heart-pop";
        s.textContent = ["💗", "💛", "✨"][Math.floor(Math.random() * 3)];
        s.style.left = (20 + Math.random() * Math.max(40, container.clientWidth - 40)) + "px";
        s.style.top = (container.clientHeight * 0.3 + Math.random() * 30) + "px";
        s.style.setProperty("--dx", (Math.random() * 70 - 35) + "px");
        container.appendChild(s);
        setTimeout(() => s.remove(), 1100);
    }
}

function catSay(container, text) {
    const old = container.querySelector(".cat-say");
    if (old) old.remove();
    const s = document.createElement("span");
    s.className = "cat-say";
    s.textContent = text;
    container.appendChild(s);
    setTimeout(() => s.remove(), 1650);
}

function playBellSound() {
    try {
        if (!audioCtx) {
            const AC = window.AudioContext || window.webkitAudioContext;
            if (!AC) return;
            audioCtx = new AC();
        }
        if (audioCtx.state === "suspended") audioCtx.resume();
        const t = audioCtx.currentTime;
        const osc = audioCtx.createOscillator();
        const gain = audioCtx.createGain();
        osc.type = "sine";
        osc.frequency.setValueAtTime(1318, t);
        osc.frequency.exponentialRampToValueAtTime(1046, t + 0.25);
        gain.gain.setValueAtTime(0.0001, t);
        gain.gain.exponentialRampToValueAtTime(0.22, t + 0.01);
        gain.gain.exponentialRampToValueAtTime(0.0001, t + 0.4);
        osc.connect(gain).connect(audioCtx.destination);
        osc.start(t);
        osc.stop(t + 0.42);
    } catch (err) {
        /* 音效失败忽略 */
    }
}

/* ========================= 木鱼 ========================= */

let audioCtx = null;
let meritKey = "";

function meritTodayKey() {
    const d = new Date();
    const p = n => String(n).padStart(2, "0");
    return "merit_" + d.getFullYear() + p(d.getMonth() + 1) + p(d.getDate());
}

function loadMerit() {
    meritKey = meritTodayKey();
    const v = parseInt(localStorage.getItem(meritKey) || "0", 10);
    document.getElementById("meritCount").textContent = v;
}

function saveMerit(v) {
    localStorage.setItem(meritKey, String(v));
}

function playWoodfishSound() {
    try {
        if (!audioCtx) {
            const AC = window.AudioContext || window.webkitAudioContext;
            if (!AC) return;
            audioCtx = new AC();
        }
        if (audioCtx.state === "suspended") audioCtx.resume();

        const t = audioCtx.currentTime;

        // 主体「笃」声：三角波 + 快速衰减
        const osc = audioCtx.createOscillator();
        const gain = audioCtx.createGain();
        osc.type = "triangle";
        osc.frequency.setValueAtTime(700, t);
        osc.frequency.exponentialRampToValueAtTime(180, t + 0.12);
        gain.gain.setValueAtTime(0.0001, t);
        gain.gain.exponentialRampToValueAtTime(0.35, t + 0.012);
        gain.gain.exponentialRampToValueAtTime(0.0001, t + 0.22);
        osc.connect(gain).connect(audioCtx.destination);
        osc.start(t);
        osc.stop(t + 0.24);

        // 低频共鸣，增加木头质感
        const osc2 = audioCtx.createOscillator();
        const gain2 = audioCtx.createGain();
        osc2.type = "sine";
        osc2.frequency.setValueAtTime(150, t);
        gain2.gain.setValueAtTime(0.12, t);
        gain2.gain.exponentialRampToValueAtTime(0.0001, t + 0.15);
        osc2.connect(gain2).connect(audioCtx.destination);
        osc2.start(t);
        osc2.stop(t + 0.16);
    } catch (e) {
        console.warn("音效播放失败", e);
    }
}

function strikeWoodfish() {
    const btn = document.getElementById("woodfishBtn");
    const fish = btn.querySelector(".woodfish");

    btn.classList.remove("strike");
    fish.classList.remove("strike");
    void btn.offsetWidth;   // 触发动画重排
    btn.classList.add("strike");
    fish.classList.add("strike");
    setTimeout(() => { btn.classList.remove("strike"); fish.classList.remove("strike"); }, 520);

    playWoodfishSound();

    // 功德飘字
    const pop = document.createElement("span");
    pop.className = "merit-pop";
    pop.textContent = "功德 +1";
    pop.style.setProperty("--dx", (Math.random() * 46 - 23) + "px");
    btn.appendChild(pop);
    setTimeout(() => pop.remove(), 920);

    // 计数
    const cur = parseInt(document.getElementById("meritCount").textContent, 10) || 0;
    const next = cur + 1;
    document.getElementById("meritCount").textContent = next;
    saveMerit(next);
}

/* ========================= 初始化 ========================= */

/**
 * 初始化入口
 * 注意：本文件可能是「动态加载」的（脚本插入时 DOMContentLoaded 已经触发过），
 * 所以不能只依赖 DOMContentLoaded 事件，必须同时判断 document.readyState。
 */
function initApp() {
    if (initApp._done) return;
    initApp._done = true;

    document.getElementById("recordTime").value = nowInputValue();
    bindForm();
    bindFilter();
    loadList();
    loadSummary();

    // 快捷金额 / 快捷分类
    bindQuickButtons();

    // 抽屉关闭
    document.getElementById("drawerClose").addEventListener("click", closeDrawer);
    document.getElementById("drawerMask").addEventListener("click", closeDrawer);

    // 招财猫：点各部位撸猫，说话走 catChatBtn
    document.getElementById("catBtn").addEventListener("click", e => petCat(e));
    document.getElementById("catChatBtn").addEventListener("click", openChat);
    document.getElementById("chatClose").addEventListener("click", closeChat);
    document.getElementById("chatSend").addEventListener("click", () => {
        handleUserText(document.getElementById("chatText").value);
    });
    document.getElementById("chatText").addEventListener("keydown", e => {
        if (e.key === "Enter") { e.preventDefault(); handleUserText(e.target.value); }
    });
    document.getElementById("chatChips").addEventListener("click", e => {
        const b = e.target.closest("button[data-text]");
        if (b) handleUserText(b.dataset.text);
    });

    // 木鱼
    loadMerit();
    // 撸猫计数
    loadPetCount();
    // 金额输入净化（委托，主表单和抽屉编辑框都生效）
    document.addEventListener("input", e => {
        if (e.target && (e.target.id === "amount" || e.target.id === "dAmount")) {
            sanitizeAmountInput(e.target);
        }
    });
    document.getElementById("woodfishBtn").addEventListener("click", strikeWoodfish);
    document.getElementById("meritClear").addEventListener("click", () => {
        document.getElementById("meritCount").textContent = "0";
        saveMerit(0);
        toast("功德已清零", "");
    });

    // ESC 关闭浮层
    document.addEventListener("keydown", e => {
        if (e.key === "Escape") {
            closeDrawer();
            closeChat();
            if (typeof closeReportPanel === "function") closeReportPanel();
        }
    });
}

/* 立即初始化：DOM 已就绪则直接跑，否则等 DOMContentLoaded */
if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", initApp);
} else {
    initApp();
}

/* ==========================================================
   与 dashboard.js 的桥接（账本切换时同步全局状态）
   ========================================================== */

/** dashboard.js 调用：切换全局账本 */
window.setGlobalBook = function (bookId) {
    state.accountId = bookId;
    const nameEl = document.getElementById("boardBookName");
    if (nameEl && typeof D !== "undefined") {
        const b = D.books.find(x => x.id === bookId);
        nameEl.textContent = b ? b.name : "日常账本";
    }
};

/** dashboard.js 调用：刷新流水与概览 */
window.refreshRecords = function () {
    state.pageNum = 1;
    loadList();
    loadSummary();
};

/** app.js 调用：刷新看板与自动化面板 */
function refreshDashboard() {
    if (typeof loadDashboard === "function") {
        loadDashboard();
        loadBudgets();
        loadCheckin();
    }
}

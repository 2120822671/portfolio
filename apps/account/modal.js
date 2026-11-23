/* ==========================================================
   招财记账 · 应用内表单模态框
   ------------------------------------------------------------
   替代原生 prompt()：一次填完所有字段，样式与应用统一，
   在 iframe / 预览面板里也能正常工作。
   ========================================================== */

/* 自带的转义函数（不依赖 dashboard.js 的加载顺序） */
function mEsc(str) {
    return String(str == null ? "" : str)
        .replace(/&/g, "&amp;").replace(/</g, "&lt;")
        .replace(/>/g, "&gt;").replace(/"/g, "&quot;");
}

/**
 * 打开一个应用内表单弹窗
 * @param {Object} cfg
 *   cfg.title    标题
 *   cfg.icon     标题图标
 *   cfg.desc     副标题说明
 *   cfg.fields   [{key, label, type, value, placeholder, options, required, hint, min, step}]
 *   cfg.onSubmit (values) => Promise|void   提交回调（抛错则保留弹窗）
 */
function openFormModal(cfg) {
    const modal = document.createElement("div");
    modal.className = "form-modal-mask";
    modal.innerHTML = `
        <div class="form-modal" role="dialog" aria-modal="true" aria-label="${mEsc(cfg.title || "填写信息")}">
            <div class="form-modal-head">
                <div class="form-modal-title">
                    <span class="form-modal-icon">${cfg.icon || "📝"}</span>
                    <div>
                        <h3>${mEsc(cfg.title || "填写信息")}</h3>
                        ${cfg.desc ? `<p>${mEsc(cfg.desc)}</p>` : ""}
                    </div>
                </div>
                <button class="form-modal-x" data-modal-close aria-label="关闭">✕</button>
            </div>
            <form class="form-modal-body" id="formModalBody">
                ${(cfg.fields || []).map(renderField).join("")}
                <div class="form-modal-error" id="formModalError"></div>
            </form>
            <div class="form-modal-foot">
                <button class="btn-ghost" data-modal-close>取消</button>
                <button class="btn-primary" id="formModalSubmit">${mEsc(cfg.submitText || "保存")}</button>
            </div>
        </div>`;

    document.body.appendChild(modal);
    // 触发入场动画
    requestAnimationFrame(() => modal.classList.add("show"));
    // 绑定分段选择器
    bindSegmentGroups(modal);

    const form = modal.querySelector("#formModalBody");
    const errBox = modal.querySelector("#formModalError");
    const submitBtn = modal.querySelector("#formModalSubmit");

    function close() {
        modal.classList.remove("show");
        setTimeout(() => modal.remove(), 220);
        document.removeEventListener("keydown", onKey);
    }

    function onKey(e) {
        if (e.key === "Escape") close();
    }

    function collect() {
        const values = {};
        let firstBad = null;
        (cfg.fields || []).forEach(f => {
            const el = form.querySelector(`[name="${f.key}"]`);
            if (!el) return;
            let v = el.type === "checkbox" ? el.checked : el.value;
            if (typeof v === "string") v = v.trim();
            if (f.type === "number" && v !== "") v = Number(v);
            if (f.required && (v === "" || v === null || v === undefined)) {
                el.classList.add("field-bad");
                if (!firstBad) firstBad = el;
            } else {
                el.classList.remove("field-bad");
            }
            values[f.key] = v;
        });
        return { values, firstBad };
    }

    async function handleSubmit() {
        const { values, firstBad } = collect();
        if (firstBad) {
            errBox.textContent = "请把标红的必填项填完整";
            firstBad.focus();
            return;
        }
        errBox.textContent = "";
        submitBtn.disabled = true;
        const originalText = submitBtn.textContent;
        submitBtn.textContent = "处理中…";
        try {
            await cfg.onSubmit(values);
            close();
        } catch (err) {
            errBox.textContent = (err && err.message) ? err.message : "保存失败，请重试";
            submitBtn.disabled = false;
            submitBtn.textContent = originalText;
        }
    }

    form.addEventListener("submit", e => { e.preventDefault(); handleSubmit(); });
    submitBtn.addEventListener("click", handleSubmit);
    modal.querySelectorAll("[data-modal-close]").forEach(b => b.addEventListener("click", close));
    modal.addEventListener("click", e => { if (e.target === modal) close(); });
    document.addEventListener("keydown", onKey);

    // 数字输入去掉浏览器自带的上下箭头
    form.querySelectorAll('input[type="number"]').forEach(i => {
        i.addEventListener("input", () => {
            let v = i.value.replace(/[^\d.]/g, "");
            const parts = v.split(".");
            if (parts.length > 2) v = parts[0] + "." + parts.slice(1).join("");
            if (i.value !== v) i.value = v;
        });
    });

    // 自动聚焦第一个可输入项
    const first = form.querySelector("input:not([type=hidden]), select, textarea");
    if (first) setTimeout(() => first.focus(), 120);
}

/** 渲染单个字段 */
function renderField(f) {
    const v = f.value === undefined || f.value === null ? "" : f.value;

    if (f.type === "select") {
        const opts = (f.options || []).map(o => {
            const val = typeof o === "object" ? o.value : o;
            const label = typeof o === "object" ? o.label : o;
            return `<option value="${mEsc(val)}" ${String(val) === String(v) ? "selected" : ""}>${mEsc(label)}</option>`;
        }).join("");
        return `
            <div class="fm-field">
                <label>${mEsc(f.label)}${f.required ? '<span class="fm-req">*</span>' : ""}</label>
                <select name="${f.key}">${opts}</select>
                ${f.hint ? `<div class="fm-hint">${mEsc(f.hint)}</div>` : ""}
            </div>`;
    }

    if (f.type === "radio-group") {
        const opts = (f.options || []).map(o => {
            const val = typeof o === "object" ? o.value : o;
            const label = typeof o === "object" ? o.label : o;
            return `
                <label class="fm-radio">
                    <input type="radio" name="${f.key}" value="${mEsc(val)}" ${String(val) === String(v) ? "checked" : ""}>
                    <span>${mEsc(label)}</span>
                </label>`;
        }).join("");
        return `
            <div class="fm-field">
                <label>${mEsc(f.label)}</label>
                <div class="fm-radio-group">${opts}</div>
                ${f.hint ? `<div class="fm-hint">${mEsc(f.hint)}</div>` : ""}
            </div>`;
    }

    if (f.type === "segment") {
        const opts = (f.options || []).map(o => {
            const val = typeof o === "object" ? o.value : o;
            const label = typeof o === "object" ? o.label : o;
            return `
                <button type="button" class="fm-seg ${String(val) === String(v) ? "active" : ""}" data-seg="${f.key}" data-val="${mEsc(val)}">
                    ${mEsc(label)}
                </button>`;
        }).join("");
        return `
            <div class="fm-field">
                <label>${mEsc(f.label)}</label>
                <div class="fm-seg-group" data-seg-group="${f.key}">
                    ${opts}
                    <input type="hidden" name="${f.key}" value="${mEsc(v)}">
                </div>
                ${f.hint ? `<div class="fm-hint">${mEsc(f.hint)}</div>` : ""}
            </div>`;
    }

    if (f.type === "textarea") {
        return `
            <div class="fm-field">
                <label>${mEsc(f.label)}</label>
                <textarea name="${f.key}" rows="3" placeholder="${mEsc(f.placeholder || "")}">${mEsc(v)}</textarea>
                ${f.hint ? `<div class="fm-hint">${mEsc(f.hint)}</div>` : ""}
            </div>`;
    }

    return `
        <div class="fm-field">
            <label>${mEsc(f.label)}${f.required ? '<span class="fm-req">*</span>' : ""}</label>
            <input type="${f.type || "text"}" name="${f.key}" value="${mEsc(v)}"
                   placeholder="${mEsc(f.placeholder || "")}"
                   ${f.required ? "required" : ""}
                   ${f.min !== undefined ? `min="${f.min}"` : ""}
                   ${f.step !== undefined ? `step="${f.step}"` : ""}
                   ${f.inputmode ? `inputmode="${f.inputmode}"` : ""}>
            ${f.hint ? `<div class="fm-hint">${mEsc(f.hint)}</div>` : ""}
        </div>`;
}

/**
 * 绑定分段选择器（segment 类型字段）
 * 在 openFormModal 渲染后调用
 */
function bindSegmentGroups(root) {
    root.querySelectorAll("[data-seg-group]").forEach(group => {
        const key = group.dataset.segGroup;
        const hidden = group.querySelector("input[type=hidden]");
        group.querySelectorAll("[data-seg]").forEach(btn => {
            btn.addEventListener("click", () => {
                group.querySelectorAll("[data-seg]").forEach(b => b.classList.remove("active"));
                btn.classList.add("active");
                if (hidden) hidden.value = btn.dataset.val;
            });
        });
    });
}

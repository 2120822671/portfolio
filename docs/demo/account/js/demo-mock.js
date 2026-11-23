/* ==========================================================
   招财记账 · 静态演示版 mock 层
   ------------------------------------------------------------
   接管 ./api/… 请求，用浏览器内存数据模拟后端全部接口。
   刷新页面即还原为初始演示数据，不依赖任何后端 / 数据库。
   ========================================================== */
(function () {
  "use strict";

  /* ---------------- 基础工具 ---------------- */

  function json(data, status) {
    return new Response(JSON.stringify(data), {
      status: status || 200,
      headers: { "Content-Type": "application/json; charset=utf-8" },
    });
  }

  function ok(data, message, extra) {
    var payload = {
      code: 200,
      message: message || "操作成功",
      data: data === undefined ? null : data,
    };
    if (extra) {
      Object.keys(extra).forEach(function (k) { payload[k] = extra[k]; });
    }
    return json(payload, 200);
  }

  function fail(message, status) {
    return Promise.resolve(json({ detail: message }, status || 400));
  }

  function pad(n) { return String(n).padStart(2, "0"); }

  function fmtDateTime(d) {
    return d.getFullYear() + "-" + pad(d.getMonth() + 1) + "-" + pad(d.getDate()) +
      " " + pad(d.getHours()) + ":" + pad(d.getMinutes()) + ":" + pad(d.getSeconds());
  }

  function fmtDate(d) {
    return d.getFullYear() + "-" + pad(d.getMonth() + 1) + "-" + pad(d.getDate());
  }

  function fmtMonth(d) {
    return d.getFullYear() + "-" + pad(d.getMonth() + 1);
  }

  function today() {
    var d = new Date();
    d.setHours(0, 0, 0, 0);
    return d;
  }

  function daysAgo(n, hh, mm) {
    var d = new Date();
    d.setDate(d.getDate() - n);
    d.setHours(hh || 12, mm || 0, 0, 0);
    return d;
  }

  function money(v) { return Math.round((Number(v) || 0) * 100) / 100; }

  /* ---------------- 内存数据 ---------------- */

  var SEQ = 0;
  function newId() { SEQ += 1; return SEQ; }

  function makeRecord(offsetDays, hh, mm, type, amount, category, remark, accountId) {
    var d = daysAgo(offsetDays, hh, mm);
    var created = new Date(d.getTime() + 3 * 60000);
    return {
      id: newId(),
      type: type,
      amount: money(amount),
      category: category,
      remark: remark,
      recordTime: fmtDateTime(d),
      createTime: fmtDateTime(created),
      accountId: accountId || 1,
    };
  }

  /* 26 条近三个月模拟流水（餐饮 / 交通 / 购物 / 娱乐 / 生活 / 医疗 / 工资 / 奖金） */
  var records = [
    // 本月（以当前日期为基准的近 7 天，保证日汇总、近 7 日柱图有数据）
    makeRecord(0, 8, 20, 2, 12.00, "餐饮", "早餐豆浆油条", 1),
    makeRecord(0, 12, 35, 2, 28.50, "餐饮", "午餐牛肉面", 1),
    makeRecord(0, 18, 10, 2, 15.00, "交通", "地铁通勤", 1),
    makeRecord(1, 12, 20, 2, 32.00, "餐饮", "公司楼下简餐", 1),
    makeRecord(1, 20, 5, 2, 68.00, "购物", "超市日用品", 1),
    makeRecord(2, 9, 10, 2, 6.00, "交通", "公交月卡补差", 1),
    makeRecord(2, 19, 30, 2, 45.00, "娱乐", "电影票", 1),
    makeRecord(3, 12, 40, 2, 26.00, "餐饮", "外卖黄焖鸡", 1),
    makeRecord(4, 8, 15, 2, 10.00, "交通", "早高峰打车", 2),
    makeRecord(4, 21, 0, 2, 128.00, "购物", "淘宝买衣服", 2),
    makeRecord(5, 12, 0, 2, 38.00, "餐饮", "和同事吃饭", 1),
    makeRecord(5, 22, 0, 2, 9.90, "生活", "视频会员月费", 1),
    makeRecord(6, 18, 40, 2, 56.00, "餐饮", "周末火锅", 1),
    makeRecord(8, 10, 0, 1, 12000.00, "工资", "本月工资到账", 1),
    makeRecord(9, 15, 20, 1, 500.00, "奖金", "季度绩效奖金", 1),
    makeRecord(12, 13, 0, 2, 240.00, "生活", "水电燃气费", 2),
    // 上月
    makeRecord(35, 12, 30, 2, 42.00, "餐饮", "月末朋友聚餐", 1),
    makeRecord(38, 9, 0, 1, 12000.00, "工资", "上月工资到账", 1),
    makeRecord(40, 20, 0, 2, 320.00, "购物", "运动鞋", 3),
    makeRecord(45, 18, 30, 2, 88.00, "餐饮", "烧烤夜宵", 2),
    makeRecord(48, 10, 0, 2, 2800.00, "生活", "房租", 2),
    // 上上月
    makeRecord(65, 9, 0, 1, 12000.00, "工资", "工资到账", 1),
    makeRecord(68, 12, 0, 2, 35.00, "交通", "高铁票", 2),
    makeRecord(70, 19, 0, 2, 199.00, "娱乐", "演唱会门票", 3),
    makeRecord(75, 12, 20, 2, 46.00, "餐饮", "工作日午餐", 1),
    makeRecord(78, 21, 10, 2, 150.00, "医疗", "感冒药", 2),
  ];

  var books = [
    { id: 1, name: "日常账本", bookType: "银行卡", icon: "💳", initBalance: 2000, isDefault: true },
    { id: 2, name: "支付宝", bookType: "支付宝", icon: "💙", initBalance: 6000, isDefault: false },
    { id: 3, name: "微信钱包", bookType: "微信", icon: "💚", initBalance: 1500, isDefault: false },
  ];

  var budgetSeq = 3;
  var budgets = [
    { id: 1, category: "餐饮", period: fmtMonth(new Date()), amount: 200, enabled: 1 },
    { id: 2, category: "购物", period: fmtMonth(new Date()), amount: 300, enabled: 1 },
    { id: 3, category: "交通", period: fmtMonth(new Date()), amount: 100, enabled: 1 },
  ];

  function monthStartMinus(months) {
    var d = new Date();
    d.setDate(1);
    d.setMonth(d.getMonth() - months);
    return d;
  }

  var recurringSeq = 3;
  var recurring = [
    {
      id: 1, name: "房租", type: 2, amount: 2800, category: "生活", remark: "房租",
      accountId: 1, cycleType: "monthly", cycleValue: 1,
      startDate: fmtDate(monthStartMinus(2)), endDate: null, autoPost: true, enabled: true,
    },
    {
      id: 2, name: "视频会员", type: 2, amount: 19.9, category: "生活", remark: "视频会员",
      accountId: 1, cycleType: "monthly", cycleValue: 1,
      startDate: fmtDate(monthStartMinus(1)), endDate: null, autoPost: true, enabled: true,
    },
    {
      id: 3, name: "工资", type: 1, amount: 12000, category: "工资", remark: "工资",
      accountId: 1, cycleType: "monthly", cycleValue: 1,
      startDate: fmtDate(monthStartMinus(2)), endDate: null, autoPost: true, enabled: true,
    },
  ];

  var reportSeq = 0;
  function makeReport(type, title, content, level, offsetDays, isRead) {
    reportSeq += 1;
    var d = daysAgo(offsetDays, 23, 0);
    return {
      id: reportSeq,
      date: fmtDate(d),
      type: type,
      title: title,
      content: content,
      data: null,
      level: level || "info",
      isRead: !!isRead,
      createdAt: fmtDateTime(d),
    };
  }

  var reports = [
    makeReport("warning", "「餐饮」预算已达 96%", "本月餐饮支出已接近预算上限，喵～后面几天可以多在家做饭。", "warning", 0, false),
    makeReport("summary", "今日收支小结", "今天共 3 笔：收入 ¥0.00，支出 ¥55.50，结余 -¥55.50。", "info", 0, false),
    makeReport("review", "昨日消费复盘", "昨天支出集中在餐饮与购物，共 ¥100.00；餐饮以工作餐为主，整体节奏平稳。", "info", 1, true),
    makeReport("summary", "昨日收支小结", "昨天共 2 笔：收入 ¥0.00，支出 ¥100.00，结余 -¥100.00。", "info", 1, true),
  ];

  /* ---------------- 派生计算 ---------------- */

  function inRange(record, startKey, endKey) {
    var d = record.recordTime.slice(0, 10);
    if (startKey && d < startKey) return false;
    if (endKey && d > endKey) return false;
    return true;
  }

  function sortRecords(list) {
    return list.slice().sort(function (a, b) {
      if (a.recordTime === b.recordTime) return b.id - a.id;
      return a.recordTime < b.recordTime ? 1 : -1;
    });
  }

  function booksPayload() {
    return books.map(function (b) {
      var income = 0, expense = 0, count = 0;
      records.forEach(function (r) {
        if (r.accountId !== b.id) return;
        count += 1;
        if (r.type === 1) income += r.amount;
        else expense += r.amount;
      });
      income = money(income);
      expense = money(expense);
      return {
        id: b.id,
        name: b.name,
        bookType: b.bookType,
        icon: b.icon,
        initBalance: money(b.initBalance),
        income: income,
        expense: expense,
        balance: money(b.initBalance + income - expense),
        count: count,
        isDefault: !!b.isDefault,
      };
    });
  }

  function monthExpenseByCategory(accountId) {
    var prefix = fmtMonth(new Date());
    var map = {};
    records.forEach(function (r) {
      if (r.type !== 2) return;
      if (accountId && r.accountId !== accountId) return;
      if (r.recordTime.slice(0, 7) !== prefix) return;
      map[r.category] = (map[r.category] || 0) + r.amount;
    });
    return Object.keys(map).map(function (name) {
      return { name: name, value: money(map[name]) };
    }).sort(function (a, b) { return b.value - a.value; });
  }

  function trendPayload(months, accountId) {
    var out = [];
    for (var i = months - 1; i >= 0; i--) {
      var base = new Date();
      base.setDate(1);
      base.setMonth(base.getMonth() - i);
      var key = fmtMonth(base);
      var income = 0, expense = 0;
      records.forEach(function (r) {
        if (r.recordTime.slice(0, 7) !== key) return;
        if (accountId && r.accountId !== accountId) return;
        if (r.type === 1) income += r.amount;
        else expense += r.amount;
      });
      out.push({ month: key, income: money(income), expense: money(expense) });
    }
    return out;
  }

  function last7Payload(accountId) {
    var out = [];
    for (var i = 6; i >= 0; i--) {
      var d = daysAgo(i, 0, 0);
      var key = fmtDate(d);
      var amount = 0;
      records.forEach(function (r) {
        if (r.type !== 2) return;
        if (accountId && r.accountId !== accountId) return;
        if (r.recordTime.slice(0, 10) !== key) return;
        amount += r.amount;
      });
      out.push({
        date: key,
        label: (d.getMonth() + 1) + "/" + d.getDate(),
        amount: money(amount),
      });
    }
    return out;
  }

  function budgetsPayload(period) {
    var startKey = period + "-01";
    var endKey = period + "-31";
    var usedMap = {};
    records.forEach(function (r) {
      if (r.type !== 2) return;
      if (r.recordTime.slice(0, 7) !== period) return;
      usedMap[r.category] = (usedMap[r.category] || 0) + r.amount;
    });
    return budgets.filter(function (b) { return b.period === period; }).map(function (b) {
      var used = money(usedMap[b.category] || 0);
      var limit = money(b.amount);
      var rate = limit > 0 ? Math.round(used / limit * 1000) / 10 : 0;
      return {
        id: b.id,
        category: b.category,
        period: b.period,
        amount: limit,
        used: used,
        rate: rate,
        remain: money(limit - used),
        over: used > limit,
        enabled: !!b.enabled,
      };
    }).sort(function (a, b) { return b.amount - a.amount; });
  }

  function checkinPayload() {
    var days = {};
    records.forEach(function (r) {
      var k = r.recordTime.slice(0, 10);
      days[k] = (days[k] || 0) + 1;
    });

    var cur = today();
    if (!days[fmtDate(cur)]) cur.setDate(cur.getDate() - 1);
    var streak = 0;
    while (days[fmtDate(cur)]) {
      streak += 1;
      cur.setDate(cur.getDate() - 1);
    }

    var totalDays = Object.keys(days).length;
    var totalRecords = 0;
    Object.keys(days).forEach(function (k) { totalRecords += days[k]; });

    var mPrefix = fmtMonth(new Date());
    var mIncome = 0, mExpense = 0;
    records.forEach(function (r) {
      if (r.recordTime.slice(0, 7) !== mPrefix) return;
      if (r.type === 1) mIncome += r.amount;
      else mExpense += r.amount;
    });

    return {
      streak: streak,
      totalDays: totalDays,
      totalRecords: totalRecords,
      days: days,
      badges: [
        { name: "开张大吉", desc: "完成第一次记账", got: totalRecords >= 1 },
        { name: "勤勉小账房", desc: "累计记录 100 笔", got: totalRecords >= 100 },
        { name: "七日连击", desc: "连续记账 7 天", got: streak >= 7 },
        { name: "月度常客", desc: "累计打卡 30 天", got: totalDays >= 30 },
        { name: "存钱有道", desc: "本月结余为正", got: mIncome > mExpense },
      ],
    };
  }

  var QUOTES = [
    "喵～今天的每一笔都算数。",
    "会记账的人，运气都不会太差。",
    "钱要花在让你眼睛发亮的地方喵。",
    "存钱不是抠门，是给未来的自己发红包。",
    "记录本身就是一种温柔喵。",
  ];

  function todayStat(accountId) {
    var key = fmtDate(new Date());
    var income = 0, expense = 0, count = 0;
    records.forEach(function (r) {
      if (r.recordTime.slice(0, 10) !== key) return;
      if (accountId && r.accountId !== accountId) return;
      count += 1;
      if (r.type === 1) income += r.amount;
      else expense += r.amount;
    });
    return { income: money(income), expense: money(expense), count: count };
  }

  function monthStat(accountId) {
    var prefix = fmtMonth(new Date());
    var income = 0, expense = 0;
    records.forEach(function (r) {
      if (r.recordTime.slice(0, 7) !== prefix) return;
      if (accountId && r.accountId !== accountId) return;
      if (r.type === 1) income += r.amount;
      else expense += r.amount;
    });
    return { income: money(income), expense: money(expense) };
  }

  function analysisReply(accountId) {
    var m = monthStat(accountId);
    var cats = monthExpenseByCategory(accountId);
    var top = cats.length ? cats[0].name + "（¥" + cats[0].value.toFixed(2) + "）" : "暂无支出";
    var lines = [];
    lines.push("喵～本月（" + fmtMonth(new Date()) + "）收入 ¥" + m.income.toFixed(2) +
      "，支出 ¥" + m.expense.toFixed(2) + "，结余 ¥" + money(m.income - m.expense).toFixed(2) + "。");
    lines.push("花钱最多的是 " + top + "，餐饮类支出笔数最多，多为工作日午餐。");
    lines.push(m.income - m.expense >= 0
      ? "整体收支健康，继续保持喵～"
      : "本月支出超过收入，建议给购物和娱乐留点缓冲。");
    return lines.join("\n");
  }

  function queryReply(accountId) {
    var s = todayStat(accountId);
    return "今天共记了 " + s.count + " 笔账，收入 ¥" + s.income.toFixed(2) +
      "，支出 ¥" + s.expense.toFixed(2) + "，结余 ¥" + money(s.income - s.expense).toFixed(2) +
      (s.count ? "。" : "，还没记账喵。");
  }

  /* 招财猫规则解析（与前端规则保持一致） */
  var INCOME_RULES = [
    { keywords: ["工资", "薪水"], category: "工资" },
    { keywords: ["奖金", "年终奖"], category: "奖金" },
    { keywords: ["报销"], category: "报销" },
    { keywords: ["红包", "转账", "收款", "到账", "兼职", "利息", "收入", "进账"], category: "其他收入" },
  ];
  var CAT_RULES = [
    { keywords: ["午饭", "午餐", "晚饭", "晚餐", "早餐", "早饭", "吃饭", "火锅", "外卖", "餐饮", "奶茶", "咖啡", "零食", "面", "饭"], category: "餐饮" },
    { keywords: ["打车", "出租", "地铁", "公交", "车费", "加油", "停车", "交通", "高铁", "机票"], category: "交通" },
    { keywords: ["购物", "衣服", "鞋", "淘宝", "京东", "超市", "日用", "买"], category: "购物" },
    { keywords: ["电影", "游戏", "娱乐", "唱歌", "旅游", "KTV", "演唱会"], category: "娱乐" },
    { keywords: ["房租", "水电", "物业", "话费", "宽带", "生活"], category: "生活" },
    { keywords: ["医院", "药", "看病", "体检", "医疗"], category: "医疗" },
  ];

  function parseChat(text) {
    var raw = String(text || "").trim();
    if (!raw) return { intent: "chat", records: [], reply: "喵～有什么想记的吗？" };

    if (/分析|复盘|解读|消费习惯/.test(raw)) {
      return { intent: "analysis", records: [], reply: analysisReply(1) };
    }
    if (/(今天|今日).*(花了|支出|消费|流水|收支)|花了多少|支出多少/.test(raw)) {
      return { intent: "query", records: [], reply: queryReply(1) };
    }

    var m = raw.match(/(\d+(?:\.\d{1,2})?)/);
    if (!m) {
      return { intent: "chat", records: [], reply: "喵～可以这样说：「午饭 30」「打车 15」「工资 8000」。" };
    }
    var amount = parseFloat(m[1]);
    if (!amount || amount <= 0) {
      return { intent: "chat", records: [], reply: "金额要大于 0 喵～再试一次？" };
    }

    var type = 2;
    var category = "";
    INCOME_RULES.forEach(function (rule) {
      if (!category && rule.keywords.some(function (k) { return raw.indexOf(k) >= 0; })) {
        type = 1;
        category = rule.category;
      }
    });
    if (!category) {
      CAT_RULES.forEach(function (rule) {
        if (!category && rule.keywords.some(function (k) { return raw.indexOf(k) >= 0; })) {
          category = rule.category;
        }
      });
    }
    if (!category) category = type === 1 ? "其他收入" : "其他";

    return {
      intent: "record",
      records: [{
        type: type,
        amount: money(amount),
        category: category,
        remark: raw,
        recordTime: fmtDateTime(new Date()),
      }],
      reply: "",
    };
  }

  /* ---------------- fetch 接管 ---------------- */

  var realFetch = window.fetch ? window.fetch.bind(window) : null;

  window.fetch = function (input, init) {
    var url = typeof input === "string" ? input : (input && input.url) || "";

    if (url.indexOf("/api/") === -1) {
      return realFetch ? realFetch(input, init) : Promise.reject(new TypeError("Failed to fetch"));
    }

    var method = ((init && init.method) || (input && input.method) || "GET").toUpperCase();
    var body = {};
    if (init && init.body) {
      try { body = JSON.parse(init.body); } catch (e) { body = {}; }
    }

    var rawPath = url.split("?")[0];
    var path = rawPath.slice(rawPath.indexOf("/api/") + 4).replace(/\/+$/, "") || "/";

    var query = {};
    var qs = url.split("?")[1] || "";
    qs.split("&").forEach(function (kv) {
      if (!kv) return;
      var p = kv.split("=");
      query[decodeURIComponent(p[0])] = decodeURIComponent((p[1] || "").replace(/\+/g, " "));
    });

    var accountId = Number(query.accountId || body.accountId || 0) || 0;

    /* ---- 记账流水 ---- */
    if (path === "/records" && method === "GET") {
      var pageNum = Math.max(1, parseInt(query.pageNum, 10) || 1);
      var pageSize = Math.min(100, Math.max(1, parseInt(query.pageSize, 10) || 10));
      var type = query.type ? parseInt(query.type, 10) : null;
      var keyword = (query.keyword || "").trim();

      var list = records.filter(function (r) {
        if (type !== null && r.type !== type) return false;
        if (accountId && r.accountId !== accountId) return false;
        if (keyword && (r.category || "").indexOf(keyword) < 0 &&
          (r.remark || "").indexOf(keyword) < 0) return false;
        return inRange(r, query.startDate, query.endDate);
      });
      list = sortRecords(list);
      var total = list.length;
      var start = (pageNum - 1) * pageSize;
      return Promise.resolve(ok({
        total: total,
        list: list.slice(start, start + pageSize),
      }, "查询成功"));
    }

    if (path === "/records/summary" && method === "GET") {
      var day = query.date || fmtDate(new Date());
      var income = 0, expense = 0, count = 0, todayList = [];
      records.forEach(function (r) {
        if (r.recordTime.slice(0, 10) !== day) return;
        if (accountId && r.accountId !== accountId) return;
        count += 1;
        if (r.type === 1) income += r.amount;
        else expense += r.amount;
        todayList.push(r);
      });
      todayList = sortRecords(todayList).slice(0, 3);
      return Promise.resolve(ok({
        date: day,
        income: money(income),
        expense: money(expense),
        balance: money(income - expense),
        count: count,
        recent: todayList,
      }, "查询成功"));
    }

    if (path === "/records" && method === "POST") {
      if (!body.category || !String(body.category).trim()) return fail("category 不能为空");
      if (!body.amount || Number(body.amount) <= 0) return fail("amount 必须大于 0");
      if (body.type !== 1 && body.type !== 2) return fail("type 必须是 1(收入) 或 2(支出)");
      if (!body.recordTime) return fail("recordTime 不能为空");
      var bookId = Number(body.accountId) || 1;
      if (!books.some(function (b) { return b.id === bookId; })) bookId = 1;

      var rec = {
        id: newId(),
        type: body.type,
        amount: money(body.amount),
        category: String(body.category).trim(),
        remark: body.remark || null,
        recordTime: String(body.recordTime),
        createTime: fmtDateTime(new Date()),
        accountId: bookId,
      };
      records.push(rec);
      return Promise.resolve(ok(rec, "添加成功"));
    }

    var recIdMatch = path.match(/^\/records\/(\d+)$/);
    if (recIdMatch) {
      var rid = parseInt(recIdMatch[1], 10);
      var target = records.find(function (r) { return r.id === rid; });
      if (!target) return fail("记录不存在", 404);

      if (method === "GET") return Promise.resolve(ok(target, "查询成功"));

      if (method === "PUT") {
        if (!body.category || !String(body.category).trim()) return fail("category 不能为空");
        if (!body.amount || Number(body.amount) <= 0) return fail("amount 必须大于 0");
        target.type = body.type === 1 ? 1 : 2;
        target.amount = money(body.amount);
        target.category = String(body.category).trim();
        target.remark = body.remark || null;
        target.recordTime = String(body.recordTime || target.recordTime);
        target.accountId = Number(body.accountId) || target.accountId;
        return Promise.resolve(ok(target, "修改成功"));
      }

      if (method === "DELETE") {
        records.splice(records.indexOf(target), 1);
        return Promise.resolve(ok({ id: rid }, "删除成功"));
      }
    }

    /* ---- 账本 ---- */
    if (path === "/books" && method === "GET") {
      return Promise.resolve(ok(booksPayload(), "查询成功"));
    }
    if (path === "/books" && method === "POST") {
      if (!body.name || !String(body.name).trim()) return fail("账本名称不能为空");
      var nextBookId = books.reduce(function (m, b) { return Math.max(m, b.id); }, 0) + 1;
      var book = {
        id: nextBookId,
        name: String(body.name).trim(),
        bookType: body.bookType || "现金",
        icon: body.icon || "💰",
        initBalance: money(body.initBalance || 0),
        isDefault: false,
      };
      books.push(book);
      return Promise.resolve(ok(book, "账本创建成功"));
    }
    var bookIdMatch = path.match(/^\/books\/(\d+)$/);
    if (bookIdMatch) {
      var bid = parseInt(bookIdMatch[1], 10);
      var bk = books.find(function (b) { return b.id === bid; });
      if (!bk) return fail("账本不存在", 404);

      if (method === "PUT") {
        bk.name = String(body.name || bk.name).trim();
        bk.bookType = body.bookType || bk.bookType;
        bk.icon = body.icon || bk.icon;
        bk.initBalance = body.initBalance === undefined ? bk.initBalance : money(body.initBalance);
        return Promise.resolve(ok(bk, "账本已更新"));
      }
      if (method === "DELETE") {
        if (bk.isDefault) return fail("默认账本不能删除");
        records.forEach(function (r) {
          if (r.accountId === bid) r.accountId = 1;
        });
        books.splice(books.indexOf(bk), 1);
        return Promise.resolve(ok({ id: bid }, "账本已删除"));
      }
    }

    /* ---- 统计看板 ---- */
    if (path === "/stats/overview" && method === "GET") {
      var months = Math.max(1, Math.min(12, parseInt(query.months, 10) || 6));
      var statsAccount = accountId || null;
      return Promise.resolve(ok({
        category: monthExpenseByCategory(statsAccount),
        trend: trendPayload(months, statsAccount),
        last7: last7Payload(statsAccount),
      }, "查询成功"));
    }

    /* ---- 预算 ---- */
    if (path === "/budgets" && method === "GET") {
      var period = /^\d{4}-\d{2}$/.test(query.period || "") ? query.period : fmtMonth(new Date());
      return Promise.resolve(ok({ period: period, budgets: budgetsPayload(period) }, "查询成功"));
    }
    if (path === "/budgets" && method === "POST") {
      if (!body.category || !String(body.category).trim()) return fail("category 不能为空");
      if (!/^\d{4}-\d{2}$/.test(body.period || "")) return fail("period 格式错误，应为 YYYY-MM");
      if (!body.amount || Number(body.amount) <= 0) return fail("amount 必须大于 0");

      var exist = budgets.find(function (b) {
        return b.category === String(body.category).trim() && b.period === body.period;
      });
      if (exist) {
        exist.amount = money(body.amount);
        exist.enabled = body.enabled === 0 ? 0 : 1;
        return Promise.resolve(ok({ id: exist.id }, "预算已保存"));
      }
      budgetSeq += 1;
      budgets.push({
        id: budgetSeq,
        category: String(body.category).trim(),
        period: body.period,
        amount: money(body.amount),
        enabled: body.enabled === 0 ? 0 : 1,
      });
      return Promise.resolve(ok({ id: budgetSeq }, "预算已保存"));
    }
    var budgetIdMatch = path.match(/^\/budgets\/(\d+)$/);
    if (budgetIdMatch && method === "DELETE") {
      var bgid = parseInt(budgetIdMatch[1], 10);
      var idx = budgets.findIndex(function (b) { return b.id === bgid; });
      if (idx < 0) return fail("预算不存在", 404);
      budgets.splice(idx, 1);
      return Promise.resolve(ok({ id: bgid }, "预算已删除"));
    }

    /* ---- 周期账单 ---- */
    if (path === "/recurring" && method === "GET") {
      return Promise.resolve(ok({ rules: recurring, runs: [] }, "查询成功"));
    }
    if (path === "/recurring" && method === "POST") {
      if (body.type !== 1 && body.type !== 2) return fail("type 必须是 1(收入) 或 2(支出)");
      if (!body.amount || Number(body.amount) <= 0) return fail("amount 必须大于 0");
      if (["daily", "weekly", "monthly"].indexOf(body.cycleType) < 0) {
        return fail("cycleType 必须是 daily/weekly/monthly");
      }
      recurringSeq += 1;
      recurring.push({
        id: recurringSeq,
        name: String(body.name || "周期账单"),
        type: body.type,
        amount: money(body.amount),
        category: body.category || "其他",
        remark: body.remark || null,
        accountId: Number(body.accountId) || 1,
        cycleType: body.cycleType,
        cycleValue: Math.max(1, parseInt(body.cycleValue, 10) || 1),
        startDate: body.startDate || fmtDate(new Date()),
        endDate: body.endDate || null,
        autoPost: body.autoPost !== 0,
        enabled: body.enabled !== 0,
      });
      return Promise.resolve(ok({ id: recurringSeq }, "创建成功"));
    }

    var runRuleMatch = path.match(/^\/recurring\/(\d+)\/run$/);
    if (runRuleMatch && method === "POST") {
      var ruleId = parseInt(runRuleMatch[1], 10);
      var rule = recurring.find(function (r) { return r.id === ruleId; });
      if (!rule) return fail("规则不存在", 404);
      if (!rule.enabled) {
        return Promise.resolve(ok({ ran: false, reason: "规则已停用" }, "跳过"));
      }
      records.push({
        id: newId(),
        type: rule.type,
        amount: money(rule.amount),
        category: rule.category,
        remark: rule.remark || rule.name,
        recordTime: fmtDateTime(new Date()),
        createTime: fmtDateTime(new Date()),
        accountId: rule.accountId || 1,
      });
      return Promise.resolve(ok({ ran: true, posted: 1, skipped: 0 }, "执行完成"));
    }

    if (path === "/recurring/run" && method === "POST") {
      var posted = 0;
      recurring.forEach(function (rule) {
        if (!rule.enabled || !rule.autoPost) return;
        records.push({
          id: newId(),
          type: rule.type,
          amount: money(rule.amount),
          category: rule.category,
          remark: rule.remark || rule.name,
          recordTime: fmtDateTime(new Date()),
          createTime: fmtDateTime(new Date()),
          accountId: rule.accountId || 1,
        });
        posted += 1;
      });
      return Promise.resolve(ok({ posted: posted, pending: 0, skipped: 0 }, "执行完成"));
    }

    var recRuleMatch = path.match(/^\/recurring\/(\d+)$/);
    if (recRuleMatch && method === "DELETE") {
      var rrid = parseInt(recRuleMatch[1], 10);
      var ridx = recurring.findIndex(function (r) { return r.id === rrid; });
      if (ridx < 0) return fail("规则不存在", 404);
      recurring.splice(ridx, 1);
      return Promise.resolve(ok({ id: rrid }, "规则已删除"));
    }

    /* ---- 消息中心 ---- */
    if (path === "/reports" && method === "GET") {
      var limit = Math.max(1, Math.min(100, parseInt(query.limit, 10) || 30));
      var unread = reports.filter(function (r) { return !r.isRead; }).length;
      return Promise.resolve(ok({ reports: reports.slice(0, limit), unread: unread }, "查询成功"));
    }
    if (path === "/reports/read-all" && method === "POST") {
      reports.forEach(function (r) { r.isRead = true; });
      return Promise.resolve(ok({ changed: reports.length }, "全部标记为已读"));
    }
    var reportReadMatch = path.match(/^\/reports\/(\d+)\/read$/);
    if (reportReadMatch && method === "POST") {
      var rpid = parseInt(reportReadMatch[1], 10);
      var rp = reports.find(function (r) { return r.id === rpid; });
      if (!rp) return fail("消息不存在", 404);
      rp.isRead = true;
      return Promise.resolve(ok({ id: rpid }, "已标记为已读"));
    }

    /* ---- 打卡 / 调度 / 自动化 ---- */
    if (path === "/checkin" && method === "GET") {
      return Promise.resolve(ok(checkinPayload(), "查询成功"));
    }
    if (path === "/scheduler/jobs" && method === "GET") {
      var now = new Date();
      var tomorrow = new Date(now.getTime() + 86400000);
      return Promise.resolve(ok({
        jobs: [
          { id: "recurring", name: "周期账单检查", nextRun: fmtDate(tomorrow) + " 00:05:00" },
          { id: "summary", name: "日终收支小结", nextRun: fmtDate(now) + " 23:00:00" },
          { id: "review", name: "消费复盘", nextRun: fmtDate(now) + " 23:10:00" },
        ],
        llmEnabled: false,
        llmModel: null,
        timezone: "Asia/Shanghai",
      }, "查询成功"));
    }
    if (path === "/automation/run-summary" && method === "POST") {
      var s = todayStat(0);
      reports.unshift(makeReport(
        "summary", "今日收支小结",
        "今天共 " + s.count + " 笔：收入 ¥" + s.income.toFixed(2) +
        "，支出 ¥" + s.expense.toFixed(2) + "，结余 ¥" + money(s.income - s.expense).toFixed(2) + "。",
        "info", 0, false
      ));
      return Promise.resolve(ok({ created: 1 }, "日终汇总已生成"));
    }
    if (path === "/automation/run-review" && method === "POST") {
      reports.unshift(makeReport(
        "review", "消费复盘",
        "近期支出以餐饮为主，购物集中在超市日用品；建议保持当前节奏，给娱乐支出留出余量。",
        "info", 0, false
      ));
      return Promise.resolve(ok({ created: 1 }, "每日复盘已生成"));
    }

    /* ---- 招财猫对话 ---- */
    if (path === "/chat" && method === "POST") {
      if (!body.text || !String(body.text).trim()) return fail("text 不能为空");
      var parsed = parseChat(body.text);
      return Promise.resolve(ok({
        intent: parsed.intent,
        records: parsed.records,
        reply: parsed.reply,
      }, "使用规则解析", { mode: "rule" }));
    }

    if (path === "/quote" && method === "GET") {
      var idx = Math.floor(new Date().getTime() / 86400000) % QUOTES.length;
      return Promise.resolve(ok({ quote: QUOTES[idx] }, "查询成功"));
    }

    return Promise.resolve(json({ detail: "演示环境未实现该接口：" + path }, 404));
  };
})();

/* 墨香书阁 · 静态演示版 mock 层
   接管前端所有 fetch 请求，用内存数据模拟后端；刷新页面即还原。 */
(function () {
  "use strict";

  const CLASSIC_IDS = new Set([8, 10, 12, 13]);

  const pad = (n) => String(n).padStart(2, "0");
  function nowStr() {
    const d = new Date();
    return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ` +
      `${pad(d.getHours())}:${pad(d.getMinutes())}:${pad(d.getSeconds())}`;
  }

  // ==================== 图书（12 本，其中 3 本在借） ====================
  const books = [
    { id: 1, title: "三体", author: "刘慈欣", isbn: "978-7-5366-9293-0", stock: 2, category: "科幻", cover_url: "covers/book_01.jpg", description: "地球文明与三体文明跨越星海的博弈，中国科幻的里程碑之作。" },
    { id: 2, title: "活着", author: "余华", isbn: "978-7-5063-6543-7", stock: 3, category: "文学", cover_url: "covers/book_02.jpg", description: "福贵的一生，是一部关于苦难、坚韧与生命意义的当代经典。" },
    { id: 3, title: "百年孤独", author: "加西亚·马尔克斯", isbn: "978-7-5442-5399-4", stock: 2, category: "文学", cover_url: "covers/book_03.jpg", description: "布恩迪亚家族七代人的传奇，魔幻现实主义的巅峰。" },
    { id: 4, title: "人类简史", author: "尤瓦尔·赫拉利", isbn: "978-7-5086-4735-9", stock: 3, category: "历史", cover_url: "covers/book_04.jpg", description: "从动物到上帝，重新审视智人如何塑造了今天的世界。" },
    { id: 5, title: "深度学习", author: "Ian Goodfellow", isbn: "978-7-115-46128-7", stock: 2, category: "科技", cover_url: "covers/book_05.jpg", description: "被称为「花书」的深度学习领域权威教材。" },
    { id: 6, title: "原则", author: "瑞·达利欧", isbn: "978-7-5086-8678-7", stock: 2, category: "商业", cover_url: "covers/book_06.jpg", description: "桥水基金创始人总结的生活与工作原则。" },
    { id: 7, title: "明朝那些事儿", author: "当年明月", isbn: "978-7-5063-7762-1", stock: 3, category: "历史", cover_url: "covers/book_07.jpg", description: "以通俗笔法讲述明朝三百年兴衰的畅销历史读物。" },
    { id: 8, title: "小王子", author: "圣埃克苏佩里", isbn: "978-7-5447-3107-5", stock: 5, category: "文学", cover_url: "covers/book_08.jpg", description: "写给大人的童话，关于爱与责任的温柔寓言。" },
    { id: 9, title: "思考，快与慢", author: "丹尼尔·卡尼曼", isbn: "978-7-5086-3355-6", stock: 2, category: "心理", cover_url: "covers/book_09.jpg", description: "系统 1 与系统 2，揭示人类判断与决策的秘密。" },
    { id: 10, title: "红楼梦", author: "曹雪芹", isbn: "978-7-02-008666-7", stock: 1, category: "文学", cover_url: "covers/book_10.jpg", description: "中国古典四大名著之首，贾府兴衰与红楼儿女的命运长卷。" },
    { id: 11, title: "算法导论", author: "Thomas H. Cormen", isbn: "978-7-111-40701-0", stock: 0, category: "科技", cover_url: "covers/book_11.jpg", description: "计算机科学领域的经典教材，全面覆盖算法设计与分析。" },
    { id: 12, title: "苏菲的世界", author: "乔斯坦·贾德", isbn: "978-7-5063-2753-0", stock: 2, category: "哲学", cover_url: null, description: "以小说形式展开的西方哲学启蒙之旅。" },
  ];

  // ==================== 借阅记录（3 条在借 + 3 条已归还） ====================
  const borrows = [
    { id: 1, book_id: 1, book_title: "三体", borrower: "赵明", borrowed_at: "2026-11-05 09:20:00", returned_at: "2026-11-09 17:45:00" },
    { id: 2, book_id: 8, book_title: "小王子", borrower: "林小满", borrowed_at: "2026-11-10 09:00:00", returned_at: "2026-11-15 20:30:00" },
    { id: 3, book_id: 2, book_title: "活着", borrower: "林小满", borrowed_at: "2026-11-12 14:20:00", returned_at: "2026-11-20 10:00:00" },
    { id: 4, book_id: 1, book_title: "三体", borrower: "陈振华", borrowed_at: "2026-11-18 10:12:00", returned_at: null },
    { id: 5, book_id: 11, book_title: "算法导论", borrower: "周知行", borrowed_at: "2026-11-21 16:40:00", returned_at: null },
    { id: 6, book_id: 10, book_title: "红楼梦", borrower: "苏晚", borrowed_at: "2026-11-22 09:30:00", returned_at: null },
  ];

  // ==================== 完书记录 ====================
  const completions = [
    { id: 1, book_id: 8, book_title: "小王子", borrower: "林小满", correct_count: 3, total_count: 3, score: 100, completed_at: "2026-11-15 21:20:00" },
    { id: 2, book_id: 2, book_title: "活着", borrower: "林小满", correct_count: 2, total_count: 3, score: 66.7, completed_at: "2026-11-20 10:30:00" },
  ];

  // ==================== 问答题库 ====================
  const quizzes = [
    {
      book_id: 1,
      questions: [
        { question: "《三体》的作者刘慈欣被誉为中国什么文学的奠基人？", options: ["悬疑推理", "科幻", "武侠", "历史"], answer: 1 },
        { question: "小说中，叶文洁通过什么方式与外星文明建立联系？", options: ["射电望远镜", "量子通信", "虫洞穿梭", "时间机器"], answer: 0 },
        { question: "三体文明派来监控地球的质子被称为什么？", options: ["智子", "暗子", "明子", "灵子"], answer: 0 },
      ],
    },
    {
      book_id: 2,
      questions: [
        { question: "《活着》的作者是哪位当代作家？", options: ["莫言", "余华", "苏童", "格非"], answer: 1 },
        { question: "小说的主人公福贵最终以什么方式度过了晚年？", options: ["孤独终老", "与老黄牛相伴", "再婚生子", "远走他乡"], answer: 1 },
        { question: "《活着》的主题是什么？", options: ["革命斗争", "苦难与生命意义", "爱情悲剧", "家族兴衰"], answer: 1 },
      ],
    },
    {
      book_id: 3,
      questions: [
        { question: "《百年孤独》是哪种文学流派的代表作？", options: ["现实主义", "魔幻现实主义", "自然主义", "现代主义"], answer: 1 },
        { question: "小说讲述了哪个家族七代人的故事？", options: ["布恩迪亚家族", "马尔克斯家族", "加西亚家族", "维多利亚家族"], answer: 0 },
        { question: "作者加西亚·马尔克斯来自哪个国家？", options: ["阿根廷", "巴西", "哥伦比亚", "墨西哥"], answer: 2 },
      ],
    },
    {
      book_id: 4,
      questions: [
        { question: "《人类简史》的副标题是什么？", options: ["从猴子到超人", "从动物到上帝", "从原始到现代", "从工具到文明"], answer: 1 },
        { question: "书中提出人类文明的哪一次革命是关键转折点？", options: ["农业革命", "认知革命", "科学革命", "工业革命"], answer: 1 },
        { question: "作者尤瓦尔·赫拉利是哪国学者？", options: ["美国", "英国", "以色列", "澳大利亚"], answer: 2 },
      ],
    },
    {
      book_id: 5,
      questions: [
        { question: "《深度学习》的三位作者中，哪位被誉为「深度学习之父」？", options: ["Ian Goodfellow", "Yoshua Bengio", "Geoffrey Hinton", "Aaron Courville"], answer: 2 },
        { question: "这本书的中文译名又称作什么？", options: ["AI 圣经", "花书", "黑书", "深度学习手册"], answer: 1 },
        { question: "神经网络中「反向传播算法」的主要作用是什么？", options: ["数据预处理", "参数更新", "模型存储", "结果输出"], answer: 1 },
      ],
    },
    {
      book_id: 6,
      questions: [
        { question: "《原则》的作者瑞·达利欧是哪家投资公司的创始人？", options: ["伯克希尔·哈撒韦", "桥水基金", "量子基金", "老虎基金"], answer: 1 },
        { question: "作者将自己的原则分为哪两大类？", options: ["工作与生活", "生活与工作", "投资与管理", "个人与团队"], answer: 1 },
        { question: "达利欧认为决策时最重要的能力是什么？", options: ["直觉", "独立思考", "集体讨论", "经验积累"], answer: 1 },
      ],
    },
    {
      book_id: 7,
      questions: [
        { question: "《明朝那些事儿》最初以什么形式发布？", options: ["正式出版物", "网络博客", "杂志连载", "有声书"], answer: 1 },
        { question: "该书讲述了明朝多少位皇帝的故事？", options: ["14 位", "16 位", "17 位", "20 位"], answer: 1 },
        { question: "作者当年明月的真实身份是什么？", options: ["大学教授", "公务员", "历史学家", "记者"], answer: 1 },
      ],
    },
    {
      book_id: 8,
      questions: [
        { question: "《小王子》的作者圣埃克苏佩里的职业是什么？", options: ["作家", "飞行员", "科学家", "画家"], answer: 1 },
        { question: "小王子从哪个星球来到地球？", options: ["B-612", "A-115", "X-001", "Z-999"], answer: 0 },
        { question: "这本书是献给谁的？", options: ["作者的母亲", "作者的童年", "一个大人", "一位王子"], answer: 2 },
      ],
    },
    {
      book_id: 9,
      questions: [
        { question: "《思考，快与慢》的作者获得过什么奖项？", options: ["诺贝尔经济学奖", "诺贝尔文学奖", "普利策奖", "菲尔兹奖"], answer: 0 },
        { question: "书中提出大脑有哪两种思考模式？", options: ["理性与感性", "系统 1 与系统 2", "意识与潜意识", "左脑与右脑"], answer: 1 },
        { question: "卡尼曼教授主要研究哪个心理学领域？", options: ["认知心理学", "社会心理学", "发展心理学", "临床心理学"], answer: 0 },
      ],
    },
    {
      book_id: 10,
      questions: [
        { question: "《红楼梦》在清代被列为哪四大名著之一？", options: ["明代四大奇书", "古典四大名著", "志怪四篇", "诗文集"], answer: 1 },
        { question: "小说中林黛玉的死因与什么有关？", options: ["瘟疫", "肺病与爱情悲剧", "战争", "家族斗争"], answer: 1 },
        { question: "后四十回一般认为是谁续写的？", options: ["罗贯中", "施耐庵", "高鹗", "吴承恩"], answer: 2 },
      ],
    },
    {
      book_id: 11,
      questions: [
        { question: "《算法导论》的英文简称是什么？", options: ["CLRS", "CLRS 2", "Introduction", "AlgoBook"], answer: 0 },
        { question: "该书的封面是什么颜色？", options: ["红色", "蓝色", "绿色", "黑色"], answer: 1 },
        { question: "这本书在计算机科学中的地位被称为什么？", options: ["入门教材", "进阶读物", "计算机科学圣经", "参考书"], answer: 2 },
      ],
    },
    {
      book_id: 12,
      questions: [
        { question: "《苏菲的世界》是什么类型的小说？", options: ["科幻", "哲学启蒙", "悬疑", "成长"], answer: 1 },
        { question: "书中的主人公苏菲收到的第一封信问了什么问题？", options: ["你是谁？", "世界从哪里来？", "你怎么看？", "你在吗？"], answer: 0 },
        { question: "作者乔斯坦·贾德来自哪个国家？", options: ["丹麦", "挪威", "瑞典", "芬兰"], answer: 1 },
      ],
    },
  ];

  // ==================== 成就定义 ====================
  const ACHIEVEMENT_DEFS = [
    { id: "first_book", name: "开卷有益", icon: "📖", description: "读完第一本书", hint: "通过完书验证即可解锁", target: 1, category: "起点" },
    { id: "three_books", name: "小有所成", icon: "📚", description: "累计读完 3 本书", hint: "坚持阅读即可达成", target: 3, category: "累计" },
    { id: "five_books", name: "博览群书", icon: "🏆", description: "累计读完 5 本书", hint: "墨香渐浓", target: 5, category: "累计" },
    { id: "ten_books", name: "书虫达人", icon: "🎖️", description: "累计读完 10 本书", hint: "真正的读书人", target: 10, category: "累计" },
    { id: "all_books", name: "书香门第", icon: "👑", description: "读完馆藏全部 12 本", hint: "典藏尽收", target: 12, category: "终极" },
    { id: "perfect_streak", name: "过目不忘", icon: "🧠", description: "连续 3 次答题全对", hint: "考验真功夫", target: 3, category: "智慧" },
    { id: "day_double", name: "一气呵成", icon: "⚡", description: "同一天读完 2 本书", hint: "效率惊人", target: 2, category: "效率" },
    { id: "night_owl", name: "烛火夜读", icon: "🕯️", description: "晚上 20:00 后完书一本", hint: "夜深正是读书时", target: 1, category: "趣味" },
    { id: "return_promise", name: "信守承诺", icon: "🔄", description: "先读完再归还（按时履约）", hint: "先读后还，言出必行", target: 1, category: "品格" },
    { id: "classic_reader", name: "经典收藏", icon: "💎", description: "读完任一经典文学", hint: "红楼 / 围城 / 小王子…", target: 1, category: "品位" },
  ];

  // ==================== 响应工具 ====================
  const JSON_HEADERS = { "Content-Type": "application/json; charset=utf-8" };
  const ok = (data, status) =>
    new Response(JSON.stringify({ code: 0, msg: "ok", data: data === undefined ? null : data }), {
      status: status || 200,
      headers: JSON_HEADERS,
    });
  const fail = (status, msg) =>
    new Response(JSON.stringify({ code: status, msg, data: null }), {
      status,
      headers: JSON_HEADERS,
    });

  const nextId = (list) => list.reduce((m, x) => Math.max(m, x.id), 0) + 1;
  const stockOf = (id) => { const b = books.find((x) => x.id === id); return b ? b.stock : 0; };
  const activeCounts = () => {
    const map = {};
    borrows.forEach((r) => {
      if (r.returned_at === null) map[r.book_id] = (map[r.book_id] || 0) + 1;
    });
    return map;
  };
  const bookPublic = (b) => ({ ...b, active_borrows: (activeCounts()[b.id] || 0) });

  function paginate(list, page, pageSize) {
    const total = list.length;
    const pages = Math.max(1, Math.ceil(total / pageSize));
    const start = (page - 1) * pageSize;
    return { list: list.slice(start, start + pageSize), total, page, page_size: pageSize, pages };
  }

  function computeAchievements() {
    const comps = [...completions].sort((a, b) => a.id - b.id);
    const uniqueCount = new Set(comps.map((c) => c.book_id)).size;

    let streak = 0;
    let maxStreak = 0;
    comps.forEach((c) => {
      if (c.correct_count === c.total_count) {
        streak += 1;
        maxStreak = Math.max(maxStreak, streak);
      } else {
        streak = 0;
      }
    });

    const dayMap = {};
    comps.forEach((c) => {
      const d = c.completed_at.slice(0, 10);
      dayMap[d] = (dayMap[d] || 0) + 1;
    });
    const maxDay = Object.keys(dayMap).reduce((m, k) => Math.max(m, dayMap[k]), 0);

    const nightOwl = comps.some((c) => Number(c.completed_at.slice(11, 13)) >= 20);
    const classicDone = new Set(comps.filter((c) => CLASSIC_IDS.has(c.book_id)).map((c) => c.book_id));
    const returnPromise = comps.some((c) => {
      const rec = borrows.find((b) => b.book_id === c.book_id && b.borrower === c.borrower && b.returned_at);
      return rec && rec.returned_at >= c.completed_at;
    });
    const lastAt = comps.length ? comps[comps.length - 1].completed_at : null;

    return ACHIEVEMENT_DEFS.map((def) => {
      let progress = 0;
      let unlock = false;
      switch (def.id) {
        case "first_book":
          progress = Math.min(uniqueCount, 1);
          unlock = uniqueCount >= 1;
          break;
        case "three_books":
        case "five_books":
        case "ten_books":
        case "all_books":
          progress = uniqueCount;
          unlock = uniqueCount >= def.target;
          break;
        case "perfect_streak":
          progress = maxStreak;
          unlock = maxStreak >= def.target;
          break;
        case "day_double":
          progress = maxDay;
          unlock = maxDay >= def.target;
          break;
        case "night_owl":
          progress = nightOwl ? 1 : 0;
          unlock = nightOwl;
          break;
        case "return_promise":
          progress = returnPromise ? 1 : 0;
          unlock = returnPromise;
          break;
        case "classic_reader":
          progress = classicDone.size;
          unlock = classicDone.size >= 1;
          break;
      }
      return {
        ...def,
        unlocked: unlock,
        unlocked_at: unlock ? lastAt : null,
        progress: Math.min(progress, def.target),
        target: def.target,
      };
    });
  }

  function borrowCsv(list) {
    const rows = [["记录ID", "图书ID", "图书名称", "借阅人", "借阅时间", "归还时间", "状态"]];
    list.forEach((r) => rows.push([
      r.id, r.book_id, r.book_title, r.borrower, r.borrowed_at,
      r.returned_at || "", r.returned_at ? "已归还" : "未归还",
    ]));
    const csv = "\ufeff" + rows.map((row) => row.map((v) => `"${String(v).replace(/"/g, '""')}"`).join(",")).join("\r\n");
    return new Response(csv, {
      status: 200,
      headers: {
        "Content-Type": "text/csv; charset=utf-8",
        "Content-Disposition": 'attachment; filename="borrow_records.csv"',
      },
    });
  }

  // ==================== fetch 接管 ====================
  const realFetch = window.fetch.bind(window);

  window.fetch = function (input, init) {
    const rawUrl = typeof input === "string" ? input : (input && input.url) || "";
    let url;
    try {
      url = new URL(rawUrl, window.location.href);
    } catch (e) {
      url = new URL(rawUrl, "http://localhost/");
    }
    const path = url.pathname.replace(/\/+$/, "") || "/";
    const method = ((init && init.method) || (input && input.method) || "GET").toUpperCase();
    const query = url.searchParams;

    let body = {};
    if (init && init.body) {
      try { body = JSON.parse(init.body); } catch (e) { body = {}; }
    }

    // 非业务接口（静态资源、字体等）放行
    if (!/^\/(stats|books|borrows|achievements|completions|categories)(\/|$)/.test(path)) {
      return realFetch(input, init);
    }

    const seg = path.split("/").filter(Boolean);

    // ---- 统计 ----
    if (path === "/stats" && method === "GET") {
      return Promise.resolve(ok({
        total_books: books.length,
        borrowed: borrows.filter((r) => r.returned_at === null).length,
        available: books.reduce((s, b) => s + b.stock, 0),
      }));
    }

    // ---- 分类 ----
    if (path === "/categories" && method === "GET") {
      return Promise.resolve(ok([...new Set(books.map((b) => b.category))]));
    }

    // ---- 图书列表 / 新增 ----
    if (path === "/books" && method === "GET") {
      const page = Math.max(1, parseInt(query.get("page"), 10) || 1);
      const pageSize = Math.min(100, Math.max(1, parseInt(query.get("page_size"), 10) || 10));
      const keyword = (query.get("keyword") || "").trim().toLowerCase();
      const category = (query.get("category") || "").trim();

      let list = books.slice();
      if (keyword) list = list.filter((b) => b.title.toLowerCase().includes(keyword));
      if (category) list = list.filter((b) => b.category === category);
      list = list.map(bookPublic);
      return Promise.resolve(ok(paginate(list, page, pageSize)));
    }

    if (path === "/books" && method === "POST") {
      if (!body.title || !body.author || !body.isbn) {
        return Promise.resolve(fail(422, "参数校验失败：书名 / 作者 / ISBN 不能为空"));
      }
      const book = {
        id: nextId(books),
        title: String(body.title),
        author: String(body.author),
        isbn: String(body.isbn),
        stock: Number(body.stock) || 0,
        category: body.category || "未分类",
        cover_url: body.cover_url || null,
        description: body.description || "",
      };
      books.push(book);
      return Promise.resolve(ok(bookPublic(book), 201));
    }

    // ---- 借阅记录（需在 /books/:id 之前判断） ----
    if (path === "/borrows" && method === "GET") {
      const page = Math.max(1, parseInt(query.get("page"), 10) || 1);
      const pageSize = Math.min(100, Math.max(1, parseInt(query.get("page_size"), 10) || 10));
      const borrower = (query.get("borrower") || "").trim();
      const bookKw = (query.get("book") || "").trim().toLowerCase();
      const status = (query.get("status") || "").trim();
      const start = (query.get("start") || "").trim();
      const end = (query.get("end") || "").trim();

      if (status && status !== "active" && status !== "returned") {
        return Promise.resolve(fail(400, "状态筛选仅支持 active（未归还）/ returned（已归还）"));
      }

      let list = borrows.slice();
      if (borrower) list = list.filter((r) => r.borrower === borrower);
      if (bookKw) list = list.filter((r) => r.book_title.toLowerCase().includes(bookKw));
      if (status === "active") list = list.filter((r) => r.returned_at === null);
      if (status === "returned") list = list.filter((r) => r.returned_at !== null);
      if (start) list = list.filter((r) => r.borrowed_at >= start);
      if (end) list = list.filter((r) => r.borrowed_at <= `${end} 23:59:59`);

      list = list.slice().sort((a, b) => b.id - a.id);
      return Promise.resolve(ok(paginate(list, page, pageSize)));
    }

    if (path === "/borrows/export" && method === "GET") {
      let list = borrows.slice();
      const borrower = (query.get("borrower") || "").trim();
      const bookKw = (query.get("book") || "").trim().toLowerCase();
      const status = (query.get("status") || "").trim();
      if (borrower) list = list.filter((r) => r.borrower === borrower);
      if (bookKw) list = list.filter((r) => r.book_title.toLowerCase().includes(bookKw));
      if (status === "active") list = list.filter((r) => r.returned_at === null);
      if (status === "returned") list = list.filter((r) => r.returned_at !== null);
      return Promise.resolve(borrowCsv(list));
    }

    // ---- 完书记录 ----
    if (path === "/completions" && method === "GET") {
      const borrower = (query.get("borrower") || "").trim();
      const list = borrower ? completions.filter((c) => c.borrower === borrower) : completions.slice();
      return Promise.resolve(ok(list));
    }

    // ---- 成就 ----
    if (path === "/achievements" && method === "GET") {
      return Promise.resolve(ok(computeAchievements()));
    }

    // ---- 单本图书相关 ----
    if (seg[0] === "books" && seg[1]) {
      const bookId = Number(seg[1]);
      const book = books.find((b) => b.id === bookId);
      if (!book) return Promise.resolve(fail(404, `图书不存在（id=${bookId}）`));

      // 图书详情
      if (seg.length === 2 && method === "GET") {
        return Promise.resolve(ok(bookPublic(book)));
      }

      // 编辑
      if (seg.length === 2 && method === "PUT") {
        ["title", "author", "isbn", "stock", "category", "cover_url", "description"].forEach((k) => {
          if (body[k] !== undefined && body[k] !== null) book[k] = body[k];
        });
        return Promise.resolve(ok(bookPublic(book)));
      }

      // 删除
      if (seg.length === 2 && method === "DELETE") {
        const active = borrows.some((r) => r.book_id === bookId && r.returned_at === null);
        if (active) return Promise.resolve(fail(400, `《${book.title}》尚有未归还的借阅记录，删除后会导致数据不一致，已禁止`));
        books.splice(books.indexOf(book), 1);
        return Promise.resolve(ok({ id: bookId }));
      }

      // 借阅
      if (seg.length === 3 && seg[2] === "borrow" && method === "POST") {
        const borrower = String(body.borrower || "").trim();
        if (!borrower) return Promise.resolve(fail(422, "参数校验失败：borrower 不能为空"));
        if (book.stock <= 0) return Promise.resolve(fail(400, `《${book.title}》库存不足，无法借阅`));
        const dup = borrows.find((r) => r.book_id === bookId && r.borrower === borrower && r.returned_at === null);
        if (dup) return Promise.resolve(fail(400, `借阅人「${borrower}」的《${book.title}》尚有未归还记录，不能重复借阅`));
        const record = {
          id: nextId(borrows),
          book_id: book.id,
          book_title: book.title,
          borrower,
          borrowed_at: nowStr(),
          returned_at: null,
        };
        book.stock -= 1;
        borrows.push(record);
        return Promise.resolve(ok(record, 201));
      }

      // 归还
      if (seg.length === 3 && seg[2] === "return" && method === "POST") {
        const borrower = (query.get("borrower") || "").trim();
        const rec = borrows.find((r) =>
          r.book_id === bookId && r.returned_at === null && (!borrower || r.borrower === borrower));
        if (!rec) {
          return Promise.resolve(fail(400, borrower
            ? `《${book.title}》没有找到借阅人「${borrower}」的未归还记录，无法归还`
            : `《${book.title}》没有未归还的借阅记录，无法归还`));
        }
        rec.returned_at = nowStr();
        book.stock += 1;
        return Promise.resolve(ok(rec));
      }

      // 问答题（隐藏答案）
      if (seg.length === 3 && seg[2] === "quiz" && method === "GET") {
        const quiz = quizzes.find((q) => q.book_id === bookId);
        if (!quiz) return Promise.resolve(fail(404, "该书暂无问答题库"));
        return Promise.resolve(ok({
          book_id: quiz.book_id,
          questions: quiz.questions.map((q) => ({ question: q.question, options: q.options })),
        }));
      }

      // 提交完书验证
      if (seg.length === 3 && seg[2] === "complete" && method === "POST") {
        const borrower = String(body.borrower || "").trim();
        const answers = Array.isArray(body.answers) ? body.answers : [];
        if (!borrower) return Promise.resolve(fail(422, "参数校验失败：borrower 不能为空"));

        const existing = completions.find((c) => c.book_id === bookId && c.borrower === borrower);
        if (existing) {
          return Promise.resolve(fail(400, `借阅人「${borrower}」已标记完《${book.title}》，不可重复`));
        }
        const quiz = quizzes.find((q) => q.book_id === bookId);
        if (!quiz) return Promise.resolve(fail(400, `《${book.title}》暂无问答题库，暂不支持完书验证`));
        if (answers.length !== quiz.questions.length) {
          return Promise.resolve(fail(400, `答案数量与题目数量不匹配（需要 ${quiz.questions.length} 个）`));
        }

        const correct = quiz.questions.reduce((n, q, i) => n + (answers[i] === q.answer ? 1 : 0), 0);
        const score = correct / quiz.questions.length;
        if (score < 0.6) {
          return Promise.resolve(fail(400,
            `答题正确率不足（${correct}/${quiz.questions.length}），60% 以上才算读完，再接再厉！`));
        }

        const record = {
          id: nextId(completions),
          book_id: book.id,
          book_title: book.title,
          borrower,
          correct_count: correct,
          total_count: quiz.questions.length,
          score: Math.round(score * 1000) / 10,
          completed_at: nowStr(),
        };
        completions.push(record);
        return Promise.resolve(ok(record, 201));
      }
    }

    return Promise.resolve(fail(404, "演示环境未实现该接口"));
  };
})();

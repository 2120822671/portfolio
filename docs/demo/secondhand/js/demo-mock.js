/* 校淘集市 · 静态演示版 mock 层
   接管前端所有业务接口请求，用内存数据模拟 FastAPI 后端；刷新页面即还原。
   统一返回结构与后端一致：{ code, msg, data }，code=0 表示成功。
   任意账号密码均可登录（默认预填 demo / demo123），token 存 localStorage。 */
(function () {
  "use strict";

  const realFetch = window.fetch.bind(window);

  /* ---------------- 基础工具 ---------------- */
  const pad = (n) => String(n).padStart(2, "0");
  const money = (n) => Number(n).toFixed(2);
  const minuteAgo = (mins) => new Date(Date.now() - mins * 60000).toISOString();
  const daysAgo = (days, h = 10, m = 0) => {
    const d = new Date();
    d.setDate(d.getDate() - days);
    d.setHours(h, m, 0, 0);
    return d.toISOString();
  };
  const stamp = (isoStr) => {
    const d = new Date(isoStr);
    return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}`;
  };
  const respond = (payload, status) =>
    new Response(JSON.stringify(payload), {
      status,
      headers: { "Content-Type": "application/json" },
    });
  const ok = (data, msg = "success") => respond({ code: 0, msg, data }, 200);
  const fail = (msg, status = 400) => respond({ code: status, msg, data: null }, status);

  const headerOf = (headers, name) => {
    if (!headers) return "";
    if (typeof headers.get === "function") return headers.get(name) || "";
    const key = Object.keys(headers).find((k) => k.toLowerCase() === name.toLowerCase());
    return key ? String(headers[key]) : "";
  };

  /* ---------------- 静态枚举 ---------------- */
  const CATEGORIES = [
    { id: 1, name: "数码电子" },
    { id: 2, name: "教材书籍" },
    { id: 3, name: "宿舍家居" },
    { id: 4, name: "运动户外" },
    { id: 5, name: "乐器文娱" },
    { id: 6, name: "生活用品" },
  ];
  const CAT_NAME = Object.fromEntries(CATEGORIES.map((c) => [c.id, c.name]));
  const GOODS_STATUS = { 1: "在售", 2: "已售出", 3: "已下架", 4: "已预订", 5: "待审核" };
  const ORDER_STATUS = { 10: "待付款", 20: "已支付", 30: "已完成", 40: "已关闭" };
  const PAY_TEXT = { campus_card: "校园一卡通", wechat: "微信支付", alipay: "支付宝", cash: "线下当面交易" };
  const CHAT_PREVIEW = {
    bargain: "【砍价】", bargain_accept: "【同意砍价】", bargain_reject: "【拒绝砍价】",
    swap: "【换物】", swap_accept: "【同意换物】", swap_reject: "【拒绝换物】",
  };

  /* ---------------- 用户 ---------------- */
  const users = [
    { id: 1, username: "linxiaoyu", nickname: "林小雨", credit_score: 98, status: 1, created_at: daysAgo(60) },
    { id: 2, username: "chenmo", nickname: "陈默", credit_score: 95, status: 1, created_at: daysAgo(45) },
    { id: 3, username: "suqing", nickname: "苏晴", credit_score: 92, status: 1, created_at: daysAgo(30) },
    { id: 4, username: "demo", nickname: "演示同学", credit_score: 90, status: 1, created_at: daysAgo(0, 9) },
  ];
  const DEMO_UID = 4;
  const userById = (id) => users.find((u) => u.id === id);

  /* ---------------- 商品 ---------------- */
  const goods = [
    {
      id: 1, title: "九成新 iPhone 13 128G 蓝色", price: 3299, original_price: 5199,
      category_id: 1, seller_id: 1, stock: 1, status: 1, view_count: 328, like_count: 42,
      cover: "uploads/goods_iphone13_1.jpg",
      images: ["uploads/goods_iphone13_1.jpg", "uploads/goods_iphone13_2.jpg"],
      description: "自用一年半，电池健康 88%，无拆无修，边框有轻微使用痕迹。\n配件齐全，可当面验机。",
      location: "三食堂门口", contact: "微信 xx_phone", created_at: daysAgo(0, 9),
      messages: [
        { id: 1, content: "同学你好，手机还在吗？", nickname: "演示同学", user_id: 4, created_at: stamp(minuteAgo(90)) },
        { id: 2, content: "在的，支持当面验机～", nickname: "林小雨", user_id: 1, created_at: stamp(minuteAgo(80)) },
      ],
    },
    {
      id: 2, title: "联想小新 Pro14 轻薄本 16G+512G", price: 2899, original_price: 4999,
      category_id: 1, seller_id: 2, stock: 1, status: 1, view_count: 256, like_count: 31,
      cover: "uploads/goods_macbook_1.jpg",
      images: ["uploads/goods_macbook_1.jpg", "uploads/goods_macbook_2.jpg"],
      description: "毕业出，一次都没摔过，键盘无油光，续航约 6 小时。原装充电器+内胆包。",
      location: "图书馆东门", contact: "QQ 123456", created_at: daysAgo(1, 15),
      messages: [],
    },
    {
      id: 3, title: "iPad Air 4 64G 附 Apple Pencil", price: 1850, original_price: 3299,
      category_id: 1, seller_id: 3, stock: 1, status: 1, view_count: 198, like_count: 25,
      cover: "uploads/goods/ipad.jpg", images: ["uploads/goods/ipad.jpg"],
      description: "网课/笔记好帮手，屏幕无划痕（一直贴膜带壳），笔和壳一起出。",
      location: "宿舍 6 号楼楼下", contact: "微信 ipad_air", created_at: daysAgo(2, 11),
      messages: [],
    },
    {
      id: 4, title: "高等数学教材（第七版）上下册", price: 25, original_price: 89,
      category_id: 2, seller_id: 1, stock: 3, status: 1, view_count: 120, like_count: 12,
      cover: "uploads/goods/math_book.jpg", images: ["uploads/goods/math_book.jpg"],
      description: "上册有少量笔记（重点标注，学弟学妹会喜欢），下册几乎全新。",
      location: "教三一楼大厅", contact: "", created_at: daysAgo(3, 16),
      messages: [],
    },
    {
      id: 5, title: "考研英语词汇书（乱序版）", price: 18, original_price: 59,
      category_id: 2, seller_id: 2, stock: 1, status: 2, view_count: 88, like_count: 6,
      cover: "uploads/goods/vocab_book.jpg", images: ["uploads/goods/vocab_book.jpg"],
      description: "背了一半，书页干净，附赠自己整理的高频词卡片。",
      location: "教学楼 B 座", contact: "", created_at: daysAgo(5, 9),
      messages: [],
    },
    {
      id: 6, title: "牛津高阶英汉双解词典（第 9 版）", price: 45, original_price: 129,
      category_id: 2, seller_id: 3, stock: 1, status: 1, view_count: 76, like_count: 9,
      cover: "uploads/goods/dictionary.jpg", images: ["uploads/goods/dictionary.jpg"],
      description: "纸质词典，查词手感很好，侧边有轻微翻阅痕迹。",
      location: "外语楼门前", contact: "", created_at: daysAgo(4, 13),
      messages: [],
    },
    {
      id: 7, title: "宿舍落地灯 暖光护眼", price: 39, original_price: 99,
      category_id: 3, seller_id: 1, stock: 1, status: 1, view_count: 143, like_count: 17,
      cover: "uploads/goods/lamp.jpg", images: ["uploads/goods/lamp.jpg", "uploads/goods_lamp_1.jpg"],
      description: "三档调光，暖光不刺眼，宿舍看书很舒服。灯罩无破损。",
      location: "宿舍 3 号楼 502", contact: "微信 lamp_2024", created_at: daysAgo(0, 14),
      messages: [],
    },
    {
      id: 8, title: "迷你小冰箱 45L（宿舍可用）", price: 260, original_price: 599,
      category_id: 3, seller_id: 2, stock: 0, status: 4, view_count: 167, like_count: 22,
      cover: "uploads/goods/fridge.jpg", images: ["uploads/goods/fridge.jpg"],
      description: "静音款，制冷正常，搬家出。需要自己搬走（女生可帮忙叫车）。",
      location: "宿舍 8 号楼 301", contact: "", created_at: daysAgo(1, 18),
      messages: [],
    },
    {
      id: 9, title: "半自动洗衣机 4.5kg", price: 380, original_price: 799,
      category_id: 3, seller_id: 3, stock: 0, status: 4, view_count: 132, like_count: 14,
      cover: "uploads/goods/washer.jpg", images: ["uploads/goods/washer.jpg"],
      description: "毕业清仓，洗得干净，脱水正常，可现场试机。",
      location: "南门快递站旁", contact: "", created_at: daysAgo(6, 10),
      messages: [],
    },
    {
      id: 10, title: "捷安特山地自行车 26 寸", price: 420, original_price: 1099,
      category_id: 4, seller_id: 1, stock: 1, status: 1, view_count: 302, like_count: 38,
      cover: "uploads/goods/bicycle.jpg", images: ["uploads/goods/bicycle.jpg", "uploads/goods_bike_1.jpg"],
      description: "骑了两年，刚换过刹车皮和链条，变速顺畅，送车锁。",
      location: "体育馆停车棚", contact: "电话 138****0000", created_at: daysAgo(0, 11),
      messages: [],
    },
    {
      id: 11, title: "斯伯丁篮球 7 号 室内外通用", price: 55, original_price: 129,
      category_id: 4, seller_id: 2, stock: 2, status: 1, view_count: 95, like_count: 8,
      cover: "uploads/goods/basketball.jpg", images: ["uploads/goods/basketball.jpg"],
      description: "打了几次，气足，手感好，附送打气筒。",
      location: "东区篮球场", contact: "", created_at: daysAgo(3, 17),
      messages: [],
    },
    {
      id: 12, title: "尤尼克斯羽毛球拍一对", price: 90, original_price: 268,
      category_id: 4, seller_id: 3, stock: 1, status: 1, view_count: 61, like_count: 5,
      cover: "uploads/goods/badminton.jpg", images: ["uploads/goods/badminton.jpg"],
      description: "双拍装，送 3 个球和拍包，适合入门。",
      location: "风雨操场", contact: "", created_at: daysAgo(7, 9),
      messages: [],
    },
    {
      id: 13, title: "雅马哈民谣吉他 F310", price: 480, original_price: 899,
      category_id: 5, seller_id: 1, stock: 1, status: 2, view_count: 210, like_count: 28,
      cover: "uploads/goods/guitar.jpg", images: ["uploads/goods/guitar.jpg", "uploads/goods_guitar_1.jpg"],
      description: "陪伴三年的吉他，音色很暖，送琴包、变调夹和拨片。",
      location: "艺术楼 201", contact: "", created_at: daysAgo(8, 12),
      messages: [],
    },
    {
      id: 14, title: "罗技机械键盘 K845 红轴", price: 150, original_price: 349,
      category_id: 1, seller_id: 2, stock: 1, status: 1, view_count: 178, like_count: 19,
      cover: "uploads/goods_keyboard_1.jpg",
      images: ["uploads/goods_keyboard_1.jpg", "uploads/goods_keyboard_2.jpg"],
      description: "红轴安静，键帽无打油，带背光，线材完好。",
      location: "图书馆自习区", contact: "", created_at: daysAgo(2, 20),
      messages: [],
    },
    {
      id: 15, title: "JBL 蓝牙音箱 GO3", price: 120, original_price: 299,
      category_id: 5, seller_id: 3, stock: 1, status: 1, view_count: 84, like_count: 7,
      cover: "uploads/goods_speaker_1.jpg", images: ["uploads/goods_speaker_1.jpg"],
      description: "户外防水小音箱，续航约 5 小时，附充电线。",
      location: "西区草坪", contact: "", created_at: daysAgo(9, 15),
      messages: [],
    },
    {
      id: 16, title: "学士服出租 / 毕业照礼服", price: 30, original_price: 80,
      category_id: 6, seller_id: 4, stock: 1, status: 2, view_count: 65, like_count: 11,
      cover: "uploads/goods/gown.jpg", images: ["uploads/goods/gown.jpg"],
      description: "毕业季出租学士服，含帽子、流苏，已干洗，按天计费。",
      location: "校门口快递柜", contact: "微信 gown_2024", created_at: daysAgo(6, 9),
      messages: [
        { id: 3, content: "已拍下，明天上午方便取吗？", nickname: "陈默", user_id: 2, created_at: stamp(daysAgo(3, 10)) },
      ],
    },
    {
      id: 17, title: "笔记本电脑支架 铝合金可折叠", price: 35, original_price: 79,
      category_id: 1, seller_id: 4, stock: 1, status: 1, view_count: 52, like_count: 4,
      cover: "uploads/goods/laptop_stand.jpg", images: ["uploads/goods/laptop_stand.jpg"],
      description: "全新未拆封，多买了一台，六档高度可调，散热好。",
      location: "宿舍 6 号楼 101", contact: "微信 demo_stand", created_at: daysAgo(1, 20),
      messages: [
        { id: 4, content: "这个支架能便宜点吗？", nickname: "陈默", user_id: 2, created_at: stamp(minuteAgo(50)) },
        { id: 5, content: "全新未拆，35 已经最低啦～", nickname: "演示同学", user_id: 4, created_at: stamp(minuteAgo(45)) },
      ],
    },
    {
      id: 18, title: "旧台灯（可当备用灯）", price: 15, original_price: 45,
      category_id: 3, seller_id: 4, stock: 1, status: 3, view_count: 40, like_count: 2,
      cover: "uploads/goods/lamp.jpg", images: ["uploads/goods/lamp.jpg"],
      description: "用了一学期，灯还能亮，灯罩有点旧，便宜出。",
      location: "宿舍 6 号楼 101", contact: "", created_at: daysAgo(10, 21),
      messages: [],
    },
    {
      id: 19, title: "全新蓝牙耳机（未拆封）", price: 199, original_price: 399,
      category_id: 1, seller_id: 2, stock: 1, status: 5, view_count: 3, like_count: 0,
      cover: "uploads/goods_keyboard_2.jpg", images: ["uploads/goods_keyboard_2.jpg"],
      description: "奖品，全新未拆封，降噪版，待管理员审核后上架。",
      location: "宿舍 8 号楼 301", contact: "", created_at: daysAgo(0, 8),
      messages: [],
    },
  ];
  const goodsById = (id) => goods.find((g) => g.id === id);

  /* 点赞记录（用于通知与是否已点赞） */
  const likeLog = [
    { goods_id: 17, user_id: 2, created_at: minuteAgo(120) },
    { goods_id: 16, user_id: 3, created_at: daysAgo(3, 16) },
    { goods_id: 1, user_id: 4, created_at: minuteAgo(300) },
  ];
  const likedBy = (goodsId, uid) => likeLog.some((l) => l.goods_id === goodsId && l.user_id === uid);

  /* ---------------- 购物车 ---------------- */
  let cartSeq = 1;
  const cart = [
    { id: cartSeq++, user_id: DEMO_UID, goods_id: 3, quantity: 1 },
    { id: cartSeq++, user_id: DEMO_UID, goods_id: 11, quantity: 1 },
    { id: cartSeq++, user_id: DEMO_UID, goods_id: 18, quantity: 1 },
  ];

  /* ---------------- 订单 ---------------- */
  let orderSeq = 1;
  const orderNo = () => {
    const d = new Date();
    return `SO${d.getFullYear()}${pad(d.getMonth() + 1)}${pad(d.getDate())}${pad(d.getHours())}${pad(d.getMinutes())}${pad(d.getSeconds())}${Math.floor(1000 + Math.random() * 9000)}`;
  };
  const orders = [
    { id: orderSeq++, order_no: "SO202611180930124821", goods_id: 16, buyer_id: 2, seller_id: 4, amount: 30, pay_method: "wechat", status: 20, close_type: null, closed_at: null, pay_deadline: daysAgo(5, 10), created_at: daysAgo(6, 9) },
    { id: orderSeq++, order_no: "SO202611211430446712", goods_id: 8, buyer_id: 4, seller_id: 2, amount: 260, pay_method: null, status: 10, close_type: null, closed_at: null, pay_deadline: new Date(Date.now() + 25 * 60000).toISOString(), created_at: minuteAgo(5) },
    { id: orderSeq++, order_no: "SO202611150900337129", goods_id: 13, buyer_id: 4, seller_id: 1, amount: 480, pay_method: null, status: 40, close_type: "user", closed_at: daysAgo(7, 12), pay_deadline: daysAgo(7, 9), created_at: daysAgo(8, 12) },
    { id: orderSeq++, order_no: "SO202611190800228834", goods_id: 5, buyer_id: 4, seller_id: 2, amount: 18, pay_method: "alipay", status: 20, close_type: null, closed_at: null, pay_deadline: daysAgo(4, 8), created_at: daysAgo(5, 9) },
    { id: orderSeq++, order_no: "SO202611211015009921", goods_id: 9, buyer_id: 4, seller_id: 3, amount: 380, pay_method: null, status: 10, close_type: null, closed_at: null, pay_deadline: minuteAgo(10), created_at: minuteAgo(40) },
  ];

  /* ---------------- 消息 / 通知 / 举报 ---------------- */
  let chatSeq = 1;
  const chats = [
    { id: chatSeq++, goods_id: 17, sender_id: 2, receiver_id: 4, msg_type: "bargain", content: "我出 ￥30.00，可以吗？", extra: { price: "30.00" }, read: false, created_at: stamp(minuteAgo(50)) },
    { id: chatSeq++, goods_id: 17, sender_id: 4, receiver_id: 2, msg_type: "text", content: "这个是全新未拆的，35 已经最低啦～", extra: null, read: true, created_at: stamp(minuteAgo(45)) },
    { id: chatSeq++, goods_id: 1, sender_id: 4, receiver_id: 1, msg_type: "text", content: "同学你好，手机还在吗？", extra: null, read: true, created_at: stamp(minuteAgo(90)) },
    { id: chatSeq++, goods_id: 1, sender_id: 1, receiver_id: 4, msg_type: "text", content: "在的，电池健康 88%，支持当面验机", extra: null, read: true, created_at: stamp(minuteAgo(85)) },
    { id: chatSeq++, goods_id: 1, sender_id: 4, receiver_id: 1, msg_type: "text", content: "好的，我今天下午去取", extra: null, read: true, created_at: stamp(minuteAgo(80)) },
  ];

  let reportSeq = 1;
  const reports = [
    { id: reportSeq++, user_id: 2, target_type: "goods", target_id: 9, reason: "描述与实际不符", handle_action: null, created_at: daysAgo(2, 11) },
    { id: reportSeq++, user_id: 3, target_type: "user", target_id: 2, reason: "恶意砍价骚扰", handle_action: "ignored", created_at: daysAgo(4, 15) },
  ];

  /* ---------------- 序列化 ---------------- */
  const brief = (g) => ({
    id: g.id, title: g.title, price: money(g.price),
    original_price: g.original_price ? money(g.original_price) : null,
    discount: g.original_price && g.original_price > 0 && g.price < g.original_price
      ? Math.round((g.price / g.original_price) * 100) / 10 : null,
    category_id: g.category_id, stock: g.stock, status: g.status,
    status_text: GOODS_STATUS[g.status] || "未知",
    view_count: g.view_count, like_count: g.like_count,
    cover: g.cover || null, seller_id: g.seller_id, created_at: g.created_at,
  });

  const orderBrief = (o) => ({
    id: o.id, order_no: o.order_no, goods_id: o.goods_id,
    buyer_id: o.buyer_id, seller_id: o.seller_id, amount: money(o.amount),
    pay_method: o.pay_method || null,
    pay_method_text: o.pay_method ? PAY_TEXT[o.pay_method] : "未选择",
    status: o.status, status_text: ORDER_STATUS[o.status] || "未知",
    pay_deadline: o.pay_deadline || null, close_type: o.close_type || null,
    closed_at: o.closed_at || null, created_at: o.created_at,
  });

  const goodsQuery = (qs) => {
    let list = goods.slice();
    const q = qs.get("q");
    if (q) list = list.filter((g) => g.title.includes(q));
    if (qs.get("category_id")) list = list.filter((g) => g.category_id === Number(qs.get("category_id")));
    if (qs.get("min_price")) list = list.filter((g) => g.price >= Number(qs.get("min_price")));
    if (qs.get("max_price")) list = list.filter((g) => g.price <= Number(qs.get("max_price")));
    if (qs.get("seller_id")) list = list.filter((g) => g.seller_id === Number(qs.get("seller_id")));
    if (qs.get("status")) list = list.filter((g) => g.status === Number(qs.get("status")));

    const sort = qs.get("sort") || "newest";
    if (sort === "price_asc") list.sort((a, b) => a.price - b.price);
    else if (sort === "price_desc") list.sort((a, b) => b.price - a.price);
    else if (sort === "views") list.sort((a, b) => b.view_count - a.view_count);
    else list.sort((a, b) => b.id - a.id);

    const page = Math.max(1, Number(qs.get("page")) || 1);
    const size = Math.max(1, Number(qs.get("page_size")) || 12);
    return { total: list.length, page, page_size: size, items: list.slice((page - 1) * size, page * size).map(brief) };
  };

  const cartItem = (c) => {
    const g = goodsById(c.goods_id);
    if (!g) return null;
    const available = g.status === 1 && g.stock > 0;
    return {
      id: c.id, goods_id: g.id, title: g.title, price: money(g.price), cover: g.cover,
      quantity: c.quantity, stock: g.stock,
      goods_status: g.status, goods_status_text: GOODS_STATUS[g.status] || "未知",
      available, reason: available ? "" : (g.status !== 1 ? (GOODS_STATUS[g.status] || "不可售") : "库存不足"),
      subtotal: money(g.price * c.quantity),
    };
  };

  const chatItem = (m, uid, answered) => ({
    id: m.id, goods_id: m.goods_id, sender_id: m.sender_id, receiver_id: m.receiver_id,
    msg_type: m.msg_type, content: m.content, extra: m.extra || null,
    mine: m.sender_id === uid, replied: answered.has(m.id), created_at: m.created_at,
  });

  /* ---------------- 演示态持久化（同一标签页内跨页面保持，关闭标签即还原） ---------------- */
  const STORE_KEY = "cs_demo_state_v1";
  const restore = () => {
    try {
      const raw = sessionStorage.getItem(STORE_KEY);
      if (!raw) return;
      const s = JSON.parse(raw);
      [["users", users], ["goods", goods], ["cart", cart], ["orders", orders],
       ["chats", chats], ["reports", reports], ["likeLog", likeLog]].forEach(([k, arr]) => {
        if (!Array.isArray(s[k])) return;
        arr.length = 0;
        s[k].forEach((v) => arr.push(v));
      });
      cartSeq = Math.max(0, ...cart.map((c) => c.id)) + 1;
      orderSeq = Math.max(0, ...orders.map((o) => o.id)) + 1;
      chatSeq = Math.max(0, ...chats.map((c) => c.id)) + 1;
      reportSeq = Math.max(0, ...reports.map((r) => r.id)) + 1;
    } catch (e) { /* 忽略损坏的演示态 */ }
  };
  const persist = () => {
    try {
      sessionStorage.setItem(STORE_KEY, JSON.stringify({ users, goods, cart, orders, chats, reports, likeLog }));
    } catch (e) { /* 忽略隐私模式 / 配额异常 */ }
  };
  restore();

  /* ---------------- 请求拦截 ---------------- */
  const API_RE = /^(auth|goods|stats|categories|upload|cart|orders|chat|report|products)(\/|$)/;
  const ADMIN_RE = /^api\/v1\/admin(\/|$)/;

  const normalize = (raw) => {
    let p = raw.split("?")[0].split("#")[0];
    p = p.replace(/^[./\\]+/, "").replace(/\/+$/, "");
    p = p.replace(/^portfolio\/demo\/secondhand\//, "").replace(/^secondhand\//, "");
    return p;
  };

  function handleApi(input, init) {
    const raw = typeof input === "string" ? input : (input && input.url) || "";
    const path = normalize(raw);
    if (!API_RE.test(path) && !ADMIN_RE.test(path)) return realFetch(input, init);

    const method = ((init && init.method) || "GET").toUpperCase();
    const headers = (init && init.headers) || {};
    const uidHeader = headerOf(headers, "X-User-Id");
    const uid = uidHeader ? Number(uidHeader) : null;
    const qs = new URLSearchParams(raw.includes("?") ? raw.split("?")[1].split("#")[0] : "");

    let body = {};
    if (init && init.body && typeof init.body === "string") {
      try { body = JSON.parse(init.body); } catch (e) { body = {}; }
    }

    /* ---- 账号（免登录） ---- */
    if (path === "auth/register" && method === "POST") {
      const name = (body.username || "").trim();
      if (!name) return fail("用户名不能为空", 422);
      let u = users.find((x) => x.username === name);
      if (u) return fail("用户名已存在", 409);
      u = { id: 100 + users.length, username: name, nickname: body.nickname || name, credit_score: 100, status: 1, created_at: new Date().toISOString() };
      users.push(u);
      return ok({ id: u.id, username: u.username, nickname: u.nickname, credit_score: u.credit_score }, "注册成功");
    }
    if (path === "auth/login" && method === "POST") {
      const name = (body.username || "").trim() || "demo";
      let u = users.find((x) => x.username === name);
      if (!name || name === "demo") u = userById(DEMO_UID);
      if (!u) {
        u = userById(DEMO_UID);
        u.username = name;
        u.nickname = name === "demo" ? "演示同学" : name;
      }
      return ok({
        token: "demo-token",
        user: { id: u.id, username: u.username, nickname: u.nickname, credit_score: u.credit_score },
      }, "登录成功");
    }
    if (path === "auth/me") {
      const u = userById(uid || DEMO_UID);
      return ok({ id: u.id, username: u.username, nickname: u.nickname, credit_score: u.credit_score });
    }

    /* ---- 免登录的读取接口 ---- */
    const isPublic = path === "stats" || path === "categories" || path === "goods" || /^goods\/\d+$/.test(path);
    if (!uid && !isPublic) return fail("请先登录", 401);

    /* ---- 分类 / 统计 ---- */
    if (path === "categories" && method === "GET") return ok({ items: CATEGORIES });
    if (path === "stats" && method === "GET") {
      const today = new Date();
      today.setHours(0, 0, 0, 0);
      return ok({
        total: goods.length,
        on_sale: goods.filter((g) => g.status === 1).length,
        sold: goods.filter((g) => g.status === 2).length,
        today_new: goods.filter((g) => new Date(g.created_at) >= today).length,
      });
    }

    /* ---- 消息通知（须在商品路由之前判断） ---- */
    if (path === "goods/notifications" && method === "GET") {
      const mine = goods.filter((g) => g.seller_id === uid);
      const items = [];
      mine.forEach((g) => {
        (g.messages || []).forEach((m) => {
          if (m.user_id === uid) return;
          items.push({
            type: "留言", icon: "💬", from: m.nickname, goods_id: g.id,
            goods_title: g.title, text: m.content, created_at: m.created_at,
          });
        });
      });
      likeLog.filter((l) => mine.some((g) => g.id === l.goods_id)).forEach((l) => {
        const g = goodsById(l.goods_id);
        const u = userById(l.user_id);
        if (!g || !u) return;
        items.push({
          type: "点赞", icon: "❤", from: u.nickname, goods_id: g.id,
          goods_title: g.title, text: "赞了你的商品", created_at: l.created_at,
        });
      });
      items.sort((a, b) => String(b.created_at).localeCompare(String(a.created_at)));
      return ok({ unread: items.length, items });
    }

    /* ---- 商品 ---- */
    if (path === "goods" && method === "GET") return ok(goodsQuery(qs));
    if (path === "goods" && method === "POST") {
      const title = (body.title || "").trim();
      const desc = (body.description || "").trim();
      if (!title) return fail("请输入商品名称", 422);
      if (!(Number(body.price) > 0)) return fail("售价必须大于 0", 422);
      if (!desc) return fail("请填写商品描述", 422);
      const images = (body.images || []).filter(Boolean);
      const g = {
        id: Math.max(...goods.map((x) => x.id)) + 1,
        title, price: Number(body.price),
        original_price: body.original_price ? Number(body.original_price) : null,
        category_id: Number(body.category_id) || 1,
        seller_id: Number(body.seller_id) || uid,
        description: desc,
        location: body.location || "",
        contact: body.contact || "",
        stock: Number(body.stock) || 0,
        status: 1,
        view_count: 0, like_count: 0,
        cover: images[0] || null,
        images,
        created_at: new Date().toISOString(),
        messages: [],
      };
      goods.push(g);
      return ok(brief(g), "发布成功");
    }
    let m = path.match(/^goods\/(\d+)$/);
    if (m && method === "GET") {
      const g = goodsById(Number(m[1]));
      if (!g) return fail("商品不存在", 404);
      g.view_count += 1;
      return ok({
        ...brief(g),
        description: g.description,
        location: g.location,
        contact: g.contact,
        category_name: CAT_NAME[g.category_id] || null,
        liked: !!uid && likedBy(g.id, uid),
        images: g.images || [],
        seller: (() => {
          const s = userById(g.seller_id) || { nickname: "用户", credit_score: 100 };
          return { id: g.seller_id, nickname: s.nickname, credit_score: s.credit_score };
        })(),
        messages: (g.messages || []).slice().sort((a, b) => b.id - a.id).map((x) => ({
          id: x.id, content: x.content, nickname: x.nickname, created_at: x.created_at,
        })),
      });
    }
    m = path.match(/^goods\/(\d+)\/like$/);
    if (m) {
      const g = goodsById(Number(m[1]));
      if (!g) return fail("商品不存在", 404);
      if (method === "POST") {
        if (likedBy(g.id, uid)) return fail("已经点过赞了", 400);
        likeLog.push({ goods_id: g.id, user_id: uid, created_at: new Date().toISOString() });
        g.like_count += 1;
        return ok({ like_count: g.like_count, liked: true }, "点赞成功");
      }
      if (method === "DELETE") {
        const idx = likeLog.findIndex((l) => l.goods_id === g.id && l.user_id === uid);
        if (idx < 0) return fail("尚未点赞", 400);
        likeLog.splice(idx, 1);
        g.like_count = Math.max(0, g.like_count - 1);
        return ok({ like_count: g.like_count, liked: false }, "已取消点赞");
      }
    }
    m = path.match(/^goods\/(\d+)\/status$/);
    if (m && method === "POST") {
      const g = goodsById(Number(m[1]));
      if (!g) return fail("商品不存在", 404);
      if (g.seller_id !== uid) return fail("只能操作自己发布的商品", 403);
      if (body.action === "off") {
        if (g.status !== 1) return fail("仅在售商品可下架", 400);
        g.status = 3;
      } else if (body.action === "on") {
        if (g.status !== 3) return fail("仅已下架商品可重新上架", 400);
        g.status = 1;
      } else if (body.action === "sold") {
        if (g.status !== 1) return fail("仅在售商品可标记已售", 400);
        g.status = 2;
      } else {
        return fail("不支持的操作", 400);
      }
      return ok({ status: g.status, status_text: GOODS_STATUS[g.status] }, "状态已更新");
    }
    m = path.match(/^goods\/(\d+)\/messages$/);
    if (m && method === "POST") {
      const g = goodsById(Number(m[1]));
      if (!g) return fail("商品不存在", 404);
      const content = (body.content || "").trim();
      if (!content) return fail("留言内容不能为空", 422);
      const u = userById(uid) || { nickname: "演示同学" };
      const item = {
        id: Math.max(0, ...(g.messages || []).map((x) => x.id)) + 1,
        content, nickname: u.nickname, user_id: uid, created_at: stamp(new Date()),
      };
      (g.messages = g.messages || []).push(item);
      return ok({ id: item.id, nickname: item.nickname, content, created_at: item.created_at }, "留言成功");
    }
    m = path.match(/^goods\/(\d+)$/);
    if (m && method === "DELETE") {
      const idx = goods.findIndex((g) => g.id === Number(m[1]));
      if (idx < 0) return fail("商品不存在", 404);
      if (goods[idx].seller_id !== uid) return fail("只能删除自己发布的商品", 403);
      goods.splice(idx, 1);
      return ok(null, "商品已删除");
    }

    /* ---- 上传 ---- */
    if (path === "upload" && method === "POST") {
      // 静态演示版无法真正落盘：回传一张已复制的示例图，保证发布后详情页有图
      const sample = ["uploads/goods/lamp.jpg", "uploads/goods/math_book.jpg", "uploads/goods/ipad.jpg"];
      return ok([sample[Math.floor(Math.random() * sample.length)]], "上传成功");
    }

    /* ---- 购物车 ---- */
    if (path === "cart" && method === "GET") {
      const items = cart.filter((c) => c.user_id === uid).map(cartItem).filter(Boolean);
      const valid = items.filter((i) => i.available);
      return ok({
        items,
        count: items.length,
        valid_count: valid.length,
        amount: money(valid.reduce((s, i) => s + Number(i.subtotal), 0)),
      });
    }
    if (path === "cart" && method === "POST") {
      const g = goodsById(Number(body.goods_id));
      if (!g) return fail("商品不存在", 404);
      if (g.seller_id === uid) return fail("不能把自己发布的商品加入购物车", 400);
      if (g.status !== 1) return fail(`商品${GOODS_STATUS[g.status] || "不可售"}，无法加入购物车`, 409);
      if (g.stock <= 0) return fail("商品库存不足", 409);
      const qty = Math.max(1, Number(body.quantity) || 1);
      const exists = cart.find((c) => c.user_id === uid && c.goods_id === g.id);
      if (exists) exists.quantity = Math.min(g.stock, exists.quantity + qty);
      else cart.push({ id: cartSeq++, user_id: uid, goods_id: g.id, quantity: Math.min(g.stock, qty) });
      return ok({ count: cart.filter((c) => c.user_id === uid).length }, "已加入购物车");
    }
    if (path === "cart" && method === "DELETE") {
      for (let i = cart.length - 1; i >= 0; i--) if (cart[i].user_id === uid) cart.splice(i, 1);
      return ok({ count: 0 }, "购物车已清空");
    }
    m = path.match(/^cart\/(\d+)$/);
    if (m) {
      const item = cart.find((c) => c.id === Number(m[1]) && c.user_id === uid);
      if (!item) return fail("购物车条目不存在", 404);
      if (method === "PATCH") {
        item.quantity = Math.max(1, Number(body.quantity) || 1);
        return ok({ id: item.id, quantity: item.quantity }, "已更新");
      }
      if (method === "DELETE") {
        cart.splice(cart.indexOf(item), 1);
        return ok({ id: item.id }, "已移出购物车");
      }
    }

    /* ---- 订单 ---- */
    if (path === "orders" && method === "GET") {
      const role = qs.get("role") === "seller" ? "seller" : "buyer";
      let list = orders.filter((o) => (role === "buyer" ? o.buyer_id : o.seller_id) === uid);
      if (qs.get("status")) list = list.filter((o) => o.status === Number(qs.get("status")));
      list = list.slice().sort((a, b) => b.id - a.id);
      const now = Date.now();
      const items = list.map((o) => {
        const g = goodsById(o.goods_id) || {};
        const buyer = userById(o.buyer_id) || {};
        const seller = userById(o.seller_id) || {};
        const left = o.status === 10 && o.pay_deadline
          ? Math.max(0, Math.floor((new Date(o.pay_deadline).getTime() - now) / 1000)) : 0;
        return {
          ...orderBrief(o),
          goods_title: g.title || "商品已删除", goods_cover: g.cover || null,
          goods_status: g.status || 0, goods_status_text: GOODS_STATUS[g.status] || "未知",
          buyer_nickname: buyer.nickname || "?", seller_nickname: seller.nickname || "?",
          pay_left_seconds: left, can_pay: o.status === 10 && left > 0, can_cancel: o.status === 10,
        };
      });
      return ok({ total: items.length, page: 1, page_size: 50, role, items });
    }
    if (path === "orders" && method === "POST") {
      const g = goodsById(Number(body.goods_id));
      if (!g) return fail("商品不存在", 404);
      if (g.seller_id === uid) return fail("不能购买自己发布的商品", 400);
      if (g.status !== 1 || g.stock <= 0) return fail("商品已被预订、已售出或已下架，无法下单", 409);
      g.status = 4;
      g.stock -= 1;
      const o = {
        id: orderSeq++, order_no: orderNo(), goods_id: g.id,
        buyer_id: uid, seller_id: g.seller_id, amount: g.price,
        pay_method: null, status: 10, close_type: null, closed_at: null,
        pay_deadline: new Date(Date.now() + 30 * 60000).toISOString(),
        created_at: new Date().toISOString(),
      };
      orders.push(o);
      return ok(orderBrief(o), "下单成功");
    }
    if (path === "orders/batch" && method === "POST") {
      const ids = [...new Set((body.goods_ids || []).map(Number))];
      if (!ids.length) return fail("请选择要结算的商品", 422);
      const methodName = PAY_TEXT[body.pay_method] ? body.pay_method : "campus_card";
      const created = [];
      let total = 0;
      for (const id of ids) {
        const g = goodsById(id);
        if (!g) return fail(`商品不存在：${id}`, 404);
        if (g.seller_id === uid) return fail("不能购买自己发布的商品", 400);
        if (g.status !== 1 || g.stock <= 0) return fail(`《${g.title}》已被预订、已售出或已下架，请刷新购物车`, 409);
        g.status = 2;
        g.stock -= 1;
        total += g.price;
        const o = {
          id: orderSeq++, order_no: orderNo(), goods_id: id,
          buyer_id: uid, seller_id: g.seller_id, amount: g.price,
          pay_method: methodName, status: 20, close_type: null, closed_at: null,
          pay_deadline: new Date(Date.now() + 30 * 60000).toISOString(),
          created_at: new Date().toISOString(),
        };
        orders.push(o);
        created.push(orderBrief(o));
      }
      for (let i = cart.length - 1; i >= 0; i--) {
        if (cart[i].user_id === uid && ids.includes(cart[i].goods_id)) cart.splice(i, 1);
      }
      return ok({
        orders: created, total_amount: money(total),
        pay_method: methodName, pay_method_text: PAY_TEXT[methodName],
      }, `支付成功，共 ${created.length} 笔订单`);
    }
    m = path.match(/^orders\/(\d+)\/pay$/);
    if (m && method === "POST") {
      const o = orders.find((x) => x.id === Number(m[1]));
      if (!o) return fail("订单不存在", 404);
      if (o.status !== 10) return fail("订单已关闭或已支付，无法支付", 409);
      if (o.pay_deadline && new Date(o.pay_deadline).getTime() < Date.now()) {
        return fail("订单已超过付款截止时间，无法支付", 409);
      }
      o.status = 20;
      o.pay_method = PAY_TEXT[body.pay_method] ? body.pay_method : "campus_card";
      const g = goodsById(o.goods_id);
      if (g && g.status === 4) g.status = 2;
      return ok(orderBrief(o), "支付成功");
    }
    m = path.match(/^orders\/(\d+)\/cancel$/);
    if (m && method === "POST") {
      const o = orders.find((x) => x.id === Number(m[1]));
      if (!o) return fail("订单不存在", 404);
      if (o.status !== 10) return fail("订单已关闭或已支付，无法取消", 409);
      o.status = 40;
      o.close_type = "user";
      o.closed_at = new Date().toISOString();
      const g = goodsById(o.goods_id);
      if (g && g.status === 4) { g.status = 1; g.stock += 1; }
      return ok(orderBrief(o), "订单已取消");
    }
    m = path.match(/^orders\/(\d+)$/);
    if (m && method === "GET") {
      const o = orders.find((x) => x.id === Number(m[1]));
      if (!o) return fail("订单不存在", 404);
      return ok({ ...orderBrief(o), logs: [] });
    }

    /* ---- 聊天 ---- */
    if (path === "chat/unread" && method === "GET") {
      return ok({ unread: chats.filter((c) => c.receiver_id === uid && !c.read).length });
    }
    if (path === "chat/conversations" && method === "GET") {
      const map = new Map();
      chats.filter((c) => c.sender_id === uid || c.receiver_id === uid)
        .sort((a, b) => b.id - a.id)
        .forEach((c) => {
          const other = c.sender_id === uid ? c.receiver_id : c.sender_id;
          const key = `${c.goods_id}:${other}`;
          if (!map.has(key)) map.set(key, { goods_id: c.goods_id, other_id: other, last: c, unread: 0 });
          if (c.receiver_id === uid && !c.read) map.get(key).unread += 1;
        });
      const items = [...map.values()].map((conv) => {
        const g = goodsById(conv.goods_id) || {};
        const other = userById(conv.other_id) || {};
        return {
          goods_id: conv.goods_id, goods_title: g.title || "商品已删除",
          goods_cover: g.cover || null, goods_status: g.status || 0,
          other_id: conv.other_id, other_nickname: other.nickname || "用户",
          last_content: (CHAT_PREVIEW[conv.last.msg_type] || "") + conv.last.content,
          last_at: conv.last.created_at, unread: conv.unread,
        };
      }).sort((a, b) => String(b.last_at).localeCompare(String(a.last_at)));
      return ok({ items, unread: items.reduce((s, i) => s + i.unread, 0) });
    }
    if (path === "chat/messages" && method === "GET") {
      const goodsId = Number(qs.get("goods_id"));
      const otherId = Number(qs.get("other_id"));
      const g = goodsById(goodsId);
      if (!g) return fail("商品不存在", 404);
      const other = userById(otherId);
      if (!other) return fail("对方用户不存在", 404);
      const list = chats.filter((c) => c.goods_id === goodsId
        && (c.sender_id === uid || c.receiver_id === uid)
        && (c.sender_id === otherId || c.receiver_id === otherId));
      const answered = new Set();
      list.forEach((c) => { if (c.extra && typeof c.extra.ref === "number") answered.add(c.extra.ref); });
      const items = list.slice().sort((a, b) => a.id - b.id).map((c) => chatItem(c, uid, answered));
      list.forEach((c) => { if (c.receiver_id === uid) c.read = true; });
      return ok({
        goods: {
          id: g.id, title: g.title, price: money(g.price), cover: g.cover,
          status: g.status, seller_id: g.seller_id,
        },
        other: { id: other.id, nickname: other.nickname, credit_score: other.credit_score },
        items,
      });
    }
    if (path === "chat/messages" && method === "POST") {
      const goodsId = Number(body.goods_id);
      const toId = Number(body.to_user_id);
      const g = goodsById(goodsId);
      if (!g) return fail("商品不存在", 404);
      if (toId === uid) return fail("不能给自己发消息", 400);
      if (!userById(toId)) return fail("对方用户不存在", 404);
      if (g.seller_id !== uid && g.seller_id !== toId) return fail("只能在买家与卖家之间聊天", 403);
      const type = body.msg_type || "text";
      if (type === "bargain_accept") {
        if (g.seller_id !== uid) return fail("只有卖家可以同意砍价", 403);
        const price = Number((body.extra || {}).price);
        if (price > 0) g.price = price;
      }
      const msg = {
        id: chatSeq++, goods_id: goodsId, sender_id: uid, receiver_id: toId,
        msg_type: type, content: body.content || "", extra: body.extra || null,
        read: false, created_at: stamp(new Date()),
      };
      chats.push(msg);
      return ok(chatItem(msg, uid, new Set()), "已发送");
    }

    /* ---- 举报 ---- */
    if (path === "report" && method === "POST") {
      if (!["goods", "user", "message"].includes(body.target_type)) {
        return fail("不支持的举报类型，仅允许 goods/user/message", 400);
      }
      const r = {
        id: reportSeq++, user_id: uid, target_type: body.target_type,
        target_id: Number(body.target_id) || 0, reason: body.reason || "",
        handle_action: null, created_at: new Date().toISOString(),
      };
      reports.push(r);
      return ok({ id: r.id }, "举报成功");
    }

    /* ---- 收藏补偿（后端补偿接口，前端未调用，做兼容） ---- */
    if (path === "products/favorite-sync" && method === "POST") {
      return ok({ scope: "all", scanned_products: goods.length, updated_products: 0, total_favorites: 0, orphan_favorites: 0 }, "收藏统计同步完成");
    }

    /* ---- 管理后台 ---- */
    if (ADMIN_RE.test(path)) {
      const sub = path.replace(/^api\/v1\/admin\/?/, "");
      if (sub === "dashboard" && method === "GET") {
        const today = new Date();
        today.setHours(0, 0, 0, 0);
        return ok({
          today_new_users: users.filter((u) => new Date(u.created_at) >= today).length,
          today_new_goods: goods.filter((g) => new Date(g.created_at) >= today).length,
          today_orders: orders.filter((o) => new Date(o.created_at) >= today).length,
          pending_goods: goods.filter((g) => g.status === 5).length,
        }, "统计看板获取成功");
      }
      if (sub === "users" && method === "GET") {
        return ok({
          total: users.length, page: 1, page_size: 50,
          items: users.map((u) => ({
            id: u.id, username: u.username, nickname: u.nickname,
            credit_score: u.credit_score, status: u.status, created_at: u.created_at,
          })),
        });
      }
      m = sub.match(/^users\/(\d+)\/status$/);
      if (m && method === "POST") {
        const u = userById(Number(m[1]));
        if (!u) return fail("用户不存在", 404);
        u.status = Number(body.status) === 1 ? 1 : 0;
        return ok({ id: u.id, status: u.status }, u.status === 1 ? "账号已解封" : "账号已冻结");
      }
      if (sub === "goods/pending" && method === "GET") {
        const list = goods.filter((g) => g.status === 5);
        return ok({
          total: list.length, page: 1, page_size: 50,
          items: list.map((g) => ({
            id: g.id, title: g.title, price: g.price, seller_id: g.seller_id,
            status: g.status, created_at: g.created_at,
          })),
        });
      }
      m = sub.match(/^goods\/(\d+)\/audit$/);
      if (m && method === "POST") {
        const g = goodsById(Number(m[1]));
        if (!g) return fail("商品不存在", 404);
        if (g.status !== 5) return fail("该商品不处于待审核状态", 409);
        g.status = body.action === "approve" ? 1 : 3;
        return ok({ id: g.id, status: g.status }, body.action === "approve" ? "审核通过，商品已上架" : "已驳回，商品已下架");
      }
      if (sub === "reports" && method === "GET") {
        const handled = qs.get("handled");
        let list = reports.slice();
        if (handled === "false") list = list.filter((r) => !r.handle_action);
        if (handled === "true") list = list.filter((r) => !!r.handle_action);
        return ok({
          total: list.length, page: 1, page_size: 50,
          items: list.map((r) => ({
            id: r.id, user_id: r.user_id, target_type: r.target_type,
            target_id: r.target_id, reason: r.reason,
            handle_action: r.handle_action, created_at: r.created_at,
          })),
        });
      }
      m = sub.match(/^reports\/(\d+)\/handle$/);
      if (m && method === "POST") {
        const r = reports.find((x) => x.id === Number(m[1]));
        if (!r) return fail("举报不存在", 404);
        r.handle_action = body.action === "ignored" ? "ignored" : "processed";
        return ok({ id: r.id, action: r.handle_action }, "举报已处理");
      }
      if (sub === "orders" && method === "GET") {
        let list = orders.slice();
        if (qs.get("status")) list = list.filter((o) => o.status === Number(qs.get("status")));
        list.sort((a, b) => b.id - a.id);
        return ok({
          total: list.length, page: 1, page_size: 50,
          items: list.map((o) => ({
            id: o.id, order_no: o.order_no, goods_id: o.goods_id,
            buyer_id: o.buyer_id, seller_id: o.seller_id, amount: Number(money(o.amount)),
            status: o.status, close_type: o.close_type, created_at: o.created_at,
          })),
        });
      }
      if (sub === "orders/abnormal" && method === "GET") {
        const list = orders.filter((o) => o.status === 10 && o.pay_deadline && new Date(o.pay_deadline).getTime() < Date.now());
        return ok({
          total: list.length,
          items: list.map((o) => ({
            id: o.id, order_no: o.order_no, goods_id: o.goods_id, buyer_id: o.buyer_id,
            amount: Number(money(o.amount)), pay_deadline: o.pay_deadline,
          })),
        });
      }
      m = sub.match(/^orders\/(\d+)\/force-close$/);
      if (m && method === "POST") {
        const o = orders.find((x) => x.id === Number(m[1]));
        if (!o) return fail("订单不存在", 404);
        if (o.status === 40) return fail("订单已关闭", 409);
        o.status = 40;
        o.close_type = "admin";
        o.closed_at = new Date().toISOString();
        const g = goodsById(o.goods_id);
        if (g && g.status === 4) { g.status = 1; g.stock += 1; }
        return ok({ id: o.id, status: 40 }, "订单已强制关闭");
      }
      return fail("演示环境未实现该管理接口", 404);
    }

    return fail("演示环境未实现该接口", 404);
  }

  /* 接管请求：写操作成功后落一次演示态，保证同一标签页内跨页面数据连续 */
  window.fetch = function (input, init) {
    const out = handleApi(input, init);
    if (!(out instanceof Promise)) {
      const method = ((init && init.method) || "GET").toUpperCase();
      if (method !== "GET") persist();
    }
    return out;
  };
})();

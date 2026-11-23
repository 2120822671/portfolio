/* ============================================================
   星坞 StarDock · 静态演示版 mock 层
   接管 /api/ 请求与 WebSocket，用浏览器内存数据模拟完整后端。
   刷新页面后按 localStorage 中的演示会话恢复登录态。
   ============================================================ */
(function () {
  "use strict";

  /* ---------- 演示根路径（兼容子路径部署）---------- */
  const selfScript = document.currentScript || document.querySelector('script[src$="demo-mock.js"]');
  const scriptSrc = selfScript ? selfScript.src : location.href;
  const cutAt = scriptSrc.indexOf("/js/demo-mock.js");
  window.SD_BASE = cutAt >= 0 ? scriptSrc.slice(0, cutAt) : "";

  /* ---------- 常量与小工具 ---------- */
  const RARITY_NAME = { 1: "N", 2: "R", 3: "SR", 4: "SSR" };
  const TOKEN_KEY = "stardock_token";
  const SESSION_KEY = "stardock_demo_session";

  const pad = (n) => String(n).padStart(2, "0");
  function nowStr() {
    const d = new Date();
    return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}:${pad(d.getSeconds())}`;
  }
  function lsGet(k) { try { return localStorage.getItem(k); } catch (e) { return null; } }
  function lsSet(k, v) { try { localStorage.setItem(k, v); } catch (e) { /* ignore */ } }
  function lsDel(k) { try { localStorage.removeItem(k); } catch (e) { /* ignore */ } }

  const json = (data, status) => new Response(JSON.stringify(data), {
    status: status || 200,
    headers: { "Content-Type": "application/json; charset=utf-8" },
  });
  const ok = (data, msg) => json({ code: 0, msg: msg || "ok", data: data === undefined ? null : data }, 200);
  const fail = (code, msg) => json({ code: code, msg: msg, data: null }, code);

  /* ---------- 用户 ---------- */
  let nextUserId = 100;
  const users = [
    { id: 1, username: "admin", nickname: "星坞管理员", avatar: null, role: 2, score: 99999, status: 1, create_time: "2026-01-05 10:00:00" },
    { id: 2, username: "star_luna", nickname: "Luna", avatar: null, role: 3, score: 52000, status: 1, create_time: "2026-01-08 12:30:00" },
    { id: 3, username: "star_kai", nickname: "凯", avatar: null, role: 3, score: 31000, status: 1, create_time: "2026-01-12 09:20:00" },
    { id: 4, username: "demo", nickname: "星海小粉丝", avatar: null, role: 1, score: 8800, status: 1, create_time: "2026-02-14 20:15:00" },
    { id: 5, username: "star_momo", nickname: "桃桃", avatar: null, role: 3, score: 26000, status: 1, create_time: "2026-02-20 18:40:00" },
    { id: 6, username: "star_echo", nickname: "回声", avatar: null, role: 3, score: 18000, status: 1, create_time: "2026-03-02 21:05:00" },
    { id: 7, username: "fan_sugar", nickname: "棉花糖", avatar: null, role: 1, score: 3200, status: 1, create_time: "2026-03-11 11:10:00" },
    { id: 8, username: "fan_night", nickname: "夜航星", avatar: null, role: 1, score: 1500, status: 0, create_time: "2026-03-15 23:45:00" },
  ];

  const strip = (u) => ({
    id: u.id, username: u.username, nickname: u.nickname, avatar: u.avatar,
    role: u.role, score: u.score, status: u.status, create_time: u.create_time,
  });

  let currentUser = null;

  function persist() {
    if (!currentUser) return;
    lsSet(SESSION_KEY, JSON.stringify({
      id: currentUser.id, username: currentUser.username, nickname: currentUser.nickname,
      avatar: currentUser.avatar, role: currentUser.role, score: currentUser.score,
    }));
  }

  function restoreSession() {
    if (!lsGet(TOKEN_KEY)) { lsDel(SESSION_KEY); return; }
    let s = null;
    try { s = JSON.parse(lsGet(SESSION_KEY) || "null"); } catch (e) { s = null; }
    if (!s || !s.username) return;
    let u = users.find((x) => x.username === s.username);
    if (!u) {
      u = {
        id: s.id || nextUserId++, username: s.username, nickname: s.nickname || s.username,
        avatar: s.avatar || null, role: s.role || 1,
        score: typeof s.score === "number" ? s.score : 5000, status: 1, create_time: nowStr(),
      };
      users.unshift(u);
    } else {
      if (s.nickname) u.nickname = s.nickname;
      if (typeof s.score === "number") u.score = s.score;
    }
    currentUser = u;
  }
  restoreSession();

  /* ---------- 明星 / 粉丝团 ---------- */
  let nextCelebId = 10;
  let nextClubId = 10;
  const celebrities = [
    {
      id: 1, user_id: 2, stage_name: "Luna 露娜", category: "歌手",
      bio: "银河系巡演中的独立唱作人，代表作《星轨》。习惯在深夜写歌，把失眠写成旋律。",
      cover_image: null, fan_count: 12800,
    },
    {
      id: 2, user_id: 3, stage_name: "Kai 凯", category: "演员",
      bio: "从科幻片走出的新生代演员，喜欢在片场即兴改词，被导演称为“意外制造机”。",
      cover_image: null, fan_count: 9600,
    },
    {
      id: 3, user_id: 5, stage_name: "Momo 桃桃", category: "虚拟主播",
      bio: "每晚八点直播间见，擅长翻唱与游戏，口头禅是“今天也要甜甜的”。",
      cover_image: null, fan_count: 7400,
    },
    {
      id: 4, user_id: 6, stage_name: "Echo 回声", category: "乐队主唱",
      bio: "地下乐队「回声」主唱，声音像从深空传来，坚持在 Livehouse 唱自己的歌。",
      cover_image: null, fan_count: 5300,
    },
  ];

  const clubs = [
    { id: 1, celebrity_id: 1, name: "Luna 后援会", description: "露娜的星轨观测站，一起追光。", member_count: 3280, create_time: "2026-01-09 10:00:00" },
    { id: 2, celebrity_id: 2, name: "凯的观测站", description: "守在片场外，记录每一个镜头。", member_count: 2100, create_time: "2026-01-13 10:00:00" },
    { id: 3, celebrity_id: 3, name: "桃桃甜品屋", description: "每晚八点，甜度满格。", member_count: 1680, create_time: "2026-02-21 10:00:00" },
    { id: 4, celebrity_id: 4, name: "回声电台", description: "把深空的声音录下来。", member_count: 940, create_time: "2026-03-03 10:00:00" },
  ];

  const clubMembers = {
    1: [{ user_id: 4, join_time: "2026-03-01 19:00:00" }, { user_id: 7, join_time: "2026-03-05 20:30:00" }],
    2: [{ user_id: 7, join_time: "2026-03-08 21:00:00" }],
    3: [],
    4: [],
  };

  const isMember = (clubId, userId) => (clubMembers[clubId] || []).some((m) => m.user_id === userId);

  function celebView(c) {
    const club = clubs.find((x) => x.celebrity_id === c.id);
    const u = users.find((x) => x.id === c.user_id) || {};
    return {
      id: c.id, stage_name: c.stage_name, category: c.category, bio: c.bio,
      cover_image: c.cover_image, fan_count: c.fan_count, nickname: u.nickname || c.stage_name,
      user_id: c.user_id, club_id: club ? club.id : null,
      club_name: club ? club.name : null, member_count: club ? club.member_count : 0,
    };
  }

  /* ---------- 卡池 / 卡片 ---------- */
  let nextCardId = 100;
  const pools = [
    {
      id: 1, name: "星轨·常驻卡池", description: "常驻卡池，收录 Luna 全系列星轨卡面。",
      cost_per_draw: 100, cost_per_ten: 900, is_active: 1, celebrity_id: 1, celebrity_name: "Luna 露娜",
    },
    {
      id: 2, name: "深海回声·限定池", description: "限时开启，SSR 概率提升，活动结束后下架。",
      cost_per_draw: 150, cost_per_ten: 1350, is_active: 0, celebrity_id: 2, celebrity_name: "Kai 凯",
    },
  ];

  const cards = [
    { id: 1, pool_id: 1, celebrity_id: 1, name: "晨光练习曲", image_url: "img/cards/luna-n1.jpg", rarity: 1, weight: 380, description: "清晨的练习室" },
    { id: 2, pool_id: 1, celebrity_id: 1, name: "深夜练习室", image_url: "img/cards/luna-n2.jpg", rarity: 1, weight: 380, description: "凌晨两点的琴声" },
    { id: 3, pool_id: 1, celebrity_id: 1, name: "舞台侧光", image_url: "img/cards/luna-r1.jpg", rarity: 2, weight: 120, description: "台下的第一束光" },
    { id: 4, pool_id: 1, celebrity_id: 1, name: "后台签名", image_url: "img/cards/luna-r2.jpg", rarity: 2, weight: 110, description: "签名笔迹很潦草" },
    { id: 5, pool_id: 1, celebrity_id: 1, name: "耳机里的银河", image_url: "img/cards/luna-r3.jpg", rarity: 2, weight: 100, description: "单曲循环一整夜" },
    { id: 6, pool_id: 1, celebrity_id: 1, name: "星轨现场", image_url: "img/cards/luna-sr1.jpg", rarity: 3, weight: 25, description: "巡演安可曲瞬间" },
    { id: 7, pool_id: 1, celebrity_id: 1, name: "月光录音棚", image_url: "img/cards/luna-sr2.jpg", rarity: 3, weight: 20, description: "录音棚里的月光" },
    { id: 8, pool_id: 1, celebrity_id: 1, name: "银河终章", image_url: "img/cards/luna-ssr.jpg", rarity: 4, weight: 5, description: "限量 SSS 级视觉卡" },
    { id: 9, pool_id: 2, celebrity_id: 2, name: "片场雨夜", image_url: "img/cards/kai-r1.jpg", rarity: 2, weight: 200, description: "限定池 R 卡" },
    { id: 10, pool_id: 2, celebrity_id: 2, name: "深海回声", image_url: "img/cards/kai-ssr.jpg", rarity: 4, weight: 15, description: "限定池 SSR" },
  ];

  const userCards = {
    4: [
      { card_id: 1, count: 3, obtain_time: "2026-11-15 21:12:00" },
      { card_id: 3, count: 2, obtain_time: "2026-11-16 22:03:00" },
      { card_id: 7, count: 1, obtain_time: "2026-11-19 20:41:00" },
    ],
    1: [
      { card_id: 2, count: 1, obtain_time: "2026-11-10 12:00:00" },
      { card_id: 8, count: 1, obtain_time: "2026-11-12 19:30:00" },
    ],
  };

  const drawRecords = {};

  function myCardsOf(uid) {
    const owned = userCards[uid] || (userCards[uid] = []);
    return owned.map((entry) => {
      const c = cards.find((x) => x.id === entry.card_id) || {};
      const rarity = c.rarity || 1;
      return {
        card_id: entry.card_id, count: entry.count, obtain_time: entry.obtain_time,
        name: c.name || "未知卡片", image_url: c.image_url || "", rarity: rarity,
        pool_id: c.pool_id || 0, rarity_name: RARITY_NAME[rarity] || "?",
      };
    });
  }

  function weightedPick(list) {
    const total = list.reduce((sum, c) => sum + c.weight, 0);
    let r = Math.floor(Math.random() * total) + 1;
    for (const c of list) {
      r -= c.weight;
      if (r <= 0) return c;
    }
    return list[list.length - 1];
  }

  /* ---------- 活动 ---------- */
  const activities = [
    {
      id: 3, title: "Luna 新单曲《星轨》全平台上线", content: "今晚 20:00 全平台上线，听完记得去超话打卡～\n后援会同步开启应援头像模板。",
      activity_type: 2, scope: 1, target_club_id: null, poster_id: 1, poster_name: "星坞管理员",
      create_time: "2026-11-20 20:00:00", status: 1,
    },
    {
      id: 2, title: "后援会周末打榜集合", content: "本周六晚八点，后援会集体打榜，进群接龙。",
      activity_type: 1, scope: 2, target_club_id: 1, poster_id: 2, poster_name: "Luna",
      create_time: "2026-11-21 09:30:00", status: 1,
    },
    {
      id: 1, title: "星坞维护公告", content: "本次维护已结束，抽卡记录与积分均已正常。",
      activity_type: 1, scope: 1, target_club_id: null, poster_id: 1, poster_name: "星坞管理员",
      create_time: "2026-11-18 08:00:00", status: 1,
    },
  ];

  function activityView(a) {
    const club = a.target_club_id ? clubs.find((c) => c.id === a.target_club_id) : null;
    return { ...a, club_name: club ? club.name : null };
  }

  function activitiesFor(u) {
    let list = activities.filter((a) => a.status === 1);
    if (u.role === 2) {
      // 管理员：全部
    } else if (u.role === 3) {
      const celeb = celebrities.find((c) => c.user_id === u.id);
      const club = celeb ? clubs.find((c) => c.celebrity_id === celeb.id) : null;
      list = list.filter((a) => a.scope === 1 || (a.scope === 2 && club && a.target_club_id === club.id));
    } else {
      const joined = clubs.filter((c) => isMember(c.id, u.id)).map((c) => c.id);
      list = list.filter((a) => a.scope === 1 || (a.scope === 2 && joined.includes(a.target_club_id)));
    }
    return list.sort((a, b) => b.id - a.id);
  }

  /* ---------- 充值 ---------- */
  const PLANS = [
    { id: 1, name: "新手礼包", amount: 1000, price: 10, bonus: 0 },
    { id: 2, name: "经典套餐", amount: 3000, price: 25, bonus: 0 },
    { id: 3, name: "热门套餐", amount: 5000, price: 48, bonus: 200 },
    { id: 4, name: "尊享套餐", amount: 10000, price: 88, bonus: 600 },
    { id: 5, name: "传说套餐", amount: 30000, price: 238, bonus: 3000 },
  ];

  const VALID_CODES = {
    STAR1000: 1000, STAR5000: 5000, STAR10000: 10000, STAR_NEW: 2000, LUNA_FAN: 3000,
  };
  const usedCodes = new Set();

  const orders = [
    { order_no: "SD20261118120000123456", user_id: 4, amount: 1000, pay_type: 1, pay_code: null, status: 1, create_time: "2026-11-18 12:00:00", pay_time: "2026-11-18 12:00:03" },
    { order_no: "SD20261120093000654321", user_id: 4, amount: 5000, pay_type: 2, pay_code: null, status: 1, create_time: "2026-11-20 09:30:00", pay_time: "2026-11-20 09:30:02" },
  ];

  function genOrderNo() {
    const d = new Date();
    const ts = `${d.getFullYear()}${pad(d.getMonth() + 1)}${pad(d.getDate())}${pad(d.getHours())}${pad(d.getMinutes())}${pad(d.getSeconds())}`;
    let rand = "";
    for (let i = 0; i < 6; i++) rand += String(Math.floor(Math.random() * 10));
    return `SD${ts}${rand}`;
  }

  /* ---------- 聊天 ---------- */
  let msgSeq = 1000;
  const clubMessages = {
    1: [
      { id: 1, content: "今晚八点的直播别错过～", msg_type: 1, create_time: "2026-11-22 19:40:00", user_id: 7, nickname: "棉花糖", avatar: null },
      { id: 2, content: "已经在超话打卡了！", msg_type: 1, create_time: "2026-11-22 19:42:00", user_id: 7, nickname: "棉花糖", avatar: null },
      { id: 3, content: "《星轨》单曲循环第 30 遍 🎧", msg_type: 1, create_time: "2026-11-22 19:45:00", user_id: 7, nickname: "棉花糖", avatar: null },
    ],
    2: [
      { id: 4, content: "新剧的花絮太可爱了吧", msg_type: 1, create_time: "2026-11-21 21:10:00", user_id: 7, nickname: "棉花糖", avatar: null },
    ],
    3: [],
    4: [],
  };

  const liveMessages = {
    1: [
      "欢迎新朋友加入后援会 🎉",
      "露娜刚刚发了新的动态，快去看！",
      "今晚的打榜群已经建好了～",
    ],
    2: ["片场路透已上传，注意查收", "凯今晚会空降聊天室（大概）"],
  };

  /* ---------- fetch 覆盖 ---------- */
  const realFetch = window.fetch.bind(window);

  const PUBLIC_PATHS = ["/auth/login", "/auth/register", "/auth/logout", "/recharge/plans", "/gacha/pools", "/celebrities"];
  function isPublic(path) {
    return PUBLIC_PATHS.some((p) => path === p || path.startsWith(p + "/"));
  }

  function adminOnly() {
    if (!currentUser) return fail(401, "未登录");
    if (currentUser.role !== 2) return fail(403, "权限不足");
    return null;
  }

  window.fetch = function (input, init) {
    const url = typeof input === "string" ? input : (input && input.url) || "";
    const at = url.indexOf("/api/");
    if (at < 0) return realFetch(input, init);

    const method = String((init && init.method) || (input && input.method) || "GET").toUpperCase();
    const qAt = url.indexOf("?", at);
    const rawPath = (qAt >= 0 ? url.slice(at + 5, qAt) : url.slice(at + 5)).replace(/\/+$/, "");
    const path = "/" + rawPath;
    const query = new URLSearchParams(qAt >= 0 ? url.slice(qAt + 1) : "");
    let body = {};
    if (init && init.body) {
      try { body = typeof init.body === "string" ? JSON.parse(init.body) : init.body; } catch (e) { body = {}; }
    }
    let m;

    if (!isPublic(path) && !lsGet(TOKEN_KEY)) return fail(401, "未登录");

    /* ===== 认证 ===== */
    if (path === "/auth/login" && method === "POST") {
      const uname = String(body.username || "").trim();
      if (!uname) return fail(400, "账号不能为空");
      let u = users.find((x) => x.username === uname);
      if (!u) {
        u = {
          id: nextUserId++, username: uname, nickname: uname, avatar: null,
          role: 1, score: 5000, status: 1, create_time: nowStr(),
        };
        users.unshift(u);
      }
      if (u.status !== 1) return fail(403, "账号已被禁用");
      currentUser = u;
      lsSet(TOKEN_KEY, "demo-token");
      persist();
      return ok(strip(u), "登录成功");
    }

    if (path === "/auth/register" && method === "POST") {
      const uname = String(body.username || "").trim();
      const pwd = String(body.password || "");
      const nick = String(body.nickname || "").trim();
      if (uname.length < 3) return fail(400, "账号至少 3 位");
      if (pwd.length < 6) return fail(400, "密码至少 6 位");
      if (!nick) return fail(400, "昵称不能为空");
      if (users.some((u) => u.username === uname)) return fail(400, "账号已存在");
      const u = {
        id: nextUserId++, username: uname, nickname: nick, avatar: null,
        role: 1, score: 5000, status: 1, create_time: nowStr(),
      };
      users.unshift(u);
      return ok({ user_id: u.id }, "注册成功，请登录");
    }

    if (path === "/auth/me" && method === "GET") {
      if (!currentUser) return fail(401, "未登录");
      return ok(strip(currentUser));
    }

    if (path === "/auth/logout" && method === "POST") {
      currentUser = null;
      lsDel(TOKEN_KEY);
      lsDel(SESSION_KEY);
      return ok(null, "已退出");
    }

    /* ===== 用户 ===== */
    if (path === "/users/me" && method === "PUT") {
      if (!currentUser) return fail(401, "未登录");
      const nick = String(body.nickname || "").trim();
      if (!nick) return fail(400, "昵称不能为空");
      currentUser.nickname = nick;
      persist();
      return ok(null, "更新成功");
    }

    if (path === "/users" && method === "GET") {
      const blocked = adminOnly();
      if (blocked) return blocked;
      const role = query.get("role");
      const status = query.get("status");
      const kw = (query.get("keyword") || "").trim();
      let list = users.slice();
      if (role) list = list.filter((u) => String(u.role) === role);
      if (status) list = list.filter((u) => String(u.status) === status);
      if (kw) list = list.filter((u) => (u.username + " " + u.nickname).includes(kw));
      list.sort((a, b) => b.id - a.id);
      return ok(list.map(strip));
    }

    if ((m = path.match(/^\/users\/(\d+)\/status$/)) && method === "PUT") {
      const blocked = adminOnly();
      if (blocked) return blocked;
      const u = users.find((x) => x.id === Number(m[1]));
      if (!u) return fail(404, "用户不存在");
      if (body.status !== 0 && body.status !== 1) return fail(400, "status 只能是 0 或 1");
      u.status = body.status;
      return ok(null, "操作成功");
    }

    if ((m = path.match(/^\/users\/(\d+)\/role$/)) && method === "PUT") {
      const blocked = adminOnly();
      if (blocked) return blocked;
      const u = users.find((x) => x.id === Number(m[1]));
      if (!u) return fail(404, "用户不存在");
      if (![1, 2, 3].includes(body.role)) return fail(400, "role 只能是 1/2/3");
      u.role = body.role;
      if (u.role === 3 && !celebrities.some((c) => c.user_id === u.id)) {
        const cid = nextCelebId++;
        celebrities.push({
          id: cid, user_id: u.id, stage_name: u.nickname, category: "其他",
          bio: "这位明星很神秘~", cover_image: null, fan_count: 0,
        });
        const clubId = nextClubId++;
        clubs.push({
          id: clubId, celebrity_id: cid, name: `${u.nickname}粉丝团`,
          description: "欢迎加入粉丝团！", member_count: 0, create_time: nowStr(),
        });
        clubMembers[clubId] = [];
      }
      return ok(null, "角色已更新");
    }

    /* ===== 明星 ===== */
    if (path === "/celebrities" && method === "GET") {
      const kw = (query.get("keyword") || "").trim();
      const cat = (query.get("category") || "").trim();
      let list = celebrities.map(celebView);
      if (kw) list = list.filter((c) => (c.stage_name + c.bio).includes(kw));
      if (cat) list = list.filter((c) => c.category === cat);
      list.sort((a, b) => b.fan_count - a.fan_count || b.id - a.id);
      return ok(list);
    }

    if ((m = path.match(/^\/celebrities\/(\d+)$/)) && method === "GET") {
      const c = celebrities.find((x) => x.id === Number(m[1]));
      if (!c) return fail(404, "明星不存在");
      const club = clubs.find((x) => x.celebrity_id === c.id);
      return ok({ ...celebView(c), club_desc: club ? club.description : "" });
    }

    /* ===== 粉丝团 ===== */
    if ((m = path.match(/^\/fan-clubs\/(\d+)$/)) && method === "GET") {
      const club = clubs.find((x) => x.id === Number(m[1]));
      if (!club) return fail(404, "粉丝团不存在");
      const celeb = celebrities.find((c) => c.id === club.celebrity_id) || {};
      const members = (clubMembers[club.id] || []).map((entry) => {
        const u = users.find((x) => x.id === entry.user_id) || {};
        return {
          id: entry.user_id, nickname: u.nickname || "神秘成员", avatar: u.avatar || null,
          role: u.role || 1, nick_in_club: null, join_time: entry.join_time,
        };
      });
      return ok({
        id: club.id, name: club.name, description: club.description,
        member_count: club.member_count, create_time: club.create_time,
        stage_name: celeb.stage_name, category: celeb.category,
        cover_image: celeb.cover_image || null, celebrity_id: club.celebrity_id,
        members: members,
      });
    }

    if ((m = path.match(/^\/fan-clubs\/(\d+)\/(join|leave)$/)) && method === "POST") {
      if (!currentUser) return fail(401, "未登录");
      const club = clubs.find((x) => x.id === Number(m[1]));
      if (!club) return fail(404, "粉丝团不存在");
      const celeb = celebrities.find((c) => c.id === club.celebrity_id);
      const list = clubMembers[club.id] || (clubMembers[club.id] = []);
      if (m[2] === "join") {
        if (list.some((x) => x.user_id === currentUser.id)) return fail(400, "你已经在这个粉丝团里了");
        list.push({ user_id: currentUser.id, join_time: nowStr() });
        club.member_count += 1;
        if (celeb) celeb.fan_count += 1;
        return ok(null, "加入成功");
      }
      const idx = list.findIndex((x) => x.user_id === currentUser.id);
      if (idx < 0) return fail(400, "你不在这个粉丝团里");
      list.splice(idx, 1);
      club.member_count = Math.max(0, club.member_count - 1);
      if (celeb) celeb.fan_count = Math.max(0, celeb.fan_count - 1);
      return ok(null, "已退出");
    }

    /* ===== 聊天历史 ===== */
    if ((m = path.match(/^\/chat\/(\d+)\/history$/)) && method === "GET") {
      if (!currentUser) return fail(401, "未登录");
      const cid = Number(m[1]);
      if (!clubs.some((c) => c.id === cid)) return fail(404, "粉丝团不存在");
      if (currentUser.role !== 2 && !isMember(cid, currentUser.id)) return fail(403, "你不是该粉丝团成员");
      const size = Math.max(1, Number(query.get("size")) || 50);
      return ok((clubMessages[cid] || []).slice(-size));
    }

    /* ===== 抽卡 ===== */
    if (path === "/gacha/pools" && method === "GET") {
      const list = pools.slice().sort((a, b) => (b.is_active - a.is_active) || (b.id - a.id));
      return ok(list);
    }

    if (path === "/gacha/pools" && method === "POST") {
      const blocked = adminOnly();
      if (blocked) return blocked;
      const pool = {
        id: pools.reduce((mx, p) => Math.max(mx, p.id), 0) + 1,
        name: String(body.name || "未命名卡池"),
        description: body.description || null,
        cost_per_draw: Number(body.cost_per_draw) || 100,
        cost_per_ten: Number(body.cost_per_ten) || 900,
        is_active: body.is_active === 0 ? 0 : 1,
        celebrity_id: body.celebrity_id || null,
        celebrity_name: (celebrities.find((c) => c.id === body.celebrity_id) || {}).stage_name || null,
      };
      pools.push(pool);
      return ok({ pool_id: pool.id }, "卡池创建成功");
    }

    if ((m = path.match(/^\/gacha\/pools\/(\d+)$/)) && method === "GET") {
      const pool = pools.find((x) => x.id === Number(m[1]));
      if (!pool) return fail(404, "卡池不存在");
      const list = cards
        .filter((c) => c.pool_id === pool.id)
        .sort((a, b) => b.rarity - a.rarity || b.weight - a.weight)
        .map((c) => ({ ...c, rarity_name: RARITY_NAME[c.rarity] || "?" }));
      return ok({ ...pool, cards: list });
    }

    if ((m = path.match(/^\/gacha\/pools\/(\d+)$/)) && method === "PUT") {
      const blocked = adminOnly();
      if (blocked) return blocked;
      const pool = pools.find((x) => x.id === Number(m[1]));
      if (!pool) return fail(404, "卡池不存在");
      ["name", "description", "cost_per_draw", "cost_per_ten", "is_active"].forEach((k) => {
        if (body[k] !== undefined && body[k] !== null) pool[k] = body[k];
      });
      return ok(null, "更新成功");
    }

    if (path === "/gacha/cards" && method === "POST") {
      const blocked = adminOnly();
      if (blocked) return blocked;
      if (![1, 2, 3, 4].includes(body.rarity)) return fail(400, "rarity 只能是 1/2/3/4");
      const card = {
        id: nextCardId++, pool_id: body.pool_id,
        celebrity_id: body.celebrity_id || null,
        name: String(body.name || "未命名卡片"),
        image_url: body.image_url || "",
        rarity: body.rarity,
        weight: Number(body.weight) || 100,
        description: body.description || "",
      };
      cards.push(card);
      return ok({ card_id: card.id }, "卡片创建成功");
    }

    if ((m = path.match(/^\/gacha\/cards\/(\d+)$/)) && method === "PUT") {
      const blocked = adminOnly();
      if (blocked) return blocked;
      const card = cards.find((x) => x.id === Number(m[1]));
      if (!card) return fail(404, "卡片不存在");
      ["pool_id", "name", "image_url", "rarity", "weight", "description"].forEach((k) => {
        if (body[k] !== undefined && body[k] !== null) card[k] = body[k];
      });
      return ok(null, "更新成功");
    }

    if ((m = path.match(/^\/gacha\/cards\/(\d+)$/)) && method === "DELETE") {
      const blocked = adminOnly();
      if (blocked) return blocked;
      const idx = cards.findIndex((x) => x.id === Number(m[1]));
      if (idx >= 0) cards.splice(idx, 1);
      return ok(null, "删除成功");
    }

    if (path === "/gacha/draw" && method === "POST") {
      if (!currentUser) return fail(401, "未登录");
      if (body.count !== 1 && body.count !== 10) return fail(400, "count 只能是 1 或 10");
      const pool = pools.find((p) => p.id === body.pool_id);
      if (!pool) return fail(404, "卡池不存在");
      if (pool.is_active !== 1) return fail(400, "卡池已关闭");
      const poolCards = cards.filter((c) => c.pool_id === pool.id);
      if (!poolCards.length) return fail(400, "卡池里没有卡片");

      const count = body.count === 10 ? 10 : 1;
      const cost = count === 10 ? pool.cost_per_ten : pool.cost_per_draw;
      if (currentUser.score < cost) return fail(400, `积分不足，需要 ${cost}，当前 ${currentUser.score}`);

      currentUser.score -= cost;
      const owned = userCards[currentUser.id] || (userCards[currentUser.id] = []);
      const drawn = [];
      for (let i = 0; i < count; i++) {
        const picked = weightedPick(poolCards);
        drawn.push({
          card_id: picked.id, name: picked.name, image_url: picked.image_url,
          rarity: picked.rarity, rarity_name: RARITY_NAME[picked.rarity] || "?",
        });
        const entry = owned.find((x) => x.card_id === picked.id);
        if (entry) { entry.count += 1; entry.obtain_time = nowStr(); }
        else owned.push({ card_id: picked.id, count: 1, obtain_time: nowStr() });
      }

      const rec = drawRecords[currentUser.id] || (drawRecords[currentUser.id] = []);
      rec.unshift({
        id: rec.length + 1, pool_id: pool.id, draw_type: count === 10 ? 2 : 1,
        total_cost: cost, results_json: drawn.slice(), create_time: nowStr(), pool_name: pool.name,
      });
      persist();

      drawn.reverse();
      return ok({ cost: cost, drawn: drawn, remain_score: currentUser.score }, "抽卡成功");
    }

    if (path === "/gacha/my-cards" && method === "GET") {
      if (!currentUser) return fail(401, "未登录");
      const rarity = Number(query.get("rarity")) || 0;
      const page = Math.max(1, Number(query.get("page")) || 1);
      const size = Math.max(1, Number(query.get("size")) || 20);
      let list = myCardsOf(currentUser.id);
      if (rarity) list = list.filter((c) => c.rarity === rarity);
      list.sort((a, b) => b.rarity - a.rarity || String(b.obtain_time).localeCompare(String(a.obtain_time)));
      return ok(list.slice((page - 1) * size, page * size));
    }

    if ((m = path.match(/^\/gacha\/my-cards\/(\d+)$/)) && method === "GET") {
      if (!currentUser) return fail(401, "未登录");
      const own = myCardsOf(currentUser.id).find((c) => c.card_id === Number(m[1]));
      if (!own) return fail(404, "没有这张卡");
      const card = cards.find((c) => c.id === own.card_id) || {};
      const pool = pools.find((p) => p.id === card.pool_id) || {};
      return ok({ ...card, ...own, rarity_name: RARITY_NAME[card.rarity] || "?", pool_name: pool.name || "" });
    }

    if (path === "/gacha/records" && method === "GET") {
      if (!currentUser) return fail(401, "未登录");
      return ok(drawRecords[currentUser.id] || []);
    }

    /* ===== 活动 ===== */
    if (path === "/activities" && method === "GET") {
      if (!currentUser) return fail(401, "未登录");
      const page = Math.max(1, Number(query.get("page")) || 1);
      const size = Math.max(1, Number(query.get("size")) || 10);
      const list = activitiesFor(currentUser).slice((page - 1) * size, page * size);
      return ok(list.map(activityView));
    }

    if (path === "/activities" && method === "POST") {
      if (!currentUser) return fail(401, "未登录");
      if (currentUser.role !== 2 && currentUser.role !== 3) return fail(403, "无权限发布活动");
      const title = String(body.title || "").trim();
      const content = String(body.content || "").trim();
      if (!title || !content) return fail(400, "标题和正文不能为空");
      const scope = body.scope === 2 ? 2 : 1;
      const rec = {
        id: activities.reduce((mx, a) => Math.max(mx, a.id), 0) + 1,
        title: title.slice(0, 100), content: content,
        activity_type: body.activity_type === 2 ? 2 : 1,
        scope: scope,
        target_club_id: scope === 2 ? (body.target_club_id || null) : null,
        poster_id: currentUser.id, poster_name: currentUser.nickname,
        create_time: nowStr(), status: 1,
      };
      activities.push(rec);
      return ok({ activity_id: rec.id }, "发布成功");
    }

    if ((m = path.match(/^\/activities\/(\d+)$/))) {
      const rec = activities.find((a) => a.id === Number(m[1]));
      if (!rec) return fail(404, "活动不存在");
      if (method === "GET") {
        if (!currentUser) return fail(401, "未登录");
        return ok(activityView(rec));
      }
      if (method === "PUT") {
        if (!currentUser) return fail(401, "未登录");
        if (currentUser.role !== 2 && rec.poster_id !== currentUser.id) return fail(403, "只有发布者或管理员可以修改");
        ["title", "content", "status"].forEach((k) => {
          if (body[k] !== undefined && body[k] !== null) rec[k] = body[k];
        });
        return ok(null, "更新成功");
      }
      if (method === "DELETE") {
        if (!currentUser) return fail(401, "未登录");
        if (currentUser.role !== 2 && rec.poster_id !== currentUser.id) return fail(403, "只有发布者或管理员可以撤回");
        rec.status = 0;
        return ok(null, "已撤回");
      }
    }

    /* ===== 充值 ===== */
    if (path === "/recharge/plans" && method === "GET") {
      return ok(PLANS);
    }

    if (path === "/recharge/order" && method === "POST") {
      if (!currentUser) return fail(401, "未登录");
      const plan = PLANS.find((p) => p.id === body.plan_id);
      if (!plan) return fail(400, "套餐不存在");
      if (body.pay_type !== 1 && body.pay_type !== 2) return fail(400, "pay_type 只能是 1 或 2");
      const amount = plan.amount + plan.bonus;
      const order = {
        order_no: genOrderNo(), user_id: currentUser.id, amount: amount,
        pay_type: body.pay_type, pay_code: null, status: 0,
        create_time: nowStr(), pay_time: null,
      };
      orders.unshift(order);
      return ok({
        order_no: order.order_no, amount: amount, plan_name: plan.name,
        pay_name: body.pay_type === 1 ? "微信支付" : "支付宝", price: plan.price,
      }, "订单创建成功");
    }

    if (path === "/recharge/pay" && method === "POST") {
      if (!currentUser) return fail(401, "未登录");
      const order = orders.find((o) => o.order_no === body.order_no && o.user_id === currentUser.id);
      if (!order) return fail(404, "订单不存在");
      if (order.status === 1) return fail(400, "订单已支付");
      if (order.status === 2) return fail(400, "订单已取消");
      order.status = 1;
      order.pay_time = nowStr();
      currentUser.score += order.amount;
      persist();
      return ok({ amount: order.amount, remain_balance: currentUser.score }, `充值成功！到账 ${order.amount} 积分`);
    }

    if (path === "/recharge/redeem" && method === "POST") {
      if (!currentUser) return fail(401, "未登录");
      const code = String(body.code || "").trim().toUpperCase();
      if (usedCodes.has(code)) return fail(400, "兑换码已被使用");
      if (!VALID_CODES[code]) return fail(400, "兑换码无效");
      const amount = VALID_CODES[code];
      usedCodes.add(code);
      orders.unshift({
        order_no: genOrderNo(), user_id: currentUser.id, amount: amount,
        pay_type: 3, pay_code: code, status: 1, create_time: nowStr(), pay_time: nowStr(),
      });
      currentUser.score += amount;
      persist();
      return ok({ amount: amount, remain_balance: currentUser.score }, `兑换成功！到账 ${amount} 积分`);
    }

    if (path === "/recharge/my-orders" && method === "GET") {
      if (!currentUser) return fail(401, "未登录");
      const page = Math.max(1, Number(query.get("page")) || 1);
      const size = Math.max(1, Number(query.get("size")) || 20);
      const list = orders.filter((o) => o.user_id === currentUser.id);
      return ok(list.slice((page - 1) * size, page * size));
    }

    if (path === "/health") return ok(null, "ok");

    return fail(404, "演示环境未模拟该接口");
  };

  /* ============================================================
     WebSocket 假实现：连接即推送 2~3 条消息，发送后本地回显
     ============================================================ */
  function pushMessage(clubId, content, user) {
    const arr = clubMessages[clubId] || (clubMessages[clubId] = []);
    const msg = {
      id: ++msgSeq, content: content, msg_type: 1, create_time: nowStr(),
      user_id: user.id, nickname: user.nickname || "星友", avatar: user.avatar || null,
    };
    arr.push(msg);
    return msg;
  }

  class DemoWebSocket {
    constructor(url) {
      this.url = url;
      this.readyState = DemoWebSocket.CONNECTING;
      this.onopen = null;
      this.onmessage = null;
      this.onclose = null;
      this.onerror = null;

      const clubMatch = String(url).match(/\/chat\/(\d+)/);
      const uidMatch = String(url).match(/[?&]user_id=(\d+)/);
      this._clubId = clubMatch ? Number(clubMatch[1]) : 0;
      this._uid = uidMatch ? Number(uidMatch[1]) : 0;

      setTimeout(() => {
        if (this.readyState !== DemoWebSocket.CONNECTING) return;
        this.readyState = DemoWebSocket.OPEN;
        if (typeof this.onopen === "function") this.onopen({ type: "open" });

        const self = this;
        const seed = liveMessages[this._clubId] || ["大家好呀～", "欢迎来到粉丝团聊天室"];
        const bot = users.find((u) => u.id === 7) || { id: 7, nickname: "棉花糖", avatar: null };
        seed.slice(0, 3).forEach((text, i) => {
          setTimeout(() => {
            if (self.readyState !== DemoWebSocket.OPEN) return;
            const msg = pushMessage(self._clubId, text, bot);
            self._emit(msg);
          }, 500 + i * 700);
        });
      }, 320);
    }

    _emit(msg) {
      if (this.readyState !== DemoWebSocket.OPEN) return;
      if (typeof this.onmessage === "function") {
        this.onmessage({ data: JSON.stringify({ type: "message", data: msg }) });
      }
    }

    send(raw) {
      let content = "";
      try { content = String(JSON.parse(raw).content || "").trim(); } catch (e) { return; }
      if (!content || this.readyState !== DemoWebSocket.OPEN) return;
      const me = currentUser || { id: this._uid, nickname: "我", avatar: null };
      const msg = pushMessage(this._clubId, content, me);
      const self = this;
      setTimeout(() => self._emit(msg), 120);
    }

    close() {
      if (this.readyState === DemoWebSocket.CLOSED) return;
      this.readyState = DemoWebSocket.CLOSED;
      if (typeof this.onclose === "function") this.onclose({ type: "close" });
    }

    addEventListener(type, fn) {
      if (type === "message") this.onmessage = fn;
      else if (type === "open") this.onopen = fn;
      else if (type === "close") this.onclose = fn;
      else if (type === "error") this.onerror = fn;
    }

    removeEventListener() { /* noop */ }
  }
  DemoWebSocket.CONNECTING = 0;
  DemoWebSocket.OPEN = 1;
  DemoWebSocket.CLOSING = 2;
  DemoWebSocket.CLOSED = 3;

  window.WebSocket = DemoWebSocket;

  /* ============================================================
     右下角「静态演示版」徽标
     ============================================================ */
  function addDemoBadge() {
    if (document.getElementById("sdDemoBadge")) return;
    const el = document.createElement("div");
    el.id = "sdDemoBadge";
    el.textContent = "静态演示版 · 数据为浏览器内模拟";
    el.style.cssText = [
      "position:fixed", "right:14px", "bottom:14px", "z-index:9998",
      "padding:6px 12px", "border-radius:999px",
      "background:rgba(5,10,42,0.78)", "border:1px solid rgba(255,215,0,0.3)",
      "color:rgba(255,255,255,0.62)", "font-size:11px", "letter-spacing:0.5px",
      "pointer-events:none", "backdrop-filter:blur(6px)",
      "font-family:'Segoe UI','PingFang SC','Microsoft YaHei',sans-serif",
    ].join(";");
    document.body.appendChild(el);
  }
  if (document.body) addDemoBadge();
  else document.addEventListener("DOMContentLoaded", addDemoBadge);
})();

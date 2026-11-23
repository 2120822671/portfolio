"""
招财猫大模型增强层（LLM）
=========================
设计原则：**规则兜底 + 大模型增强**
- 大模型不可用 / 超时 / 报错 → 自动回落前端规则解析，功能永不中断
- 密钥只从环境变量读取，绝不硬编码、不写进提示词
- 响应格式用 JSON Schema 钉死，解析失败重试一次后仍失败则回落规则

环境变量（按你使用的服务商二选一设置）：
  LLM_API_KEY   大模型 API Key（必填，不填则全程走规则模式）
  LLM_BASE_URL  OpenAI 兼容接口地址，默认 https://api.deepseek.com/v1
  LLM_MODEL     模型名，默认 deepseek-chat

> 接口参数以你所选服务商的官方文档为准：本文档使用 OpenAI 兼容的
> /chat/completions 规范（多数国内服务商均兼容）。
"""

import os
import json
import time

import requests


# ==========================================
# 配置（全部来自环境变量，不硬编码密钥）
# ==========================================
API_KEY = os.getenv("LLM_API_KEY", "").strip()
BASE_URL = os.getenv("LLM_BASE_URL", "https://api.deepseek.com/v1").strip().rstrip("/")
MODEL = os.getenv("LLM_MODEL", "deepseek-chat").strip()

TIMEOUT = 30          # 单次请求超时（秒）
MAX_RETRY = 2         # 最多重试次数
RETRY_BASE = 1.0      # 退避基数：1s → 2s


def llm_enabled() -> bool:
    """是否具备调用大模型的条件"""
    return bool(API_KEY)


def _chat(messages: list, temperature: float = 0.3) -> str:
    """调用 OpenAI 兼容的 chat/completions 接口，返回 message.content 文本"""
    if not llm_enabled():
        raise RuntimeError("未配置 LLM_API_KEY")

    url = f"{BASE_URL}/chat/completions"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {API_KEY}",
    }
    payload = {
        "model": MODEL,
        "messages": messages,
        "temperature": temperature,
        "stream": False,
    }

    last_err = None
    for attempt in range(MAX_RETRY + 1):
        try:
            resp = requests.post(url, headers=headers, json=payload, timeout=TIMEOUT)
            # 4xx 属于确定性错误（Key 错、参数错），重试无意义
            if resp.status_code < 500 and resp.status_code != 429:
                resp.raise_for_status()
            resp.raise_for_status()
            data = resp.json()
            return data["choices"][0]["message"]["content"]
        except Exception as e:  # noqa: BLE001 - 统一兜底，交由调用方降级
            last_err = e
            if attempt < MAX_RETRY:
                time.sleep(RETRY_BASE * (2 ** attempt))
    raise RuntimeError(f"大模型调用失败：{last_err}")


def _extract_json(text: str) -> dict:
    """从模型输出里抠出 JSON 对象（容忍 ```json 包裹与前后废话）"""
    if not text:
        raise ValueError("模型返回为空")
    raw = text.strip()
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.lstrip().lower().startswith("json"):
            raw = raw.lstrip()[4:]
    raw = raw.strip().strip("`").strip()
    start = raw.find("{")
    end = raw.rfind("}")
    if start == -1 or end == -1 or end <= start:
        raise ValueError("未找到 JSON 结构")
    return json.loads(raw[start:end + 1])


# ==========================================
# 能力 1：记账意图解析（多笔 + 复杂表达）
# ==========================================
PARSE_PROMPT = """你是「招财猫」，一个中文个人记账系统的记账解析器。
把用户的一句话拆解成 1 到 5 笔记账记录。

输出必须是合法 JSON，字段与顺序固定，禁止输出 JSON 以外的任何文字：
{"records": [{"type": 1, "amount": 12.5, "category": "餐饮", "remark": "午饭", "recordTime": "2026-11-16 12:30:00"}]}

字段含义与规则：
- type：1=收入，2=支出
- amount：数字，正数，最多两位小数
- category：中文分类，只能从 餐饮/交通/购物/娱乐/生活/医疗/其他/工资/奖金/报销/其他收入 中选
- remark：简短原文摘要
- recordTime：格式 yyyy-MM-dd HH:mm:ss，相对时间请换算成绝对时间

示例1：
输入：午饭30
输出：{"records": [{"type": 2, "amount": 30, "category": "餐饮", "remark": "午饭", "recordTime": "2026-11-16 12:00:00"}]}

示例2：
输入：昨天打车15 今天午饭32 工资8000
输出：{"records": [{"type": 2, "amount": 15, "category": "交通", "remark": "打车", "recordTime": "2026-11-15 12:00:00"}, {"type": 2, "amount": 32, "category": "餐饮", "remark": "午饭", "recordTime": "2026-11-16 12:00:00"}, {"type": 1, "amount": 8000, "category": "工资", "remark": "工资", "recordTime": "2026-11-16 12:00:00"}]}

当前时间：{now}
"""


def parse_records(text: str, now_str: str) -> list:
    """
    大模型解析记账语句，返回记录数组。
    失败抛异常，由调用方回落规则解析。
    """
    prompt = PARSE_PROMPT.replace("{now}", now_str)
    messages = [
        {"role": "system", "content": "你是一个只输出 JSON 的记账解析器。"},
        {"role": "user", "content": text},
    ]
    raw = _chat(messages)
    data = _extract_json(raw)
    records = data.get("records")
    if not isinstance(records, list) or not records:
        raise ValueError("未解析出记录")

    out = []
    for r in records:
        try:
            t = int(r.get("type", 2))
            amt = float(r.get("amount", 0))
            if t not in (1, 2) or amt <= 0:
                continue
            out.append({
                "type": t,
                "amount": round(amt, 2),
                "category": str(r.get("category") or "其他"),
                "remark": str(r.get("remark") or "")[:255],
                "recordTime": str(r.get("recordTime") or now_str),
            })
        except (TypeError, ValueError):
            continue
    if not out:
        raise ValueError("记录字段非法")
    return out


# ==========================================
# 能力 2：对话式意图识别（记账 / 查询 / 分析 / 闲聊）
# ==========================================
INTENT_PROMPT = """你是「招财猫」，一个中文个人记账系统的助手。
判断用户这句话的意图，只输出合法 JSON，禁止输出 JSON 以外的任何文字：

{"intent": "record|query|analysis|chat", "reply": "给用户看的一句话", "records": []}

- record：用户要记一笔账。records 填解析出的记录数组，字段同记账解析器。
- query：用户要查询/播报收支数据。reply 写明要查什么。
- analysis：用户要分析消费情况、给建议或评价。reply 写明要分析什么。
- chat：与记账无关的闲聊或夸奖。reply 给出符合人设的回应。

reply 是面向用户的口吻，可以用「喵」结尾，语气亲切但内容准确。

当前时间：{now}
"""


def detect_intent(text: str, now_str: str) -> dict:
    """
    识别意图 + 顺带解析记账记录。
    失败抛异常，由调用方回落规则解析。
    """
    prompt = INTENT_PROMPT.replace("{now}", now_str)
    messages = [
        {"role": "system", "content": "你是一个只输出 JSON 的意图分类器。"},
        {"role": "user", "content": text},
    ]
    raw = _chat(messages)
    data = _extract_json(raw)
    intent = str(data.get("intent") or "chat")
    if intent not in ("record", "query", "analysis", "chat"):
        intent = "chat"
    reply = str(data.get("reply") or "").strip()
    records = data.get("records") or []
    if not isinstance(records, list):
        records = []
    return {"intent": intent, "reply": reply, "records": records}


# ==========================================
# 能力 3：每日消费复盘（给结构化数据，产出人话建议）
# ==========================================
REVIEW_PROMPT = """你是「招财猫」，一位懂生活、会理财的中文记账管家。
请根据用户当天的消费数据，写一段 120 字以内的复盘点评。

写作要求：
- 先给结论（今天花得怎么样），再给 1-2 条具体建议
- 语气亲切自然，可以适度用「喵」，但不要卖萌过度
- 金额必须严格使用给定数据里的数字，禁止编造或四舍五入改写
- 如果当天没有支出，就夸他克制并鼓励
- 禁止输出 Markdown 标题、列表符号或换行以外的格式

数据：
{data}
"""


def daily_review(data: dict) -> str:
    """生成每日消费复盘文案，失败抛异常由调用方用规则文案兜底"""
    payload = json.dumps(data, ensure_ascii=False, indent=2)
    messages = [
        {"role": "system", "content": "你是一个输出纯文本点评的中文记账管家。"},
        {"role": "user", "content": REVIEW_PROMPT.replace("{data}", payload)},
    ]
    raw = _chat(messages, temperature=0.6)
    return raw.strip()


# ==========================================
# 能力 4：月度账单解读
# ==========================================
MONTHLY_PROMPT = """你是「招财猫」，一位中文记账管家。
根据用户提供的月度账单数据，写一份 200 字以内的解读。

要求：
- 结构：整体结余 → 支出结构 → 2 条可执行的省钱建议
- 金额严格使用给定数字，禁止编造
- 语气亲切专业，可用「喵」收尾
- 纯文本输出，不要 Markdown 标题或列表符号

数据：
{data}
"""


def monthly_review(data: dict) -> str:
    """生成月度账单解读，失败抛异常由调用方用规则文案兜底"""
    payload = json.dumps(data, ensure_ascii=False, indent=2)
    messages = [
        {"role": "system", "content": "你是一个输出纯文本解读的中文记账管家。"},
        {"role": "user", "content": MONTHLY_PROMPT.replace("{data}", payload)},
    ]
    raw = _chat(messages, temperature=0.6)
    return raw.strip()

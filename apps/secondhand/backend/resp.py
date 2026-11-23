"""统一接口返回格式：{code, msg, data}，code=0 表示成功"""


def ok(data=None, msg: str = "success") -> dict:
    return {"code": 0, "msg": msg, "data": data}

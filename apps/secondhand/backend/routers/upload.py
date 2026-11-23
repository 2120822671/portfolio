"""图片上传：支持多图，限制类型与大小，返回可访问URL"""
import os
import uuid

from fastapi import APIRouter, File, HTTPException, UploadFile

from paths import UPLOAD_DIR
from resp import ok

router = APIRouter(prefix="/upload", tags=["图片"])

ALLOWED_EXT = {".jpg", ".jpeg", ".png", ".gif", ".webp"}
MAX_SIZE = 2 * 1024 * 1024  # 单张 2MB


@router.post("", summary="上传图片（multipart 多图）")
async def upload_images(files: list[UploadFile] = File(..., description="图片文件，jpg/png/gif/webp，单张≤2MB")):
    os.makedirs(UPLOAD_DIR, exist_ok=True)
    urls = []
    for f in files:
        ext = os.path.splitext(f.filename or "")[1].lower()
        if ext not in ALLOWED_EXT:
            raise HTTPException(status_code=400, detail=f"不支持的图片格式：{ext or '未知'}，仅允许 jpg/png/gif/webp")
        data = await f.read()
        if len(data) > MAX_SIZE:
            raise HTTPException(status_code=400, detail=f"图片 {f.filename} 超过 2MB 限制")
        name = f"{uuid.uuid4().hex}{ext}"
        with open(os.path.join(UPLOAD_DIR, name), "wb") as fp:
            fp.write(data)
        urls.append(f"/static/uploads/{name}")
    return ok(urls, "上传成功")

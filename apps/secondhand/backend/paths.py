"""项目路径常量

整理后前端静态资源与后端代码分属不同目录，统一在此解析绝对路径，
避免依赖启动时的工作目录（uvicorn 从 backend 或项目根启动均可用）。
"""
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent          # 项目/backend
PROJECT_ROOT = BACKEND_DIR.parent                      # 项目根
FRONTEND_DIR = PROJECT_ROOT / "frontend"               # 前端静态资源
UPLOAD_DIR = FRONTEND_DIR / "uploads"                  # 上传图片落盘目录

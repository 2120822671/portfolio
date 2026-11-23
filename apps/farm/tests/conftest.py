"""
测试配置

在导入应用前把 DATABASE_URL 指向临时 SQLite 文件，
避免污染开发库 pixel_farm.db。
"""
from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

TEST_DB = Path(tempfile.gettempdir()) / f"pixel_farm_test_{os.getpid()}.db"
if TEST_DB.exists():
    TEST_DB.unlink()

os.environ["DATABASE_URL"] = f"sqlite+aiosqlite:///{TEST_DB.as_posix()}"
os.environ["DEBUG"] = "true"
os.environ["SQL_ECHO"] = "false"

from app.main import app  # noqa: E402


@pytest.fixture
async def client():
    """每个测试独立启动一次应用生命周期，保证建表与种子数据就绪"""
    async with app.router.lifespan_context(app):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as c:
            yield c


def pytest_sessionfinish(session, exitstatus):
    """测试结束后删除临时数据库"""
    if TEST_DB.exists():
        TEST_DB.unlink(missing_ok=True)

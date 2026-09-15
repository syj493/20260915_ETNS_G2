import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent


_DATABASE_URL = os.environ.get("DATABASE_URL", f"sqlite:///{BASE_DIR / 'moving_cs.db'}")
_IS_POSTGRES = _DATABASE_URL.startswith("postgres")


class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-only-secret-key-change-me")
    SQLALCHEMY_DATABASE_URI = _DATABASE_URL
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    UPLOAD_FOLDER = "/tmp/uploads" if os.environ.get("VERCEL") else str(BASE_DIR / "uploads")
    MAX_CONTENT_LENGTH = 20 * 1024 * 1024  # 20MB
    ALLOWED_EXTENSIONS = {"jpg", "jpeg", "png", "pdf", "xlsx", "docx"}

    if _IS_POSTGRES:
        # Supabase Supavisor Transaction Pooler(6543) 대상 서버리스 최적화:
        # - 커넥션을 오래 붙들지 않도록 pool을 작게 유지 + pre_ping으로 죽은 커넥션 자동 감지
        # - Transaction 모드는 세션 상태를 유지하지 않으므로 pool_size를 크게 잡을 이유가 없음
        SQLALCHEMY_ENGINE_OPTIONS = {
            "pool_size": 3,
            "max_overflow": 2,
            "pool_pre_ping": True,
            "pool_recycle": 280,
            "connect_args": {"sslmode": "require"},
        }

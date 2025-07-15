from __future__ import annotations

import os

try:
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    SQLALCHEMY_AVAILABLE = True
except Exception:  # pragma: no cover - optional dependency
    SQLALCHEMY_AVAILABLE = False

    def create_engine(*args, **kwargs):  # type: ignore
        return None

    class sessionmaker:  # type: ignore
        def __init__(self, *args, **kwargs):
            pass

        def __call__(self, *args, **kwargs):
            return None

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./app.db")

engine = create_engine(DATABASE_URL) if SQLALCHEMY_AVAILABLE else None
SessionLocal = sessionmaker(bind=engine) if SQLALCHEMY_AVAILABLE else lambda: None


def init_db() -> None:
    if not SQLALCHEMY_AVAILABLE:
        return
    from .models import Base

    Base.metadata.create_all(bind=engine)

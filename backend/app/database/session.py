"""Database connection and session factory."""

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

from app.config import settings

_is_sqlite = settings.DATABASE_URL.startswith("sqlite")

connect_args = {}
engine_options = {
    "pool_pre_ping": True,
    "future": True,
}

if _is_sqlite:
    connect_args = {"check_same_thread": False}
    engine_options["connect_args"] = connect_args
else:
    engine_options.update(
        pool_size=settings.DB_POOL_SIZE,
        max_overflow=settings.DB_MAX_OVERFLOW,
        pool_recycle=settings.DB_POOL_RECYCLE_SECONDS,
        pool_timeout=30,
    )

engine = create_engine(settings.DATABASE_URL, **engine_options)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def database_backend() -> str:
    return "sqlite" if _is_sqlite else "postgresql"


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

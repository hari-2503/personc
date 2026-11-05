"""Database engine and session management for Person C.

Each CSI3007 project owns a SEPARATE database. Person A consumes this
app's outputs ONLY through documented HTTP REST endpoints (/history,
/bill/estimate, /consumption/monthly); nobody opens this database from
outside this project.

DATABASE_URL handling:
- unset                     -> SQLite file at <project>/data/smart_home_energy.db
- sqlite:///relative/path   -> resolved against the project folder (not the
                               shell's working directory), so it works the same
                               on macOS, Windows and Render
- postgres:// or postgresql:// (Render Postgres) -> normalized to the psycopg
                               (v3) driver that requirements.txt installs
"""
import os
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

BASE_DIR = Path(__file__).resolve().parent
DEFAULT_DB_PATH = BASE_DIR / "data" / "smart_home_energy.db"


def normalize_database_url(raw: str | None) -> str:
    """Return a SQLAlchemy URL for the configured database."""
    url = (raw or "").strip()
    if not url:
        return f"sqlite:///{DEFAULT_DB_PATH.as_posix()}"
    if url.startswith("postgres://"):
        url = "postgresql://" + url[len("postgres://"):]
    if url.startswith("postgresql://"):
        url = "postgresql+psycopg://" + url[len("postgresql://"):]
    if url.startswith("sqlite:///") and url != "sqlite:///:memory:":
        db_path = Path(url[len("sqlite:///"):])
        if not db_path.is_absolute():
            db_path = (BASE_DIR / db_path).resolve()
        db_path.parent.mkdir(parents=True, exist_ok=True)
        url = f"sqlite:///{db_path.as_posix()}"
    return url


DATABASE_URL = normalize_database_url(os.getenv("DATABASE_URL"))
IS_SQLITE = DATABASE_URL.startswith("sqlite")

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False} if IS_SQLITE else {},
    pool_pre_ping=not IS_SQLITE,
    future=True,
)

SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
Base = declarative_base()


def database_backend() -> str:
    """Short, credential-free label for /health ("sqlite" or "postgresql")."""
    return "sqlite" if IS_SQLITE else engine.dialect.name


def get_db():
    """FastAPI dependency yielding a SQLAlchemy session (rolled back on error)."""
    db = SessionLocal()
    try:
        yield db
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()

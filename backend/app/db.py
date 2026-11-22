from pathlib import Path
from sqlalchemy import MetaData, create_engine, event, text
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from .config import ROOT, get_settings

_url = get_settings().database_url
if _url.startswith("sqlite:///"):
    _raw_path = _url[len("sqlite:///"):]
    _p = Path(_raw_path)
    if not _p.is_absolute():
        if _p.name == "test.db":
            _url = f"sqlite:///{ROOT / 'backend' / 'test.db'}"
        else:
            _url = f"sqlite:///{ROOT / 'backend' / 'lifeline.db'}"

_sqlite = _url.startswith("sqlite")
engine = create_engine(_url, pool_pre_ping=True, **({"connect_args": {"check_same_thread": False, "timeout": 30}} if _sqlite else {}))
if _sqlite:
    @event.listens_for(engine, "connect")
    def _pragmas(conn, _):  # WAL avoids writer/reader lock contention between API and pipeline threads
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")

SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)

NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=NAMING_CONVENTION)


def get_db():
    db = SessionLocal()
    try:
        yield db
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def check_db_health() -> bool:
    """Verify database connectivity and query execution."""
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except Exception:
        return False
